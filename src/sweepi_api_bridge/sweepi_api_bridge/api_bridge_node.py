#!/usr/bin/env python3
"""HTTP JSON API bridge for SweePi."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
import threading
import time
import traceback

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import Float32, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from sweepi_api_bridge.json_utils import (
    clamp,
    json_response,
    occupancy_grid_to_json,
    parse_json_body,
    path_to_json,
    pose_to_json,
    split_path,
    yaw_to_quaternion,
)
from sweepi_api_bridge.map_store import MapStore, sanitize_map_id
from sweepi_api_bridge.runtime_state import StateStore
from sweepi_robot_manager_interfaces.srv import StartTask


class SweePiApiBridge(Node):
    """ROS node with a small threaded HTTP JSON API."""

    def __init__(self):
        super().__init__('sweepi_api_bridge')

        self.declare_parameter('api_host', '0.0.0.0')
        self.declare_parameter('api_port', 8080)
        self.api_host = str(self.get_parameter('api_host').value)
        self.api_port = int(self.get_parameter('api_port').value)

        self.state = StateStore()
        self.map_store = MapStore()
        self.data_lock = threading.RLock()

        self.manager_status = ''
        self.live_map = None
        self.coverage_map = None
        self.coverage_path = None
        self.coverage_percentage = 0.0
        self.coverage_stats = ''
        self.coverage_execution_status = 'WAITING_FOR_PATH'
        self.last_coverage_summary_topic = ''
        self.coverage_path_signature = None
        self.validated_coverage_path_signature = None
        self.robot_pose = None
        self.pose_available = False
        self.last_pose_lookup_time = 0.0
        self.validated_for_current_path = False
        self.manual_command_expiry = 0.0
        self.last_api_initial_pose_publish_time = 0.0

        self.start_exploration_client = self.create_client(
            StartTask,
            '/sweepi_robot_manager/start_exploration',
        )
        self.start_coverage_client = self.create_client(
            StartTask,
            '/sweepi_robot_manager/start_coverage',
        )
        self.switch_exploration_mode_client = self.create_client(
            StartTask,
            '/sweepi_robot_manager/exploration/switch_mode',
        )
        self.trigger_clients = {}
        for service_name in (
            '/sweepi_robot_manager/stop_task',
            '/sweepi_robot_manager/exploration/start_auto',
            '/sweepi_robot_manager/exploration/manual',
            '/sweepi_robot_manager/exploration/stop',
            '/sweepi_robot_manager/exploration/stop_and_save',
            '/sweepi_robot_manager/coverage/validate',
            '/sweepi_robot_manager/coverage/start',
            '/sweepi_robot_manager/coverage/pause',
            '/sweepi_robot_manager/coverage/continue',
            '/sweepi_robot_manager/coverage/stop',
            '/sweepi_robot_manager/coverage/return_home',
            '/sweepi_robot_manager/coverage/reset',
            '/sweepi_robot_manager/coverage/last_summary',
        ):
            self.trigger_clients[service_name] = self.create_client(
                Trigger,
                service_name,
            )

        transient_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        string_qos = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped,
            '/initialpose',
            10,
        )
        self.initial_pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/initialpose',
            self._initial_pose_callback,
            10,
        )
        self.create_subscription(
            String,
            '/sweepi_robot_manager/status',
            self._manager_status_callback,
            string_qos,
        )
        self.create_subscription(
            String,
            '/sweepi_robot_manager/coverage/last_summary',
            self._coverage_last_summary_topic_callback,
            string_qos,
        )
        self.create_subscription(
            String,
            '/exploration/mode',
            self._exploration_mode_callback,
            10,
        )
        self.create_subscription(OccupancyGrid, '/map', self._map_callback, transient_qos)
        self.create_subscription(
            OccupancyGrid,
            '/coverage_map',
            self._coverage_map_callback,
            transient_qos,
        )
        self.create_subscription(
            Path,
            '/coverage_path',
            self._coverage_path_callback,
            transient_qos,
        )
        self.create_subscription(
            Float32,
            '/coverage_percentage',
            self._coverage_percentage_callback,
            transient_qos,
        )
        self.create_subscription(
            String,
            '/coverage_stats',
            self._coverage_stats_callback,
            string_qos,
        )
        self.create_subscription(
            String,
            '/coverage_execution_status',
            self._coverage_execution_status_callback,
            string_qos,
        )

        self.tf_buffer = None
        self.tf_listener = None

        self.timer = self.create_timer(0.2, self._timer_callback)
        self.http_server = None
        self.http_thread = None
        self._start_http_server()

        self.get_logger().info(
            'SweePi API bridge listening on http://%s:%d/api'
            % (self.api_host, self.api_port)
        )

    def destroy_node(self):
        self._publish_zero_velocity()
        if self.http_server is not None:
            self.http_server.shutdown()
            self.http_server.server_close()
        if self.http_thread is not None:
            self.http_thread.join(timeout=2.0)
        super().destroy_node()

    def _start_http_server(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                json_response(self, 200, {'ok': True})

            def do_GET(self):
                self._handle('GET')

            def do_POST(self):
                self._handle('POST')

            def do_PUT(self):
                self._handle('PUT')

            def log_message(self, fmt, *args):
                bridge.get_logger().info('HTTP ' + (fmt % args))

            def _handle(self, method):
                try:
                    body = {}
                    if method in ('POST', 'PUT'):
                        try:
                            body = parse_json_body(self)
                        except ValueError as exc:
                            json_response(
                                self,
                                400,
                                bridge._error(
                                    str(exc),
                                    'VALIDATION_ERROR',
                                    {'field': 'body'},
                                ),
                            )
                            return
                    status, payload = bridge.handle_http_request(
                        method,
                        self.path,
                        body,
                    )
                    json_response(self, status, payload)
                except Exception as exc:
                    bridge.get_logger().error(
                        'HTTP handler error: %s\n%s'
                        % (exc, traceback.format_exc())
                    )
                    json_response(
                        self,
                        500,
                        bridge._error(
                            'Internal API bridge error',
                            'INTERNAL_ERROR',
                        ),
                    )

        self.http_server = ThreadingHTTPServer(
            (self.api_host, self.api_port),
            Handler,
        )
        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever,
            name='sweepi_api_bridge_http',
            daemon=True,
        )
        self.http_thread.start()

    def handle_http_request(self, method, path, body):
        parts, query = split_path(path)
        if not parts or parts[0] != 'api':
            return 404, self._error('Unknown route', 'VALIDATION_ERROR')
        route = parts[1:]

        if method == 'GET' and route == ['system', 'health']:
            return 200, self._system_health()
        if method == 'GET' and route == ['robot', 'status']:
            return 200, self._robot_status()

        if route and route[0] == 'exploration':
            return self._handle_exploration(method, route[1:], body)
        if route and route[0] == 'localization':
            return self._handle_localization(method, route[1:], body)
        if route and route[0] == 'maps':
            return self._handle_maps(method, route[1:], body)
        if route and route[0] == 'cleaning':
            return self._handle_cleaning(method, route[1:], body, query)

        return 404, self._error('Unknown route', 'VALIDATION_ERROR')

    def _timestamp(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            '+00:00',
            'Z',
        )

    def _success(
        self,
        message,
        accepted=None,
        completed=None,
        task_finished=None,
        command=None,
        state=None,
        **fields
    ):
        payload = {
            'success': True,
            'message': message,
            'error': None,
            'timestamp': self._timestamp(),
        }
        if command is not None:
            payload['command'] = command
        if accepted is not None:
            payload['accepted'] = bool(accepted)
        if completed is not None:
            payload['completed'] = bool(completed)
        if task_finished is not None:
            payload['task_finished'] = bool(task_finished)
        if state is not None:
            payload['state'] = state
        payload.update(fields)
        self._record_command_result(payload)
        return payload

    def _error(
        self,
        message,
        code,
        details=None,
        accepted=None,
        completed=None,
        task_finished=None,
        command=None,
        state=None,
        **fields
    ):
        payload = {
            'success': False,
            'message': message,
            'error': {
                'code': code,
                'details': details or {},
            },
            'timestamp': self._timestamp(),
        }
        if command is not None:
            payload['command'] = command
        if accepted is not None:
            payload['accepted'] = bool(accepted)
        if completed is not None:
            payload['completed'] = bool(completed)
        if task_finished is not None:
            payload['task_finished'] = bool(task_finished)
        if state is not None:
            payload['state'] = state
        payload.update(fields)
        self._record_command_result(payload)
        return payload

    def _service_payload(
        self,
        result,
        success_message=None,
        failure_code='TASK_FAILED',
        command=None,
        state=None,
        task_finished=False,
        accepted_on_failure=True,
        **fields
    ):
        if result.get('success'):
            return self._success(
                success_message or result.get('message', ''),
                accepted=True,
                completed=True,
                task_finished=task_finished,
                command=command,
                state=state,
                **fields,
            )
        return self._error(
            result.get('message', 'Service call failed'),
            failure_code,
            accepted=result.get('accepted', accepted_on_failure),
            completed=False,
            task_finished=False,
            command=command,
            state=state,
        )

    def _record_command_result(self, payload):
        command = payload.get('command')
        if not command:
            return
        updates = {
            'last_command': command,
            'last_command_result': payload,
        }
        if payload.get('error'):
            updates['last_error'] = payload['error']
        elif payload.get('success'):
            updates['last_error'] = None
        if 'task_finished' in payload:
            updates['task_finished'] = bool(payload.get('task_finished'))
        if payload.get('task_result') is not None:
            updates['task_result'] = payload.get('task_result')
        if payload.get('state') is not None:
            updates['task_phase'] = payload.get('state')
        self.state.update(**updates)

    def _command_response_fields(self, payload, command, state='invalid_request'):
        payload['command'] = command
        payload.setdefault('accepted', False)
        payload.setdefault('completed', False)
        payload.setdefault('task_finished', False)
        payload.setdefault('state', state)
        self._record_command_result(payload)
        return payload

    def _handle_exploration(self, method, route, body):
        if method == 'POST' and route == ['start']:
            return 200, self._api_start_exploration(body)
        if method == 'GET' and route == ['status']:
            return 200, self._exploration_status()
        if method == 'POST' and route == ['switch']:
            return 200, self._api_switch_exploration_mode(body)
        if method == 'POST' and route == ['mode']:
            return 200, self._api_switch_exploration_mode(body)
        if method == 'POST' and route == ['switch-mode']:
            return 200, self._api_switch_exploration_mode(body)
        if method == 'POST' and route == ['manual-drive']:
            return 200, self._api_manual_drive_command(body)
        if method == 'POST' and route == ['manual', 'drive']:
            return 200, self._api_manual_drive(body)
        if method == 'POST' and route == ['manual', 'command']:
            return 200, self._api_manual_command(body)
        if method == 'POST' and route == ['manual', 'stop']:
            self._publish_zero_velocity()
            return 200, self._success(
                'Manual motion stopped.',
                accepted=True,
                completed=True,
                task_finished=False,
                command='stop_manual_drive',
                state=self.state.snapshot()['robot_state'],
                verified_motion=False,
            )
        if method == 'POST' and route == ['stop']:
            if body.get('save_map') is False:
                self._publish_zero_velocity()
                result = self._call_trigger('/sweepi_robot_manager/exploration/stop')
                if result['success']:
                    self.state.update(
                        robot_state='exploration_stopped',
                        active_task='exploration',
                        exploration_active=True,
                        exploration_mode='stopped',
                    )
                return 200, self._service_payload(
                    result,
                    success_message='Exploration motion stopped without saving.',
                    command='stop_exploration',
                    state=self.state.snapshot()['robot_state'],
                    task_finished=True,
                    task_result='stopped',
                    map_saved=False,
                    map_id=self.state.snapshot().get('active_map_id'),
                    map_name=self.state.snapshot().get('active_map_id'),
                )
            return 200, self._api_stop_exploration_and_save()
        if method == 'POST' and route == ['stop-motion']:
            self._publish_zero_velocity()
            result = self._call_trigger('/sweepi_robot_manager/exploration/stop')
            if result['success']:
                self.state.update(
                    robot_state='exploration_stopped',
                    active_task='exploration',
                    exploration_active=True,
                    exploration_mode='stopped',
                )
            return 200, self._service_payload(
                result,
                success_message='Exploration motion stopped.',
                command='stop_exploration_motion',
                state=self.state.snapshot()['robot_state'],
                task_finished=False,
            )
        if method == 'POST' and route == ['stop-and-save']:
            return 200, self._api_stop_exploration_and_save()
        return 404, self._error('Unknown exploration route', 'VALIDATION_ERROR')

    def _handle_localization(self, method, route, body):
        if method == 'POST' and route == ['initial-pose']:
            return 200, self._api_initial_pose(body)
        if method == 'GET' and route == ['status']:
            snapshot = self.state.snapshot()
            return 200, self._success(
                'Localization status fetched.',
                initial_pose_received=snapshot['initial_pose_received'],
                initial_pose_confirmed=snapshot['initial_pose_confirmed'],
                initial_pose_source=snapshot['initial_pose_source'],
                initial_pose=snapshot['initial_pose'],
                pose_available=self.pose_available,
                pose=self.robot_pose,
            )
        return 404, self._error('Unknown localization route', 'VALIDATION_ERROR')

    def _handle_maps(self, method, route, body):
        if method == 'GET' and route == ['current']:
            with self.data_lock:
                live_map = self.live_map
                pose = self.robot_pose
            if live_map is None:
                return 200, {'ok': True, 'available': False, 'message': 'No live map cached'}
            payload = occupancy_grid_to_json(live_map, include_occupancy=True)
            payload.update({
                'ok': True,
                'map_id': self.state.snapshot().get('active_map_id'),
                'robot_pose': pose,
            })
            return 200, payload
        if method == 'GET' and route == []:
            return 200, self._success(
                'Maps fetched.',
                items=[
                    self._contract_map_metadata(metadata)
                    for metadata in self.map_store.list_maps()
                ],
            )
        if len(route) >= 1:
            map_id = sanitize_map_id(route[0])
            if method == 'GET' and len(route) == 1:
                return 200, self._api_get_map(map_id)
            if method == 'GET' and len(route) == 2 and route[1] == 'metadata':
                return 200, self._api_get_map_metadata(map_id)
            if method == 'PUT' and len(route) == 2 and route[1] == 'metadata':
                return 200, self._api_update_map_metadata(map_id, body)
            if method == 'PUT' and len(route) == 2 and route[1] == 'sections':
                return 200, self._api_store_sections(map_id, body)
        return 404, self._error('Unknown maps route', 'VALIDATION_ERROR')

    def _handle_cleaning(self, method, route, body, query):
        if method == 'POST' and route == ['start']:
            return 200, self._api_start_cleaning(body)
        if method == 'GET' and route == ['status']:
            return 200, self._cleaning_status()
        if method == 'GET' and route == ['path']:
            stride = int(query.get('stride', ['1'])[0] or '1')
            return 200, self._cleaning_path(stride)
        if method == 'GET' and route == ['coverage-map']:
            return 200, self._cleaning_coverage_map()
        if method == 'POST' and route == ['validate']:
            return 200, self._api_validate_cleaning()
        if method == 'POST' and route == ['start-motion']:
            return 200, self._api_start_cleaning_motion()
        if method == 'POST' and route == ['pause']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/pause')
            if result['success']:
                self.state.update(robot_state='paused', cleaning_paused=True, task_phase='paused')
            return 200, self._service_payload(
                result,
                success_message='Cleaning paused.',
                command='pause_cleaning',
                state='paused',
                task_finished=False,
                task_id=self.state.snapshot().get('active_task_id'),
            )
        if method == 'POST' and route == ['resume']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/continue')
            if result['success']:
                self.state.update(robot_state='cleaning', cleaning_paused=False, task_phase='cleaning')
            return 200, self._service_payload(
                result,
                success_message='Cleaning resumed.',
                command='resume_cleaning',
                state='cleaning',
                task_finished=False,
                task_id=self.state.snapshot().get('active_task_id'),
            )
        if method == 'POST' and route == ['stop']:
            self._publish_zero_velocity()
            task_id = self.state.snapshot().get('active_task_id')
            result = self._call_trigger('/sweepi_robot_manager/coverage/stop')
            if result['success']:
                self.state.reset_cleaning()
            return 200, self._service_payload(
                result,
                success_message='Cleaning stopped.',
                command='stop_cleaning',
                state='stopped',
                task_finished=True,
                task_result='stopped',
                task_id=task_id,
            )
        if method == 'POST' and route == ['reset']:
            self._publish_zero_velocity()
            task_id = self.state.snapshot().get('active_task_id')
            result = self._call_trigger('/sweepi_robot_manager/coverage/reset')
            if result['success']:
                self._clear_coverage_cache()
                self.state.reset_cleaning()
            return 200, self._service_payload(
                result,
                success_message='Cleaning state reset.',
                command='reset_cleaning',
                state='idle',
                task_finished=True,
                task_result='reset',
                task_id=None if result['success'] else task_id,
            )
        if method == 'POST' and route == ['return-home']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/return_home')
            if result['success']:
                self.state.update(robot_state='returning_home', task_phase='returning_home')
            return 200, self._service_payload(
                result,
                success_message='Robot is returning home.',
                command='return_home',
                state='returning_home',
                task_finished=False,
            )
        if method == 'GET' and route == ['last-summary']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/last_summary')
            return 200, self._success(
                'Last cleaning summary fetched.',
                accepted=result['success'],
                summary=result['message'],
                topic_summary=self.last_coverage_summary_topic,
            )
        return 404, self._error('Unknown cleaning route', 'VALIDATION_ERROR')

    def _api_start_exploration(self, body):
        snapshot = self.state.snapshot()
        if snapshot['cleaning_active'] or snapshot['cleaning_paused']:
            return self._error(
                'Cannot start exploration while cleaning is active.',
                'ROBOT_BUSY',
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_exploration',
                state=snapshot['robot_state'],
            )
        if snapshot['exploration_active']:
            return self._error(
                'Exploration is already active.',
                'ROBOT_BUSY',
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_exploration',
                state=snapshot['robot_state'],
            )

        requested_map_name = str(body.get('map_name') or '').strip()
        if not requested_map_name:
            return self._error(
                'map_name is required.',
                'VALIDATION_ERROR',
                {'field': 'map_name'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_exploration',
                state='invalid_request',
            )
        map_id = sanitize_map_id(requested_map_name)
        api_mode, manager_mode = self._normalize_exploration_api_mode(
            body.get('mode') or 'automatic'
        )
        if not api_mode:
            return self._error(
                'mode must be automatic or manual.',
                'VALIDATION_ERROR',
                {'field': 'mode', 'allowed_values': ['automatic', 'manual']},
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_exploration',
                state='invalid_request',
            )
        request = StartTask.Request()
        request.map_name = map_id
        request.mode = manager_mode
        request.auto_start = False
        result = self._call_start_task(self.start_exploration_client, request)
        if result['success']:
            self.state.update(
                robot_state='exploring',
                active_task='exploration',
                exploration_active=True,
                exploration_mode=api_mode,
                active_map_id=map_id,
                active_area_name=requested_map_name,
                active_task_id=None,
                task_finished=False,
                task_result=None,
                task_phase='exploring',
            )
        if not result['success']:
            return self._error(
                result['message'],
                'TASK_FAILED',
                accepted=result.get('accepted', True),
                completed=False,
                task_finished=False,
                command='start_exploration',
                state='exploration_start_failed',
            )
        return self._success(
            'Exploration started.',
            command='start_exploration',
            accepted=True,
            completed=True,
            task_finished=False,
            state='exploring',
            map_id=map_id,
            map_name=map_id,
            mode=api_mode,
        )

    def _normalize_exploration_api_mode(self, value):
        mode = str(value or '').strip().lower()
        if mode in ('auto', 'automatic', 'autonomous'):
            return 'automatic', 'auto'
        if mode in ('manual', 'teleop'):
            return 'manual', 'manual'
        return '', ''

    def _api_switch_exploration_mode(self, body):
        api_mode, manager_mode = self._normalize_exploration_api_mode(
            body.get('new_mode') or body.get('mode')
        )
        if not api_mode:
            return self._error(
                'new_mode must be automatic or manual.',
                'VALIDATION_ERROR',
                {'field': 'new_mode', 'allowed_values': ['automatic', 'manual']},
                accepted=False,
                completed=False,
                task_finished=False,
                command='switch_exploration_mode',
                state='invalid_request',
            )
        snapshot = self.state.snapshot()
        if snapshot['active_task'] != 'exploration' or not snapshot['exploration_active']:
            return self._error(
                'Exploration is not active.',
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='switch_exploration_mode',
                state='exploration_inactive',
            )

        request = StartTask.Request()
        request.map_name = snapshot.get('active_map_id') or ''
        request.mode = manager_mode
        request.auto_start = False
        result = self._call_start_task(self.switch_exploration_mode_client, request)
        if result['success']:
            self.state.update(
                robot_state='exploring',
                active_task='exploration',
                exploration_active=True,
                exploration_mode=api_mode,
                task_phase='exploring',
            )
        if not result['success']:
            return self._error(
                result['message'],
                'TASK_FAILED',
                accepted=result.get('accepted', True),
                completed=False,
                task_finished=False,
                command='switch_exploration_mode',
                state='exploration_mode_switch_failed',
                mode=api_mode,
            )
        return self._success(
            'Exploration mode switched.',
            command='switch_exploration_mode',
            accepted=True,
            completed=True,
            task_finished=False,
            state='exploring',
            mode=api_mode,
            map_id=snapshot.get('active_map_id'),
            map_name=snapshot.get('active_map_id'),
        )

    def _api_stop_exploration_and_save(self):
        self._publish_zero_velocity()
        result = self._call_trigger('/sweepi_robot_manager/exploration/stop_and_save')
        snapshot = self.state.snapshot()
        map_id = snapshot.get('active_map_id')
        if map_id:
            self.map_store.ensure_meta(
                map_id,
                {
                    'name': snapshot.get('active_area_name') or map_id,
                    'source': 'exploration',
                },
            )
        if result['success']:
            self.state.reset_exploration()
        map_saved = self.map_store.exists(map_id) if map_id else False
        if not result['success']:
            return self._error(
                result['message'],
                'TASK_FAILED',
                accepted=result.get('accepted', True),
                completed=False,
                task_finished=False,
                command='stop_exploration',
                state='exploration_stop_failed',
                map_saved=False,
                map_id=map_id,
                map_name=map_id,
            )
        if not map_saved:
            return self._error(
                'Exploration stopped, but saved map was not confirmed.',
                'MAP_SAVE_FAILED',
                {'map_id': map_id, 'service_message': result.get('message')},
                accepted=result.get('accepted', True),
                completed=False,
                task_finished=False,
                command='stop_exploration',
                state='map_save_failed',
                map_saved=False,
                map_id=map_id,
                map_name=map_id,
            )
        return self._success(
            'Exploration stopped and map saved.',
            command='stop_exploration',
            accepted=True,
            completed=True,
            task_finished=True,
            task_result='map_saved',
            state='idle',
            map_saved=map_saved,
            map_id=map_id,
            map_name=map_id,
        )

    def _api_manual_drive_command(self, body):
        if not self._manual_drive_allowed():
            return self._error(
                'Manual driving is allowed only during manual exploration.',
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state=self.state.snapshot()['robot_state'],
            )

        command = str(body.get('command') or '').strip().lower()
        try:
            speed = abs(float(body.get('speed', 0.15)))
        except (TypeError, ValueError):
            return self._error(
                'speed must be a number.',
                'VALIDATION_ERROR',
                {'field': 'speed'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state='invalid_request',
            )
        speed = clamp(speed, 0.0, 0.8)
        mapping = {
            'forward': (min(speed, 0.20), 0.0),
            'backward': (-min(speed, 0.20), 0.0),
            'left': (0.0, min(speed, 0.80)),
            'right': (0.0, -min(speed, 0.80)),
            'stop': (0.0, 0.0),
        }
        if command not in mapping:
            return self._error(
                'command must be forward, backward, left, right, or stop.',
                'VALIDATION_ERROR',
                {
                    'field': 'command',
                    'allowed_values': ['forward', 'backward', 'left', 'right', 'stop'],
                },
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state='invalid_request',
            )

        linear_x, angular_z = mapping[command]
        self._publish_velocity(linear_x, angular_z)
        self.manual_command_expiry = time.monotonic() + 0.3
        return self._success(
            'Manual drive command published.',
            accepted=True,
            completed=True,
            task_finished=False,
            command='manual_drive',
            direction=command,
            speed=speed,
            state=self.state.snapshot()['robot_state'],
            verified_motion=False,
        )

    def _api_manual_drive(self, body):
        if not self._manual_drive_allowed():
            return self._error(
                'Manual driving is allowed only during manual exploration.',
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state=self.state.snapshot()['robot_state'],
            )
        try:
            linear_x = clamp(float(body.get('linear_x', 0.0)), -0.20, 0.20)
            angular_z = clamp(float(body.get('angular_z', 0.0)), -0.80, 0.80)
            duration_ms = int(clamp(int(body.get('duration_ms', 300)), 1, 1000))
        except (TypeError, ValueError):
            return self._error(
                'linear_x, angular_z, and duration_ms must be numeric.',
                'VALIDATION_ERROR',
                {'field': 'manual_drive'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state='invalid_request',
            )
        self._publish_velocity(linear_x, angular_z)
        self.manual_command_expiry = time.monotonic() + (duration_ms / 1000.0)
        return self._success(
            'Manual drive command published.',
            command='manual_drive',
            accepted=True,
            completed=True,
            task_finished=False,
            state=self.state.snapshot()['robot_state'],
            linear_x=linear_x,
            angular_z=angular_z,
            duration_ms=duration_ms,
            verified_motion=False,
        )

    def _api_manual_command(self, body):
        command = str(body.get('command') or '').strip().lower()
        try:
            speed = abs(float(body.get('speed', 0.15)))
            duration_ms = int(body.get('duration_ms', 300))
        except (TypeError, ValueError):
            return self._error(
                'speed and duration_ms must be numeric.',
                'VALIDATION_ERROR',
                {'field': 'manual_command'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state='invalid_request',
            )
        mapping = {
            'forward': (speed, 0.0),
            'backward': (-speed, 0.0),
            'rotate_left': (0.0, speed),
            'rotate_right': (0.0, -speed),
            'stop': (0.0, 0.0),
        }
        if command not in mapping:
            return self._error(
                'Unsupported manual command.',
                'VALIDATION_ERROR',
                {
                    'field': 'command',
                    'allowed_values': [
                        'forward',
                        'backward',
                        'rotate_left',
                        'rotate_right',
                        'stop',
                    ],
                },
                accepted=False,
                completed=False,
                task_finished=False,
                command='manual_drive',
                state='invalid_request',
            )
        return self._api_manual_drive({
            'linear_x': mapping[command][0],
            'angular_z': mapping[command][1],
            'duration_ms': duration_ms,
        })

    def _api_initial_pose(self, body):
        map_id = body.get('map_id')
        snapshot = self.state.snapshot()
        if map_id and snapshot.get('active_map_id'):
            clean_map_id = sanitize_map_id(map_id)
            active_pose_map_id = snapshot.get('active_coverage_map_id') or snapshot['active_map_id']
            if clean_map_id != active_pose_map_id and clean_map_id != snapshot['active_map_id']:
                return self._error(
                    'Initial pose map_id does not match active map.',
                    'VALIDATION_ERROR',
                    {'field': 'map_id'},
                    accepted=False,
                    completed=False,
                    task_finished=False,
                    command='set_initial_pose',
                    state='invalid_initial_pose',
                )
        try:
            x = float(body['x'])
            y = float(body['y'])
            yaw = float(body.get('yaw', 0.0))
        except (KeyError, TypeError, ValueError):
            return self._error(
                'x, y, and optional yaw are required.',
                'VALIDATION_ERROR',
                {'field': 'pose'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='set_initial_pose',
                state='invalid_initial_pose',
            )
        if not all(math.isfinite(value) for value in (x, y, yaw)):
            return self._error(
                'x, y, and yaw must be finite numbers.',
                'VALIDATION_ERROR',
                {'field': 'pose'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='set_initial_pose',
                state='invalid_initial_pose',
            )

        if snapshot.get('active_task') == 'cleaning' and not snapshot.get('cleaning_active'):
            return self._error(
                'Cleaning has not been prepared.',
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='set_initial_pose',
                state='cleaning_not_prepared',
            )

        if snapshot.get('active_task') == 'cleaning':
            validation_map_id = (
                snapshot.get('active_coverage_map_id')
                or snapshot.get('active_map_id')
                or sanitize_map_id(map_id, fallback='')
            )
        else:
            validation_map_id = (
                sanitize_map_id(map_id, fallback='')
                or snapshot.get('active_map_id')
            )
        pose_check = None
        if validation_map_id:
            pose_check = self.map_store.check_pose(validation_map_id, x, y)
            if not pose_check.get('ok'):
                return self._error(
                    pose_check.get('message', 'Initial pose is invalid.'),
                    pose_check.get('code') or 'INVALID_INITIAL_POSE',
                    {'pose_check': pose_check},
                    accepted=False,
                    completed=False,
                    task_finished=False,
                    command='set_initial_pose',
                    state='invalid_initial_pose',
                )

        self._publish_initial_pose(x, y, yaw, source='api')
        self.state.update(
            initial_pose_received=True,
            initial_pose_confirmed=False,
            initial_pose_source='api',
            initial_pose={
                'x': x,
                'y': y,
                'yaw': yaw,
                'frame': body.get('frame', 'map'),
            },
            coverage_validated=False,
            task_finished=False,
            task_result=None,
            task_phase='initial_pose_pending',
        )
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None
        confirmation = self._confirm_initial_pose(x, y, yaw)
        if not confirmation.get('ok'):
            self.state.update(
                initial_pose_confirmed=False,
                coverage_validated=False,
                robot_state='initial_pose_failed'
                if snapshot.get('cleaning_active')
                else snapshot.get('robot_state'),
            )
            return self._error(
                'Initial pose was published, but localization was not confirmed.',
                'INITIAL_POSE_NOT_CONFIRMED',
                {'reason': confirmation.get('message'), 'confirmation': confirmation},
                accepted=True,
                completed=False,
                task_finished=False,
                command='set_initial_pose',
                state='initial_pose_failed',
                initial_pose_received=True,
                initial_pose_confirmed=False,
                initial_pose_source='api',
                initial_pose={
                    'x': x,
                    'y': y,
                    'yaw': yaw,
                    'frame': body.get('frame', 'map'),
                },
            )
        self._record_initial_pose(x, y, yaw, source='api', confirmed=True)
        return self._success(
            'Initial pose confirmed.',
            command='set_initial_pose',
            accepted=True,
            completed=True,
            task_finished=False,
            state='initial_pose_confirmed',
            initial_pose_received=True,
            initial_pose_confirmed=True,
            initial_pose_source='api',
            initial_pose={
                'x': x,
                'y': y,
                'yaw': yaw,
                'frame': body.get('frame', 'map'),
            },
            pose=self.robot_pose,
            pose_check=pose_check,
            next_steps=[
                'Call POST /api/cleaning/validate.',
                'Call POST /api/cleaning/start-motion after validation completes.',
            ] if snapshot.get('cleaning_active') else [],
        )

    def _api_get_map(self, map_id):
        payload = self.map_store.read_map(map_id)
        if not payload.get('available'):
            return self._error(
                payload.get('message', 'Map not found.'),
                'MAP_NOT_FOUND',
                {'map_id': map_id},
            )
        metadata = payload.get('metadata', {})
        return self._success(
            'Map fetched.',
            map_id=payload['map_id'],
            name=metadata.get('name') or payload['map_id'],
            resolution=payload['resolution'],
            origin=payload['origin'],
            width=payload['width'],
            height=payload['height'],
            occupancy=payload['occupancy'],
            sections=metadata.get('sections', []),
        )

    def _api_get_map_metadata(self, map_id):
        if not self.map_store.exists(map_id):
            return self._error(
                'Map not found.',
                'MAP_NOT_FOUND',
                {'map_id': map_id},
            )
        metadata = self.map_store.metadata(map_id)
        return self._success(
            'Map metadata fetched.',
            **self._contract_map_metadata(metadata),
        )

    def _api_update_map_metadata(self, map_id, body):
        if not self.map_store.exists(map_id):
            return self._error(
                'Map not found.',
                'MAP_NOT_FOUND',
                {'map_id': map_id},
            )
        validation = self._validate_sections_payload(
            {'sections': body.get('sections', [])},
            require_bounds=True,
            allow_empty=True,
        )
        if validation is not None:
            return validation
        metadata = self.map_store.update_metadata(
            map_id,
            name=body.get('name'),
            sections=body.get('sections', []),
        )
        return self._success(
            'Map metadata updated.',
            **self._contract_map_metadata(metadata),
        )

    def _contract_map_metadata(self, metadata):
        return {
            'map_id': metadata.get('map_id'),
            'name': metadata.get('name'),
            'created_at': metadata.get('created_at'),
            'updated_at': metadata.get('updated_at'),
            'resolution': metadata.get('resolution'),
            'origin': metadata.get('origin') or {'x': 0.0, 'y': 0.0, 'yaw': 0.0},
            'width': metadata.get('width'),
            'height': metadata.get('height'),
            'sections': metadata.get('sections', []),
        }

    def _api_start_cleaning(self, body):
        snapshot = self.state.snapshot()
        if snapshot['exploration_active']:
            return self._error(
                'Cannot start cleaning while exploration is active.',
                'ROBOT_BUSY',
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state=snapshot['robot_state'],
            )
        if snapshot['cleaning_active'] or snapshot['cleaning_paused']:
            return self._error(
                'Cleaning is already active.',
                'ROBOT_BUSY',
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state=snapshot['robot_state'],
            )
        map_id = sanitize_map_id(body.get('map_id') or '', fallback='')
        if not map_id:
            return self._error(
                'map_id is required.',
                'VALIDATION_ERROR',
                {'field': 'map_id'},
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='invalid_request',
            )
        if not self.map_store.exists(map_id):
            return self._error(
                'Requested map does not exist.',
                'MAP_NOT_FOUND',
                {'map_id': map_id},
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='invalid_request',
            )

        cleaning_mode = self._normalize_cleaning_mode(body.get('cleaning_mode'))
        if not cleaning_mode:
            return self._error(
                'Invalid cleaning_mode. Allowed values are full-map and sections.',
                'VALIDATION_ERROR',
                {
                    'field': 'cleaning_mode',
                    'allowed_values': ['full-map', 'sections'],
                },
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='invalid_request',
            )
        if 'initial_pose' in body:
            return self._error(
                'initial_pose must be sent separately after cleaning/start.',
                'VALIDATION_ERROR',
                {
                    'field': 'initial_pose',
                    'use_endpoint': '/api/localization/initial-pose',
                },
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='invalid_request',
            )

        sections = body.get('sections', [])
        if cleaning_mode == 'sections':
            validation = self._validate_sections_payload(
                {'sections': sections},
                require_bounds=True,
                allow_empty=False,
            )
            if validation is not None:
                return self._command_response_fields(validation, 'prepare_cleaning')
        elif sections:
            validation = self._validate_sections_payload(
                {'sections': sections},
                require_bounds=True,
                allow_empty=True,
            )
            if validation is not None:
                return self._command_response_fields(validation, 'prepare_cleaning')
        elif sections is None:
            sections = []

        processed_map = body.get('processed_map')
        if processed_map is not None:
            processed_validation = self._validate_processed_map(processed_map)
            if processed_validation is not None:
                return self._command_response_fields(processed_validation, 'prepare_cleaning')

        task_id = 'cleaning_%s' % datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        coverage_map_id = map_id
        try:
            if processed_map is not None:
                coverage_map_id = sanitize_map_id('%s_%s_processed' % (map_id, task_id))
                self.map_store.write_processed_map(
                    coverage_map_id,
                    processed_map,
                    {
                        'name': '%s processed cleaning map' % map_id,
                        'source_map_id': map_id,
                        'source': 'api_processed_map',
                        'sections': sections or [],
                    },
                )
            elif cleaning_mode == 'sections':
                coverage_map_id = sanitize_map_id('%s_%s_sections' % (map_id, task_id))
                self.map_store.write_section_map(
                    map_id,
                    coverage_map_id,
                    sections,
                    {
                        'name': '%s section cleaning map' % map_id,
                        'source_map_id': map_id,
                        'source': 'api_sections',
                        'sections': sections,
                    },
                )
            if sections:
                self.map_store.update_metadata(map_id, sections=sections)
        except (OSError, ValueError) as exc:
            return self._error(
                'Could not prepare cleaning map: %s' % exc,
                'TASK_FAILED',
                accepted=False,
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='cleaning_prepare_failed',
            )

        self._clear_coverage_cache()
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None
        self.state.update(
            robot_state='waiting_for_initial_pose',
            active_task='cleaning',
            cleaning_active=True,
            cleaning_paused=False,
            active_map_id=map_id,
            active_coverage_map_id=coverage_map_id,
            active_task_id=task_id,
            cleaning_mode=cleaning_mode,
            active_sections=sections or [],
            coverage_validated=False,
            coverage_path_available=False,
            coverage_map_available=False,
            initial_pose_received=False,
            initial_pose_confirmed=False,
            initial_pose_source=None,
            initial_pose=None,
            task_finished=False,
            task_result=None,
            task_phase='waiting_for_initial_pose',
            last_error=None,
        )

        request = StartTask.Request()
        request.map_name = coverage_map_id
        request.mode = ''
        request.auto_start = False
        result = self._call_start_task(self.start_coverage_client, request)
        if not result['success']:
            self.state.reset_cleaning()
            return self._error(
                result['message'],
                'TASK_FAILED',
                accepted=result.get('accepted', True),
                completed=False,
                task_finished=False,
                command='prepare_cleaning',
                state='cleaning_prepare_failed',
            )

        self._update_coverage_readiness()
        return self._success(
            'Coverage prepared. Waiting for initial pose from mobile app or RViz.',
            command='prepare_cleaning',
            accepted=True,
            completed=True,
            task_finished=False,
            task_id=task_id,
            state='waiting_for_initial_pose',
            map_id=map_id,
            cleaning_mode=cleaning_mode,
            sections=sections or [],
            initial_pose=None,
            initial_pose_required=True,
            progress_percent=0.0,
            coverage_map_id=coverage_map_id,
            next_steps=[
                'Set initial pose from RViz or POST /api/localization/initial-pose.',
                'Call POST /api/cleaning/validate.',
                'Call POST /api/cleaning/start-motion.',
            ],
        )

    def _api_validate_cleaning(self):
        ready = self._cleaning_preconditions(require_path=False)
        if not ready['accepted']:
            return self._error(
                ready['message'],
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='validate_cleaning',
                state=ready.get('state', 'validation_blocked'),
            )
        result = self._call_trigger('/sweepi_robot_manager/coverage/validate')
        if result['success']:
            self.validated_for_current_path = True
            self.validated_coverage_path_signature = self.coverage_path_signature
            self.state.update(coverage_validated=True, robot_state='coverage_validated', task_phase='coverage_validated')
            return self._success(
                'Coverage validation completed successfully.',
                command='validate_cleaning',
                accepted=True,
                completed=True,
                task_finished=False,
                state='coverage_validated',
                task_id=self.state.snapshot().get('active_task_id'),
                map_id=self.state.snapshot().get('active_map_id'),
                coverage_map_id=self.state.snapshot().get('active_coverage_map_id'),
                next_steps=['Call POST /api/cleaning/start-motion.'],
            )
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None
        self.state.update(coverage_validated=False, task_phase='coverage_validation_failed')
        return self._error(
            'Coverage validation failed.',
            'COVERAGE_VALIDATION_FAILED',
            {'reason': result.get('message', 'Service call failed')},
            accepted=result.get('accepted', True),
            completed=False,
            task_finished=False,
            command='validate_cleaning',
            state='coverage_validation_failed',
            task_id=self.state.snapshot().get('active_task_id'),
            map_id=self.state.snapshot().get('active_map_id'),
            coverage_map_id=self.state.snapshot().get('active_coverage_map_id'),
        )

    def _api_start_cleaning_motion(self):
        ready = self._cleaning_preconditions(require_path=False)
        if not ready['accepted']:
            return self._error(
                ready['message'],
                'INVALID_STATE',
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_cleaning_motion',
                state=ready.get('state', 'start_blocked'),
            )
        snapshot = self.state.snapshot()
        path_changed_after_validation = (
            self.validated_coverage_path_signature is not None
            and self.coverage_path_signature != self.validated_coverage_path_signature
        )
        if not snapshot.get('coverage_validated') or path_changed_after_validation:
            return self._error(
                'Coverage validation is required before starting motion.',
                'VALIDATION_REQUIRED',
                accepted=False,
                completed=False,
                task_finished=False,
                command='start_cleaning_motion',
                state='validation_required',
                task_id=snapshot.get('active_task_id'),
                map_id=snapshot.get('active_map_id'),
                coverage_map_id=snapshot.get('active_coverage_map_id'),
            )
        result = self._call_trigger('/sweepi_robot_manager/coverage/start')
        if result['success']:
            self.state.update(robot_state='cleaning', cleaning_paused=False, task_phase='cleaning')
            return self._success(
                'Cleaning motion started.',
                command='start_cleaning_motion',
                accepted=True,
                completed=True,
                task_finished=False,
                state='cleaning',
                task_id=self.state.snapshot().get('active_task_id'),
                map_id=self.state.snapshot().get('active_map_id'),
                coverage_map_id=self.state.snapshot().get('active_coverage_map_id'),
            )
        return self._error(
            'Cleaning motion failed to start.',
            'CLEANING_START_FAILED',
            {'reason': result.get('message', 'Service call failed')},
            accepted=result.get('accepted', True),
            completed=False,
            task_finished=False,
            command='start_cleaning_motion',
            state='cleaning_start_failed',
            task_id=self.state.snapshot().get('active_task_id'),
            map_id=self.state.snapshot().get('active_map_id'),
            coverage_map_id=self.state.snapshot().get('active_coverage_map_id'),
        )

    def _api_store_sections(self, map_id, body):
        if not self.map_store.exists(map_id):
            return self._error(
                'Map not found.',
                'MAP_NOT_FOUND',
                {'map_id': map_id},
                accepted=False,
            )
        validation = self._validate_sections_payload(
            body,
            require_bounds=True,
            allow_empty=True,
        )
        if validation is not None:
            return validation
        meta = self.map_store.update_metadata(
            map_id,
            sections=body.get('sections', []),
            no_go_zones=body.get('no_go_zones', []),
        )
        return self._success(
            'Map sections saved.',
            accepted=True,
            **self._contract_map_metadata(meta),
        )

    def _store_inline_sections_if_present(self, map_id, body):
        if 'sections' not in body and 'no_go_zones' not in body:
            return None
        validation = self._validate_sections_payload(body)
        if validation is not None:
            return validation
        self.map_store.write_sections(
            map_id,
            body.get('sections', []),
            body.get('no_go_zones', []),
        )
        return {'ok': True}

    def _normalize_cleaning_mode(self, value):
        mode = str(value or '').strip().lower().replace('_', '-')
        if mode in ('full-map', 'fullmap'):
            return 'full-map'
        if mode == 'sections':
            return 'sections'
        return ''

    def _validate_initial_pose_payload(self, initial_pose):
        if not isinstance(initial_pose, dict):
            return self._error(
                'initial_pose is required.',
                'VALIDATION_ERROR',
                {'field': 'initial_pose'},
                accepted=False,
            )
        for field in ('x', 'y', 'yaw'):
            if field not in initial_pose:
                return self._error(
                    'initial_pose.%s is required.' % field,
                    'VALIDATION_ERROR',
                    {'field': 'initial_pose.%s' % field},
                    accepted=False,
                )
            try:
                float(initial_pose[field])
            except (TypeError, ValueError):
                return self._error(
                    'initial_pose.%s must be a number.' % field,
                    'VALIDATION_ERROR',
                    {'field': 'initial_pose.%s' % field},
                    accepted=False,
                )
        return None

    def _validate_processed_map(self, processed_map):
        if not isinstance(processed_map, dict):
            return self._error(
                'processed_map must be an object.',
                'VALIDATION_ERROR',
                {'field': 'processed_map'},
                accepted=False,
            )
        for field in ('width', 'height', 'resolution', 'origin', 'occupancy'):
            if field not in processed_map:
                return self._error(
                    'processed_map.%s is required.' % field,
                    'VALIDATION_ERROR',
                    {'field': 'processed_map.%s' % field},
                    accepted=False,
                )
        try:
            width = int(processed_map['width'])
            height = int(processed_map['height'])
            float(processed_map['resolution'])
        except (TypeError, ValueError):
            return self._error(
                'processed_map width, height, and resolution must be numeric.',
                'VALIDATION_ERROR',
                {'field': 'processed_map'},
                accepted=False,
            )
        occupancy = processed_map.get('occupancy')
        if not isinstance(occupancy, list) or len(occupancy) != width * height:
            return self._error(
                'processed_map occupancy size must match width*height.',
                'VALIDATION_ERROR',
                {'field': 'processed_map.occupancy'},
                accepted=False,
            )
        origin = processed_map.get('origin')
        if not isinstance(origin, dict):
            return self._error(
                'processed_map.origin is required.',
                'VALIDATION_ERROR',
                {'field': 'processed_map.origin'},
                accepted=False,
            )
        return None

    def _validate_sections_payload(self, body, require_bounds=False, allow_empty=True):
        sections = body.get('sections', [])
        no_go_zones = body.get('no_go_zones', [])
        if not isinstance(sections, list):
            return self._error(
                'sections must be a list.',
                'VALIDATION_ERROR',
                {'field': 'sections'},
                accepted=False,
            )
        if not allow_empty and not sections:
            return self._error(
                'sections must contain at least one section when cleaning_mode is sections.',
                'VALIDATION_ERROR',
                {'field': 'sections', 'cleaning_mode': 'sections'},
                accepted=False,
            )
        if not isinstance(no_go_zones, list):
            return self._error(
                'no_go_zones must be a list.',
                'VALIDATION_ERROR',
                {'field': 'no_go_zones'},
                accepted=False,
            )
        ids = set()
        for group_name, zones in (('sections', sections), ('no_go_zones', no_go_zones)):
            for index, zone in enumerate(zones):
                if not isinstance(zone, dict):
                    return self._error(
                        '%s entries must be objects.' % group_name,
                        'VALIDATION_ERROR',
                        {'field': '%s[%d]' % (group_name, index)},
                        accepted=False,
                    )
                zone_id = str(zone.get('section_id') or zone.get('zone_id') or '').strip()
                if not zone_id:
                    return self._error(
                        '%s[%d] id is required.' % (group_name, index),
                        'VALIDATION_ERROR',
                        {'field': '%s[%d].section_id' % (group_name, index)},
                        accepted=False,
                    )
                if zone_id in ids:
                    return self._error(
                        'section IDs must be unique.',
                        'VALIDATION_ERROR',
                        {'field': 'sections'},
                        accepted=False,
                    )
                ids.add(zone_id)
                if require_bounds or 'bounds' in zone:
                    bounds = zone.get('bounds')
                    if not isinstance(bounds, dict):
                        return self._error(
                            '%s[%d].bounds is required.' % (group_name, index),
                            'VALIDATION_ERROR',
                            {'field': '%s[%d].bounds' % (group_name, index)},
                            accepted=False,
                        )
                    for field in ('x', 'y', 'width', 'height'):
                        try:
                            value = float(bounds[field])
                        except (KeyError, TypeError, ValueError):
                            return self._error(
                                '%s[%d].bounds.%s must be a number.'
                                % (group_name, index, field),
                                'VALIDATION_ERROR',
                                {
                                    'field': '%s[%d].bounds.%s'
                                    % (group_name, index, field)
                                },
                                accepted=False,
                            )
                        if field in ('width', 'height') and value <= 0.0:
                            return self._error(
                                '%s[%d].bounds.%s must be positive.'
                                % (group_name, index, field),
                                'VALIDATION_ERROR',
                                {
                                    'field': '%s[%d].bounds.%s'
                                    % (group_name, index, field)
                                },
                                accepted=False,
                            )
                    continue
                polygon = zone.get('polygon')
                if not isinstance(polygon, list) or len(polygon) < 3:
                    return self._error(
                        '%s[%d] polygon needs at least 3 points.'
                        % (group_name, index),
                        'VALIDATION_ERROR',
                        {'field': '%s[%d].polygon' % (group_name, index)},
                        accepted=False,
                    )
                for point in polygon:
                    if (
                        not isinstance(point, list)
                        or len(point) != 2
                        or not all(isinstance(value, (int, float)) for value in point)
                    ):
                        return self._error(
                            'Polygon points must be [x, y] numbers.',
                            'VALIDATION_ERROR',
                            {'field': '%s[%d].polygon' % (group_name, index)},
                            accepted=False,
                        )
        return None

    def _cleaning_preconditions(self, require_path=False):
        snapshot = self.state.snapshot()
        if snapshot['active_task'] != 'cleaning' or not snapshot['cleaning_active']:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Cleaning has not been prepared',
                'state': 'cleaning_not_prepared',
            }
        if not snapshot['initial_pose_confirmed']:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Confirmed initial pose is required before coverage validation or motion',
                'state': 'initial_pose_required',
            }
        if not self.pose_available:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Robot pose TF map -> base_link is not available yet',
                'state': 'pose_unavailable',
            }
        if require_path and not snapshot['coverage_path_available']:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Coverage path is not available yet',
                'state': 'coverage_path_unavailable',
            }
        return {'ok': True, 'accepted': True}

    def _wait_for_cleaning_ready(self, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline and rclpy.ok():
            self._update_robot_pose()
            self._update_coverage_readiness()
            status = self._cleaning_status()
            if status.get('ready_to_start_motion'):
                return True
            time.sleep(0.1)
        return False

    def _cleaning_status(self):
        self._update_coverage_readiness()
        snapshot = self.state.snapshot()
        ready = (
            snapshot['cleaning_active']
            and snapshot['initial_pose_confirmed']
            and self.pose_available
        )
        ready_to_start_motion = ready and snapshot['coverage_validated']
        if not snapshot['cleaning_active']:
            message = 'Cleaning is idle'
        elif ready_to_start_motion:
            message = 'Coverage validated. Ready to start motion'
        elif ready:
            message = 'Coverage ready to validate'
        elif snapshot['robot_state'] == 'cleaning':
            message = 'Cleaning in progress'
        elif snapshot['robot_state'] == 'paused':
            message = 'Cleaning paused'
        elif snapshot['robot_state'] == 'initial_pose_failed':
            message = 'Initial pose was not confirmed. Set initial pose again.'
        else:
            message = 'Coverage prepared. Waiting for confirmed initial pose from API or RViz.'
        state = snapshot['robot_state']
        if not snapshot['cleaning_active']:
            state = 'idle'
        return self._success(
            'Cleaning status fetched.',
            active=snapshot['cleaning_active'],
            state=state,
            task_id=snapshot['active_task_id'],
            map_id=snapshot['active_map_id'],
            coverage_map_id=snapshot['active_coverage_map_id'],
            cleaning_mode=snapshot['cleaning_mode'],
            sections=snapshot.get('active_sections', []),
            progress_percent=self.coverage_percentage,
            pose=self.robot_pose or snapshot['initial_pose'],
            nav={'execution_status': self.coverage_execution_status},
            coverage=self._coverage_area_summary(),
            paused=snapshot['cleaning_paused'],
            initial_pose_received=snapshot['initial_pose_received'],
            initial_pose_confirmed=snapshot['initial_pose_confirmed'],
            initial_pose_source=snapshot['initial_pose_source'],
            coverage_path_available=snapshot['coverage_path_available'],
            path_available=snapshot['coverage_path_available'],
            coverage_map_available=snapshot['coverage_map_available'],
            coverage_validated=snapshot['coverage_validated'],
            pose_available=self.pose_available,
            ready_to_validate=ready and snapshot['robot_state'] != 'cleaning',
            ready_to_start_motion=ready_to_start_motion and snapshot['robot_state'] != 'cleaning',
            task_finished=snapshot['task_finished'],
            task_result=snapshot['task_result'],
            last_error=snapshot['last_error'],
            next_steps=self._cleaning_next_steps(snapshot, ready, ready_to_start_motion),
            status_message=message,
        )

    def _cleaning_path(self, stride):
        with self.data_lock:
            path = self.coverage_path
            map_id = self.state.snapshot().get('active_map_id')
        if path is None or not path.poses:
            return {'ok': True, 'available': False, 'map_id': map_id, 'points': []}
        payload = path_to_json(path, stride=stride)
        payload.update({'ok': True, 'map_id': map_id})
        return payload

    def _cleaning_coverage_map(self):
        with self.data_lock:
            coverage_map = self.coverage_map
            map_id = self.state.snapshot().get('active_map_id')
        if coverage_map is None:
            return {'ok': True, 'available': False, 'map_id': map_id}
        payload = occupancy_grid_to_json(coverage_map, include_occupancy=True)
        payload.update({'ok': True, 'map_id': map_id})
        return payload

    def _cleaning_next_steps(self, snapshot, ready_to_validate, ready_to_start_motion):
        if not snapshot['cleaning_active']:
            return ['Call POST /api/cleaning/start.']
        if not snapshot['initial_pose_confirmed']:
            return ['Set initial pose with POST /api/localization/initial-pose.']
        if not ready_to_validate:
            return ['Wait for robot pose TF map -> base_link to become available.']
        if not snapshot['coverage_validated']:
            return ['Call POST /api/cleaning/validate.']
        if ready_to_start_motion and snapshot['robot_state'] != 'cleaning':
            return ['Call POST /api/cleaning/start-motion.']
        if snapshot['robot_state'] == 'cleaning':
            return ['Poll GET /api/cleaning/status until task_finished is true.']
        return []

    def _coverage_area_summary(self):
        with self.data_lock:
            coverage_map = self.coverage_map
        if coverage_map is None:
            return {
                'covered_area_m2': 0.0,
                'total_area_m2': 0.0,
            }
        covered_cells = 0
        uncovered_cells = 0
        for value in coverage_map.data:
            if value == 100:
                covered_cells += 1
            elif value == 50:
                uncovered_cells += 1
        cell_area = float(coverage_map.info.resolution) ** 2
        return {
            'covered_area_m2': round(covered_cells * cell_area, 3),
            'total_area_m2': round((covered_cells + uncovered_cells) * cell_area, 3),
        }

    def _exploration_status(self):
        snapshot = self.state.snapshot()
        return self._success(
            'Exploration status fetched.',
            active=snapshot['exploration_active'],
            state=snapshot['robot_state'],
            map_name=snapshot['active_map_id'],
            map_id=snapshot['active_map_id'],
            mode=snapshot['exploration_mode'] if snapshot['exploration_active'] else None,
            progress_percent=None,
            pose=self.robot_pose,
            map_available=bool(snapshot['live_map_available']),
            saved_map_available=bool(
                snapshot['active_map_id'] and self.map_store.exists(snapshot['active_map_id'])
            ),
        )

    def _robot_status(self):
        snapshot = self.state.snapshot()
        return self._success(
            'Robot status fetched.',
            robot_id='sweepi-robot-001',
            state=snapshot['robot_state'],
            active_task=None if snapshot['active_task'] == 'none' else snapshot['active_task'],
            mode=snapshot['exploration_mode'] if snapshot['active_task'] == 'exploration' else None,
            battery={'percent': None, 'charging': None},
            pose=self.robot_pose,
            localization={
                'initial_pose_received': snapshot['initial_pose_received'],
                'initial_pose_confirmed': snapshot['initial_pose_confirmed'],
                'initial_pose_source': snapshot['initial_pose_source'],
                'pose_available': self.pose_available,
            },
            exploration={
                'active': snapshot['exploration_active'],
                'mode': snapshot['exploration_mode'] if snapshot['exploration_active'] else None,
                'map_name': snapshot['active_map_id'] if snapshot['active_task'] == 'exploration' else None,
                'map_id': snapshot['active_map_id'] if snapshot['active_task'] == 'exploration' else None,
                'map_available': snapshot['live_map_available'],
            },
            cleaning={
                'active': snapshot['cleaning_active'],
                'paused': snapshot['cleaning_paused'],
                'task_id': snapshot['active_task_id'],
                'cleaning_mode': snapshot['cleaning_mode'],
                'progress_percent': self.coverage_percentage,
                'map_id': snapshot['active_map_id'] if snapshot['active_task'] == 'cleaning' else None,
                'sections': snapshot.get('active_sections', []),
                'path_available': snapshot['coverage_path_available'],
                'coverage_path_available': snapshot['coverage_path_available'],
                'coverage_map_available': snapshot['coverage_map_available'],
                'coverage_validated': snapshot['coverage_validated'],
                'execution_status': self.coverage_execution_status,
                'coverage_stats': self.coverage_stats,
                'task_finished': snapshot['task_finished'],
                'task_result': snapshot['task_result'],
                'last_error': snapshot['last_error'],
            },
            map={
                'map_id': snapshot['active_map_id'],
                'name': snapshot['active_area_name'] or snapshot['active_map_id'],
                'live_available': snapshot['live_map_available'],
                'saved_available': bool(snapshot['active_map_id'] and self.map_store.exists(snapshot['active_map_id'])),
            },
            nav={'execution_status': self.coverage_execution_status},
            errors=[snapshot['last_error']] if snapshot['last_error'] else [],
            warnings=snapshot['warnings'],
        )

    def _system_health(self):
        return self._success(
            'API server is healthy.',
            status='ok',
            robot_connected=bool(self.manager_status),
            server='sweepi_api_bridge',
            api={'host': self.api_host, 'port': self.api_port, 'prefix': '/api'},
            manager_status=self.manager_status,
            ros_time_sec=self.get_clock().now().nanoseconds / 1e9,
        )

    def _call_start_task(self, client, request, timeout_sec=10.0):
        if not client.wait_for_service(timeout_sec=1.0):
            return {'success': False, 'accepted': False, 'message': 'Service unavailable'}
        event = threading.Event()
        result_box = {}
        future = client.call_async(request)
        future.add_done_callback(lambda done: self._future_to_box(done, event, result_box))
        if not event.wait(timeout_sec):
            return {'success': False, 'accepted': True, 'message': 'Service call timed out'}
        return result_box

    def _call_trigger(self, service_name, timeout_sec=10.0):
        client = self.trigger_clients[service_name]
        if not client.wait_for_service(timeout_sec=1.0):
            return {
                'success': False,
                'accepted': False,
                'message': 'Service unavailable: %s' % service_name,
            }
        event = threading.Event()
        result_box = {}
        future = client.call_async(Trigger.Request())
        future.add_done_callback(lambda done: self._future_to_box(done, event, result_box))
        if not event.wait(timeout_sec):
            return {
                'success': False,
                'accepted': True,
                'message': 'Service call timed out: %s' % service_name,
            }
        return result_box

    def _future_to_box(self, future, event, result_box):
        try:
            result = future.result()
            result_box['success'] = bool(result.success)
            result_box['accepted'] = True
            result_box['message'] = str(result.message)
        except Exception as exc:
            result_box['success'] = False
            result_box['accepted'] = True
            result_box['message'] = str(exc)
        finally:
            event.set()

    def _accepted_from_service(self, result):
        return {
            'ok': True,
            'accepted': bool(result.get('success')),
            'message': result.get('message', ''),
        }

    def _publish_initial_pose(self, x, y, yaw, source):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        quat = yaw_to_quaternion(float(yaw))
        msg.pose.pose.orientation.z = quat['z']
        msg.pose.pose.orientation.w = quat['w']
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        if source == 'api':
            self.last_api_initial_pose_publish_time = time.monotonic()
        self.initial_pose_pub.publish(msg)

    def _record_initial_pose(self, x, y, yaw, source, confirmed=True):
        self.state.update(
            initial_pose_received=True,
            initial_pose_confirmed=bool(confirmed),
            initial_pose_source=source,
            initial_pose={
                'x': float(x),
                'y': float(y),
                'yaw': float(yaw),
                'frame': 'map',
            },
            coverage_validated=False,
            task_phase='initial_pose_confirmed' if confirmed else 'initial_pose_pending',
        )
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None
        self._update_coverage_readiness()

    def _confirm_initial_pose(
        self,
        x,
        y,
        yaw,
        timeout_sec=5.0,
        distance_tolerance=0.75,
        yaw_tolerance=1.0,
    ):
        deadline = time.monotonic() + float(timeout_sec)
        last_pose = None
        while time.monotonic() < deadline and rclpy.ok():
            self._update_robot_pose(force=True)
            if self.pose_available and self.robot_pose:
                last_pose = dict(self.robot_pose)
                distance = math.hypot(
                    float(self.robot_pose['x']) - float(x),
                    float(self.robot_pose['y']) - float(y),
                )
                yaw_error = abs(self._angle_delta(float(self.robot_pose['yaw']), float(yaw)))
                if distance <= distance_tolerance and yaw_error <= yaw_tolerance:
                    return {
                        'ok': True,
                        'message': 'Localization confirmed.',
                        'distance': distance,
                        'yaw_error': yaw_error,
                        'pose': last_pose,
                        'distance_tolerance': distance_tolerance,
                        'yaw_tolerance': yaw_tolerance,
                    }
            time.sleep(0.1)
        return {
            'ok': False,
            'message': (
                'map -> base_link TF was not available before timeout'
                if last_pose is None
                else 'Robot pose did not match requested initial pose before timeout'
            ),
            'pose': last_pose,
            'distance_tolerance': distance_tolerance,
            'yaw_tolerance': yaw_tolerance,
            'timeout_sec': timeout_sec,
        }

    def _angle_delta(self, a, b):
        return math.atan2(math.sin(a - b), math.cos(a - b))

    def _publish_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        try:
            self.cmd_vel_pub.publish(msg)
        except Exception as exc:
            self.get_logger().debug('Could not publish /cmd_vel: %s' % exc)

    def _publish_zero_velocity(self):
        self.manual_command_expiry = 0.0
        self._publish_velocity(0.0, 0.0)

    def _manual_drive_allowed(self):
        snapshot = self.state.snapshot()
        return (
            snapshot['active_task'] == 'exploration'
            and snapshot['exploration_active']
            and snapshot['exploration_mode'] == 'manual'
        )

    def _clear_coverage_cache(self):
        with self.data_lock:
            self.coverage_map = None
            self.coverage_path = None
            self.coverage_percentage = 0.0
            self.coverage_stats = ''
            self.coverage_execution_status = 'WAITING_FOR_PATH'
            self.coverage_path_signature = None
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None

    def _timer_callback(self):
        now = time.monotonic()
        if self.manual_command_expiry and now >= self.manual_command_expiry:
            self._publish_zero_velocity()
        if now - self.last_pose_lookup_time >= 1.0:
            self.last_pose_lookup_time = now
            self._update_robot_pose()
        self._update_coverage_readiness()

    def _update_robot_pose(self, force=False):
        snapshot = self.state.snapshot()
        needs_pose = (
            force
            or snapshot['initial_pose_received']
            or snapshot['exploration_active']
            or snapshot['robot_state'] in ('cleaning', 'paused', 'returning_home')
        )
        if not needs_pose:
            self.pose_available = False
            return
        self._ensure_tf_listener()
        try:
            transform = self.tf_buffer.lookup_transform(
                'map',
                'base_link',
                Time(),
                timeout=Duration(seconds=0.02),
            )
        except TransformException:
            self.pose_available = False
            return
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z),
        )
        self.robot_pose = {
            'x': float(translation.x),
            'y': float(translation.y),
            'yaw': float(yaw),
            'frame': 'map',
        }
        self.pose_available = True

    def _ensure_tf_listener(self):
        if self.tf_buffer is not None:
            return
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def _update_coverage_readiness(self):
        snapshot = self.state.snapshot()
        if not snapshot['cleaning_active']:
            return
        path_available = snapshot['coverage_path_available']
        map_available = snapshot['coverage_map_available']
        if snapshot['robot_state'] in ('cleaning', 'paused', 'returning_home'):
            self.state.update(
                coverage_path_available=path_available,
                coverage_map_available=map_available,
            )
            return
        if (
            not snapshot['initial_pose_confirmed']
            and snapshot['robot_state'] == 'initial_pose_failed'
        ):
            next_state = 'initial_pose_failed'
        elif not snapshot['initial_pose_confirmed']:
            next_state = 'waiting_for_initial_pose'
        elif snapshot['coverage_validated']:
            next_state = 'coverage_validated'
        elif self.pose_available and path_available:
            next_state = 'coverage_ready'
        else:
            next_state = 'coverage_preparing'
        self.state.update(
            robot_state=next_state,
            coverage_path_available=path_available,
            coverage_map_available=map_available,
        )

    def _manager_status_callback(self, msg):
        self.manager_status = str(msg.data or '')
        fields = self._parse_status_fields(self.manager_status)
        task = fields.get('task')
        if task == 'idle':
            snapshot = self.state.snapshot()
            if snapshot['active_task'] == 'exploration':
                self.state.reset_exploration()
            elif (
                snapshot['active_task'] == 'cleaning'
                and snapshot['robot_state'] not in ('paused',)
                and not snapshot.get('task_finished')
            ):
                self.state.reset_cleaning()
        elif task == 'exploration':
            mode = fields.get('latest_exploration_mode', '')
            robot_state = (
                'exploration_stopped'
                if mode == 'stopped'
                else 'exploring'
            )
            self.state.update(
                robot_state=robot_state,
                active_task='exploration',
                exploration_active=True,
            )
        elif task == 'coverage':
            self.state.update(active_task='cleaning', cleaning_active=True)

    def _coverage_last_summary_topic_callback(self, msg):
        self.last_coverage_summary_topic = str(msg.data or '')

    def _exploration_mode_callback(self, msg):
        mode = str(msg.data or '').strip().lower()
        if mode == 'auto':
            mode = 'automatic'
        if mode not in ('automatic', 'manual', 'stopped'):
            mode = 'unknown'
        updates = {
            'exploration_mode': mode,
        }
        if mode == 'stopped':
            updates.update(
                robot_state='exploration_stopped',
                active_task='exploration',
                exploration_active=True,
            )
        elif mode in ('automatic', 'manual'):
            updates.update(
                robot_state='exploring',
                active_task='exploration',
                exploration_active=True,
            )
        self.state.update(**updates)

    def _map_callback(self, msg):
        with self.data_lock:
            self.live_map = msg
        self.state.update(live_map_available=True)

    def _coverage_map_callback(self, msg):
        available = bool(msg.info.width and msg.info.height and msg.data)
        with self.data_lock:
            self.coverage_map = msg if available else None
        self.state.update(coverage_map_available=available)

    def _coverage_path_callback(self, msg):
        available = bool(msg.poses)
        new_signature = self._coverage_path_signature(msg) if available else None
        path_changed = new_signature != self.coverage_path_signature
        with self.data_lock:
            self.coverage_path = msg if available else None
            self.coverage_path_signature = new_signature
        updates = {'coverage_path_available': available}
        if not available or path_changed:
            self.validated_for_current_path = False
            self.validated_coverage_path_signature = None
            updates['coverage_validated'] = False
        self.state.update(**updates)

    def _coverage_path_signature(self, msg):
        poses = list(msg.poses or [])
        if not poses:
            return None
        first = poses[0].pose.position
        last = poses[-1].pose.position
        return (
            len(poses),
            round(float(first.x), 3),
            round(float(first.y), 3),
            round(float(last.x), 3),
            round(float(last.y), 3),
        )

    def _coverage_percentage_callback(self, msg):
        self.coverage_percentage = float(msg.data)

    def _coverage_stats_callback(self, msg):
        self.coverage_stats = str(msg.data or '')

    def _coverage_execution_status_callback(self, msg):
        status = str(msg.data or '').strip()
        if status:
            self.coverage_execution_status = status
        if status == 'PAUSED':
            self.state.update(robot_state='paused', cleaning_paused=True)
        elif status in ('FOLLOWING_PATH', 'RUNNING'):
            self.state.update(
                robot_state='cleaning',
                cleaning_paused=False,
                task_finished=False,
                task_result=None,
                task_phase='cleaning',
            )
        elif status in ('COMPLETED', 'SUCCEEDED', 'DONE'):
            self.state.update(
                robot_state='cleaning_completed',
                cleaning_paused=False,
                task_finished=True,
                task_result='completed',
                task_phase='completed',
            )
        elif status in ('FAILED', 'ABORTED', 'CANCELED', 'CANCELLED'):
            self.state.update(
                robot_state='cleaning_failed',
                cleaning_paused=False,
                task_finished=True,
                task_result='failed',
                task_phase='failed',
                last_error={
                    'code': 'CLEANING_TASK_FAILED',
                    'details': {'execution_status': status},
                },
            )

    def _initial_pose_callback(self, msg):
        if time.monotonic() - self.last_api_initial_pose_publish_time < 0.5:
            return
        pose = msg.pose.pose
        yaw = pose_to_json(pose, frame=msg.header.frame_id or 'map')['yaw']
        x = float(pose.position.x)
        y = float(pose.position.y)
        self.state.update(
            initial_pose_received=True,
            initial_pose_confirmed=False,
            initial_pose_source='rviz',
            initial_pose={'x': x, 'y': y, 'yaw': yaw, 'frame': 'map'},
            coverage_validated=False,
            task_phase='initial_pose_pending',
        )
        self.validated_for_current_path = False
        self.validated_coverage_path_signature = None
        confirmation = self._confirm_initial_pose(x, y, yaw)
        if confirmation.get('ok'):
            self._record_initial_pose(x, y, yaw, source='rviz', confirmed=True)
        else:
            self.state.update(
                initial_pose_confirmed=False,
                coverage_validated=False,
                last_error={
                    'code': 'INITIAL_POSE_NOT_CONFIRMED',
                    'details': {'reason': confirmation.get('message')},
                },
                task_phase='initial_pose_failed',
            )

    def _parse_status_fields(self, status_text):
        fields = {}
        for token in status_text.split():
            if '=' in token:
                key, value = token.split('=', 1)
                fields[key] = value
        return fields


def main(args=None):
    rclpy.init(args=args)
    node = SweePiApiBridge()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.remove_node(node)
        node.destroy_node()
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()

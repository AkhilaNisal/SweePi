#!/usr/bin/env python3
"""HTTP JSON API bridge for SweePi."""

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
                                {'ok': False, 'message': str(exc)},
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
                        {'ok': False, 'message': 'Internal API bridge error'},
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
            return 404, {'ok': False, 'message': 'Unknown route'}
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

        return 404, {'ok': False, 'message': 'Unknown route'}

    def _handle_exploration(self, method, route, body):
        if method == 'POST' and route == ['start']:
            return 200, self._api_start_exploration(body)
        if method == 'GET' and route == ['status']:
            return 200, self._exploration_status()
        if method == 'POST' and route == ['mode']:
            return 200, self._api_switch_exploration_mode(body)
        if method == 'POST' and route == ['switch-mode']:
            return 200, self._api_switch_exploration_mode(body)
        if method == 'POST' and route == ['manual', 'drive']:
            return 200, self._api_manual_drive(body)
        if method == 'POST' and route == ['manual', 'command']:
            return 200, self._api_manual_command(body)
        if method == 'POST' and route == ['manual', 'stop']:
            self._publish_zero_velocity()
            return 200, {'ok': True, 'accepted': True, 'message': 'Manual motion stopped'}
        if method == 'POST' and route == ['stop']:
            self._publish_zero_velocity()
            result = self._call_trigger('/sweepi_robot_manager/exploration/stop')
            if result['success']:
                self.state.update(
                    robot_state='exploration_stopped',
                    active_task='exploration',
                    exploration_active=True,
                    exploration_mode='stopped',
                )
            return 200, self._accepted_from_service(result)
        if method == 'POST' and route == ['stop-and-save']:
            self._publish_zero_velocity()
            result = self._call_trigger('/sweepi_robot_manager/exploration/stop_and_save')
            snapshot = self.state.snapshot()
            map_id = snapshot.get('active_map_id')
            map_saved = self.map_store.exists(map_id) if map_id else False
            if map_id:
                self.map_store.ensure_meta(
                    map_id,
                    {
                        'area_name': snapshot.get('active_area_name'),
                        'source': 'exploration',
                    },
                )
            if result['success']:
                self.state.reset_exploration()
            payload = self._accepted_from_service(result)
            payload['map_id'] = map_id
            payload['map_saved'] = map_saved
            return 200, payload
        return 404, {'ok': False, 'message': 'Unknown exploration route'}

    def _handle_localization(self, method, route, body):
        if method == 'POST' and route == ['initial-pose']:
            return 200, self._api_initial_pose(body)
        if method == 'GET' and route == ['status']:
            snapshot = self.state.snapshot()
            return 200, {
                'ok': True,
                'initial_pose_received': snapshot['initial_pose_received'],
                'initial_pose_source': snapshot['initial_pose_source'],
                'initial_pose': snapshot['initial_pose'],
                'pose_available': self.pose_available,
                'pose': self.robot_pose,
            }
        return 404, {'ok': False, 'message': 'Unknown localization route'}

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
            return 200, {'ok': True, 'maps': self.map_store.list_maps()}
        if len(route) >= 1:
            map_id = sanitize_map_id(route[0])
            if method == 'GET' and len(route) == 1:
                payload = self.map_store.read_map(map_id)
                payload['ok'] = True
                return 200, payload
            if method == 'GET' and len(route) == 2 and route[1] == 'metadata':
                return 200, {'ok': True, 'metadata': self.map_store.metadata(map_id)}
            if method == 'PUT' and len(route) == 2 and route[1] == 'sections':
                return 200, self._api_store_sections(map_id, body)
        return 404, {'ok': False, 'message': 'Unknown maps route'}

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
                self.state.update(robot_state='paused', cleaning_paused=True)
            return 200, self._accepted_from_service(result)
        if method == 'POST' and route == ['resume']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/continue')
            if result['success']:
                self.state.update(robot_state='cleaning', cleaning_paused=False)
            return 200, self._accepted_from_service(result)
        if method == 'POST' and route == ['stop']:
            self._publish_zero_velocity()
            result = self._call_trigger('/sweepi_robot_manager/coverage/stop')
            if result['success']:
                self.state.reset_cleaning()
            return 200, self._accepted_from_service(result)
        if method == 'POST' and route == ['reset']:
            self._publish_zero_velocity()
            result = self._call_trigger('/sweepi_robot_manager/coverage/reset')
            if result['success']:
                self._clear_coverage_cache()
                self.state.reset_cleaning()
            return 200, self._accepted_from_service(result)
        if method == 'POST' and route == ['return-home']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/return_home')
            if result['success']:
                self.state.update(robot_state='returning_home')
            return 200, self._accepted_from_service(result)
        if method == 'GET' and route == ['last-summary']:
            result = self._call_trigger('/sweepi_robot_manager/coverage/last_summary')
            return 200, {
                'ok': True,
                'accepted': result['success'],
                'message': result['message'],
                'topic_summary': self.last_coverage_summary_topic,
            }
        return 404, {'ok': False, 'message': 'Unknown cleaning route'}

    def _api_start_exploration(self, body):
        snapshot = self.state.snapshot()
        if snapshot['cleaning_active'] or snapshot['cleaning_paused']:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Cannot start exploration while cleaning is active',
            }

        area_name = str(body.get('area_name') or body.get('map_id') or 'map').strip()
        map_id = sanitize_map_id(body.get('map_id') or area_name)
        api_mode, manager_mode = self._normalize_exploration_api_mode(
            body.get('mode') or 'automatic'
        )
        if not api_mode:
            return {
                'ok': True,
                'accepted': False,
                'message': 'mode must be automatic/auto or manual',
            }
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
                active_area_name=area_name,
                active_task_id=None,
            )
        return {
            'ok': True,
            'accepted': result['success'],
            'state': self.state.snapshot()['robot_state'],
            'map_id': map_id,
            'area_name': area_name,
            'mode': api_mode,
            'message': result['message'],
        }

    def _normalize_exploration_api_mode(self, value):
        mode = str(value or '').strip().lower()
        if mode in ('auto', 'automatic', 'autonomous'):
            return 'automatic', 'auto'
        if mode in ('manual', 'teleop'):
            return 'manual', 'manual'
        return '', ''

    def _api_switch_exploration_mode(self, body):
        api_mode, manager_mode = self._normalize_exploration_api_mode(
            body.get('mode')
        )
        if not api_mode:
            return {
                'ok': True,
                'accepted': False,
                'message': 'mode must be manual or automatic/auto',
            }
        snapshot = self.state.snapshot()
        if snapshot['active_task'] != 'exploration':
            return {'ok': True, 'accepted': False, 'message': 'Exploration is not active'}

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
            )
        payload = self._accepted_from_service(result)
        payload['mode'] = api_mode
        payload['map_id'] = snapshot.get('active_map_id')
        return payload

    def _api_manual_drive(self, body):
        if not self._manual_drive_allowed():
            return {
                'ok': True,
                'accepted': False,
                'message': 'Manual driving is allowed only during manual exploration',
            }
        linear_x = clamp(float(body.get('linear_x', 0.0)), -0.20, 0.20)
        angular_z = clamp(float(body.get('angular_z', 0.0)), -0.80, 0.80)
        duration_ms = int(clamp(int(body.get('duration_ms', 300)), 1, 1000))
        self._publish_velocity(linear_x, angular_z)
        self.manual_command_expiry = time.monotonic() + (duration_ms / 1000.0)
        return {
            'ok': True,
            'accepted': True,
            'linear_x': linear_x,
            'angular_z': angular_z,
            'duration_ms': duration_ms,
            'message': 'Manual drive command accepted',
        }

    def _api_manual_command(self, body):
        command = str(body.get('command') or '').strip().lower()
        speed = abs(float(body.get('speed', 0.15)))
        duration_ms = int(body.get('duration_ms', 300))
        mapping = {
            'forward': (speed, 0.0),
            'backward': (-speed, 0.0),
            'rotate_left': (0.0, speed),
            'rotate_right': (0.0, -speed),
            'stop': (0.0, 0.0),
        }
        if command not in mapping:
            return {'ok': True, 'accepted': False, 'message': 'Unsupported manual command'}
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
            if clean_map_id != snapshot['active_map_id']:
                return {
                    'ok': True,
                    'accepted': False,
                    'message': 'Initial pose map_id does not match active map',
                }
        try:
            x = float(body['x'])
            y = float(body['y'])
            yaw = float(body.get('yaw', 0.0))
        except (KeyError, TypeError, ValueError):
            return {'ok': True, 'accepted': False, 'message': 'x, y, and optional yaw are required'}
        self._publish_initial_pose(x, y, yaw, source='api')
        return {
            'ok': True,
            'accepted': True,
            'initial_pose_received': True,
            'initial_pose_source': 'api',
            'message': 'Initial pose published',
        }

    def _api_start_cleaning(self, body):
        snapshot = self.state.snapshot()
        if snapshot['exploration_active']:
            return {
                'ok': True,
                'accepted': False,
                'message': 'Cannot start cleaning while exploration is active',
            }
        map_id = sanitize_map_id(body.get('map_id') or '')
        if not map_id:
            return {'ok': True, 'accepted': False, 'message': 'map_id is required'}
        if not self.map_store.exists(map_id):
            return {'ok': True, 'accepted': False, 'message': 'Requested map does not exist'}

        cleaning_mode = str(body.get('cleaning_mode') or 'full_map').strip().lower()
        if cleaning_mode == 'sections':
            store_result = self._store_inline_sections_if_present(map_id, body)
            if store_result is not None and not store_result['ok']:
                return store_result
            return {
                'ok': True,
                'accepted': False,
                'map_id': map_id,
                'message': (
                    'Selected-section cleaning API is stored but coverage planner '
                    'section masking is not implemented yet'
                ),
            }
        if cleaning_mode != 'full_map':
            return {'ok': True, 'accepted': False, 'message': 'Unsupported cleaning_mode'}

        initial_pose = body.get('initial_pose')
        if isinstance(initial_pose, dict):
            pose_result = self._api_initial_pose({'map_id': map_id, **initial_pose})
            if not pose_result.get('accepted'):
                return pose_result

        task_id = 'cleaning_%d' % int(time.time())
        self._clear_coverage_cache()
        self.validated_for_current_path = False
        self.state.update(
            robot_state='coverage_preparing',
            active_task='cleaning',
            cleaning_active=True,
            cleaning_paused=False,
            active_map_id=map_id,
            active_task_id=task_id,
            cleaning_mode=cleaning_mode,
            coverage_validated=False,
            coverage_path_available=False,
            coverage_map_available=False,
            initial_pose_received=bool(isinstance(initial_pose, dict)),
            initial_pose_source='api' if isinstance(initial_pose, dict) else None,
        )

        request = StartTask.Request()
        request.map_name = map_id
        request.mode = ''
        request.auto_start = False
        result = self._call_start_task(self.start_coverage_client, request)
        if not result['success']:
            self.state.reset_cleaning()
            return self._accepted_from_service(result)

        self._update_coverage_readiness()
        auto_start = bool(body.get('auto_start', False))
        if auto_start:
            ready = self._wait_for_cleaning_ready(timeout_sec=20.0)
            if not ready:
                return {
                    'ok': True,
                    'accepted': False,
                    'state': self.state.snapshot()['robot_state'],
                    'map_id': map_id,
                    'message': 'Coverage prepared, but initial pose, TF, or path is not ready yet',
                }
            return self._api_start_cleaning_motion()

        return {
            'ok': True,
            'accepted': True,
            'state': self.state.snapshot()['robot_state'],
            'map_id': map_id,
            'task_id': task_id,
            'message': (
                'Coverage prepared. Waiting for initial pose from API or RViz; '
                'coverage path will be generated after initial pose and TF are ready.'
            ),
        }

    def _api_validate_cleaning(self):
        ready = self._cleaning_preconditions(require_path=False)
        if not ready['accepted']:
            return ready
        result = self._call_trigger('/sweepi_robot_manager/coverage/validate')
        if result['success']:
            self.validated_for_current_path = True
            self.state.update(coverage_validated=True)
        return self._accepted_from_service(result)

    def _api_start_cleaning_motion(self):
        ready = self._cleaning_preconditions(require_path=False)
        if not ready['accepted']:
            return ready
        if not self.validated_for_current_path:
            validate_result = self._call_trigger('/sweepi_robot_manager/coverage/validate')
            if not validate_result['success']:
                return self._accepted_from_service(validate_result)
            self.validated_for_current_path = True
            self.state.update(coverage_validated=True)
        result = self._call_trigger('/sweepi_robot_manager/coverage/start')
        if result['success']:
            self.state.update(robot_state='cleaning', cleaning_paused=False)
        payload = self._accepted_from_service(result)
        payload['state'] = self.state.snapshot()['robot_state']
        payload['map_id'] = self.state.snapshot().get('active_map_id')
        return payload

    def _api_store_sections(self, map_id, body):
        if not self.map_store.exists(map_id):
            return {'ok': True, 'accepted': False, 'message': 'Map does not exist'}
        validation = self._validate_sections_payload(body)
        if validation is not None:
            return validation
        meta = self.map_store.write_sections(
            map_id,
            body.get('sections', []),
            body.get('no_go_zones', []),
        )
        return {
            'ok': True,
            'accepted': True,
            'metadata': meta,
            'message': 'Map sections saved',
        }

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

    def _validate_sections_payload(self, body):
        sections = body.get('sections', [])
        no_go_zones = body.get('no_go_zones', [])
        if not isinstance(sections, list):
            return {'ok': True, 'accepted': False, 'message': 'sections must be a list'}
        if not isinstance(no_go_zones, list):
            return {'ok': True, 'accepted': False, 'message': 'no_go_zones must be a list'}
        ids = set()
        for group_name, zones in (('sections', sections), ('no_go_zones', no_go_zones)):
            for index, zone in enumerate(zones):
                if not isinstance(zone, dict):
                    return {'ok': True, 'accepted': False, 'message': '%s entries must be objects' % group_name}
                zone_id = str(zone.get('section_id') or zone.get('zone_id') or '').strip()
                if not zone_id:
                    return {'ok': True, 'accepted': False, 'message': '%s[%d] id is required' % (group_name, index)}
                if zone_id in ids:
                    return {'ok': True, 'accepted': False, 'message': 'section IDs must be unique'}
                ids.add(zone_id)
                polygon = zone.get('polygon')
                if not isinstance(polygon, list) or len(polygon) < 3:
                    return {'ok': True, 'accepted': False, 'message': '%s[%d] polygon needs at least 3 points' % (group_name, index)}
                for point in polygon:
                    if (
                        not isinstance(point, list)
                        or len(point) != 2
                        or not all(isinstance(value, (int, float)) for value in point)
                    ):
                        return {'ok': True, 'accepted': False, 'message': 'Polygon points must be [x, y] numbers'}
        return None

    def _cleaning_preconditions(self, require_path=False):
        snapshot = self.state.snapshot()
        if snapshot['active_task'] != 'cleaning' or not snapshot['cleaning_active']:
            return {'ok': True, 'accepted': False, 'message': 'Cleaning has not been prepared'}
        if not snapshot['initial_pose_received']:
            return {'ok': True, 'accepted': False, 'message': 'Initial pose is required before starting coverage'}
        if not self.pose_available:
            return {'ok': True, 'accepted': False, 'message': 'Robot pose TF map -> base_link is not available yet'}
        if require_path and not snapshot['coverage_path_available']:
            return {'ok': True, 'accepted': False, 'message': 'Coverage path is not available yet'}
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
            and snapshot['initial_pose_received']
            and self.pose_available
            and snapshot['coverage_path_available']
        )
        if not snapshot['cleaning_active']:
            message = 'Cleaning is idle'
        elif ready and snapshot['robot_state'] in ('coverage_ready', 'coverage_preparing', 'waiting_for_initial_pose'):
            message = 'Coverage ready to start motion'
        elif snapshot['robot_state'] == 'cleaning':
            message = 'Cleaning in progress'
        elif snapshot['robot_state'] == 'paused':
            message = 'Cleaning paused'
        else:
            message = 'Coverage prepared. Waiting for initial pose from API or RViz.'
        return {
            'ok': True,
            'state': snapshot['robot_state'],
            'active': snapshot['cleaning_active'],
            'paused': snapshot['cleaning_paused'],
            'map_id': snapshot['active_map_id'],
            'task_id': snapshot['active_task_id'],
            'cleaning_mode': snapshot['cleaning_mode'],
            'initial_pose_received': snapshot['initial_pose_received'],
            'initial_pose_source': snapshot['initial_pose_source'],
            'pose': snapshot['initial_pose'],
            'pose_available': self.pose_available,
            'path_available': snapshot['coverage_path_available'],
            'coverage_map_available': snapshot['coverage_map_available'],
            'progress_percent': self.coverage_percentage,
            'execution_status': self.coverage_execution_status,
            'coverage_stats': self.coverage_stats,
            'ready_to_start_motion': ready and snapshot['robot_state'] != 'cleaning',
            'message': message,
        }

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

    def _exploration_status(self):
        snapshot = self.state.snapshot()
        return {
            'ok': True,
            'state': snapshot['robot_state'],
            'mode': snapshot['exploration_mode'],
            'area_name': snapshot['active_area_name'],
            'map_id': snapshot['active_map_id'],
            'map_available': bool(snapshot['active_map_id'] and self.map_store.exists(snapshot['active_map_id'])),
            'robot_pose': self.robot_pose,
            'live_map_available': snapshot['live_map_available'],
            'message': 'Exploration active' if snapshot['exploration_active'] else 'Exploration idle',
        }

    def _robot_status(self):
        snapshot = self.state.snapshot()
        return {
            'ok': True,
            'robot_id': 'sweepi-robot-001',
            'state': snapshot['robot_state'],
            'active_task': None if snapshot['active_task'] == 'none' else snapshot['active_task'],
            'mode': snapshot['exploration_mode'] if snapshot['active_task'] == 'exploration' else None,
            'battery': {'percent': None, 'charging': None},
            'pose': self.robot_pose,
            'localization': {
                'initial_pose_received': snapshot['initial_pose_received'],
                'initial_pose_source': snapshot['initial_pose_source'],
                'pose_available': self.pose_available,
            },
            'exploration': {
                'active': snapshot['exploration_active'],
                'mode': snapshot['exploration_mode'] if snapshot['exploration_active'] else None,
                'area_name': snapshot['active_area_name'],
                'map_id': snapshot['active_map_id'] if snapshot['active_task'] == 'exploration' else None,
                'map_available': snapshot['live_map_available'],
            },
            'cleaning': {
                'active': snapshot['cleaning_active'],
                'paused': snapshot['cleaning_paused'],
                'task_id': snapshot['active_task_id'],
                'cleaning_mode': snapshot['cleaning_mode'],
                'progress_percent': self.coverage_percentage,
                'map_id': snapshot['active_map_id'] if snapshot['active_task'] == 'cleaning' else None,
                'path_available': snapshot['coverage_path_available'],
                'coverage_map_available': snapshot['coverage_map_available'],
                'execution_status': self.coverage_execution_status,
                'coverage_stats': self.coverage_stats,
            },
            'map': {
                'map_id': snapshot['active_map_id'],
                'name': snapshot['active_area_name'] or snapshot['active_map_id'],
                'live_available': snapshot['live_map_available'],
                'saved_available': bool(snapshot['active_map_id'] and self.map_store.exists(snapshot['active_map_id'])),
            },
            'errors': [snapshot['last_error']] if snapshot['last_error'] else [],
            'warnings': snapshot['warnings'],
        }

    def _system_health(self):
        return {
            'ok': True,
            'api': {'host': self.api_host, 'port': self.api_port, 'prefix': '/api'},
            'manager_status': self.manager_status,
            'ros_time_sec': self.get_clock().now().nanoseconds / 1e9,
        }

    def _call_start_task(self, client, request, timeout_sec=10.0):
        if not client.wait_for_service(timeout_sec=1.0):
            return {'success': False, 'message': 'Service unavailable'}
        event = threading.Event()
        result_box = {}
        future = client.call_async(request)
        future.add_done_callback(lambda done: self._future_to_box(done, event, result_box))
        if not event.wait(timeout_sec):
            return {'success': False, 'message': 'Service call timed out'}
        return result_box

    def _call_trigger(self, service_name, timeout_sec=10.0):
        client = self.trigger_clients[service_name]
        if not client.wait_for_service(timeout_sec=1.0):
            return {'success': False, 'message': 'Service unavailable: %s' % service_name}
        event = threading.Event()
        result_box = {}
        future = client.call_async(Trigger.Request())
        future.add_done_callback(lambda done: self._future_to_box(done, event, result_box))
        if not event.wait(timeout_sec):
            return {'success': False, 'message': 'Service call timed out: %s' % service_name}
        return result_box

    def _future_to_box(self, future, event, result_box):
        try:
            result = future.result()
            result_box['success'] = bool(result.success)
            result_box['message'] = str(result.message)
        except Exception as exc:
            result_box['success'] = False
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
        self._record_initial_pose(x, y, yaw, source)

    def _record_initial_pose(self, x, y, yaw, source):
        self.state.update(
            initial_pose_received=True,
            initial_pose_source=source,
            initial_pose={
                'x': float(x),
                'y': float(y),
                'yaw': float(yaw),
                'frame': 'map',
            },
        )
        self._update_coverage_readiness()

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
        self.validated_for_current_path = False

    def _timer_callback(self):
        now = time.monotonic()
        if self.manual_command_expiry and now >= self.manual_command_expiry:
            self._publish_zero_velocity()
        if now - self.last_pose_lookup_time >= 1.0:
            self.last_pose_lookup_time = now
            self._update_robot_pose()
        self._update_coverage_readiness()

    def _update_robot_pose(self):
        snapshot = self.state.snapshot()
        needs_pose = (
            snapshot['initial_pose_received']
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
        if not snapshot['initial_pose_received']:
            next_state = 'waiting_for_initial_pose'
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
            elif snapshot['active_task'] == 'cleaning' and snapshot['robot_state'] not in ('paused',):
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
        with self.data_lock:
            self.coverage_path = msg if available else None
        self.validated_for_current_path = False
        self.state.update(
            coverage_path_available=available,
            coverage_validated=False,
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
            self.state.update(robot_state='cleaning', cleaning_paused=False)

    def _initial_pose_callback(self, msg):
        if time.monotonic() - self.last_api_initial_pose_publish_time < 0.5:
            return
        pose = msg.pose.pose
        yaw = pose_to_json(pose, frame=msg.header.frame_id or 'map')['yaw']
        self._record_initial_pose(
            pose.position.x,
            pose.position.y,
            yaw,
            source='rviz',
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

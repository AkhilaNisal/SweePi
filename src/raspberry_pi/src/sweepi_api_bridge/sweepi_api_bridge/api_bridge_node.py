#!/usr/bin/env python3
"""HTTP and websocket bridge for the SweePi mobile app."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import socketserver
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Float32, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from sweepi_api_bridge.map_io import (
    list_saved_maps,
    load_map_metadata,
    save_map_metadata,
    save_occupancy_grid,
)
from sweepi_api_bridge.runtime_paths import active_map_file, database_path
from sweepi_api_bridge.storage import BridgeStorage


@dataclass
class TaskContext:
    task_id: str
    task_type: str
    selection: dict
    map_id: str | None
    started_at: str
    schedule_id: str | None = None


class ApiBridgeNode(Node):
    """Serve the LAN-facing robot API and translate requests into ROS actions."""

    def __init__(self):
        super().__init__('api_bridge_node')

        self.declare_parameter('api_host', '0.0.0.0')
        self.declare_parameter('api_port', 8080)
        self.declare_parameter('ws_port', 8765)
        self.declare_parameter('manager_status_topic', '/manager/status_json')
        self.declare_parameter('selection_topic', '/coverage_selection')
        self.declare_parameter('robot_base_frame', 'base_link')
        self.declare_parameter('global_frame', 'map')

        self.api_host = self.get_parameter('api_host').value
        self.api_port = int(self.get_parameter('api_port').value)
        self.ws_port = int(self.get_parameter('ws_port').value)
        self.manager_status_topic = self.get_parameter('manager_status_topic').value
        self.selection_topic = self.get_parameter('selection_topic').value
        self.robot_base_frame = self.get_parameter('robot_base_frame').value
        self.global_frame = self.get_parameter('global_frame').value

        self.storage = BridgeStorage(database_path())
        self.map_msg: OccupancyGrid | None = None
        self.coverage_map_msg: OccupancyGrid | None = None
        self.coverage_percent = 0.0
        self.coverage_stats_text = ''
        self.manager_status = {
            'state': 'idle',
            'mode': 'auto',
            'errors': [],
            'warnings': [],
        }
        self.exploration_area_name: str | None = None
        self.exploration_status = {
            'state': 'idle',
            'map_available': False,
            'frontiers_remaining': 0,
            'last_goal': None,
            'message': 'Exploration status has not been received yet',
        }
        self.selection = {
            'selection_id': None,
            'room_ids': [],
            'zones': [],
            'no_go_zones': [],
            'map_id': None,
            'map_revision': None,
        }
        self.active_task: TaskContext | None = None
        self.last_terminal_status = ''
        self._lock = threading.Lock()
        self._ws_lock = threading.Lock()

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.map_sub = self.create_subscription(
            OccupancyGrid,
            '/map',
            self._map_callback,
            10,
        )
        self.coverage_map_sub = self.create_subscription(
            OccupancyGrid,
            '/coverage_map',
            self._coverage_map_callback,
            10,
        )
        self.coverage_percent_sub = self.create_subscription(
            Float32,
            '/coverage_percentage',
            self._coverage_percent_callback,
            10,
        )
        self.coverage_stats_sub = self.create_subscription(
            String,
            '/coverage_stats',
            self._coverage_stats_callback,
            10,
        )
        self.manager_status_sub = self.create_subscription(
            String,
            self.manager_status_topic,
            self._manager_status_callback,
            10,
        )
        self.exploration_status_sub = self.create_subscription(
            String,
            '/exploration/status_json',
            self._exploration_status_callback,
            10,
        )
        self.selection_pub = self.create_publisher(String, self.selection_topic, 10)

        self.start_exploration_client = self.create_client(
            Trigger,
            '/exploration/start',
        )
        self.stop_exploration_client = self.create_client(
            Trigger,
            '/exploration/stop',
        )
        self.start_cleaning_client = self.create_client(
            Trigger,
            '/manager/start_cleaning',
        )
        self.stop_cleaning_client = self.create_client(
            Trigger,
            '/manager/stop_cleaning',
        )
        self.pause_cleaning_client = self.create_client(
            Trigger,
            '/manager/pause_cleaning',
        )
        self.resume_cleaning_client = self.create_client(
            Trigger,
            '/manager/resume_cleaning',
        )
        self.return_to_dock_client = self.create_client(
            Trigger,
            '/manager/return_to_dock',
        )

        self.http_server = self._start_http_server()
        self.ws_server, self.ws_clients = self._start_websocket_server()
        self.schedule_timer = self.create_timer(30.0, self._run_scheduler)

        self.get_logger().info(
            'API bridge listening on http://%s:%d and ws://%s:%d'
            % (self.api_host, self.api_port, self.api_host, self.ws_port)
        )

    def _map_callback(self, msg: OccupancyGrid) -> None:
        with self._lock:
            self.map_msg = msg
        self._broadcast('map.updated', {'map_revision': self._map_revision()})

    def _coverage_map_callback(self, msg: OccupancyGrid) -> None:
        with self._lock:
            self.coverage_map_msg = msg
        self._broadcast('map.updated', {'map_revision': self._map_revision()})

    def _coverage_percent_callback(self, msg: Float32) -> None:
        with self._lock:
            self.coverage_percent = float(msg.data)
        self._broadcast('status.update', self.robot_status())

    def _coverage_stats_callback(self, msg: String) -> None:
        with self._lock:
            self.coverage_stats_text = msg.data
        self._broadcast('status.update', self.robot_status())

    def _manager_status_callback(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn('Ignoring invalid manager status JSON')
            return

        completed_task = None
        with self._lock:
            self.manager_status = payload
            terminal_status = payload.get('execution_status', '')
            if (
                self.active_task is not None
                and terminal_status
                and terminal_status != self.last_terminal_status
                and terminal_status
                in {
                    'SUCCEEDED',
                    'COMPLETED_WITH_SKIPS',
                    'FAILED',
                    'BLOCKED_DYNAMIC_OBJECT',
                    'CANCELED',
                }
            ):
                completed_task = (self.active_task, terminal_status, self.coverage_percent)
                self.last_terminal_status = terminal_status
                self.active_task = None

        if completed_task is not None:
            task, result, coverage_percent = completed_task
            history = self.storage.get_history(task.task_id) or {}
            history.update(
                {
                    'task_id': task.task_id,
                    'task_type': task.task_type,
                    'map_id': task.map_id,
                    'selection': task.selection,
                    'started_at': task.started_at,
                    'ended_at': datetime.now(timezone.utc).isoformat(),
                    'result': result,
                    'coverage_percent': coverage_percent,
                    'notes': {},
                }
            )
            self.storage.upsert_history(history)
            self._broadcast(
                'task.completed',
                {
                    'task_id': task.task_id,
                    'result': result,
                    'coverage_percent': coverage_percent,
                },
            )

        self._broadcast('status.update', self.robot_status())

    def _exploration_status_callback(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn('Ignoring invalid exploration status JSON')
            return

        with self._lock:
            self.exploration_status = payload
        self._broadcast('exploration.update', self.exploration_status_payload())

    def _start_http_server(self) -> ThreadingHTTPServer:
        node = self

        class Handler(BaseHTTPRequestHandler):
            server_version = 'SweePiBridge/0.1'

            def do_GET(self):
                node._handle_http_request(self, 'GET')

            def do_POST(self):
                node._handle_http_request(self, 'POST')

            def do_PUT(self):
                node._handle_http_request(self, 'PUT')

            def do_DELETE(self):
                node._handle_http_request(self, 'DELETE')

            def log_message(self, format, *args):
                node.get_logger().debug(format % args)

        server = ThreadingHTTPServer((self.api_host, self.api_port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def _start_websocket_server(self):
        clients: set = set()
        node = self

        class WebSocketClient:
            def __init__(self, handler):
                self._handler = handler
                self._send_lock = threading.Lock()

            def send(self, message: str) -> None:
                payload = message.encode('utf-8')
                frame = bytearray([0x81])
                if len(payload) < 126:
                    frame.append(len(payload))
                elif len(payload) <= 0xFFFF:
                    frame.extend(
                        [126, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF]
                    )
                else:
                    frame.append(127)
                    frame.extend(len(payload).to_bytes(8, byteorder='big'))
                frame.extend(payload)
                with self._send_lock:
                    self._handler.request.sendall(frame)

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                client = None
                try:
                    if not self._perform_handshake():
                        return
                    client = WebSocketClient(self)
                    with node._ws_lock:
                        clients.add(client)
                    client.send(
                        json.dumps(
                            {
                                'type': 'status.snapshot',
                                'payload': node.robot_status(),
                            }
                        )
                    )
                    self._read_until_close()
                except Exception as exc:  # pragma: no cover - defensive runtime logging
                    node.get_logger().debug(f'WebSocket client disconnected: {exc}')
                finally:
                    if client is not None:
                        with node._ws_lock:
                            clients.discard(client)

            def _perform_handshake(self) -> bool:
                request_line = self.rfile.readline().decode('ascii', errors='ignore')
                if not request_line.startswith('GET '):
                    return False

                headers = {}
                while True:
                    line = self.rfile.readline().decode('ascii', errors='ignore')
                    if line in ('\r\n', '\n', ''):
                        break
                    key, _, value = line.partition(':')
                    headers[key.strip().lower()] = value.strip()

                ws_key = headers.get('sec-websocket-key')
                if not ws_key:
                    return False

                accept = base64.b64encode(
                    hashlib.sha1(
                        (ws_key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode(
                            'ascii'
                        )
                    ).digest()
                ).decode('ascii')
                response = (
                    'HTTP/1.1 101 Switching Protocols\r\n'
                    'Upgrade: websocket\r\n'
                    'Connection: Upgrade\r\n'
                    f'Sec-WebSocket-Accept: {accept}\r\n'
                    '\r\n'
                )
                self.request.sendall(response.encode('ascii'))
                return True

            def _read_until_close(self) -> None:
                while True:
                    first = self.rfile.read(2)
                    if len(first) < 2:
                        return
                    opcode = first[0] & 0x0F
                    masked = bool(first[1] & 0x80)
                    length = first[1] & 0x7F
                    if length == 126:
                        length = int.from_bytes(self.rfile.read(2), byteorder='big')
                    elif length == 127:
                        length = int.from_bytes(self.rfile.read(8), byteorder='big')
                    mask = self.rfile.read(4) if masked else b''
                    payload = self.rfile.read(length) if length else b''
                    if masked and payload:
                        payload = bytes(
                            byte ^ mask[index % 4]
                            for index, byte in enumerate(payload)
                        )
                    if opcode == 0x8:
                        return
                    if opcode == 0x9:
                        self._send_control_frame(0xA, payload)

            def _send_control_frame(self, opcode: int, payload: bytes) -> None:
                if len(payload) > 125:
                    payload = payload[:125]
                self.request.sendall(bytes([0x80 | opcode, len(payload)]) + payload)

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        server = Server((self.api_host, self.ws_port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, clients

    def _broadcast(self, message_type: str, payload: dict) -> None:
        if not hasattr(self, 'ws_clients'):
            return
        message = json.dumps({'type': message_type, 'payload': payload})
        dead_clients = []
        with self._ws_lock:
            clients = list(self.ws_clients)
        for client in clients:
            try:
                client.send(message)
            except Exception:
                dead_clients.append(client)
        if dead_clients:
            with self._ws_lock:
                for client in dead_clients:
                    self.ws_clients.discard(client)

    def _handle_http_request(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        parsed = urlparse(handler.path)
        path = parsed.path.rstrip('/') or '/'
        body = self._read_json_body(handler)
        try:
            payload, status = self._route_request(method, path, body, parse_qs(parsed.query))
        except ValueError as exc:
            payload, status = ({'error': str(exc)}, HTTPStatus.BAD_REQUEST)
        except KeyError:
            payload, status = ({'error': 'Not found'}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - defensive runtime logging
            self.get_logger().error(f'HTTP request failed: {exc}')
            payload, status = (
                {'error': 'Internal server error'},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        raw = json.dumps(payload).encode('utf-8')
        handler.send_response(int(status))
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(raw)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.end_headers()
        handler.wfile.write(raw)

    def _route_request(self, method: str, path: str, body: dict, _query: dict):
        if path == '/api/v1/robot/status' and method == 'GET':
            return self.robot_status(), HTTPStatus.OK
        if path == '/api/v1/maps/current' and method == 'GET':
            return self.current_map_payload(), HTTPStatus.OK
        if path == '/api/v1/maps' and method == 'GET':
            return {'items': list_saved_maps()}, HTTPStatus.OK
        if path == '/api/v1/history' and method == 'GET':
            return {'items': self.storage.history_items()}, HTTPStatus.OK
        if path == '/api/v1/schedules' and method == 'GET':
            return {'items': self.storage.list_schedules()}, HTTPStatus.OK
        if path == '/api/v1/schedules' and method == 'POST':
            schedule = self._normalize_schedule(body)
            return self.storage.upsert_schedule(schedule), HTTPStatus.OK
        if path.startswith('/api/v1/schedules/') and method == 'PUT':
            schedule_id = path.split('/')[-1]
            schedule = self._normalize_schedule(body, schedule_id=schedule_id)
            return self.storage.upsert_schedule(schedule), HTTPStatus.OK
        if path.startswith('/api/v1/schedules/') and method == 'DELETE':
            schedule_id = path.split('/')[-1]
            deleted = self.storage.delete_schedule(schedule_id)
            return {'deleted': deleted}, HTTPStatus.OK
        if path == '/api/v1/maps/save' and method == 'POST':
            map_name = body.get('name', f'map_{int(time.time())}')
            return self.save_current_map(map_name), HTTPStatus.OK
        if path == '/api/v1/maps/load' and method == 'POST':
            return self.load_saved_map(body), HTTPStatus.OK
        if path.startswith('/api/v1/maps/') and path.endswith('/metadata') and method == 'GET':
            map_id = path.split('/')[-2]
            return load_map_metadata(map_id), HTTPStatus.OK
        if path.startswith('/api/v1/maps/') and path.endswith('/metadata') and method == 'PUT':
            map_id = path.split('/')[-2]
            return save_map_metadata(map_id, body), HTTPStatus.OK
        if path == '/api/v1/exploration/start' and method == 'POST':
            return self.start_exploration(body), HTTPStatus.OK
        if path == '/api/v1/exploration/stop' and method == 'POST':
            return self.stop_exploration(), HTTPStatus.OK
        if path == '/api/v1/exploration/status' and method == 'GET':
            return self.exploration_status_payload(), HTTPStatus.OK
        if path == '/api/v1/cleaning/selection' and method == 'PUT':
            return self.update_selection(body), HTTPStatus.OK
        if path == '/api/v1/cleaning/start' and method == 'POST':
            return self.start_cleaning('full', body), HTTPStatus.OK
        if path == '/api/v1/cleaning/start-selected' and method == 'POST':
            return self.start_cleaning('selected', body), HTTPStatus.OK
        if path == '/api/v1/cleaning/stop' and method == 'POST':
            return self._service_result(self.stop_cleaning_client), HTTPStatus.OK
        if path == '/api/v1/cleaning/pause' and method == 'POST':
            return self._service_result(self.pause_cleaning_client), HTTPStatus.OK
        if path == '/api/v1/cleaning/resume' and method == 'POST':
            return self._service_result(self.resume_cleaning_client), HTTPStatus.OK
        if path == '/api/v1/robot/return-to-dock' and method == 'POST':
            return self._service_result(self.return_to_dock_client), HTTPStatus.OK
        raise KeyError(path)

    def robot_status(self) -> dict:
        with self._lock:
            manager_status = dict(self.manager_status)
            selection = dict(self.selection)
            coverage_percent = self.coverage_percent
            active_task = self.active_task
            map_id = selection.get('map_id')

        pose = self._lookup_robot_pose()
        return {
            'robot_id': 'sweepi-sim-001',
            'state': manager_status.get('state', 'idle'),
            'mode': manager_status.get('mode', 'auto'),
            'battery': {'percent': None, 'charging': None},
            'pose': pose,
            'cleaning': {
                'task_id': active_task.task_id if active_task else None,
                'type': active_task.task_type if active_task else None,
                'progress_percent': coverage_percent,
                'selection': selection,
            },
            'map': {
                'map_id': map_id,
                'revision': self._map_revision(),
            },
            'nav': {
                'execution_status': manager_status.get('execution_status'),
                'coverage_stats': self.coverage_stats_text,
            },
            'errors': manager_status.get('errors', []),
            'warnings': manager_status.get('warnings', []),
        }

    def exploration_status_payload(self) -> dict:
        with self._lock:
            status = dict(self.exploration_status)
            area_name = self.exploration_area_name
            map_available = self.map_msg is not None

        last_goal = status.get('last_goal')
        if not isinstance(last_goal, dict):
            last_goal = None

        return {
            'state': status.get('state', 'idle'),
            'area_name': area_name,
            'map_available': map_available,
            'frontiers_remaining': int(status.get('frontiers_remaining', 0) or 0),
            'last_goal': last_goal,
            'message': status.get('message', ''),
        }

    def current_map_payload(self) -> dict:
        with self._lock:
            map_msg = self.map_msg
            coverage_msg = self.coverage_map_msg
            selection = dict(self.selection)

        if map_msg is None:
            return {
                'map_id': selection.get('map_id'),
                'revision': 0,
                'available': False,
                'selection': selection,
            }

        map_id = selection.get('map_id') or 'live_map'
        metadata = load_map_metadata(map_id)
        return {
            'map_id': map_id,
            'revision': self._map_revision(),
            'available': True,
            'resolution': map_msg.info.resolution,
            'origin': {
                'x': map_msg.info.origin.position.x,
                'y': map_msg.info.origin.position.y,
            },
            'width': map_msg.info.width,
            'height': map_msg.info.height,
            'occupancy': list(map_msg.data),
            'coverage': list(coverage_msg.data) if coverage_msg is not None else None,
            'selection': selection,
            'metadata': metadata,
            'robot_pose': self._lookup_robot_pose(),
        }

    def update_selection(self, body: dict) -> dict:
        zones = body.get('zones', [])
        room_ids = body.get('room_ids', [])
        no_go_zones = body.get('no_go_zones', [])
        map_id = body.get('map_id', 'live_map')
        rooms = self._resolve_rooms(map_id, room_ids)
        payload = {
            'selection_id': body.get('selection_id', f'sel_{uuid.uuid4().hex[:8]}'),
            'map_id': map_id,
            'map_revision': body.get('map_revision', self._map_revision()),
            'room_ids': room_ids,
            'rooms': rooms,
            'zones': zones,
            'no_go_zones': no_go_zones,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        self._validate_selection_payload(payload)

        message = String()
        message.data = json.dumps(payload)
        self.selection_pub.publish(message)
        with self._lock:
            self.selection = payload
        self._broadcast('status.update', self.robot_status())
        return {'accepted': True, 'selection': payload}

    def start_exploration(self, body: dict) -> dict:
        area_name = str(body.get('area_name', '')).strip()
        if not area_name:
            raise ValueError('area_name is required')

        service_result = self._trigger_service_result(
            self.start_exploration_client,
            '/exploration/start',
        )
        if not service_result.get('accepted', False):
            return {
                'accepted': False,
                'state': self.exploration_status_payload().get('state', 'idle'),
                'area_name': area_name,
                'message': service_result.get('message', 'Exploration start failed'),
            }

        with self._lock:
            self.exploration_area_name = area_name
            self.exploration_status = {
                **self.exploration_status,
                'state': 'exploring',
                'message': 'Exploration started',
            }
        payload = {
            'accepted': True,
            'state': 'exploring',
            'area_name': area_name,
            'message': 'Exploration started',
        }
        self._broadcast('exploration.update', self.exploration_status_payload())
        return payload

    def stop_exploration(self) -> dict:
        with self._lock:
            area_name = self.exploration_area_name

        service_result = self._trigger_service_result(
            self.stop_exploration_client,
            '/exploration/stop',
        )
        if not service_result.get('accepted', False):
            return {
                'accepted': False,
                'state': self.exploration_status_payload().get('state', 'idle'),
                'area_name': area_name,
                'map_saved': False,
                'message': service_result.get('message', 'Exploration stop failed'),
            }

        map_saved = False
        map_id = None
        if area_name:
            try:
                save_result = self.save_current_map(area_name)
                map_saved = True
                map_id = save_result['map_id']
                message = 'Exploration stopped and map saved'
            except ValueError as exc:
                message = f'Exploration stopped, but {exc}'
        else:
            message = 'Exploration stopped, but no active area_name was available for map saving'

        if not map_saved and message == 'Exploration stopped, but No live /map is available to save':
            message = 'Exploration stopped, but no live /map was available to save'

        with self._lock:
            self.exploration_status = {
                **self.exploration_status,
                'state': 'idle',
                'message': message,
            }
        self._broadcast('exploration.update', self.exploration_status_payload())

        response = {
            'accepted': True,
            'state': 'idle',
            'area_name': area_name,
            'map_saved': map_saved,
            'message': message,
        }
        if map_id is not None:
            response['map_id'] = map_id
        return response

    def start_cleaning(self, task_type: str, body: dict) -> dict:
        if task_type == 'selected' and not self.selection.get('zones') and not self.selection.get('room_ids'):
            raise ValueError('Selected cleaning requires at least one zone or room')

        service_result = self._service_result(self.start_cleaning_client)
        if not service_result.get('accepted', False):
            return service_result

        task = TaskContext(
            task_id=body.get('task_id', f'task_{uuid.uuid4().hex[:8]}'),
            task_type=task_type,
            selection=dict(self.selection),
            map_id=self.selection.get('map_id'),
            started_at=datetime.now(timezone.utc).isoformat(),
            schedule_id=body.get('schedule_id'),
        )
        with self._lock:
            self.active_task = task
            self.last_terminal_status = ''
        self.storage.upsert_history(
            {
                'task_id': task.task_id,
                'task_type': task.task_type,
                'map_id': task.map_id,
                'selection': task.selection,
                'started_at': task.started_at,
                'ended_at': None,
                'result': None,
                'coverage_percent': None,
                'notes': {'command_id': body.get('command_id')},
            }
        )
        self._broadcast('status.update', self.robot_status())
        return {
            'accepted': True,
            'task_id': task.task_id,
            'state': 'cleaning',
        }

    def save_current_map(self, name: str) -> dict:
        with self._lock:
            map_msg = self.map_msg
        if map_msg is None:
            raise ValueError('No live /map is available to save')
        result = save_occupancy_grid(map_msg, name)
        active_map_file().write_text(
            json.dumps({'map_id': result['map_id']}, indent=2),
            encoding='utf-8',
        )
        return {'accepted': True, **result}

    def load_saved_map(self, body: dict) -> dict:
        map_id = body.get('map_id')
        if not map_id:
            raise ValueError('map_id is required')
        catalog = {item['map_id']: item for item in list_saved_maps()}
        if map_id not in catalog:
            raise ValueError(f'Unknown map_id "{map_id}"')
        active_map_file().write_text(
            json.dumps(
                {
                    'map_id': map_id,
                    'loaded_at': datetime.now(timezone.utc).isoformat(),
                    'robot_apply_supported': False,
                },
                indent=2,
            ),
            encoding='utf-8',
        )
        with self._lock:
            self.selection['map_id'] = map_id
        return {
            'accepted': True,
            'active_map_id': map_id,
            'robot_apply_supported': False,
            'note': (
                'Saved map selection is tracked by the bridge, but applying it to '
                'the localization stack is still a planned simulation-first step.'
            ),
        }

    def _service_result(self, client) -> dict:
        return self._trigger_service_result(client, 'Required ROS service')

    def _trigger_service_result(self, client, service_name: str) -> dict:
        if not client.wait_for_service(timeout_sec=1.0):
            return {
                'accepted': False,
                'message': f'{service_name} is unavailable',
            }

        event = threading.Event()
        result: dict = {}

        future = client.call_async(Trigger.Request())

        def done_callback(done_future):
            try:
                response = done_future.result()
                result['accepted'] = bool(response.success)
                result['message'] = response.message
            except Exception as exc:  # pragma: no cover - defensive runtime logging
                result['accepted'] = False
                result['message'] = str(exc)
            finally:
                event.set()

        future.add_done_callback(done_callback)
        event.wait(timeout=5.0)
        if not result:
            return {'accepted': False, 'message': 'Service call timed out'}
        return result

    def _validate_selection_payload(self, payload: dict) -> None:
        for zone in payload.get('zones', []):
            polygon = zone.get('polygon', [])
            if len(polygon) < 3:
                raise ValueError('Each zone polygon must contain at least 3 points')
            for point in polygon:
                if len(point) != 2:
                    raise ValueError('Polygon points must be [x, y] pairs')
        for room in payload.get('rooms', []):
            polygon = room.get('polygon', [])
            if len(polygon) < 3:
                raise ValueError('Each room polygon must contain at least 3 points')
            for point in polygon:
                if len(point) != 2:
                    raise ValueError('Polygon points must be [x, y] pairs')
        for zone in payload.get('no_go_zones', []):
            polygon = zone.get('polygon', [])
            if len(polygon) < 3:
                raise ValueError('Each no-go polygon must contain at least 3 points')

    def _normalize_schedule(self, body: dict, schedule_id: str | None = None) -> dict:
        if not body.get('time_local'):
            raise ValueError('time_local is required')
        return {
            'id': schedule_id or body.get('id', f'sch_{uuid.uuid4().hex[:8]}'),
            'enabled': bool(body.get('enabled', True)),
            'timezone': body.get('timezone', 'UTC'),
            'days': body.get('days', []),
            'time_local': body['time_local'],
            'map_id': body.get('map_id'),
            'selection': body.get('selection', {}),
            'last_run_at': body.get('last_run_at'),
            'next_run_at': body.get('next_run_at'),
        }

    def _run_scheduler(self) -> None:
        for schedule in self.storage.list_schedules():
            if not schedule['enabled']:
                continue

            schedule_now = self._schedule_now(schedule.get('timezone', 'UTC'))
            if schedule_now.strftime('%a').upper()[:3] not in schedule['days']:
                continue
            current_time = schedule_now.strftime('%H:%M')
            if current_time != schedule['time_local']:
                continue
            if self._schedule_already_ran_this_minute(schedule, schedule_now):
                continue

            with self._lock:
                busy = self.active_task is not None
            if busy:
                continue

            selection = {
                'selection_id': f'sched_{schedule["id"]}',
                'map_id': schedule.get('map_id', 'live_map'),
                'map_revision': self._map_revision(),
                'room_ids': schedule.get('selection', {}).get('room_ids', []),
                'rooms': self._resolve_rooms(
                    schedule.get('map_id', 'live_map'),
                    schedule.get('selection', {}).get('room_ids', []),
                ),
                'zones': schedule.get('selection', {}).get('zones', []),
                'no_go_zones': schedule.get('selection', {}).get('no_go_zones', []),
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            self._validate_selection_payload(selection)
            message = String()
            message.data = json.dumps(selection)
            self.selection_pub.publish(message)
            with self._lock:
                self.selection = selection
            self.start_cleaning(
                'selected' if selection['zones'] or selection['room_ids'] else 'full',
                {
                    'task_id': f'sched_task_{uuid.uuid4().hex[:8]}',
                    'schedule_id': schedule['id'],
                },
            )
            self.storage.mark_schedule_run(schedule['id'], next_run_at=None)

    def _resolve_rooms(self, map_id: str | None, room_ids: list) -> list[dict]:
        if not map_id or not room_ids:
            return []

        metadata = load_map_metadata(map_id)
        rooms_by_id = {
            room.get('id'): room
            for room in metadata.get('rooms', [])
            if isinstance(room, dict) and room.get('id')
        }

        resolved_rooms = []
        for room_id in room_ids:
            room = rooms_by_id.get(room_id)
            if room is not None:
                resolved_rooms.append(room)
        return resolved_rooms

    def _schedule_now(self, timezone_name: str) -> datetime:
        try:
            tzinfo = ZoneInfo(timezone_name)
        except Exception:
            tzinfo = timezone.utc
        return datetime.now(tzinfo)

    def _schedule_already_ran_this_minute(self, schedule: dict, schedule_now: datetime) -> bool:
        last_run_at = schedule.get('last_run_at')
        if not last_run_at:
            return False

        try:
            last_run = datetime.fromisoformat(last_run_at)
        except ValueError:
            return False

        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        return last_run.astimezone(schedule_now.tzinfo).strftime('%Y-%m-%dT%H:%M') == (
            schedule_now.strftime('%Y-%m-%dT%H:%M')
        )

    def _lookup_robot_pose(self) -> dict | None:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException:
            return None

        pose = PoseStamped()
        pose.header.frame_id = self.global_frame
        pose.pose.position.x = transform.transform.translation.x
        pose.pose.position.y = transform.transform.translation.y
        pose.pose.position.z = transform.transform.translation.z
        pose.pose.orientation = transform.transform.rotation
        yaw = self._yaw_from_quaternion(pose.pose.orientation)
        return {
            'x': pose.pose.position.x,
            'y': pose.pose.position.y,
            'yaw': yaw,
            'frame': self.global_frame,
        }

    def _map_revision(self) -> int:
        with self._lock:
            map_msg = self.map_msg
        if map_msg is None:
            return 0
        stamp = map_msg.header.stamp
        return int(stamp.sec * 1000 + stamp.nanosec / 1_000_000)

    def _yaw_from_quaternion(self, quaternion) -> float:
        siny_cosp = 2.0 * (
            quaternion.w * quaternion.z + quaternion.x * quaternion.y
        )
        cosy_cosp = 1.0 - 2.0 * (
            quaternion.y * quaternion.y + quaternion.z * quaternion.z
        )
        return float(math.atan2(siny_cosp, cosy_cosp))

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict:
        content_length = int(handler.headers.get('Content-Length', '0') or '0')
        if content_length <= 0:
            return {}
        raw = handler.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw.decode('utf-8'))

    def destroy_node(self):
        if hasattr(self, 'http_server'):
            self.http_server.shutdown()
        if hasattr(self, 'ws_server'):
            self.ws_server.shutdown()
            self.ws_server.server_close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ApiBridgeNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

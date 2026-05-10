#!/usr/bin/env python3
"""High-level cleaning state manager for SweePi coverage tasks."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Float32, String
from std_srvs.srv import Trigger


class CoverageManagerNode(Node):
    """Coordinate app-facing cleaning state around the FollowPath executor."""

    def __init__(self):
        super().__init__('coverage_manager_node')

        self.declare_parameter('status_topic', '/manager/status_json')
        self.declare_parameter('selection_topic', '/coverage_selection')
        self.declare_parameter('executor_status_topic', '/coverage_execution_status')
        self.declare_parameter('dynamic_status_topic', '/coverage_dynamic_skip_status')
        self.declare_parameter('coverage_percentage_topic', '/coverage_percentage')
        self.declare_parameter('coverage_stats_topic', '/coverage_stats')

        self.status_topic = self.get_parameter('status_topic').value
        self.selection_topic = self.get_parameter('selection_topic').value
        self.executor_status_topic = self.get_parameter('executor_status_topic').value
        self.dynamic_status_topic = self.get_parameter('dynamic_status_topic').value
        self.coverage_percentage_topic = self.get_parameter('coverage_percentage_topic').value
        self.coverage_stats_topic = self.get_parameter('coverage_stats_topic').value

        self.state = 'idle'
        self.mode = 'auto'
        self.execution_status = 'WAITING_FOR_PATH'
        self.coverage_percent = 0.0
        self.coverage_stats = ''
        self.dynamic_status = ''
        self.last_error = None
        self.last_warning = None
        self.selection = {
            'selection_id': None,
            'room_ids': [],
            'zones': [],
            'no_go_zones': [],
        }
        self.map_available = False
        self.paused_context = None
        self.pause_requested = False

        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.selection_sub = self.create_subscription(
            String,
            self.selection_topic,
            self._selection_callback,
            10,
        )
        self.map_sub = self.create_subscription(
            OccupancyGrid,
            '/map',
            self._map_callback,
            10,
        )
        self.executor_status_sub = self.create_subscription(
            String,
            self.executor_status_topic,
            self._executor_status_callback,
            10,
        )
        self.dynamic_status_sub = self.create_subscription(
            String,
            self.dynamic_status_topic,
            self._dynamic_status_callback,
            10,
        )
        self.coverage_percentage_sub = self.create_subscription(
            Float32,
            self.coverage_percentage_topic,
            self._coverage_percentage_callback,
            10,
        )
        self.coverage_stats_sub = self.create_subscription(
            String,
            self.coverage_stats_topic,
            self._coverage_stats_callback,
            10,
        )

        self.start_executor_client = self.create_client(
            Trigger,
            '/start_coverage_follow_path',
        )
        self.cancel_executor_client = self.create_client(
            Trigger,
            '/cancel_coverage_follow_path',
        )
        self.validate_executor_client = self.create_client(
            Trigger,
            '/validate_coverage_follow_path',
        )
        self.reset_executor_client = self.create_client(
            Trigger,
            '/reset_coverage_follow_path',
        )

        self.start_cleaning_service = self.create_service(
            Trigger,
            '/manager/start_cleaning',
            self._start_cleaning_callback,
        )
        self.stop_cleaning_service = self.create_service(
            Trigger,
            '/manager/stop_cleaning',
            self._stop_cleaning_callback,
        )
        self.pause_cleaning_service = self.create_service(
            Trigger,
            '/manager/pause_cleaning',
            self._pause_cleaning_callback,
        )
        self.resume_cleaning_service = self.create_service(
            Trigger,
            '/manager/resume_cleaning',
            self._resume_cleaning_callback,
        )
        self.return_to_dock_service = self.create_service(
            Trigger,
            '/manager/return_to_dock',
            self._return_to_dock_callback,
        )

        self.status_timer = self.create_timer(1.0, self.publish_status)
        self.get_logger().info(
            'Coverage manager started: executor_status=%s selection=%s status=%s'
            % (
                self.executor_status_topic,
                self.selection_topic,
                self.status_topic,
            )
        )

    def _selection_callback(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.last_warning = 'Ignoring invalid coverage selection JSON'
            return

        self.selection = {
            'selection_id': payload.get('selection_id'),
            'room_ids': payload.get('room_ids', []),
            'zones': payload.get('zones', []),
            'no_go_zones': payload.get('no_go_zones', []),
        }
        self.publish_status()

    def _map_callback(self, _msg: OccupancyGrid) -> None:
        self.map_available = True

    def _coverage_percentage_callback(self, msg: Float32) -> None:
        self.coverage_percent = float(msg.data)

    def _coverage_stats_callback(self, msg: String) -> None:
        self.coverage_stats = msg.data

    def _dynamic_status_callback(self, msg: String) -> None:
        self.dynamic_status = msg.data

    def _executor_status_callback(self, msg: String) -> None:
        self.execution_status = msg.data.strip()

        if self.execution_status == 'EXECUTING':
            self.state = 'cleaning'
            self.last_error = None
            self.pause_requested = False
        elif self.execution_status == 'SKIPPING_DYNAMIC_OBSTACLE':
            self.state = 'cleaning'
            self.last_warning = msg.data.strip()
        elif self.execution_status == 'SUCCEEDED':
            self.state = 'idle'
            self.paused_context = None
            self.pause_requested = False
            self.last_error = None
        elif self.execution_status == 'COMPLETED_WITH_SKIPS':
            self.state = 'idle'
            self.paused_context = None
            self.pause_requested = False
            self.last_warning = 'Cleaning completed with skipped segments'
        elif self.execution_status == 'FAILED':
            self.state = 'error'
            self.pause_requested = False
            self.last_error = 'Coverage execution failed'
        elif self.execution_status == 'BLOCKED_DYNAMIC_OBJECT':
            self.state = 'error'
            self.pause_requested = False
            self.last_error = 'Coverage blocked by a dynamic obstacle'
        elif self.execution_status == 'CANCELED':
            if self.pause_requested:
                self.state = 'paused'
                self.paused_context = {
                    'paused_at': datetime.now(timezone.utc).isoformat(),
                    'coverage_percent': self.coverage_percent,
                }
                self.pause_requested = False
            else:
                self.state = 'idle'
                self.paused_context = None
        elif self.execution_status == 'WAITING_FOR_PATH' and self.state == 'idle':
            self.last_error = None
        self.publish_status()

    def _start_cleaning_callback(self, _request, response):
        if self.state not in {'idle', 'charging'}:
            response.success = False
            response.message = f'Cannot start cleaning while state={self.state}'
            return response
        if not self.map_available:
            response.success = False
            response.message = 'Cannot start cleaning before /map is available'
            return response

        validation = self._call_trigger(self.validate_executor_client)
        if not validation['success']:
            response.success = False
            response.message = validation['message']
            return response

        start_result = self._call_trigger(self.start_executor_client)
        response.success = start_result['success']
        response.message = start_result['message']
        if start_result['success']:
            self.state = 'cleaning'
            self.last_error = None
            self.pause_requested = False
        return response

    def _stop_cleaning_callback(self, _request, response):
        if self.state not in {'cleaning', 'paused', 'error'}:
            response.success = False
            response.message = f'Cannot stop cleaning while state={self.state}'
            return response

        if self.state == 'paused':
            reset_result = self._call_trigger(self.reset_executor_client)
            response.success = reset_result['success']
            response.message = reset_result['message']
            if reset_result['success']:
                self.state = 'idle'
                self.paused_context = None
                self.last_error = None
            return response

        cancel_result = self._call_trigger(self.cancel_executor_client)
        response.success = cancel_result['success']
        response.message = cancel_result['message']
        if cancel_result['success']:
            self.state = 'idle'
            self.paused_context = None
            self.pause_requested = False
        return response

    def _pause_cleaning_callback(self, _request, response):
        if self.state != 'cleaning':
            response.success = False
            response.message = f'Cannot pause cleaning while state={self.state}'
            return response

        cancel_result = self._call_trigger(self.cancel_executor_client)
        response.success = cancel_result['success']
        response.message = cancel_result['message']
        if cancel_result['success']:
            self.pause_requested = True
            self.state = 'paused'
            self.paused_context = {
                'paused_at': datetime.now(timezone.utc).isoformat(),
                'coverage_percent': self.coverage_percent,
            }
        return response

    def _resume_cleaning_callback(self, _request, response):
        if self.state != 'paused':
            response.success = False
            response.message = f'Cannot resume cleaning while state={self.state}'
            return response

        start_result = self._call_trigger(self.start_executor_client)
        response.success = start_result['success']
        response.message = start_result['message']
        if start_result['success']:
            self.state = 'cleaning'
            self.pause_requested = False
        return response

    def _return_to_dock_callback(self, _request, response):
        response.success = False
        response.message = (
            'Return to dock is still a planned simulation-first feature and is '
            'not automated in the current stack.'
        )
        return response

    def _call_trigger(self, client) -> dict:
        if not client.wait_for_service(timeout_sec=1.0):
            return {'success': False, 'message': 'Required executor service is unavailable'}

        event = threading.Event()
        result = {'success': False, 'message': 'Service call timed out'}
        future = client.call_async(Trigger.Request())

        def done_callback(done_future):
            nonlocal result
            try:
                response = done_future.result()
                result = {
                    'success': bool(response.success),
                    'message': response.message,
                }
            except Exception as exc:  # pragma: no cover - defensive runtime logging
                result = {'success': False, 'message': str(exc)}
            finally:
                event.set()

        future.add_done_callback(done_callback)
        event.wait(timeout=5.0)
        return result

    def _allowed_commands(self) -> list[str]:
        if self.state == 'idle':
            return ['start_cleaning']
        if self.state == 'cleaning':
            return ['pause_cleaning', 'stop_cleaning']
        if self.state == 'paused':
            return ['resume_cleaning', 'stop_cleaning']
        if self.state == 'error':
            return ['stop_cleaning']
        return []

    def publish_status(self) -> None:
        payload = {
            'state': self.state,
            'mode': self.mode,
            'execution_status': self.execution_status,
            'coverage_percent': self.coverage_percent,
            'coverage_stats': self.coverage_stats,
            'dynamic_status': self.dynamic_status,
            'selection': self.selection,
            'map_available': self.map_available,
            'paused_context': self.paused_context,
            'errors': [self.last_error] if self.last_error else [],
            'warnings': [self.last_warning] if self.last_warning else [],
            'allowed_commands': self._allowed_commands(),
        }
        message = String()
        message.data = json.dumps(payload)
        self.status_pub.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = CoverageManagerNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

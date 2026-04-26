#!/usr/bin/env python3
"""Execute the published coverage path directly with Nav2 FollowPath."""

import copy
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point
from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.exceptions import ParameterAlreadyDeclaredException
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray


class CoverageFollowPathExecutorNode(Node):
    """Send the latest coverage Path to Nav2 without waypoint conversion."""

    STATUS_IDLE = 'IDLE'
    STATUS_WAITING_FOR_PATH = 'WAITING_FOR_PATH'
    STATUS_WAITING_FOR_NAV2 = 'WAITING_FOR_NAV2'
    STATUS_EXECUTING = 'EXECUTING'
    STATUS_SUCCEEDED = 'SUCCEEDED'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_TF_ERROR = 'TF_ERROR'
    STATUS_INVALID_PATH_LOCAL = 'INVALID_PATH_LOCAL'
    STATUS_START_TOO_FAR = 'START_TOO_FAR'
    STATUS_ROBOT_TOO_FAR_FROM_PATH = 'ROBOT_TOO_FAR_FROM_PATH'

    FOLLOW_PATH_ERROR_CODES = {
        0: 'NONE',
        100: 'UNKNOWN',
        101: 'INVALID_CONTROLLER',
        102: 'TF_ERROR',
        103: 'INVALID_PATH',
        104: 'PATIENCE_EXCEEDED',
        105: 'FAILED_TO_MAKE_PROGRESS',
        106: 'NO_VALID_CONTROL',
    }

    def __init__(self):
        super().__init__('coverage_follow_path_executor_node')

        self._declare_parameter_if_needed('use_sim_time', True)
        self._declare_parameter_if_needed('coverage_path_topic', '/coverage_path')
        self._declare_parameter_if_needed('active_path_topic', '/coverage_active_path')
        self._declare_parameter_if_needed(
            'execution_status_topic',
            '/coverage_execution_status',
        )
        self._declare_parameter_if_needed(
            'nav2_feedback_topic',
            '/coverage_nav2_feedback',
        )
        self._declare_parameter_if_needed(
            'path_markers_topic',
            '/coverage_path_markers',
        )
        self._declare_parameter_if_needed('follow_path_action_name', '/follow_path')
        self._declare_parameter_if_needed('controller_id', 'FollowPath')
        self._declare_parameter_if_needed('goal_checker_id', '')
        self._declare_parameter_if_needed('progress_checker_id', '')
        self._declare_parameter_if_needed('auto_start', False)
        self._declare_parameter_if_needed('execute_once_on_first_path', False)
        self._declare_parameter_if_needed('min_path_poses', 2)
        self._declare_parameter_if_needed('wait_for_nav2_timeout_sec', 10.0)
        self._declare_parameter_if_needed('action_result_timeout_sec', 0.0)
        self._declare_parameter_if_needed('republish_active_path_hz', 1.0)
        self._declare_parameter_if_needed('allow_new_path_while_executing', False)
        self._declare_parameter_if_needed('robot_base_frame', 'base_link')
        self._declare_parameter_if_needed('tf_lookup_timeout_sec', 1.0)
        self._declare_parameter_if_needed('require_robot_near_start', True)
        self._declare_parameter_if_needed('max_start_distance_m', 0.50)
        self._declare_parameter_if_needed('max_nearest_path_distance_m', 0.50)
        self._declare_parameter_if_needed('minimum_path_length_m', 0.10)
        self._declare_parameter_if_needed('max_consecutive_pose_jump_m', 1.00)
        self._declare_parameter_if_needed('debug_info_topic', '/coverage_debug_info')
        self._declare_parameter_if_needed(
            'debug_markers_topic',
            '/coverage_debug_markers',
        )
        self._declare_parameter_if_needed('auto_restart_on_failed_progress', False)
        self._declare_parameter_if_needed('failed_progress_restart_delay_sec', 1.0)
        self._declare_parameter_if_needed('max_failed_progress_restarts', 3)

        self.coverage_path_topic = self._string_param('coverage_path_topic')
        self.active_path_topic = self._string_param('active_path_topic')
        self.execution_status_topic = self._string_param('execution_status_topic')
        self.nav2_feedback_topic = self._string_param('nav2_feedback_topic')
        self.path_markers_topic = self._string_param('path_markers_topic')
        self.follow_path_action_name = self._string_param('follow_path_action_name')
        self.controller_id = self._string_param('controller_id')
        self.goal_checker_id = self._string_param('goal_checker_id')
        self.progress_checker_id = self._string_param('progress_checker_id')
        self.auto_start = self._bool_param('auto_start')
        self.execute_once_on_first_path = self._bool_param(
            'execute_once_on_first_path'
        )
        self.min_path_poses = max(1, self._int_param('min_path_poses'))
        self.wait_for_nav2_timeout_sec = max(
            0.0,
            self._double_param('wait_for_nav2_timeout_sec'),
        )
        self.action_result_timeout_sec = max(
            0.0,
            self._double_param('action_result_timeout_sec'),
        )
        self.republish_active_path_hz = max(
            0.1,
            self._double_param('republish_active_path_hz'),
        )
        self.allow_new_path_while_executing = self._bool_param(
            'allow_new_path_while_executing'
        )
        self.robot_base_frame = self._string_param('robot_base_frame')
        self.tf_lookup_timeout_sec = max(
            0.0,
            self._double_param('tf_lookup_timeout_sec'),
        )
        self.require_robot_near_start = self._bool_param('require_robot_near_start')
        self.max_start_distance_m = max(
            0.0,
            self._double_param('max_start_distance_m'),
        )
        self.max_nearest_path_distance_m = max(
            0.0,
            self._double_param('max_nearest_path_distance_m'),
        )
        self.minimum_path_length_m = max(
            0.0,
            self._double_param('minimum_path_length_m'),
        )
        self.max_consecutive_pose_jump_m = max(
            0.0,
            self._double_param('max_consecutive_pose_jump_m'),
        )
        self.debug_info_topic = self._string_param('debug_info_topic')
        self.debug_markers_topic = self._string_param('debug_markers_topic')
        self.auto_restart_on_failed_progress = self._bool_param(
            'auto_restart_on_failed_progress'
        )
        self.failed_progress_restart_delay_sec = max(
            0.0,
            self._double_param('failed_progress_restart_delay_sec'),
        )
        self.max_failed_progress_restarts = max(
            0,
            self._int_param('max_failed_progress_restarts'),
        )

        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.latest_path = None
        self.latest_path_checksum = None
        self.latest_path_error = 'No coverage path received yet'
        self.active_path = None
        self.pending_start_path = None
        self.pending_start_monotonic = None
        self.pending_start_not_before_monotonic = 0.0
        self.pending_restart_path = None
        self.active_path_checksum = None
        self.current_goal_handle = None
        self.goal_in_flight = False
        self.cancel_requested = False
        self.cancel_reason = ''
        self.cancel_future_in_flight = False
        self.executed_once_on_first_path = False
        self.last_auto_started_checksum = None
        self.execution_start_monotonic = None
        self.last_distance_to_goal = None
        self.last_feedback_text = ''
        self.failed_progress_restart_count = 0
        self.execution_status = self.STATUS_WAITING_FOR_PATH
        self.latest_status_msg = String()
        self.latest_status_msg.data = self.execution_status
        self.latest_validation_report = self._make_empty_validation_report()

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.follow_path_client = ActionClient(
            self,
            FollowPath,
            self.follow_path_action_name,
        )

        self.coverage_path_sub = self.create_subscription(
            Path,
            self.coverage_path_topic,
            self.coverage_path_callback,
            qos,
        )
        self.active_path_pub = self.create_publisher(Path, self.active_path_topic, qos)
        self.execution_status_pub = self.create_publisher(
            String,
            self.execution_status_topic,
            qos,
        )
        self.nav2_feedback_pub = self.create_publisher(
            String,
            self.nav2_feedback_topic,
            qos,
        )
        self.path_markers_pub = self.create_publisher(
            MarkerArray,
            self.path_markers_topic,
            qos,
        )
        self.debug_info_pub = self.create_publisher(
            String,
            self.debug_info_topic,
            qos,
        )
        self.debug_markers_pub = self.create_publisher(
            MarkerArray,
            self.debug_markers_topic,
            qos,
        )

        self.start_service = self.create_service(
            Trigger,
            '/start_coverage_follow_path',
            self.start_service_callback,
        )
        self.cancel_service = self.create_service(
            Trigger,
            '/cancel_coverage_follow_path',
            self.cancel_service_callback,
        )
        self.validate_service = self.create_service(
            Trigger,
            '/validate_coverage_follow_path',
            self.validate_service_callback,
        )

        publish_period = 1.0 / self.republish_active_path_hz
        self.timer = self.create_timer(publish_period, self.timer_callback)

        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self.get_logger().info(
            'Coverage FollowPath executor started: path=%s, active_path=%s, '
            'markers=%s, debug_info=%s, debug_markers=%s, status=%s, '
            'feedback=%s, action=%s, controller_id=%s, robot_base_frame=%s'
            % (
                self.coverage_path_topic,
                self.active_path_topic,
                self.path_markers_topic,
                self.debug_info_topic,
                self.debug_markers_topic,
                self.execution_status_topic,
                self.nav2_feedback_topic,
                self.follow_path_action_name,
                self.controller_id,
                self.robot_base_frame,
            )
        )

    def coverage_path_callback(self, msg):
        """Cache each valid path without changing an active FollowPath goal."""
        validation_error = self._validate_path(msg)
        if validation_error:
            self.latest_path_error = validation_error
            self.get_logger().warn(
                'Ignoring invalid coverage path: %s' % validation_error,
                throttle_duration_sec=5.0,
            )
            if self.latest_path is None and not self.goal_in_flight:
                self._set_status(self.STATUS_WAITING_FOR_PATH)
            return

        checksum = self._path_checksum(msg)
        is_new_path = checksum != self.latest_path_checksum
        self.latest_path = copy.deepcopy(msg)
        self.latest_path_checksum = checksum
        self.latest_path_error = ''

        if is_new_path:
            self._log_path_summary(self.latest_path, 'Cached coverage path')
            if not self.goal_in_flight and self.pending_start_path is None:
                self._set_status(self.STATUS_IDLE)
        elif not self.goal_in_flight and self.pending_start_path is None:
            if self.execution_status == self.STATUS_WAITING_FOR_PATH:
                self._set_status(self.STATUS_IDLE)

        if self.goal_in_flight:
            self.get_logger().info(
                'Received a new coverage path while executing; cached it for a '
                'future explicit start request.',
                throttle_duration_sec=5.0,
            )
            return

        should_start_once = (
            self.execute_once_on_first_path
            and not self.executed_once_on_first_path
        )
        should_auto_start = (
            self.auto_start
            and checksum != self.last_auto_started_checksum
        )

        if should_start_once or should_auto_start:
            if should_start_once:
                self.executed_once_on_first_path = True
            if should_auto_start:
                self.last_auto_started_checksum = checksum
            self._request_execution_from_latest('path_received')

    def start_service_callback(self, request, response):
        """Start FollowPath execution using the latest cached valid path."""
        del request

        if self.latest_path is None:
            self._set_status(self.STATUS_WAITING_FOR_PATH)
            response.success = False
            response.message = self.latest_path_error or 'No valid coverage path cached'
            return response

        if self.goal_in_flight:
            if not self.allow_new_path_while_executing:
                response.success = False
                response.message = (
                    'FollowPath is already executing; cancel first or set '
                    'allow_new_path_while_executing=true'
                )
                return response

            self.pending_restart_path = copy.deepcopy(self.latest_path)
            self._request_cancel('restart_requested')
            response.success = True
            response.message = (
                'Canceling active FollowPath goal; latest coverage path will start '
                'after cancel completes'
            )
            return response

        if self._request_execution_from_latest('service_start'):
            response.success = True
            response.message = 'Coverage FollowPath execution requested'
        else:
            response.success = False
            response.message = self._format_validation_response(
                self.latest_validation_report
            )
        return response

    def cancel_service_callback(self, request, response):
        """Cancel an active or pending FollowPath execution."""
        del request

        if self.pending_start_path is not None and not self.goal_in_flight:
            self.pending_start_path = None
            self.pending_start_monotonic = None
            self.pending_start_not_before_monotonic = 0.0
            self._set_status(self.STATUS_CANCELED)
            response.success = True
            response.message = 'Pending coverage FollowPath execution canceled'
            return response

        if not self.goal_in_flight:
            response.success = False
            response.message = 'No active FollowPath goal to cancel'
            return response

        self.pending_restart_path = None
        self._request_cancel('service_cancel')
        response.success = True
        response.message = 'Cancel request sent to active FollowPath goal'
        return response

    def validate_service_callback(self, request, response):
        """Validate the cached path without sending a FollowPath goal."""
        del request

        report = self._run_preflight_validation(
            self.latest_path,
            publish_debug=True,
        )
        response.success = report['valid']
        response.message = self._format_validation_response(report)
        if report['valid']:
            self.get_logger().info('Coverage FollowPath validation passed')
        else:
            self.get_logger().warn(
                'Coverage FollowPath validation failed: %s' % response.message
            )
        return response

    def timer_callback(self):
        """Republish debug outputs and advance pending action state."""
        self._send_pending_start_if_ready()
        self._enforce_action_result_timeout()

        if self.active_path is not None:
            self.active_path_pub.publish(self.active_path)
            self.path_markers_pub.publish(self._make_path_markers(self.active_path))
        elif self.latest_path is not None:
            self.path_markers_pub.publish(self._make_path_markers(self.latest_path))
        else:
            self.path_markers_pub.publish(self._make_delete_markers('map'))

        self.latest_status_msg.data = self.execution_status
        self.execution_status_pub.publish(self.latest_status_msg)

    def _request_execution_from_latest(self, reason):
        if self.latest_path is None:
            self._set_status(self.STATUS_WAITING_FOR_PATH)
            return False

        path = copy.deepcopy(self.latest_path)
        report = self._run_preflight_validation(path, publish_debug=True)
        if not report['valid']:
            self.latest_path_error = report['reason']
            self._set_status(report['status'])
            self.get_logger().warn(
                'Cannot start FollowPath execution: %s'
                % self._format_validation_response(report)
            )
            return False

        self.pending_start_path = path
        self.pending_start_monotonic = time.monotonic()
        self.pending_start_not_before_monotonic = 0.0
        self._set_status(self.STATUS_WAITING_FOR_NAV2)
        self.get_logger().info(
            'FollowPath execution requested (%s): action=%s'
            % (reason, self.follow_path_action_name)
        )
        self._log_path_summary(path, 'Pending FollowPath path')
        return True

    def _send_pending_start_if_ready(self):
        if self.pending_start_path is None or self.goal_in_flight:
            return

        if time.monotonic() < self.pending_start_not_before_monotonic:
            return

        if not self.follow_path_client.server_is_ready():
            self._set_status(self.STATUS_WAITING_FOR_NAV2)
            elapsed = time.monotonic() - self.pending_start_monotonic
            if (
                self.wait_for_nav2_timeout_sec > 0.0
                and elapsed > self.wait_for_nav2_timeout_sec
            ):
                self.get_logger().warn(
                    'FollowPath action server %s was not available after %.1f seconds'
                    % (self.follow_path_action_name, elapsed)
                )
                self.pending_start_path = None
                self.pending_start_monotonic = None
                self.pending_start_not_before_monotonic = 0.0
                self._set_status(self.STATUS_FAILED)
            return

        path = self.pending_start_path
        self.pending_start_path = None
        self.pending_start_monotonic = None
        self.pending_start_not_before_monotonic = 0.0

        report = self._run_preflight_validation(path, publish_debug=True)
        if not report['valid']:
            self.latest_path_error = report['reason']
            self._set_status(report['status'])
            self.get_logger().warn(
                'FollowPath preflight failed before send: %s'
                % self._format_validation_response(report)
            )
            return

        self._send_follow_path_goal(path)

    def _send_follow_path_goal(self, path):
        goal_msg = FollowPath.Goal()
        goal_msg.path = copy.deepcopy(path)
        goal_msg.controller_id = self.controller_id
        goal_msg.goal_checker_id = self.goal_checker_id
        goal_msg.progress_checker_id = self.progress_checker_id

        self.active_path = copy.deepcopy(path)
        self.active_path_checksum = self._path_checksum(path)
        self.current_goal_handle = None
        self.goal_in_flight = True
        self.cancel_requested = False
        self.cancel_reason = ''
        self.cancel_future_in_flight = False
        self.execution_start_monotonic = time.monotonic()
        self.last_distance_to_goal = None
        self.last_feedback_text = ''

        self._set_status(self.STATUS_EXECUTING)
        self._log_path_summary(path, 'Sending FollowPath goal')
        self.get_logger().info(
            'FollowPath goal details: action_server=%s controller_id=%s '
            'goal_checker_id=%s progress_checker_id=%s'
            % (
                self.follow_path_action_name,
                self.controller_id,
                self.goal_checker_id,
                self.progress_checker_id,
            )
        )

        send_goal_future = self.follow_path_client.send_goal_async(
            goal_msg,
            feedback_callback=self._follow_path_feedback_callback,
        )
        send_goal_future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.get_logger().error('FollowPath goal response failed: %s' % exc)
            self._finish_execution(self.STATUS_FAILED)
            return

        if not goal_handle.accepted:
            self.get_logger().warn('FollowPath goal was rejected by Nav2')
            self._finish_execution(self.STATUS_FAILED)
            return

        self.current_goal_handle = goal_handle
        self.get_logger().info('FollowPath goal accepted by Nav2')

        if self.cancel_requested:
            self._send_cancel_request()

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_callback)

    def _result_callback(self, future):
        try:
            wrapped_result = future.result()
        except Exception as exc:
            self.get_logger().error('FollowPath result failed: %s' % exc)
            self._finish_execution(self.STATUS_FAILED)
            return

        result = wrapped_result.result
        status = wrapped_result.status
        error_code = getattr(result, 'error_code', 0)
        error_label = self._follow_path_error_label(error_code)
        error_msg = getattr(result, 'error_msg', '')
        if not error_msg:
            error_msg = 'status=%d error_code=%s %s' % (
                status,
                error_code,
                error_label,
            )

        self.get_logger().info(
            'FollowPath result: status=%d error_code=%s %s error_msg=%s'
            % (status, error_code, error_label, error_msg)
        )

        if self.pending_restart_path is not None:
            restart_path = self.pending_restart_path
            self.pending_restart_path = None
            self.goal_in_flight = False
            self.current_goal_handle = None
            self.cancel_requested = False
            self.cancel_future_in_flight = False
            self.pending_start_path = copy.deepcopy(restart_path)
            self.pending_start_monotonic = time.monotonic()
            self._set_status(self.STATUS_WAITING_FOR_NAV2)
            return

        if self.cancel_reason == 'action_result_timeout':
            self._finish_execution(self.STATUS_FAILED)
            return

        if status == GoalStatus.STATUS_SUCCEEDED and error_code == 0:
            self._finish_execution(self.STATUS_SUCCEEDED)
        elif status == GoalStatus.STATUS_CANCELED or self.cancel_requested:
            self._finish_execution(self.STATUS_CANCELED)
        else:
            self.get_logger().warn(
                'FollowPath failed with error_code=%s %s error_msg=%s'
                % (error_code, error_label, error_msg)
            )
            if error_code == 103:
                self.get_logger().warn(
                    'FollowPath INVALID_PATH likely causes: robot too far from '
                    'path start; path frame mismatch; TF unavailable; malformed '
                    'path; path crosses obstacle or invalid costmap area; '
                    'controller cannot prune/transform the path.'
                )
            if error_code == 105 and self._queue_replanned_path_after_failed_progress():
                return
            self._finish_execution(self.STATUS_FAILED)

    def _follow_path_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        fields = self._feedback_fields(feedback)

        distance_to_goal = getattr(feedback, 'distance_to_goal', None)
        if distance_to_goal is not None and math.isfinite(distance_to_goal):
            self.last_distance_to_goal = float(distance_to_goal)

        if not fields:
            fields.append('feedback_received=true')
        if self.execution_start_monotonic is not None:
            elapsed = time.monotonic() - self.execution_start_monotonic
            fields.append('elapsed=%.1f' % elapsed)

        msg = String()
        msg.data = ' '.join(fields)
        self.last_feedback_text = msg.data
        self.nav2_feedback_pub.publish(msg)

    def _request_cancel(self, reason):
        self.cancel_requested = True
        self.cancel_reason = reason
        self.get_logger().info('Canceling FollowPath goal: reason=%s' % reason)
        self._send_cancel_request()

    def _send_cancel_request(self):
        if self.current_goal_handle is None or self.cancel_future_in_flight:
            return

        try:
            cancel_future = self.current_goal_handle.cancel_goal_async()
        except Exception as exc:
            self.get_logger().warn('Failed to send FollowPath cancel request: %s' % exc)
            self._finish_execution(self.STATUS_FAILED)
            return

        self.cancel_future_in_flight = True
        cancel_future.add_done_callback(self._cancel_done_callback)

    def _cancel_done_callback(self, future):
        self.cancel_future_in_flight = False
        try:
            cancel_response = future.result()
        except Exception as exc:
            self.get_logger().warn('FollowPath cancel response failed: %s' % exc)
            return

        canceling = len(getattr(cancel_response, 'goals_canceling', []))
        self.get_logger().info(
            'FollowPath cancel response received: goals_canceling=%d' % canceling
        )

    def _enforce_action_result_timeout(self):
        if (
            not self.goal_in_flight
            or self.action_result_timeout_sec <= 0.0
            or self.execution_start_monotonic is None
            or self.cancel_requested
        ):
            return

        elapsed = time.monotonic() - self.execution_start_monotonic
        if elapsed <= self.action_result_timeout_sec:
            return

        self.get_logger().warn(
            'FollowPath action result timeout after %.1f seconds; canceling goal'
            % elapsed
        )
        self._request_cancel('action_result_timeout')

    def _finish_execution(self, status):
        self.goal_in_flight = False
        self.current_goal_handle = None
        self.cancel_requested = False
        self.cancel_reason = ''
        self.cancel_future_in_flight = False
        self.execution_start_monotonic = None
        if status == self.STATUS_SUCCEEDED:
            self.failed_progress_restart_count = 0
        self._set_status(status)

    def _queue_replanned_path_after_failed_progress(self):
        if not self.auto_restart_on_failed_progress:
            return False
        if self.failed_progress_restart_count >= self.max_failed_progress_restarts:
            self.get_logger().warn(
                'Not restarting after FAILED_TO_MAKE_PROGRESS: restart limit %d reached'
                % self.max_failed_progress_restarts
            )
            return False
        if self.latest_path is None:
            return False
        if self.latest_path_checksum == self.active_path_checksum:
            self.get_logger().warn(
                'Not restarting after FAILED_TO_MAKE_PROGRESS: no newer replanned '
                'coverage path is available'
            )
            return False

        self.failed_progress_restart_count += 1
        self.goal_in_flight = False
        self.current_goal_handle = None
        self.cancel_requested = False
        self.cancel_reason = ''
        self.cancel_future_in_flight = False
        self.execution_start_monotonic = None
        self.pending_start_path = copy.deepcopy(self.latest_path)
        self.pending_start_monotonic = time.monotonic()
        self.pending_start_not_before_monotonic = (
            time.monotonic() + self.failed_progress_restart_delay_sec
        )
        self._set_status(self.STATUS_WAITING_FOR_NAV2)
        self.get_logger().warn(
            'FAILED_TO_MAKE_PROGRESS: queued newer replanned coverage path '
            'restart attempt %d/%d after %.1fs'
            % (
                self.failed_progress_restart_count,
                self.max_failed_progress_restarts,
                self.failed_progress_restart_delay_sec,
            )
        )
        return True

    def _run_preflight_validation(self, path_msg, publish_debug=False):
        report = self._make_empty_validation_report()

        if path_msg is None:
            report['status'] = self.STATUS_WAITING_FOR_PATH
            report['reason'] = 'no_cached_path'
            self._publish_validation_debug(report, publish_debug)
            return report

        report['pose_count'] = len(path_msg.poses)
        report['frame_id'] = path_msg.header.frame_id.strip()

        local_error = self._validate_path(path_msg)
        if local_error:
            report['status'] = self.STATUS_INVALID_PATH_LOCAL
            report['reason'] = local_error
            self._fill_path_debug_fields(report, path_msg)
            self._publish_validation_debug(report, publish_debug)
            return report

        self._fill_path_debug_fields(report, path_msg)

        path_length = self._path_length(path_msg)
        max_jump, max_jump_index = self._max_consecutive_pose_jump_info(path_msg)
        report['path_length'] = path_length
        report['max_consecutive_pose_jump'] = max_jump
        report['max_jump_index'] = max_jump_index
        self._fill_jump_debug_fields(report, path_msg)

        if path_length <= self.minimum_path_length_m:
            report['status'] = self.STATUS_INVALID_PATH_LOCAL
            report['reason'] = (
                'path_length=%.3f is not greater than minimum_path_length_m=%.3f'
                % (path_length, self.minimum_path_length_m)
            )
            self._publish_validation_debug(report, publish_debug)
            return report

        if max_jump > self.max_consecutive_pose_jump_m:
            report['status'] = self.STATUS_INVALID_PATH_LOCAL
            report['reason'] = (
                'max_consecutive_pose_jump=%.3f exceeds limit=%.3f at index=%d'
                % (max_jump, self.max_consecutive_pose_jump_m, max_jump_index)
            )
            self.get_logger().warn(
                'Coverage path jump diagnostic: %s'
                % self._format_jump_debug(report)
            )
            self._publish_validation_debug(report, publish_debug)
            return report

        robot_pose = self._lookup_robot_pose(path_msg.header.frame_id)
        if robot_pose is None:
            report['status'] = self.STATUS_TF_ERROR
            report['reason'] = (
                'could not lookup TF %s -> %s'
                % (path_msg.header.frame_id, self.robot_base_frame)
            )
            self._publish_validation_debug(report, publish_debug)
            return report

        report['robot_pose'] = robot_pose
        first_pose = path_msg.poses[0].pose
        distance_to_first = self._point_distance_2d(
            robot_pose['x'],
            robot_pose['y'],
            first_pose.position.x,
            first_pose.position.y,
        )
        nearest_index, nearest_distance = self._nearest_path_pose(
            path_msg,
            robot_pose['x'],
            robot_pose['y'],
        )

        report['distance_to_first'] = distance_to_first
        report['nearest_index'] = nearest_index
        report['distance_to_nearest'] = nearest_distance
        if nearest_index >= 0:
            report['nearest_pose'] = self._pose_debug_dict(
                path_msg.poses[nearest_index].pose
            )

        if (
            self.require_robot_near_start
            and distance_to_first > self.max_start_distance_m
        ):
            report['status'] = self.STATUS_START_TOO_FAR
            report['reason'] = (
                'distance_to_first=%.3f exceeds max_start_distance_m=%.3f'
                % (distance_to_first, self.max_start_distance_m)
            )
            self._publish_validation_debug(report, publish_debug)
            return report

        if nearest_distance > self.max_nearest_path_distance_m:
            report['status'] = self.STATUS_ROBOT_TOO_FAR_FROM_PATH
            report['reason'] = (
                'distance_to_nearest=%.3f exceeds max_nearest_path_distance_m=%.3f'
                % (nearest_distance, self.max_nearest_path_distance_m)
            )
            self._publish_validation_debug(report, publish_debug)
            return report

        report['valid'] = True
        report['status'] = 'VALID'
        report['reason'] = 'ok'
        self._publish_validation_debug(report, publish_debug)
        return report

    def _make_empty_validation_report(self):
        return {
            'valid': False,
            'status': self.STATUS_WAITING_FOR_PATH,
            'reason': 'not_run',
            'frame_id': '',
            'pose_count': 0,
            'robot_pose': None,
            'first_pose': None,
            'last_pose': None,
            'nearest_pose': None,
            'nearest_index': -1,
            'distance_to_first': float('nan'),
            'distance_to_nearest': float('nan'),
            'path_length': 0.0,
            'max_consecutive_pose_jump': 0.0,
            'max_jump_index': -1,
            'max_jump_start_pose': None,
            'max_jump_end_pose': None,
        }

    def _fill_path_debug_fields(self, report, path_msg):
        if not path_msg.poses:
            return

        report['first_pose'] = self._pose_debug_dict(path_msg.poses[0].pose)
        report['last_pose'] = self._pose_debug_dict(path_msg.poses[-1].pose)
        report['path_length'] = self._path_length(path_msg)
        max_jump, max_jump_index = self._max_consecutive_pose_jump_info(path_msg)
        report['max_consecutive_pose_jump'] = max_jump
        report['max_jump_index'] = max_jump_index
        self._fill_jump_debug_fields(report, path_msg)

    def _fill_jump_debug_fields(self, report, path_msg):
        index = report['max_jump_index']
        if index < 0 or index + 1 >= len(path_msg.poses):
            return

        report['max_jump_start_pose'] = self._pose_debug_dict(
            path_msg.poses[index].pose
        )
        report['max_jump_end_pose'] = self._pose_debug_dict(
            path_msg.poses[index + 1].pose
        )

    def _lookup_robot_pose(self, path_frame):
        try:
            transform = self.tf_buffer.lookup_transform(
                path_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=self.tf_lookup_timeout_sec),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not lookup TF %s -> %s: %s'
                % (path_frame, self.robot_base_frame, exc),
                throttle_duration_sec=2.0,
            )
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        return {
            'x': translation.x,
            'y': translation.y,
            'yaw': self._yaw_from_quaternion(rotation),
        }

    def _publish_validation_debug(self, report, publish_debug):
        self.latest_validation_report = report
        if not publish_debug:
            return

        info_msg = String()
        info_msg.data = self._format_validation_response(report)
        self.debug_info_pub.publish(info_msg)
        self.debug_markers_pub.publish(self._make_debug_markers(report))

    def _format_validation_response(self, report):
        return (
            'validation=%s status=%s reason=%s robot=%s first=%s last=%s '
            'distance_to_first=%s nearest_index=%d distance_to_nearest=%s '
            'path_length=%.3f max_consecutive_pose_jump=%.3f '
            'max_jump_index=%d jump_start=%s jump_end=%s '
            'jump_distance_m=%.3f total_poses=%d path_length_m=%.3f'
            % (
                'PASS' if report['valid'] else 'FAIL',
                report['status'],
                report['reason'],
                self._format_debug_pose(report['robot_pose']),
                self._format_debug_pose(report['first_pose']),
                self._format_debug_pose(report['last_pose']),
                self._format_float(report['distance_to_first']),
                report['nearest_index'],
                self._format_float(report['distance_to_nearest']),
                report['path_length'],
                report['max_consecutive_pose_jump'],
                report['max_jump_index'],
                self._format_debug_pose(report['max_jump_start_pose']),
                self._format_debug_pose(report['max_jump_end_pose']),
                report['max_consecutive_pose_jump'],
                report['pose_count'],
                report['path_length'],
            )
        )

    def _format_jump_debug(self, report):
        return (
            'max_jump_index=%d pose[%d]=%s pose[%d]=%s jump_distance_m=%.3f '
            'total_poses=%d path_length_m=%.3f'
            % (
                report['max_jump_index'],
                report['max_jump_index'],
                self._format_debug_pose(report['max_jump_start_pose']),
                report['max_jump_index'] + 1,
                self._format_debug_pose(report['max_jump_end_pose']),
                report['max_consecutive_pose_jump'],
                report['pose_count'],
                report['path_length'],
            )
        )

    def _make_debug_markers(self, report):
        frame_id = report['frame_id'] or 'map'
        markers = self._make_debug_delete_markers(frame_id)
        stamp = self.get_clock().now().to_msg()

        robot_pose = report['robot_pose']
        first_pose = report['first_pose']
        last_pose = report['last_pose']
        nearest_pose = report['nearest_pose']
        jump_start_pose = report['max_jump_start_pose']
        jump_end_pose = report['max_jump_end_pose']

        marker_id = 1
        if robot_pose is not None:
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_robot_pose',
                    robot_pose,
                    Marker.ARROW,
                    (0.1, 0.35, 1.0, 0.95),
                    0.28,
                )
            )
            marker_id += 1

        if first_pose is not None:
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_first_path_pose',
                    first_pose,
                    Marker.SPHERE,
                    (0.0, 0.9, 0.2, 0.95),
                    0.18,
                )
            )
            marker_id += 1

        if last_pose is not None:
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_last_path_pose',
                    last_pose,
                    Marker.CUBE,
                    (1.0, 0.15, 0.05, 0.95),
                    0.18,
                )
            )
            marker_id += 1

        if nearest_pose is not None:
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_nearest_path_pose',
                    nearest_pose,
                    Marker.SPHERE,
                    (1.0, 0.85, 0.0, 0.95),
                    0.16,
                )
            )
            marker_id += 1

        if robot_pose is not None and first_pose is not None:
            markers.markers.append(
                self._make_debug_line_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_robot_to_first',
                    robot_pose,
                    first_pose,
                    (0.0, 0.9, 0.2, 0.9),
                )
            )
            marker_id += 1

        if robot_pose is not None and nearest_pose is not None:
            markers.markers.append(
                self._make_debug_line_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_robot_to_nearest',
                    robot_pose,
                    nearest_pose,
                    (1.0, 0.85, 0.0, 0.9),
                )
            )
            marker_id += 1

        if jump_start_pose is not None and jump_end_pose is not None:
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_jump_start',
                    jump_start_pose,
                    Marker.SPHERE,
                    (1.0, 0.0, 0.0, 0.95),
                    0.20,
                )
            )
            marker_id += 1
            markers.markers.append(
                self._make_debug_point_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_jump_end',
                    jump_end_pose,
                    Marker.CUBE,
                    (1.0, 0.0, 0.0, 0.95),
                    0.20,
                )
            )
            marker_id += 1
            markers.markers.append(
                self._make_debug_line_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_jump_line',
                    jump_start_pose,
                    jump_end_pose,
                    (1.0, 0.0, 0.0, 0.95),
                )
            )
            marker_id += 1

            jump_label = Marker()
            jump_label.header.frame_id = frame_id
            jump_label.header.stamp = stamp
            jump_label.ns = 'coverage_debug_jump_text'
            jump_label.id = marker_id
            jump_label.type = Marker.TEXT_VIEW_FACING
            jump_label.action = Marker.ADD
            jump_label.pose.position.x = (
                jump_start_pose['x'] + jump_end_pose['x']
            ) * 0.5
            jump_label.pose.position.y = (
                jump_start_pose['y'] + jump_end_pose['y']
            ) * 0.5
            jump_label.pose.position.z = 0.42
            jump_label.pose.orientation.w = 1.0
            jump_label.scale.z = 0.18
            jump_label.color.r = 1.0
            jump_label.color.g = 0.0
            jump_label.color.b = 0.0
            jump_label.color.a = 0.95
            jump_label.text = 'JUMP %.2fm at index %d' % (
                report['max_consecutive_pose_jump'],
                report['max_jump_index'],
            )
            markers.markers.append(jump_label)
            marker_id += 1

        label_pose = robot_pose or first_pose or last_pose
        if label_pose is not None:
            label = Marker()
            label.header.frame_id = frame_id
            label.header.stamp = stamp
            label.ns = 'coverage_debug_validation_text'
            label.id = marker_id
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position.x = label_pose['x']
            label.pose.position.y = label_pose['y']
            label.pose.position.z = 0.55
            label.pose.orientation.w = 1.0
            label.scale.z = 0.18
            if report['valid']:
                label.color.r = 0.0
                label.color.g = 1.0
                label.color.b = 0.25
            else:
                label.color.r = 1.0
                label.color.g = 0.2
                label.color.b = 0.1
            label.color.a = 0.95
            label.text = (
                '%s\nfirst=%s nearest=%s idx=%d\njump=%s at %d\n%s'
                % (
                    report['status'],
                    self._format_float(report['distance_to_first']),
                    self._format_float(report['distance_to_nearest']),
                    report['nearest_index'],
                    self._format_float(report['max_consecutive_pose_jump']),
                    report['max_jump_index'],
                    report['reason'],
                )
            )
            markers.markers.append(label)

        return markers

    def _make_debug_delete_markers(self, frame_id):
        marker = Marker()
        marker.header.frame_id = frame_id or 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'coverage_debug_cleanup'
        marker.id = 0
        marker.action = Marker.DELETEALL
        markers = MarkerArray()
        markers.markers.append(marker)
        return markers

    def _make_debug_point_marker(
        self,
        frame_id,
        stamp,
        marker_id,
        namespace,
        pose_dict,
        marker_type,
        rgba,
        scale,
    ):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = stamp
        marker.ns = namespace
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.position.x = pose_dict['x']
        marker.pose.position.y = pose_dict['y']
        marker.pose.position.z = 0.12
        marker.pose.orientation.z = math.sin(pose_dict['yaw'] * 0.5)
        marker.pose.orientation.w = math.cos(pose_dict['yaw'] * 0.5)
        marker.scale.x = scale
        marker.scale.y = scale * 0.45 if marker_type == Marker.ARROW else scale
        marker.scale.z = scale * 0.45 if marker_type == Marker.ARROW else scale
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]
        return marker

    def _make_debug_line_marker(
        self,
        frame_id,
        stamp,
        marker_id,
        namespace,
        start_pose,
        end_pose,
        rgba,
    ):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = stamp
        marker.ns = namespace
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x = 0.025
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]

        start_point = Point()
        start_point.x = start_pose['x']
        start_point.y = start_pose['y']
        start_point.z = 0.08
        end_point = Point()
        end_point.x = end_pose['x']
        end_point.y = end_pose['y']
        end_point.z = 0.08
        marker.points = [start_point, end_point]
        return marker

    def _pose_debug_dict(self, pose):
        return {
            'x': pose.position.x,
            'y': pose.position.y,
            'yaw': self._yaw_from_quaternion(pose.orientation),
        }

    def _format_debug_pose(self, pose_dict):
        if pose_dict is None:
            return '(unavailable)'
        return '(x=%.3f y=%.3f yaw=%.2f)' % (
            pose_dict['x'],
            pose_dict['y'],
            pose_dict['yaw'],
        )

    def _format_float(self, value):
        if value is None or not math.isfinite(value):
            return 'unavailable'
        return '%.3f' % value

    def _nearest_path_pose(self, path_msg, x, y):
        nearest_index = -1
        nearest_distance = float('inf')
        for index, pose_stamped in enumerate(path_msg.poses):
            position = pose_stamped.pose.position
            distance = self._point_distance_2d(
                x,
                y,
                position.x,
                position.y,
            )
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_index = index
        return nearest_index, nearest_distance

    def _max_consecutive_pose_jump_info(self, path_msg):
        max_jump = 0.0
        max_jump_index = -1
        poses = path_msg.poses
        for index in range(1, len(poses)):
            previous = poses[index - 1].pose.position
            current = poses[index].pose.position
            jump = self._point_distance_3d(
                previous.x,
                previous.y,
                previous.z,
                current.x,
                current.y,
                current.z,
            )
            if jump > max_jump:
                max_jump = jump
                max_jump_index = index - 1
        return max_jump, max_jump_index

    def _point_distance_2d(self, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    def _point_distance_3d(self, x1, y1, z1, x2, y2, z2):
        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _follow_path_error_label(self, error_code):
        return self.FOLLOW_PATH_ERROR_CODES.get(error_code, 'UNRECOGNIZED')

    def _validate_path(self, path_msg):
        frame_id = path_msg.header.frame_id.strip()
        if not frame_id:
            return 'missing header.frame_id'

        pose_count = len(path_msg.poses)
        if pose_count < self.min_path_poses:
            return 'pose_count=%d is below min_path_poses=%d' % (
                pose_count,
                self.min_path_poses,
            )

        for index, pose_stamped in enumerate(path_msg.poses):
            position = pose_stamped.pose.position
            orientation = pose_stamped.pose.orientation
            if not all(
                math.isfinite(value)
                for value in (position.x, position.y, position.z)
            ):
                return 'pose[%d] has NaN or infinite position' % index
            if not all(
                math.isfinite(value)
                for value in (
                    orientation.x,
                    orientation.y,
                    orientation.z,
                    orientation.w,
                )
            ):
                return 'pose[%d] has NaN or infinite orientation' % index

            quaternion_norm = math.sqrt(
                orientation.x * orientation.x
                + orientation.y * orientation.y
                + orientation.z * orientation.z
                + orientation.w * orientation.w
            )
            if not math.isfinite(quaternion_norm) or quaternion_norm < 1.0e-3:
                return 'pose[%d] has invalid quaternion norm=%.6f' % (
                    index,
                    quaternion_norm,
                )

        return ''

    def _path_checksum(self, path_msg):
        values = [path_msg.header.frame_id, len(path_msg.poses)]
        for pose_stamped in path_msg.poses:
            pose = pose_stamped.pose
            values.extend(
                [
                    round(pose.position.x, 6),
                    round(pose.position.y, 6),
                    round(pose.position.z, 6),
                    round(pose.orientation.x, 6),
                    round(pose.orientation.y, 6),
                    round(pose.orientation.z, 6),
                    round(pose.orientation.w, 6),
                ]
            )
        return tuple(values)

    def _log_path_summary(self, path_msg, prefix):
        first_pose = path_msg.poses[0].pose
        last_pose = path_msg.poses[-1].pose
        self.get_logger().info(
            '%s: poses=%d frame_id=%s length=%.2fm first=%s last=%s'
            % (
                prefix,
                len(path_msg.poses),
                path_msg.header.frame_id,
                self._path_length(path_msg),
                self._format_pose(first_pose),
                self._format_pose(last_pose),
            )
        )

    def _path_length(self, path_msg):
        total = 0.0
        poses = path_msg.poses
        for index in range(1, len(poses)):
            current = poses[index].pose.position
            previous = poses[index - 1].pose.position
            dx = current.x - previous.x
            dy = current.y - previous.y
            dz = current.z - previous.z
            total += math.sqrt(dx * dx + dy * dy + dz * dz)
        return total

    def _format_pose(self, pose):
        yaw = self._yaw_from_quaternion(pose.orientation)
        return '(x=%.3f y=%.3f yaw=%.2f)' % (
            pose.position.x,
            pose.position.y,
            yaw,
        )

    def _yaw_from_quaternion(self, quaternion):
        siny_cosp = 2.0 * (
            quaternion.w * quaternion.z + quaternion.x * quaternion.y
        )
        cosy_cosp = 1.0 - 2.0 * (
            quaternion.y * quaternion.y + quaternion.z * quaternion.z
        )
        return math.atan2(siny_cosp, cosy_cosp)

    def _feedback_fields(self, feedback):
        fields = []
        try:
            field_names = feedback.get_fields_and_field_types().keys()
        except AttributeError:
            field_names = []

        for name in field_names:
            value = getattr(feedback, name)
            if isinstance(value, float):
                if math.isfinite(value):
                    fields.append('%s=%.3f' % (name, value))
            elif isinstance(value, bool):
                fields.append('%s=%s' % (name, str(value).lower()))
            elif isinstance(value, int):
                fields.append('%s=%d' % (name, value))
            elif isinstance(value, str):
                fields.append('%s=%s' % (name, value))

        return fields

    def _make_path_markers(self, path_msg):
        frame_id = path_msg.header.frame_id or 'map'
        markers = self._make_delete_markers(frame_id)
        if not path_msg.poses:
            return markers

        stamp = self.get_clock().now().to_msg()

        line_marker = Marker()
        line_marker.header.frame_id = frame_id
        line_marker.header.stamp = stamp
        line_marker.ns = 'coverage_follow_path_line'
        line_marker.id = 0
        line_marker.type = Marker.LINE_STRIP
        line_marker.action = Marker.ADD
        line_marker.pose.orientation.w = 1.0
        line_marker.scale.x = 0.035
        line_marker.color.r = 0.0
        line_marker.color.g = 0.85
        line_marker.color.b = 1.0
        line_marker.color.a = 0.95
        for pose_stamped in path_msg.poses:
            point = Point()
            point.x = pose_stamped.pose.position.x
            point.y = pose_stamped.pose.position.y
            point.z = pose_stamped.pose.position.z + 0.04
            line_marker.points.append(point)
        markers.markers.append(line_marker)

        start_marker = self._make_pose_marker(
            frame_id,
            stamp,
            'coverage_follow_path_start',
            1,
            Marker.SPHERE,
            path_msg.poses[0],
            (0.0, 0.9, 0.2, 0.95),
            0.16,
            0.08,
        )
        markers.markers.append(start_marker)

        end_marker = self._make_pose_marker(
            frame_id,
            stamp,
            'coverage_follow_path_end',
            2,
            Marker.CUBE,
            path_msg.poses[-1],
            (1.0, 0.15, 0.05, 0.95),
            0.16,
            0.08,
        )
        markers.markers.append(end_marker)

        state_point = self._estimate_current_state_point(path_msg)
        if state_point is not None:
            state_marker = Marker()
            state_marker.header.frame_id = frame_id
            state_marker.header.stamp = stamp
            state_marker.ns = 'coverage_follow_path_state'
            state_marker.id = 3
            state_marker.type = Marker.SPHERE
            state_marker.action = Marker.ADD
            state_marker.pose.position = state_point
            state_marker.pose.position.z += 0.12
            state_marker.pose.orientation.w = 1.0
            state_marker.scale.x = 0.18
            state_marker.scale.y = 0.18
            state_marker.scale.z = 0.18
            state_marker.color.r = 0.1
            state_marker.color.g = 0.25
            state_marker.color.b = 1.0
            state_marker.color.a = 0.95
            markers.markers.append(state_marker)

            label = Marker()
            label.header.frame_id = frame_id
            label.header.stamp = stamp
            label.ns = 'coverage_follow_path_state_label'
            label.id = 4
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position = copy.deepcopy(state_point)
            label.pose.position.z += 0.34
            label.pose.orientation.w = 1.0
            label.scale.z = 0.18
            label.color.r = 1.0
            label.color.g = 1.0
            label.color.b = 1.0
            label.color.a = 0.95
            label.text = self.execution_status
            markers.markers.append(label)

        return markers

    def _make_pose_marker(
        self,
        frame_id,
        stamp,
        namespace,
        marker_id,
        marker_type,
        pose_stamped,
        rgba,
        scale,
        z_offset,
    ):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = stamp
        marker.ns = namespace
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose = copy.deepcopy(pose_stamped.pose)
        marker.pose.position.z += z_offset
        marker.scale.x = scale
        marker.scale.y = scale
        marker.scale.z = scale
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]
        return marker

    def _estimate_current_state_point(self, path_msg):
        if not path_msg.poses:
            return None

        if self.execution_status == self.STATUS_SUCCEEDED:
            return copy.deepcopy(path_msg.poses[-1].pose.position)

        if (
            self.execution_status
            in (
                self.STATUS_EXECUTING,
                self.STATUS_FAILED,
                self.STATUS_CANCELED,
            )
            and self.last_distance_to_goal is not None
        ):
            target_distance = max(
                0.0,
                self._path_length(path_msg) - self.last_distance_to_goal,
            )
            return self._point_at_path_distance(path_msg, target_distance)

        return copy.deepcopy(path_msg.poses[0].pose.position)

    def _point_at_path_distance(self, path_msg, target_distance):
        poses = path_msg.poses
        if len(poses) == 1:
            return copy.deepcopy(poses[0].pose.position)

        traversed = 0.0
        for index in range(1, len(poses)):
            previous = poses[index - 1].pose.position
            current = poses[index].pose.position
            dx = current.x - previous.x
            dy = current.y - previous.y
            dz = current.z - previous.z
            segment_length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if segment_length <= 0.0:
                continue

            if traversed + segment_length >= target_distance:
                ratio = (target_distance - traversed) / segment_length
                point = Point()
                point.x = previous.x + ratio * dx
                point.y = previous.y + ratio * dy
                point.z = previous.z + ratio * dz
                return point

            traversed += segment_length

        return copy.deepcopy(poses[-1].pose.position)

    def _make_delete_markers(self, frame_id):
        marker = Marker()
        marker.header.frame_id = frame_id or 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'coverage_follow_path_cleanup'
        marker.id = 0
        marker.action = Marker.DELETEALL
        markers = MarkerArray()
        markers.markers.append(marker)
        return markers

    def _set_status(self, status):
        if status != self.execution_status:
            self.get_logger().info('Coverage FollowPath status: %s' % status)
        self.execution_status = status
        self.latest_status_msg.data = status
        if hasattr(self, 'execution_status_pub'):
            self.execution_status_pub.publish(self.latest_status_msg)

    def _declare_parameter_if_needed(self, name, default_value):
        try:
            self.declare_parameter(name, default_value)
        except ParameterAlreadyDeclaredException:
            pass

    def _string_param(self, name):
        return self.get_parameter(name).get_parameter_value().string_value

    def _bool_param(self, name):
        return self.get_parameter(name).get_parameter_value().bool_value

    def _int_param(self, name):
        return self.get_parameter(name).get_parameter_value().integer_value

    def _double_param(self, name):
        return self.get_parameter(name).get_parameter_value().double_value


def main(args=None):
    rclpy.init(args=args)
    node = CoverageFollowPathExecutorNode()

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

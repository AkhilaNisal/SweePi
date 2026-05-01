#!/usr/bin/env python3
"""Execute one frozen coverage path with Nav2 FollowPath."""

import copy
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point, PoseStamped
from nav2_msgs.action import FollowPath, SmoothPath
from nav_msgs.msg import OccupancyGrid, Path
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

from sweepi_coverage.coverage_utils import in_bounds, map_to_flat_index, world_to_map


class CoverageFollowPathExecutorNode(Node):
    """Freeze, optionally smooth, validate, and execute a coverage Path."""

    STATUS_IDLE = 'IDLE'
    STATUS_WAITING_FOR_PATH = 'WAITING_FOR_PATH'
    STATUS_VALIDATING = 'VALIDATING'
    STATUS_SMOOTHING = 'SMOOTHING'
    STATUS_WAITING_FOR_NAV2 = 'WAITING_FOR_NAV2'
    STATUS_EXECUTING = 'EXECUTING'
    STATUS_SUCCEEDED = 'SUCCEEDED'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELED = 'CANCELED'

    FOLLOW_PATH_ERROR_CODES = {
        0: 'NONE',
        100: 'UNKNOWN',
        101: 'INVALID_CONTROLLER',
        102: 'TF_ERROR',
        103: 'INVALID_PATH',
        104: 'PATIENCE_EXCEEDED',
        105: 'FAILED_TO_MAKE_PROGRESS',
        106: 'NO_VALID_CONTROL',
        107: 'CONTROLLER_TIMED_OUT',
    }

    SMOOTH_PATH_ERROR_CODES = {
        0: 'NONE',
        500: 'UNKNOWN',
        501: 'INVALID_SMOOTHER',
        502: 'TIMEOUT',
        503: 'SMOOTHED_PATH_IN_COLLISION',
        504: 'FAILED_TO_SMOOTH_PATH',
        505: 'INVALID_PATH',
    }

    def __init__(self):
        super().__init__('coverage_follow_path_executor_node')

        self._declare_parameters()
        self._load_parameters()

        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        costmap_qos = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.cached_raw_path = None
        self.coverage_path_frozen = False
        self.active_path = None
        self.smoothed_path = None
        self.latest_path_error = 'No coverage path received yet'
        self.latest_status_msg = String()
        self.execution_status = self.STATUS_WAITING_FOR_PATH
        self.latest_feedback_text = ''
        self.latest_debug_info = ''
        self.selected_start_index = 0
        self.latest_validation_report = self._make_empty_report()
        self.nav_costmap = None
        self.nav_costmap_received = False
        self.nav_costmap_stamp_monotonic = 0.0
        self.rounded_turn_sections = []
        self.blocked_debug_points = []
        self.current_goal_handle = None
        self.current_smoothing_goal_handle = None
        self.goal_in_flight = False
        self.smoothing_in_flight = False
        self.cancel_requested = False
        self.execution_start_monotonic = None
        self.last_distance_to_goal = None
        self.pending_follow_path = None
        self.pending_start_report = None
        self.pending_custom_smoothed_length = 0.0
        self.pending_smoothing_start_monotonic = None

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.follow_path_client = ActionClient(
            self,
            FollowPath,
            self.follow_path_action_name,
        )
        self.smoother_client = ActionClient(
            self,
            SmoothPath,
            self.smoother_action_name,
        )

        self.coverage_path_sub = self.create_subscription(
            Path,
            self.coverage_path_topic,
            self.coverage_path_callback,
            qos,
        )
        self.nav_costmap_sub = self.create_subscription(
            OccupancyGrid,
            self.costmap_topic,
            self.nav_costmap_callback,
            costmap_qos,
        )

        self.raw_path_pub = self.create_publisher(Path, self.raw_path_topic, qos)
        self.smoothed_path_pub = self.create_publisher(
            Path,
            self.smoothed_path_topic,
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
        self.path_markers_pub = self.create_publisher(
            MarkerArray,
            self.path_markers_topic,
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
        self.reset_service = self.create_service(
            Trigger,
            '/reset_coverage_follow_path',
            self.reset_service_callback,
        )

        publish_period = 1.0 / max(0.1, self.republish_active_path_hz)
        self.timer = self.create_timer(publish_period, self.timer_callback)

        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self.get_logger().info(
            'Coverage FollowPath executor started: action=%s controller_id=%s '
            'smoother_action=%s smoother_id=%s path=%s raw=%s smoothed=%s '
            'active=%s costmap=%s. This mode uses FollowPath, not '
            'NavigateThroughPoses.'
            % (
                self.follow_path_action_name,
                self.controller_id,
                self.smoother_action_name,
                self.smoother_id,
                self.coverage_path_topic,
                self.raw_path_topic,
                self.smoothed_path_topic,
                self.active_path_topic,
                self.costmap_topic,
            )
        )

    def _declare_parameters(self):
        defaults = {
            'use_sim_time': True,
            'coverage_path_topic': '/coverage_path',
            'raw_path_topic': '/coverage_path_raw',
            'smoothed_path_topic': '/coverage_smoothed_path',
            'active_path_topic': '/coverage_active_path',
            'execution_status_topic': '/coverage_execution_status',
            'nav2_feedback_topic': '/coverage_nav2_feedback',
            'debug_info_topic': '/coverage_debug_info',
            'debug_markers_topic': '/coverage_debug_markers',
            'path_markers_topic': '/coverage_path_markers',
            'follow_path_action_name': '/follow_path',
            'controller_id': 'FollowPath',
            'goal_checker_id': '',
            'progress_checker_id': '',
            'global_frame': 'map',
            'robot_base_frame': 'base_link',
            'costmap_topic': '/global_costmap/costmap',
            'enable_costmap_validation': True,
            'require_costmap_for_validation': True,
            'max_allowed_nav_cost': 90,
            'treat_unknown_cost_as_blocked': True,
            'freeze_path_on_start': True,
            'ignore_path_updates_while_executing': True,
            'require_robot_near_start': False,
            'max_start_distance_m': 0.75,
            'start_from_nearest_valid_pose_if_far': True,
            'max_nearest_path_distance_m': 1.50,
            'max_consecutive_pose_jump_m': 0.50,
            'min_path_poses': 2,
            'minimum_path_length_m': 0.10,
            'tf_lookup_timeout_sec': 1.0,
            'wait_for_nav2_timeout_sec': 10.0,
            'republish_active_path_hz': 1.0,
            'auto_start': False,
            'enable_coverage_turn_smoothing': True,
            'turn_smoothing_radius_m': 0.15,
            'preserve_strip_lines': True,
            'validate_turn_smoothing_against_costmap': True,
            'enable_nav2_smoothing': True,
            'smoother_action_name': '/smooth_path',
            'smoother_id': 'simple_smoother',
            'max_smoothing_duration_s': 2.0,
            'check_smooth_path_for_collisions': True,
            'fallback_to_raw_path_on_smoothing_failure': False,
            'publish_raw_and_smoothed_paths': True,
            'publish_debug_markers': True,
        }
        for name, value in defaults.items():
            self._declare_parameter_if_needed(name, value)

    def _load_parameters(self):
        self.coverage_path_topic = self._string_param('coverage_path_topic')
        self.raw_path_topic = self._string_param('raw_path_topic')
        self.smoothed_path_topic = self._string_param('smoothed_path_topic')
        self.active_path_topic = self._string_param('active_path_topic')
        self.execution_status_topic = self._string_param('execution_status_topic')
        self.nav2_feedback_topic = self._string_param('nav2_feedback_topic')
        self.debug_info_topic = self._string_param('debug_info_topic')
        self.debug_markers_topic = self._string_param('debug_markers_topic')
        self.path_markers_topic = self._string_param('path_markers_topic')
        self.follow_path_action_name = self._string_param('follow_path_action_name')
        self.controller_id = self._string_param('controller_id')
        self.goal_checker_id = self._string_param('goal_checker_id')
        self.progress_checker_id = self._string_param('progress_checker_id')
        self.global_frame = self._string_param('global_frame')
        self.robot_base_frame = self._string_param('robot_base_frame')
        self.costmap_topic = self._string_param('costmap_topic')
        self.enable_costmap_validation = self._bool_param('enable_costmap_validation')
        self.require_costmap_for_validation = self._bool_param(
            'require_costmap_for_validation'
        )
        self.max_allowed_nav_cost = self._int_param('max_allowed_nav_cost')
        self.treat_unknown_cost_as_blocked = self._bool_param(
            'treat_unknown_cost_as_blocked'
        )
        self.freeze_path_on_start = self._bool_param('freeze_path_on_start')
        self.ignore_path_updates_while_executing = self._bool_param(
            'ignore_path_updates_while_executing'
        )
        self.require_robot_near_start = self._bool_param('require_robot_near_start')
        self.max_start_distance_m = self._double_param('max_start_distance_m')
        self.start_from_nearest_valid_pose_if_far = self._bool_param(
            'start_from_nearest_valid_pose_if_far'
        )
        self.max_nearest_path_distance_m = self._double_param(
            'max_nearest_path_distance_m'
        )
        self.max_consecutive_pose_jump_m = self._double_param(
            'max_consecutive_pose_jump_m'
        )
        self.min_path_poses = self._int_param('min_path_poses')
        self.minimum_path_length_m = self._double_param('minimum_path_length_m')
        self.tf_lookup_timeout_sec = self._double_param('tf_lookup_timeout_sec')
        self.wait_for_nav2_timeout_sec = self._double_param(
            'wait_for_nav2_timeout_sec'
        )
        self.republish_active_path_hz = self._double_param('republish_active_path_hz')
        self.auto_start = self._bool_param('auto_start')
        self.enable_coverage_turn_smoothing = self._bool_param(
            'enable_coverage_turn_smoothing'
        )
        self.turn_smoothing_radius_m = self._double_param('turn_smoothing_radius_m')
        self.preserve_strip_lines = self._bool_param('preserve_strip_lines')
        self.validate_turn_smoothing_against_costmap = self._bool_param(
            'validate_turn_smoothing_against_costmap'
        )
        self.enable_nav2_smoothing = self._bool_param('enable_nav2_smoothing')
        self.smoother_action_name = self._string_param('smoother_action_name')
        self.smoother_id = self._string_param('smoother_id')
        self.max_smoothing_duration_s = self._double_param('max_smoothing_duration_s')
        self.check_smooth_path_for_collisions = self._bool_param(
            'check_smooth_path_for_collisions'
        )
        self.fallback_to_raw_path_on_smoothing_failure = self._bool_param(
            'fallback_to_raw_path_on_smoothing_failure'
        )
        self.publish_raw_and_smoothed_paths = self._bool_param(
            'publish_raw_and_smoothed_paths'
        )
        self.publish_debug_markers = self._bool_param('publish_debug_markers')

        self.max_allowed_nav_cost = min(100, max(0, self.max_allowed_nav_cost))
        self.max_start_distance_m = max(0.0, self.max_start_distance_m)
        self.max_nearest_path_distance_m = max(0.0, self.max_nearest_path_distance_m)
        self.max_consecutive_pose_jump_m = max(0.01, self.max_consecutive_pose_jump_m)
        self.min_path_poses = max(1, self.min_path_poses)
        self.minimum_path_length_m = max(0.0, self.minimum_path_length_m)
        self.tf_lookup_timeout_sec = max(0.0, self.tf_lookup_timeout_sec)
        self.wait_for_nav2_timeout_sec = max(0.0, self.wait_for_nav2_timeout_sec)
        self.turn_smoothing_radius_m = max(0.0, self.turn_smoothing_radius_m)
        self.max_smoothing_duration_s = max(0.0, self.max_smoothing_duration_s)

    def coverage_path_callback(self, msg):
        if self.goal_in_flight and self.ignore_path_updates_while_executing:
            self.get_logger().info(
                'Ignoring /coverage_path update because active coverage path is frozen.',
                throttle_duration_sec=5.0,
            )
            return

        if self.cached_raw_path is not None:
            self.get_logger().info(
                'Ignoring /coverage_path update because the first valid coverage '
                'path is already cached. Call /reset_coverage_follow_path to '
                'accept a new path.',
                throttle_duration_sec=5.0,
            )
            return

        report = self._validate_path_structure(msg, check_costmap=False)
        if not report['valid']:
            self.latest_path_error = report['reason']
            self._publish_debug(report)
            self.get_logger().warn(
                'Ignoring invalid /coverage_path: %s' % report['reason'],
                throttle_duration_sec=5.0,
            )
            return

        self.cached_raw_path = copy.deepcopy(msg)
        self.coverage_path_frozen = True
        self.latest_path_error = ''
        self._stamp_path(self.cached_raw_path)
        self.raw_path_pub.publish(self.cached_raw_path)
        self._set_status(self.STATUS_IDLE)
        self._log_path_summary(self.cached_raw_path, 'Coverage path frozen')
        self.get_logger().info(
            'Path is frozen from the first valid /coverage_path. Later updates '
            'will not replace the active coverage path without reset.'
        )
        if self.auto_start:
            self._request_execution('auto_start')

    def nav_costmap_callback(self, msg):
        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring global costmap with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        self.nav_costmap = msg
        self.nav_costmap_stamp_monotonic = time.monotonic()
        if not self.nav_costmap_received:
            self.nav_costmap_received = True
            self.get_logger().info(
                'Global costmap received for FollowPath validation: topic=%s '
                'frame=%s size=%dx%d resolution=%.3f max_allowed_nav_cost=%d '
                'unknown_blocked=%s'
                % (
                    self.costmap_topic,
                    msg.header.frame_id or self.global_frame,
                    msg.info.width,
                    msg.info.height,
                    msg.info.resolution,
                    self.max_allowed_nav_cost,
                    str(self.treat_unknown_cost_as_blocked).lower(),
                )
            )

    def start_service_callback(self, request, response):
        del request
        if self._request_execution('service_start'):
            response.success = True
            response.message = 'Coverage FollowPath execution requested'
        else:
            response.success = False
            response.message = self.latest_path_error
        return response

    def cancel_service_callback(self, request, response):
        del request
        if self.smoothing_in_flight and self.current_smoothing_goal_handle is not None:
            self.cancel_requested = True
            self.current_smoothing_goal_handle.cancel_goal_async()
            self._set_status(self.STATUS_CANCELED)
            response.success = True
            response.message = 'Cancel request sent to active SmoothPath goal'
            return response

        if self.goal_in_flight and self.current_goal_handle is not None:
            self.cancel_requested = True
            self.current_goal_handle.cancel_goal_async()
            response.success = True
            response.message = 'Cancel request sent to active FollowPath goal'
            return response

        response.success = False
        response.message = 'No active SmoothPath or FollowPath goal to cancel'
        return response

    def validate_service_callback(self, request, response):
        del request
        report = self._run_preflight_validation(self.cached_raw_path)
        response.success = report['valid']
        response.message = self._format_report(report)
        self._publish_debug(report)
        if report['valid']:
            self.get_logger().info('Coverage FollowPath validation passed')
        else:
            self.get_logger().warn(
                'Coverage FollowPath validation failed: %s' % report['reason']
            )
        return response

    def reset_service_callback(self, request, response):
        del request
        if self.goal_in_flight or self.smoothing_in_flight:
            response.success = False
            response.message = (
                'Coverage execution is active; call /cancel_coverage_follow_path '
                'before reset'
            )
            return response

        self.cached_raw_path = None
        self.coverage_path_frozen = False
        self.active_path = None
        self.smoothed_path = None
        self.latest_path_error = 'No coverage path received yet'
        self.latest_debug_info = ''
        self.latest_validation_report = self._make_empty_report()
        self.rounded_turn_sections = []
        self.blocked_debug_points = []
        self.selected_start_index = 0
        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self._publish_empty_paths_and_markers()
        response.success = True
        response.message = 'Coverage FollowPath cache reset; waiting for /coverage_path'
        return response

    def timer_callback(self):
        self.latest_status_msg.data = self.execution_status
        self.execution_status_pub.publish(self.latest_status_msg)

        if self.publish_raw_and_smoothed_paths:
            if self.cached_raw_path is not None:
                self._stamp_path(self.cached_raw_path)
                self.raw_path_pub.publish(self.cached_raw_path)
            if self.smoothed_path is not None:
                self._stamp_path(self.smoothed_path)
                self.smoothed_path_pub.publish(self.smoothed_path)

        if self.active_path is not None:
            self._stamp_path(self.active_path)
            self.active_path_pub.publish(self.active_path)
            self.path_markers_pub.publish(self._make_path_markers(self.active_path))
        elif self.cached_raw_path is not None:
            self.path_markers_pub.publish(self._make_path_markers(self.cached_raw_path))

    def _request_execution(self, reason):
        if self.goal_in_flight or self.smoothing_in_flight:
            self.latest_path_error = 'Coverage FollowPath is already active'
            return False

        if self.cached_raw_path is None:
            self._set_status(self.STATUS_WAITING_FOR_PATH)
            self.latest_path_error = self.latest_path_error or 'No coverage path cached'
            return False

        self._set_status(self.STATUS_VALIDATING)
        raw_report = self._run_preflight_validation(self.cached_raw_path)
        self._publish_debug(raw_report)
        if not raw_report['valid']:
            self.latest_path_error = raw_report['reason']
            self._set_status(self.STATUS_FAILED)
            self.get_logger().warn(
                'Cannot start FollowPath execution: %s'
                % self._format_report(raw_report)
            )
            return False

        start_path, start_report = self._select_start_path(
            self.cached_raw_path,
            raw_report,
        )
        if start_path is None:
            self.latest_path_error = start_report['reason']
            self._publish_debug(start_report)
            self._set_status(self.STATUS_FAILED)
            self.get_logger().warn(
                'Cannot start FollowPath execution: %s'
                % self._format_report(start_report)
            )
            return False

        self.pending_start_report = start_report
        working_path = start_path
        custom_smoothed_length = self._path_length(working_path)
        raw_length = self._path_length(self.cached_raw_path)

        if self.enable_coverage_turn_smoothing:
            self._set_status(self.STATUS_SMOOTHING)
            working_path = self._smooth_coverage_turns(working_path)
            custom_smoothed_length = self._path_length(working_path)
            custom_report = self._run_preflight_validation(
                working_path,
                check_costmap=self.validate_turn_smoothing_against_costmap,
            )
            if not custom_report['valid']:
                self.latest_path_error = (
                    'custom turn smoothing produced invalid path: %s'
                    % custom_report['reason']
                )
                self._publish_debug(custom_report)
                self._set_status(self.STATUS_FAILED)
                self.get_logger().warn(self.latest_path_error)
                return False

        self.smoothed_path = copy.deepcopy(working_path)
        self.smoothed_path_pub.publish(self.smoothed_path)

        if self.enable_nav2_smoothing:
            self.pending_follow_path = copy.deepcopy(working_path)
            self.pending_custom_smoothed_length = custom_smoothed_length
            self.get_logger().info(
                'Requesting Nav2 SmoothPath before FollowPath: action=%s '
                'smoother_id=%s poses=%d raw_length=%.2fm custom_length=%.2fm'
                % (
                    self.smoother_action_name,
                    self.smoother_id,
                    len(working_path.poses),
                    raw_length,
                    custom_smoothed_length,
                )
            )
            if not self._send_smooth_path_goal(working_path):
                return False
            self.latest_path_error = ''
            return True

        final_report = self._run_preflight_validation(
            working_path,
            check_costmap=self.check_smooth_path_for_collisions,
        )
        if not final_report['valid']:
            self.latest_path_error = final_report['reason']
            self._publish_debug(final_report)
            self._set_status(self.STATUS_FAILED)
            return False

        self.get_logger().info(
            'Smoothing result: raw path length=%.2fm custom-smoothed path '
            'length=%.2fm Nav2-smoothed path length=not_used collision_check=%s'
            % (
                raw_length,
                custom_smoothed_length,
                str(final_report.get('costmap_valid', True)).lower(),
            )
        )
        self._send_follow_path_goal(working_path, reason)
        return True

    def _send_smooth_path_goal(self, path):
        self._set_status(self.STATUS_SMOOTHING)
        if not self.smoother_client.wait_for_server(
            timeout_sec=self.wait_for_nav2_timeout_sec
        ):
            return self._handle_smoothing_failure(
                'SmoothPath action server %s is not available'
                % self.smoother_action_name
            )

        goal_msg = SmoothPath.Goal()
        goal_msg.path = copy.deepcopy(path)
        goal_msg.smoother_id = self.smoother_id
        goal_msg.max_smoothing_duration = Duration(
            seconds=self.max_smoothing_duration_s
        ).to_msg()
        goal_msg.check_for_collisions = self.check_smooth_path_for_collisions

        self.smoothing_in_flight = True
        self.cancel_requested = False
        self.current_smoothing_goal_handle = None
        self.pending_smoothing_start_monotonic = time.monotonic()

        send_goal_future = self.smoother_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self._smooth_goal_response_callback)
        return True

    def _smooth_goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._handle_smoothing_failure('SmoothPath goal response failed: %s' % exc)
            return

        if not goal_handle.accepted:
            self._handle_smoothing_failure('SmoothPath goal was rejected by Nav2')
            return

        self.current_smoothing_goal_handle = goal_handle
        self.get_logger().info('SmoothPath goal accepted by Nav2')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._smooth_result_callback)

    def _smooth_result_callback(self, future):
        self.smoothing_in_flight = False
        self.current_smoothing_goal_handle = None

        try:
            wrapped_result = future.result()
        except Exception as exc:
            self._handle_smoothing_failure('SmoothPath result failed: %s' % exc)
            return

        result = wrapped_result.result
        status = wrapped_result.status
        error_code = getattr(result, 'error_code', 0)
        error_label = self.SMOOTH_PATH_ERROR_CODES.get(error_code, 'UNRECOGNIZED')
        error_msg = getattr(result, 'error_msg', '')
        smoothed = getattr(result, 'path', Path())
        duration = 0.0
        if self.pending_smoothing_start_monotonic is not None:
            duration = time.monotonic() - self.pending_smoothing_start_monotonic

        if (
            status != GoalStatus.STATUS_SUCCEEDED
            or error_code != 0
            or len(smoothed.poses) == 0
        ):
            self._handle_smoothing_failure(
                'SmoothPath failed: status=%d error_code=%d %s error_msg=%s'
                % (status, error_code, error_label, error_msg)
            )
            return

        if not smoothed.header.frame_id:
            smoothed.header.frame_id = self.global_frame
        self._stamp_path(smoothed)

        report = self._run_preflight_validation(
            smoothed,
            check_costmap=self.check_smooth_path_for_collisions,
        )
        self._publish_debug(report)
        if not report['valid']:
            self._handle_smoothing_failure(
                'Nav2-smoothed path failed validation: %s' % report['reason']
            )
            return

        self.smoothed_path = copy.deepcopy(smoothed)
        self.smoothed_path_pub.publish(self.smoothed_path)
        self.get_logger().info(
            'Smoothing result: raw path length=%.2fm custom-smoothed path '
            'length=%.2fm Nav2-smoothed path length=%.2fm smoothing_duration=%.2fs '
            'collision_check=%s'
            % (
                self._path_length(self.cached_raw_path),
                self.pending_custom_smoothed_length,
                self._path_length(smoothed),
                duration,
                str(report.get('costmap_valid', True)).lower(),
            )
        )
        self._send_follow_path_goal(smoothed, 'smooth_path_done')

    def _handle_smoothing_failure(self, reason):
        self.smoothing_in_flight = False
        self.current_smoothing_goal_handle = None
        self.get_logger().warn(reason)
        if self.fallback_to_raw_path_on_smoothing_failure and self.pending_follow_path:
            self.get_logger().warn(
                'Falling back to custom/raw coverage path after smoothing failure'
            )
            self._send_follow_path_goal(self.pending_follow_path, 'smoothing_fallback')
            return True

        self.latest_path_error = reason
        self._publish_debug_info('status=FAILED reason=%s' % reason)
        self._set_status(self.STATUS_FAILED)
        return False

    def _send_follow_path_goal(self, path, reason):
        self._set_status(self.STATUS_WAITING_FOR_NAV2)
        if not self.follow_path_client.wait_for_server(
            timeout_sec=self.wait_for_nav2_timeout_sec
        ):
            self.latest_path_error = (
                'FollowPath action server %s is not available'
                % self.follow_path_action_name
            )
            self.get_logger().warn(self.latest_path_error)
            self._set_status(self.STATUS_FAILED)
            return False

        report = self._run_preflight_validation(
            path,
            check_costmap=self.check_smooth_path_for_collisions,
        )
        self._publish_debug(report)
        if not report['valid']:
            self.latest_path_error = report['reason']
            self.get_logger().warn(
                'Final FollowPath validation failed: %s' % self._format_report(report)
            )
            self._set_status(self.STATUS_FAILED)
            return False

        goal_msg = FollowPath.Goal()
        goal_msg.path = copy.deepcopy(path)
        goal_msg.controller_id = self.controller_id
        goal_msg.goal_checker_id = self.goal_checker_id
        goal_msg.progress_checker_id = self.progress_checker_id

        self.active_path = copy.deepcopy(path)
        self._stamp_path(self.active_path)
        self.active_path_pub.publish(self.active_path)
        self.path_markers_pub.publish(self._make_path_markers(self.active_path))
        self.coverage_path_frozen = self.freeze_path_on_start or self.coverage_path_frozen
        self.goal_in_flight = True
        self.current_goal_handle = None
        self.cancel_requested = False
        self.execution_start_monotonic = time.monotonic()
        self.last_distance_to_goal = None
        self.latest_feedback_text = ''
        self.latest_path_error = ''
        self._set_status(self.STATUS_EXECUTING)

        self._log_follow_path_send(path, report, reason)
        send_goal_future = self.follow_path_client.send_goal_async(
            goal_msg,
            feedback_callback=self._follow_path_feedback_callback,
        )
        send_goal_future.add_done_callback(self._goal_response_callback)
        return True

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
        error_label = self.FOLLOW_PATH_ERROR_CODES.get(error_code, 'UNRECOGNIZED')
        error_msg = getattr(result, 'error_msg', '')

        self.get_logger().info(
            'FollowPath result: status=%d error_code=%d %s error_msg=%s'
            % (status, error_code, error_label, error_msg)
        )

        if status == GoalStatus.STATUS_SUCCEEDED and error_code == 0:
            self._finish_execution(self.STATUS_SUCCEEDED)
            return

        if status == GoalStatus.STATUS_CANCELED or self.cancel_requested:
            self._finish_execution(self.STATUS_CANCELED)
            return

        if error_code == 105:
            debug = (
                'FollowPath failed with FAILED_TO_MAKE_PROGRESS. Likely causes: '
                'progress checker too strict, local costmap collision checking, '
                'sharp turn, robot not near the selected start pose, or cmd_vel '
                'blocked. last_feedback="%s"'
                % self.latest_feedback_text
            )
            self.get_logger().warn(debug)
            self._publish_debug_info(debug)
        else:
            self._publish_debug_info(
                'FollowPath failed: status=%d error_code=%d %s error_msg=%s'
                % (status, error_code, error_label, error_msg)
            )
        self._finish_execution(self.STATUS_FAILED)

    def _follow_path_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        fields = []
        distance_to_goal = getattr(feedback, 'distance_to_goal', None)
        speed = getattr(feedback, 'speed', None)
        if distance_to_goal is not None and math.isfinite(distance_to_goal):
            self.last_distance_to_goal = float(distance_to_goal)
            fields.append('distance_to_goal=%.3f' % distance_to_goal)
        if speed is not None and math.isfinite(speed):
            fields.append('speed=%.3f' % speed)
        if self.execution_start_monotonic is not None:
            fields.append(
                'elapsed=%.1f' % (time.monotonic() - self.execution_start_monotonic)
            )
        if not fields:
            fields.append('feedback_received=true')
        msg = String()
        msg.data = ' '.join(fields)
        self.latest_feedback_text = msg.data
        self.nav2_feedback_pub.publish(msg)

    def _finish_execution(self, status):
        self.goal_in_flight = False
        self.current_goal_handle = None
        self.cancel_requested = False
        self.execution_start_monotonic = None
        self._set_status(status)

    def _run_preflight_validation(self, path, check_costmap=True):
        report = self._validate_path_structure(path, check_costmap=check_costmap)
        if not report['valid']:
            return report

        robot_pose = self._lookup_robot_pose(self.global_frame)
        if robot_pose is None:
            report['valid'] = False
            report['status'] = self.STATUS_FAILED
            report['reason'] = (
                'TF %s -> %s unavailable'
                % (self.global_frame, self.robot_base_frame)
            )
            return report

        first_pose = path.poses[0].pose
        nearest_index, nearest_distance = self._nearest_path_pose(
            path,
            robot_pose['x'],
            robot_pose['y'],
        )
        distance_to_first = self._distance_2d(
            robot_pose['x'],
            robot_pose['y'],
            first_pose.position.x,
            first_pose.position.y,
        )

        report['robot_pose'] = robot_pose
        report['distance_to_first'] = distance_to_first
        report['nearest_index'] = nearest_index
        report['distance_to_nearest'] = nearest_distance
        report['nearest_pose'] = self._pose_debug_dict(path.poses[nearest_index].pose)

        if distance_to_first > self.max_start_distance_m:
            if not self.start_from_nearest_valid_pose_if_far:
                report['valid'] = False
                report['status'] = self.STATUS_FAILED
                report['reason'] = (
                    'first pose is %.3fm from robot, exceeds %.3fm, and '
                    'start_from_nearest_valid_pose_if_far=false'
                    % (distance_to_first, self.max_start_distance_m)
                )
                return report
            if self.require_robot_near_start:
                report['valid'] = False
                report['status'] = self.STATUS_FAILED
                report['reason'] = (
                    'first pose is %.3fm from robot, exceeds %.3fm, and '
                    'require_robot_near_start=true'
                    % (distance_to_first, self.max_start_distance_m)
                )
                return report
            if nearest_distance > self.max_nearest_path_distance_m:
                report['valid'] = False
                report['status'] = self.STATUS_FAILED
                report['reason'] = (
                    'nearest path pose is %.3fm from robot, exceeds %.3fm'
                    % (nearest_distance, self.max_nearest_path_distance_m)
                )
                return report

        report['valid'] = True
        report['status'] = 'VALID'
        report['reason'] = 'ok'
        return report

    def _validate_path_structure(self, path, check_costmap=True):
        report = self._make_empty_report()
        if path is None:
            report['reason'] = 'no_cached_path'
            return report

        report['frame_id'] = path.header.frame_id.strip()
        report['pose_count'] = len(path.poses)
        if report['pose_count'] == 0:
            report['reason'] = 'path is empty'
            return report
        if report['pose_count'] < self.min_path_poses:
            report['reason'] = (
                'pose_count=%d is below min_path_poses=%d'
                % (report['pose_count'], self.min_path_poses)
            )
            return report
        if report['frame_id'] != self.global_frame:
            report['reason'] = (
                'path frame_id "%s" is not "%s"'
                % (report['frame_id'], self.global_frame)
            )
            return report

        for index, pose_stamped in enumerate(path.poses):
            pose = pose_stamped.pose
            position = pose.position
            orientation = pose.orientation
            if not all(
                math.isfinite(value)
                for value in (position.x, position.y, position.z)
            ):
                report['reason'] = 'pose[%d] has non-finite position' % index
                return report
            if not all(
                math.isfinite(value)
                for value in (
                    orientation.x,
                    orientation.y,
                    orientation.z,
                    orientation.w,
                )
            ):
                report['reason'] = 'pose[%d] has non-finite orientation' % index
                return report
            norm = math.sqrt(
                orientation.x * orientation.x
                + orientation.y * orientation.y
                + orientation.z * orientation.z
                + orientation.w * orientation.w
            )
            if norm < 1.0e-3:
                report['reason'] = 'pose[%d] has invalid quaternion norm' % index
                return report

        report['first_pose'] = self._pose_debug_dict(path.poses[0].pose)
        report['last_pose'] = self._pose_debug_dict(path.poses[-1].pose)
        report['path_length'] = self._path_length(path)
        report['segment_count'] = max(0, len(path.poses) - 1)
        report['max_jump'], report['max_jump_index'] = self._max_jump(path)
        if report['max_jump_index'] >= 0:
            report['max_jump_start_pose'] = self._pose_debug_dict(
                path.poses[report['max_jump_index']].pose
            )
            report['max_jump_end_pose'] = self._pose_debug_dict(
                path.poses[report['max_jump_index'] + 1].pose
            )

        if report['path_length'] <= self.minimum_path_length_m:
            report['reason'] = (
                'path_length=%.3f is not greater than minimum_path_length_m=%.3f'
                % (report['path_length'], self.minimum_path_length_m)
            )
            return report

        if report['max_jump'] > self.max_consecutive_pose_jump_m:
            report['reason'] = (
                'max_consecutive_pose_jump=%.3f exceeds %.3f at index=%d'
                % (
                    report['max_jump'],
                    self.max_consecutive_pose_jump_m,
                    report['max_jump_index'],
                )
            )
            return report

        if check_costmap and self.enable_costmap_validation:
            cost_report = self._validate_path_against_costmap(path)
            report.update(cost_report)
            if not cost_report['costmap_valid']:
                report['reason'] = cost_report['costmap_reason']
                return report

        report['valid'] = True
        report['status'] = 'VALID'
        report['reason'] = 'ok'
        return report

    def _validate_path_against_costmap(self, path):
        self.blocked_debug_points = []
        report = {
            'costmap_used': False,
            'costmap_valid': True,
            'costmap_reason': 'ok',
            'blocked_pose_count': 0,
            'unknown_pose_count': 0,
            'max_observed_cost': 0,
        }
        if self.nav_costmap is None:
            report['costmap_valid'] = not self.require_costmap_for_validation
            report['costmap_reason'] = 'global costmap has not been received'
            return report

        costmap_frame = self.nav_costmap.header.frame_id or self.global_frame
        if costmap_frame != self.global_frame:
            report['costmap_valid'] = False
            report['costmap_reason'] = (
                'costmap frame "%s" does not match path frame "%s"'
                % (costmap_frame, self.global_frame)
            )
            return report

        report['costmap_used'] = True
        sample_step = max(0.01, self.nav_costmap.info.resolution * 0.5)
        blocked_count = 0
        unknown_count = 0
        max_cost = 0

        for index in range(len(path.poses)):
            pose = path.poses[index].pose
            cost_info = self._costmap_value_at(pose.position.x, pose.position.y)
            if cost_info['unknown']:
                unknown_count += 1
            max_cost = max(max_cost, cost_info['cost'])
            if cost_info['blocked']:
                blocked_count += 1
                self._append_blocked_debug_point(pose.position)

            if index == 0:
                continue

            previous = path.poses[index - 1].pose.position
            current = pose.position
            distance = self._distance_2d(previous.x, previous.y, current.x, current.y)
            steps = max(1, int(math.ceil(distance / sample_step)))
            for step in range(1, steps):
                ratio = step / steps
                x = previous.x + ratio * (current.x - previous.x)
                y = previous.y + ratio * (current.y - previous.y)
                cost_info = self._costmap_value_at(x, y)
                if cost_info['unknown']:
                    unknown_count += 1
                max_cost = max(max_cost, cost_info['cost'])
                if cost_info['blocked']:
                    blocked_count += 1
                    point = Point()
                    point.x = x
                    point.y = y
                    point.z = 0.0
                    self._append_blocked_debug_point(point)

        report['blocked_pose_count'] = blocked_count
        report['unknown_pose_count'] = unknown_count
        report['max_observed_cost'] = max_cost
        if blocked_count > 0:
            report['costmap_valid'] = False
            report['costmap_reason'] = (
                'path has %d blocked costmap samples, unknown_samples=%d, '
                'max_observed_cost=%d, max_allowed_nav_cost=%d'
                % (
                    blocked_count,
                    unknown_count,
                    max_cost,
                    self.max_allowed_nav_cost,
                )
            )
        return report

    def _costmap_value_at(self, x, y):
        try:
            map_x, map_y = world_to_map(x, y, self.nav_costmap.info)
        except ValueError:
            return {'cost': 100, 'unknown': False, 'blocked': True}

        if not in_bounds(
            map_x,
            map_y,
            self.nav_costmap.info.width,
            self.nav_costmap.info.height,
        ):
            return {'cost': 100, 'unknown': False, 'blocked': True}

        index = map_to_flat_index(map_x, map_y, self.nav_costmap.info.width)
        cost = self.nav_costmap.data[index]
        if cost < 0:
            return {
                'cost': 100,
                'unknown': True,
                'blocked': self.treat_unknown_cost_as_blocked,
            }
        return {
            'cost': cost,
            'unknown': False,
            'blocked': cost > self.max_allowed_nav_cost,
        }

    def _append_blocked_debug_point(self, point):
        if len(self.blocked_debug_points) < 50:
            self.blocked_debug_points.append(copy.deepcopy(point))

    def _select_start_path(self, path, report):
        distance_to_first = report['distance_to_first']
        nearest_index = report['nearest_index']
        nearest_distance = report['distance_to_nearest']
        start_report = copy.deepcopy(report)
        start_report['start_index'] = 0
        start_report['robot_start_used'] = True

        if distance_to_first <= self.max_start_distance_m:
            self.selected_start_index = 0
            return copy.deepcopy(path), start_report

        if not self.start_from_nearest_valid_pose_if_far:
            start_report['valid'] = False
            start_report['reason'] = (
                'first active pose is too far from robot: %.3fm > %.3fm'
                % (distance_to_first, self.max_start_distance_m)
            )
            return None, start_report

        if nearest_index < 0 or nearest_distance > self.max_nearest_path_distance_m:
            start_report['valid'] = False
            start_report['reason'] = (
                'nearest frozen path pose is too far: %.3fm > %.3fm'
                % (nearest_distance, self.max_nearest_path_distance_m)
            )
            return None, start_report

        trimmed = self._trim_path(path, nearest_index)
        self.selected_start_index = nearest_index
        start_report['start_index'] = nearest_index
        start_report['first_pose'] = self._pose_debug_dict(trimmed.poses[0].pose)
        start_report['distance_to_first'] = nearest_distance
        self.get_logger().info(
            'Robot is %.2fm from frozen path[0]; selected nearest valid start '
            'index=%d distance=%.2fm without reordering the path.'
            % (distance_to_first, nearest_index, nearest_distance)
        )
        return trimmed, start_report

    def _smooth_coverage_turns(self, path):
        self.rounded_turn_sections = []
        if len(path.poses) < 3 or self.turn_smoothing_radius_m <= 0.0:
            return copy.deepcopy(path)

        output = Path()
        output.header = copy.deepcopy(path.header)
        output.poses.append(copy.deepcopy(path.poses[0]))

        for index in range(1, len(path.poses) - 1):
            prev_pose = path.poses[index - 1].pose
            current_pose = path.poses[index].pose
            next_pose = path.poses[index + 1].pose
            heading_in = math.atan2(
                current_pose.position.y - prev_pose.position.y,
                current_pose.position.x - prev_pose.position.x,
            )
            heading_out = math.atan2(
                next_pose.position.y - current_pose.position.y,
                next_pose.position.x - current_pose.position.x,
            )
            turn_angle = abs(self._normalize_angle(heading_out - heading_in))
            if turn_angle < math.radians(120.0):
                self._append_pose_without_duplicate(output, path.poses[index])
                continue

            rounded = self._make_rounded_turn(path.header, prev_pose, current_pose, next_pose)
            if not rounded:
                self._append_pose_without_duplicate(output, path.poses[index])
                self.get_logger().warn(
                    'Keeping original sharp turn at index=%d; rounded turn was invalid'
                    % index,
                    throttle_duration_sec=5.0,
                )
                continue

            for pose_stamped in rounded:
                self._append_pose_without_duplicate(output, pose_stamped)
            self.rounded_turn_sections.append(rounded)

        self._append_pose_without_duplicate(output, path.poses[-1])
        self._recompute_orientations(output)
        self.get_logger().info(
            'Coverage turn smoothing completed: rounded_turns=%d poses_before=%d '
            'poses_after=%d preserve_strip_lines=%s'
            % (
                len(self.rounded_turn_sections),
                len(path.poses),
                len(output.poses),
                str(self.preserve_strip_lines).lower(),
            )
        )
        return output

    def _make_rounded_turn(self, header, prev_pose, current_pose, next_pose):
        prev = prev_pose.position
        current = current_pose.position
        next_point = next_pose.position
        in_len = self._distance_2d(prev.x, prev.y, current.x, current.y)
        out_len = self._distance_2d(current.x, current.y, next_point.x, next_point.y)
        if in_len <= 1.0e-6 or out_len <= 1.0e-6:
            return []

        in_unit = ((current.x - prev.x) / in_len, (current.y - prev.y) / in_len)
        out_unit = (
            (next_point.x - current.x) / out_len,
            (next_point.y - current.y) / out_len,
        )

        for scale in (1.0, 0.5, 0.25):
            radius = min(self.turn_smoothing_radius_m * scale, in_len * 0.45, out_len * 0.45)
            if radius <= 0.01:
                continue

            start_x = current.x - in_unit[0] * radius
            start_y = current.y - in_unit[1] * radius
            end_x = current.x + out_unit[0] * radius
            end_y = current.y + out_unit[1] * radius
            if self._distance_2d(start_x, start_y, end_x, end_y) <= 0.01:
                continue

            rounded = []
            point_count = 7
            for step in range(point_count):
                t = step / (point_count - 1)
                one_minus = 1.0 - t
                x = (
                    one_minus * one_minus * start_x
                    + 2.0 * one_minus * t * current.x
                    + t * t * end_x
                )
                y = (
                    one_minus * one_minus * start_y
                    + 2.0 * one_minus * t * current.y
                    + t * t * end_y
                )
                pose = PoseStamped()
                pose.header = copy.deepcopy(header)
                pose.pose.position.x = x
                pose.pose.position.y = y
                pose.pose.position.z = 0.0
                pose.pose.orientation.w = 1.0
                rounded.append(pose)

            turn_path = Path()
            turn_path.header = copy.deepcopy(header)
            turn_path.poses = copy.deepcopy(rounded)
            self._recompute_orientations(turn_path)
            if not self.validate_turn_smoothing_against_costmap:
                return turn_path.poses

            report = self._validate_path_structure(turn_path, check_costmap=True)
            if report['valid']:
                return turn_path.poses

        return []

    def _append_pose_without_duplicate(self, path, pose_stamped):
        if path.poses:
            last = path.poses[-1].pose.position
            current = pose_stamped.pose.position
            if self._distance_2d(last.x, last.y, current.x, current.y) < 1.0e-4:
                return
        path.poses.append(copy.deepcopy(pose_stamped))

    def _trim_path(self, path, start_index):
        trimmed = Path()
        trimmed.header = copy.deepcopy(path.header)
        trimmed.poses = copy.deepcopy(path.poses[start_index:])
        self._stamp_path(trimmed)
        return trimmed

    def _lookup_robot_pose(self, frame_id):
        try:
            transform = self.tf_buffer.lookup_transform(
                frame_id,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=self.tf_lookup_timeout_sec),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not lookup TF %s -> %s: %s'
                % (frame_id, self.robot_base_frame, exc),
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

    def _make_empty_report(self):
        return {
            'valid': False,
            'status': self.STATUS_WAITING_FOR_PATH,
            'reason': 'not_run',
            'frame_id': '',
            'pose_count': 0,
            'segment_count': 0,
            'path_length': 0.0,
            'first_pose': None,
            'last_pose': None,
            'robot_pose': None,
            'nearest_pose': None,
            'nearest_index': -1,
            'distance_to_first': float('nan'),
            'distance_to_nearest': float('nan'),
            'max_jump': 0.0,
            'max_jump_index': -1,
            'max_jump_start_pose': None,
            'max_jump_end_pose': None,
            'start_index': getattr(self, 'selected_start_index', 0),
            'robot_start_used': False,
            'costmap_used': False,
            'costmap_valid': True,
            'costmap_reason': 'not_checked',
            'blocked_pose_count': 0,
            'unknown_pose_count': 0,
            'max_observed_cost': 0,
        }

    def _publish_debug(self, report):
        self.latest_validation_report = report
        self._publish_debug_info(self._format_report(report))
        if self.publish_debug_markers:
            self.debug_markers_pub.publish(self._make_debug_markers(report))

    def _publish_debug_info(self, text):
        self.latest_debug_info = text
        msg = String()
        msg.data = text
        self.debug_info_pub.publish(msg)

    def _format_report(self, report):
        return (
            'validation=%s status=%s reason=%s frame_id=%s total_poses=%d '
            'segments=%d path_length_m=%.3f first=%s last=%s robot=%s '
            'distance_to_first=%s nearest_index=%d distance_to_nearest=%s '
            'start_index=%d max_consecutive_pose_jump=%.3f max_jump_index=%d '
            'follow_path_ready=%s robot_start_used=%s nav_costmap_used=%s '
            'nav_blocked_cells=%d nav_unknown_samples=%d max_observed_cost=%d'
            % (
                'PASS' if report['valid'] else 'FAIL',
                report['status'],
                report['reason'],
                report['frame_id'],
                report['pose_count'],
                report['segment_count'],
                report['path_length'],
                self._format_debug_pose(report['first_pose']),
                self._format_debug_pose(report['last_pose']),
                self._format_debug_pose(report['robot_pose']),
                self._format_float(report['distance_to_first']),
                report['nearest_index'],
                self._format_float(report['distance_to_nearest']),
                report.get('start_index', 0),
                report['max_jump'],
                report['max_jump_index'],
                str(report['valid']).lower(),
                str(report.get('robot_start_used', False)).lower(),
                str(report.get('costmap_used', False)).lower(),
                report.get('blocked_pose_count', 0),
                report.get('unknown_pose_count', 0),
                report.get('max_observed_cost', 0),
            )
        )

    def _make_debug_markers(self, report):
        frame_id = report['frame_id'] or self.global_frame
        markers = self._delete_all_markers(frame_id, 'coverage_debug_cleanup')
        stamp = self.get_clock().now().to_msg()
        marker_id = 1

        for namespace, pose_dict, marker_type, rgba, scale in (
            ('coverage_debug_first_pose', report['first_pose'], Marker.SPHERE, (0.0, 0.9, 0.2, 0.95), 0.16),
            ('coverage_debug_last_pose', report['last_pose'], Marker.CUBE, (1.0, 0.2, 0.05, 0.95), 0.16),
            ('coverage_debug_robot_pose', report['robot_pose'], Marker.ARROW, (0.1, 0.35, 1.0, 0.95), 0.28),
            ('coverage_debug_nearest_pose', report['nearest_pose'], Marker.SPHERE, (1.0, 0.85, 0.0, 0.95), 0.14),
        ):
            if pose_dict is None:
                continue
            markers.markers.append(
                self._make_pose_dict_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    namespace,
                    pose_dict,
                    marker_type,
                    rgba,
                    scale,
                )
            )
            marker_id += 1

        if report['max_jump_start_pose'] and report['max_jump_end_pose']:
            markers.markers.append(
                self._make_line_marker(
                    frame_id,
                    stamp,
                    marker_id,
                    'coverage_debug_largest_jump',
                    report['max_jump_start_pose'],
                    report['max_jump_end_pose'],
                    (1.0, 0.0, 0.0, 0.95),
                    0.04,
                )
            )
            marker_id += 1

        if self.active_path is not None:
            markers.markers.append(
                self._make_path_line_marker(
                    self.active_path,
                    stamp,
                    marker_id,
                    'coverage_debug_active_path',
                    (0.0, 0.85, 1.0, 0.9),
                    0.035,
                    0.06,
                )
            )
            marker_id += 1
        if self.cached_raw_path is not None:
            markers.markers.append(
                self._make_path_line_marker(
                    self.cached_raw_path,
                    stamp,
                    marker_id,
                    'coverage_debug_raw_path',
                    (0.8, 0.8, 0.8, 0.65),
                    0.02,
                    0.03,
                )
            )
            marker_id += 1
        if self.smoothed_path is not None:
            markers.markers.append(
                self._make_path_line_marker(
                    self.smoothed_path,
                    stamp,
                    marker_id,
                    'coverage_debug_smoothed_path',
                    (0.1, 1.0, 0.55, 0.8),
                    0.025,
                    0.05,
                )
            )
            marker_id += 1

        if self.blocked_debug_points:
            marker = Marker()
            marker.header.frame_id = frame_id
            marker.header.stamp = stamp
            marker.ns = 'coverage_debug_blocked_samples'
            marker.id = marker_id
            marker.type = Marker.SPHERE_LIST
            marker.action = Marker.ADD
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.08
            marker.scale.y = 0.08
            marker.scale.z = 0.08
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0
            marker.color.a = 0.9
            for point in self.blocked_debug_points:
                p = copy.deepcopy(point)
                p.z = 0.12
                marker.points.append(p)
            markers.markers.append(marker)
            marker_id += 1

        for section_index, section in enumerate(self.rounded_turn_sections):
            turn_path = Path()
            turn_path.header.frame_id = frame_id
            turn_path.poses = section
            markers.markers.append(
                self._make_path_line_marker(
                    turn_path,
                    stamp,
                    marker_id,
                    'coverage_debug_rounded_turn_%d' % section_index,
                    (1.0, 0.45, 0.0, 0.9),
                    0.04,
                    0.10,
                )
            )
            marker_id += 1

        label_pose = report['robot_pose'] or report['first_pose'] or report['last_pose']
        if label_pose is not None:
            label = Marker()
            label.header.frame_id = frame_id
            label.header.stamp = stamp
            label.ns = 'coverage_debug_status_text'
            label.id = marker_id
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position.x = label_pose['x']
            label.pose.position.y = label_pose['y']
            label.pose.position.z = 0.55
            label.pose.orientation.w = 1.0
            label.scale.z = 0.18
            label.color.r = 0.0 if report['valid'] else 1.0
            label.color.g = 1.0 if report['valid'] else 0.1
            label.color.b = 0.2
            label.color.a = 0.95
            label.text = '%s\n%s' % (self.execution_status, report['reason'])
            markers.markers.append(label)

        return markers

    def _make_path_markers(self, path):
        frame_id = path.header.frame_id or self.global_frame
        markers = self._delete_all_markers(frame_id, 'coverage_path_cleanup')
        if not path.poses:
            return markers
        stamp = self.get_clock().now().to_msg()
        markers.markers.append(
            self._make_path_line_marker(
                path,
                stamp,
                1,
                'coverage_active_path_line',
                (0.0, 0.85, 1.0, 0.95),
                0.035,
                0.05,
            )
        )
        markers.markers.append(
            self._make_pose_marker(
                frame_id,
                stamp,
                2,
                'coverage_active_first_pose',
                path.poses[0],
                Marker.SPHERE,
                (0.0, 0.9, 0.2, 0.95),
                0.16,
            )
        )
        markers.markers.append(
            self._make_pose_marker(
                frame_id,
                stamp,
                3,
                'coverage_active_last_pose',
                path.poses[-1],
                Marker.CUBE,
                (1.0, 0.2, 0.05, 0.95),
                0.16,
            )
        )
        return markers

    def _make_pose_dict_marker(
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

    def _make_pose_marker(
        self,
        frame_id,
        stamp,
        marker_id,
        namespace,
        pose_stamped,
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
        marker.pose = copy.deepcopy(pose_stamped.pose)
        marker.pose.position.z += 0.12
        marker.scale.x = scale
        marker.scale.y = scale
        marker.scale.z = scale
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]
        return marker

    def _make_line_marker(self, frame_id, stamp, marker_id, namespace, start, end, rgba, width):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = stamp
        marker.ns = namespace
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x = width
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]
        for pose_dict in (start, end):
            point = Point()
            point.x = pose_dict['x']
            point.y = pose_dict['y']
            point.z = 0.12
            marker.points.append(point)
        return marker

    def _make_path_line_marker(self, path, stamp, marker_id, namespace, rgba, width, z):
        marker = Marker()
        marker.header.frame_id = path.header.frame_id or self.global_frame
        marker.header.stamp = stamp
        marker.ns = namespace
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x = width
        marker.color.r = rgba[0]
        marker.color.g = rgba[1]
        marker.color.b = rgba[2]
        marker.color.a = rgba[3]
        for pose_stamped in path.poses:
            point = Point()
            point.x = pose_stamped.pose.position.x
            point.y = pose_stamped.pose.position.y
            point.z = z
            marker.points.append(point)
        return marker

    def _delete_all_markers(self, frame_id, namespace):
        marker = Marker()
        marker.header.frame_id = frame_id or self.global_frame
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = namespace
        marker.id = 0
        marker.action = Marker.DELETEALL
        markers = MarkerArray()
        markers.markers.append(marker)
        return markers

    def _publish_empty_paths_and_markers(self):
        empty = Path()
        empty.header.frame_id = self.global_frame
        empty.header.stamp = self.get_clock().now().to_msg()
        self.raw_path_pub.publish(empty)
        self.smoothed_path_pub.publish(empty)
        self.active_path_pub.publish(empty)
        delete_markers = self._delete_all_markers(self.global_frame, 'coverage_cleanup')
        self.debug_markers_pub.publish(delete_markers)
        self.path_markers_pub.publish(delete_markers)

    def _log_follow_path_send(self, path, report, reason):
        first_pose = path.poses[0].pose
        last_pose = path.poses[-1].pose
        robot_pose = report.get('robot_pose')
        self.get_logger().info(
            'Sending final frozen path to Nav2 FollowPath: reason=%s action=%s '
            'controller_id=%s goal_checker_id=%s poses=%d path_length=%.2fm '
            'first=%s last=%s robot=%s start_index=%d. This is FollowPath, '
            'not NavigateThroughPoses.'
            % (
                reason,
                self.follow_path_action_name,
                self.controller_id,
                self.goal_checker_id,
                len(path.poses),
                self._path_length(path),
                self._format_pose(first_pose),
                self._format_pose(last_pose),
                self._format_debug_pose(robot_pose),
                self.selected_start_index,
            )
        )

    def _log_path_summary(self, path, prefix):
        if path is None or not path.poses:
            self.get_logger().info('%s: empty path' % prefix)
            return
        self.get_logger().info(
            '%s: frame_id=%s poses=%d path_length=%.2fm first=%s last=%s'
            % (
                prefix,
                path.header.frame_id,
                len(path.poses),
                self._path_length(path),
                self._format_pose(path.poses[0].pose),
                self._format_pose(path.poses[-1].pose),
            )
        )

    def _nearest_path_pose(self, path, x, y):
        nearest_index = -1
        nearest_distance = float('inf')
        for index, pose_stamped in enumerate(path.poses):
            position = pose_stamped.pose.position
            distance = self._distance_2d(x, y, position.x, position.y)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_index = index
        return nearest_index, nearest_distance

    def _max_jump(self, path):
        max_jump = 0.0
        max_jump_index = -1
        for index in range(1, len(path.poses)):
            previous = path.poses[index - 1].pose.position
            current = path.poses[index].pose.position
            jump = self._distance_2d(previous.x, previous.y, current.x, current.y)
            if jump > max_jump:
                max_jump = jump
                max_jump_index = index - 1
        return max_jump, max_jump_index

    def _path_length(self, path):
        if path is None or len(path.poses) < 2:
            return 0.0
        total = 0.0
        for index in range(1, len(path.poses)):
            previous = path.poses[index - 1].pose.position
            current = path.poses[index].pose.position
            total += self._distance_2d(previous.x, previous.y, current.x, current.y)
        return total

    def _recompute_orientations(self, path):
        for index, pose_stamped in enumerate(path.poses):
            if index + 1 < len(path.poses):
                current = pose_stamped.pose.position
                next_point = path.poses[index + 1].pose.position
                yaw = math.atan2(next_point.y - current.y, next_point.x - current.x)
            elif index > 0:
                previous = path.poses[index - 1].pose.position
                current = pose_stamped.pose.position
                yaw = math.atan2(current.y - previous.y, current.x - previous.x)
            else:
                yaw = 0.0
            pose_stamped.pose.orientation = self._quaternion_from_yaw(yaw)

    def _stamp_path(self, path):
        stamp = self.get_clock().now().to_msg()
        path.header.stamp = stamp
        for pose_stamped in path.poses:
            pose_stamped.header.frame_id = path.header.frame_id
            pose_stamped.header.stamp = stamp

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

    def _format_pose(self, pose):
        return '(x=%.3f y=%.3f yaw=%.2f)' % (
            pose.position.x,
            pose.position.y,
            self._yaw_from_quaternion(pose.orientation),
        )

    def _format_float(self, value):
        if value is None or not math.isfinite(value):
            return 'unavailable'
        return '%.3f' % value

    def _distance_2d(self, x1, y1, x2, y2):
        return math.hypot(x2 - x1, y2 - y1)

    def _normalize_angle(self, angle):
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def _yaw_from_quaternion(self, quaternion):
        siny_cosp = 2.0 * (
            quaternion.w * quaternion.z + quaternion.x * quaternion.y
        )
        cosy_cosp = 1.0 - 2.0 * (
            quaternion.y * quaternion.y + quaternion.z * quaternion.z
        )
        return math.atan2(siny_cosp, cosy_cosp)

    def _quaternion_from_yaw(self, yaw):
        quaternion = PoseStamped().pose.orientation
        quaternion.z = math.sin(yaw * 0.5)
        quaternion.w = math.cos(yaw * 0.5)
        return quaternion

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

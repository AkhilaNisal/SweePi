#!/usr/bin/env python3
"""Execute one frozen coverage path with Nav2 FollowPath."""

import copy
import heapq
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point, PoseStamped, Twist
from nav2_msgs.action import ComputePathToPose, FollowPath, NavigateToPose, SmoothPath
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
    STATUS_SKIPPING_DYNAMIC_OBSTACLE = 'SKIPPING_DYNAMIC_OBSTACLE'
    STATUS_SUCCEEDED = 'SUCCEEDED'
    STATUS_COMPLETED_WITH_SKIPS = 'COMPLETED_WITH_SKIPS'
    STATUS_BLOCKED_DYNAMIC_OBJECT = 'BLOCKED_DYNAMIC_OBJECT'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_PAUSED = 'PAUSED'
    STATUS_STOPPED = 'STOPPED'
    STATUS_RETURNING_HOME = 'RETURNING_HOME'
    STATUS_RETURNED_HOME = 'RETURNED_HOME'

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
        static_map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
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
        self.local_costmap = None
        self.local_costmap_received = False
        self.local_costmap_stamp_monotonic = 0.0
        self.static_map = None
        self.static_map_received = False
        self.static_map_stamp_monotonic = 0.0
        self.rounded_turn_sections = []
        self.blocked_debug_points = []
        self.skipped_segments = []
        self.dynamic_detection_candidate = None
        self.dynamic_confirmed_marker_report = None
        self.dynamic_ignored_static_marker_poses = []
        self.dynamic_candidate_marker_path = None
        self.dynamic_skip_in_progress = False
        self.last_dynamic_skip_check_monotonic = 0.0
        self.dynamic_skip_cancel_requested = False
        self.dynamic_skip_cancel_goal_handle = None
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_pending_original_rejoin_index = None
        self.dynamic_skip_pending_active_rejoin_index = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self.dynamic_skip_counter = 0
        self.dynamic_skip_failure_counter = 0
        self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
        self.dynamic_last_nearest_index = 0
        self.dynamic_skip_pending_monitor_resume_index = None
        self.dynamic_skip_monitor_resume_index = None
        self.dynamic_active_path_is_temporary = False
        self.dynamic_active_original_rejoin_index = None
        self.dynamic_active_rejoin_path_index = None
        self.dynamic_last_temporary_rejoin_refresh_monotonic = 0.0
        self.dynamic_planner_in_flight = False
        self.dynamic_planner_goal_handle = None
        self.dynamic_planner_pending_context = None
        self.dynamic_rejoin_candidates_pending = []
        self.dynamic_connector_attempt_in_progress = False
        self.dynamic_planner_timeout_timer = None
        self.dynamic_planner_request_id = 0
        self.dynamic_controller_blocked_reports_count = 0
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
        self.coverage_stopped = False
        self.coverage_pause_requested = False
        self.coverage_control_cancel_reason = None
        self.home_pose = None
        self.return_home_goal_handle = None
        self.return_home_in_flight = False

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
        self.compute_path_to_pose_client = ActionClient(
            self,
            ComputePathToPose,
            self.compute_path_to_pose_action_name,
        )
        self.navigate_to_pose_client = ActionClient(
            self,
            NavigateToPose,
            self.navigate_to_pose_action_name,
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
        self.local_costmap_sub = self.create_subscription(
            OccupancyGrid,
            self.local_costmap_topic,
            self.local_costmap_callback,
            costmap_qos,
        )
        self.static_map_sub = self.create_subscription(
            OccupancyGrid,
            self.static_map_topic,
            self.static_map_callback,
            static_map_qos,
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
        self.skipped_segments_pub = self.create_publisher(
            MarkerArray,
            self.skipped_segments_topic,
            qos,
        )
        self.dynamic_skip_status_pub = self.create_publisher(
            String,
            self.dynamic_skip_status_topic,
            qos,
        )
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            self.cmd_vel_topic,
            10,
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
        self.pause_service = self.create_service(
            Trigger,
            '/pause_coverage_follow_path',
            self.pause_service_callback,
        )
        self.continue_service = self.create_service(
            Trigger,
            '/continue_coverage_follow_path',
            self.continue_service_callback,
        )
        self.stop_service = self.create_service(
            Trigger,
            '/stop_coverage_follow_path',
            self.stop_service_callback,
        )
        self.return_home_service = self.create_service(
            Trigger,
            '/return_home_coverage_follow_path',
            self.return_home_service_callback,
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
        self.dynamic_timer = None
        if self.enable_dynamic_obstacle_skip:
            dynamic_period = 1.0 / max(0.1, self.dynamic_skip_check_rate_hz)
            self.dynamic_timer = self.create_timer(
                dynamic_period,
                self.dynamic_timer_callback,
            )

        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self.get_logger().info(
            'Coverage FollowPath executor started: action=%s controller_id=%s '
            'smoother_action=%s smoother_id=%s path=%s raw=%s smoothed=%s '
            'active=%s costmap=%s. This mode uses FollowPath, not '
            'NavigateThroughPoses. dynamic_obstacle_skip=%s local_costmap=%s '
            'static_map=%s'
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
                str(self.enable_dynamic_obstacle_skip).lower(),
                self.local_costmap_topic,
                self.static_map_topic,
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
            'skipped_segments_topic': '/coverage_skipped_segments',
            'dynamic_skip_status_topic': '/coverage_dynamic_skip_status',
            'cmd_vel_topic': '/cmd_vel',
            'follow_path_action_name': '/follow_path',
            'navigate_to_pose_action_name': '/navigate_to_pose',
            'controller_id': 'FollowPath',
            'goal_checker_id': '',
            'progress_checker_id': '',
            'global_frame': 'map',
            'robot_base_frame': 'base_link',
            'costmap_topic': '/global_costmap/costmap',
            'robot_radius_m': 0.20,
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
            'enable_dynamic_obstacle_skip': True,
            'local_costmap_topic': '/local_costmap/costmap',
            'static_map_topic': '/map',
            'static_map_occupied_threshold': 50,
            'dynamic_use_static_reference_check': True,
            'static_reference_padding_m': 0.05,
            'dynamic_enable_local_only_inscribed_fallback': True,
            'dynamic_inscribed_cost_threshold': 99,
            'dynamic_inscribed_static_reference_padding_m': 0.05,
            'dynamic_obstacle_cost_threshold': 100,
            'dynamic_obstacle_distance_threshold_m': 0.05,
            'dynamic_treat_unknown_as_blocked': True,
            'dynamic_object_clearance_m': 0.05,
            'dynamic_collision_check_radius_m': 0.0,
            'dynamic_connector_tracking_clearance_m': 0.12,
            'dynamic_use_corridor_for_detection': True,
            'dynamic_monitor_temporary_paths': True,
            'dynamic_connector_allow_blocked_start': True,
            'dynamic_connector_start_grace_m': 0.20,
            'dynamic_refresh_temporary_rejoin': True,
            'dynamic_temporary_rejoin_check_distance_m': 0.80,
            'dynamic_temporary_rejoin_refresh_cooldown_sec': 0.75,
            'dynamic_refine_connector_path': True,
            'dynamic_connector_refinement_iterations': 3,
            'dynamic_connector_refinement_step_m': 0.04,
            'dynamic_connector_refinement_influence_m': 0.45,
            'dynamic_skip_lookahead_m': 0.60,
            'dynamic_skip_padding_m': 0.05,
            'dynamic_rejoin_min_clearance_m': 0.05,
            'dynamic_rejoin_max_search_distance_m': 1.00,
            'dynamic_max_rejoin_candidates': 20,
            'dynamic_required_consecutive_detections': 2,
            'dynamic_min_blocked_pose_count': 2,
            'dynamic_min_blocked_path_length_m': 0.10,
            'dynamic_detection_hysteresis_sec': 0.30,
            'dynamic_validate_rejoin_before_cancel': True,
            'dynamic_cancel_only_if_imminent_blocked': True,
            'dynamic_imminent_block_distance_m': 0.35,
            'dynamic_resume_ignore_index_margin': 5,
            'dynamic_skip_check_rate_hz': 5.0,
            'dynamic_skip_min_remaining_poses': 2,
            'dynamic_skip_max_consecutive_failures': 5,
            'dynamic_skip_replan_cooldown_sec': 3.0,
            'dynamic_progress_search_backtrack_m': 0.20,
            'dynamic_progress_search_forward_m': 3.00,
            'retry_skipped_segments_at_end': False,
            'mark_skipped_segments_uncovered': True,
            'publish_skipped_segments': True,
            'dynamic_use_nav2_planner_connector': True,
            'compute_path_to_pose_action_name': '/compute_path_to_pose',
            'dynamic_planner_id': 'GridBased',
            'dynamic_planner_timeout_sec': 2.0,
            'dynamic_connector_start_with_robot_pose': True,
            'dynamic_connector_goal_tolerance_m': 0.15,
            'dynamic_static_encroachment_tolerance_m': 0.05,
            'dynamic_require_safe_connector': False,
            'dynamic_enable_local_astar_detour': True,
            'dynamic_enable_local_detour': True,
            'dynamic_detour_min_lateral_offset_m': 0.10,
            'dynamic_detour_max_lateral_offset_m': 0.80,
            'dynamic_detour_offset_step_m': 0.05,
            'dynamic_detour_sample_step_m': 0.05,
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
        self.skipped_segments_topic = self._string_param('skipped_segments_topic')
        self.dynamic_skip_status_topic = self._string_param(
            'dynamic_skip_status_topic'
        )
        self.cmd_vel_topic = self._string_param('cmd_vel_topic')
        self.follow_path_action_name = self._string_param('follow_path_action_name')
        self.navigate_to_pose_action_name = self._string_param(
            'navigate_to_pose_action_name'
        )
        self.controller_id = self._string_param('controller_id')
        self.goal_checker_id = self._string_param('goal_checker_id')
        self.progress_checker_id = self._string_param('progress_checker_id')
        self.global_frame = self._string_param('global_frame')
        self.robot_base_frame = self._string_param('robot_base_frame')
        self.costmap_topic = self._string_param('costmap_topic')
        self.robot_radius_m = self._double_param('robot_radius_m')
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
        self.enable_dynamic_obstacle_skip = self._bool_param(
            'enable_dynamic_obstacle_skip'
        )
        self.local_costmap_topic = self._string_param('local_costmap_topic')
        self.static_map_topic = self._string_param('static_map_topic')
        self.static_map_occupied_threshold = self._int_param(
            'static_map_occupied_threshold'
        )
        self.dynamic_use_static_reference_check = self._bool_param(
            'dynamic_use_static_reference_check'
        )
        self.static_reference_padding_m = self._double_param(
            'static_reference_padding_m'
        )
        self.dynamic_enable_local_only_inscribed_fallback = self._bool_param(
            'dynamic_enable_local_only_inscribed_fallback'
        )
        self.dynamic_inscribed_cost_threshold = self._int_param(
            'dynamic_inscribed_cost_threshold'
        )
        self.dynamic_inscribed_static_reference_padding_m = self._double_param(
            'dynamic_inscribed_static_reference_padding_m'
        )
        self.dynamic_obstacle_cost_threshold = self._int_param(
            'dynamic_obstacle_cost_threshold'
        )
        self.dynamic_obstacle_distance_threshold_m = self._double_param(
            'dynamic_obstacle_distance_threshold_m'
        )
        self.dynamic_treat_unknown_as_blocked = self._bool_param(
            'dynamic_treat_unknown_as_blocked'
        )
        self.dynamic_object_clearance_m = self._double_param(
            'dynamic_object_clearance_m'
        )
        self.dynamic_collision_check_radius_m = self._double_param(
            'dynamic_collision_check_radius_m'
        )
        self.dynamic_connector_tracking_clearance_m = self._double_param(
            'dynamic_connector_tracking_clearance_m'
        )
        self.dynamic_use_corridor_for_detection = self._bool_param(
            'dynamic_use_corridor_for_detection'
        )
        self.dynamic_monitor_temporary_paths = self._bool_param(
            'dynamic_monitor_temporary_paths'
        )
        self.dynamic_connector_allow_blocked_start = self._bool_param(
            'dynamic_connector_allow_blocked_start'
        )
        self.dynamic_connector_start_grace_m = self._double_param(
            'dynamic_connector_start_grace_m'
        )
        self.dynamic_refresh_temporary_rejoin = self._bool_param(
            'dynamic_refresh_temporary_rejoin'
        )
        self.dynamic_temporary_rejoin_check_distance_m = self._double_param(
            'dynamic_temporary_rejoin_check_distance_m'
        )
        self.dynamic_temporary_rejoin_refresh_cooldown_sec = self._double_param(
            'dynamic_temporary_rejoin_refresh_cooldown_sec'
        )
        self.dynamic_refine_connector_path = self._bool_param(
            'dynamic_refine_connector_path'
        )
        self.dynamic_connector_refinement_iterations = self._int_param(
            'dynamic_connector_refinement_iterations'
        )
        self.dynamic_connector_refinement_step_m = self._double_param(
            'dynamic_connector_refinement_step_m'
        )
        self.dynamic_connector_refinement_influence_m = self._double_param(
            'dynamic_connector_refinement_influence_m'
        )
        self.dynamic_skip_lookahead_m = self._double_param('dynamic_skip_lookahead_m')
        self.dynamic_skip_padding_m = self._double_param('dynamic_skip_padding_m')
        self.dynamic_rejoin_min_clearance_m = self._double_param(
            'dynamic_rejoin_min_clearance_m'
        )
        self.dynamic_rejoin_max_search_distance_m = self._double_param(
            'dynamic_rejoin_max_search_distance_m'
        )
        self.dynamic_max_rejoin_candidates = self._int_param(
            'dynamic_max_rejoin_candidates'
        )
        self.dynamic_required_consecutive_detections = self._int_param(
            'dynamic_required_consecutive_detections'
        )
        self.dynamic_min_blocked_pose_count = self._int_param(
            'dynamic_min_blocked_pose_count'
        )
        self.dynamic_min_blocked_path_length_m = self._double_param(
            'dynamic_min_blocked_path_length_m'
        )
        self.dynamic_detection_hysteresis_sec = self._double_param(
            'dynamic_detection_hysteresis_sec'
        )
        self.dynamic_validate_rejoin_before_cancel = self._bool_param(
            'dynamic_validate_rejoin_before_cancel'
        )
        self.dynamic_cancel_only_if_imminent_blocked = self._bool_param(
            'dynamic_cancel_only_if_imminent_blocked'
        )
        self.dynamic_imminent_block_distance_m = self._double_param(
            'dynamic_imminent_block_distance_m'
        )
        self.dynamic_resume_ignore_index_margin = self._int_param(
            'dynamic_resume_ignore_index_margin'
        )
        self.dynamic_skip_check_rate_hz = self._double_param(
            'dynamic_skip_check_rate_hz'
        )
        self.dynamic_skip_min_remaining_poses = self._int_param(
            'dynamic_skip_min_remaining_poses'
        )
        self.dynamic_skip_max_consecutive_failures = self._int_param(
            'dynamic_skip_max_consecutive_failures'
        )
        self.dynamic_skip_replan_cooldown_sec = self._double_param(
            'dynamic_skip_replan_cooldown_sec'
        )
        self.dynamic_progress_search_backtrack_m = self._double_param(
            'dynamic_progress_search_backtrack_m'
        )
        self.dynamic_progress_search_forward_m = self._double_param(
            'dynamic_progress_search_forward_m'
        )
        self.retry_skipped_segments_at_end = self._bool_param(
            'retry_skipped_segments_at_end'
        )
        self.mark_skipped_segments_uncovered = self._bool_param(
            'mark_skipped_segments_uncovered'
        )
        self.publish_skipped_segments = self._bool_param('publish_skipped_segments')
        self.dynamic_use_nav2_planner_connector = self._bool_param(
            'dynamic_use_nav2_planner_connector'
        )
        self.compute_path_to_pose_action_name = self._string_param(
            'compute_path_to_pose_action_name'
        )
        self.dynamic_planner_id = self._string_param('dynamic_planner_id')
        self.dynamic_planner_timeout_sec = self._double_param(
            'dynamic_planner_timeout_sec'
        )
        self.dynamic_connector_start_with_robot_pose = self._bool_param(
            'dynamic_connector_start_with_robot_pose'
        )
        self.dynamic_connector_goal_tolerance_m = self._double_param(
            'dynamic_connector_goal_tolerance_m'
        )
        self.dynamic_static_encroachment_tolerance_m = self._double_param(
            'dynamic_static_encroachment_tolerance_m'
        )
        self.dynamic_require_safe_connector = self._bool_param(
            'dynamic_require_safe_connector'
        )
        self.dynamic_enable_local_astar_detour = self._bool_param(
            'dynamic_enable_local_astar_detour'
        )
        self.dynamic_enable_local_detour = self._bool_param(
            'dynamic_enable_local_detour'
        )
        self.dynamic_detour_min_lateral_offset_m = self._double_param(
            'dynamic_detour_min_lateral_offset_m'
        )
        self.dynamic_detour_max_lateral_offset_m = self._double_param(
            'dynamic_detour_max_lateral_offset_m'
        )
        self.dynamic_detour_offset_step_m = self._double_param(
            'dynamic_detour_offset_step_m'
        )
        self.dynamic_detour_sample_step_m = self._double_param(
            'dynamic_detour_sample_step_m'
        )

        self.max_allowed_nav_cost = min(100, max(0, self.max_allowed_nav_cost))
        self.robot_radius_m = max(0.01, self.robot_radius_m)
        self.dynamic_obstacle_cost_threshold = min(
            100,
            max(0, self.dynamic_obstacle_cost_threshold),
        )
        self.dynamic_obstacle_distance_threshold_m = max(
            0.0,
            self.dynamic_obstacle_distance_threshold_m,
        )
        self.dynamic_object_clearance_m = max(0.0, self.dynamic_object_clearance_m)
        if self.dynamic_collision_check_radius_m <= 0.0:
            self.dynamic_collision_check_radius_m = (
                self.robot_radius_m + self.dynamic_object_clearance_m
            )
        self.dynamic_collision_check_radius_m = max(
            self.robot_radius_m,
            self.dynamic_collision_check_radius_m,
        )
        self.dynamic_connector_tracking_clearance_m = max(
            0.0,
            self.dynamic_connector_tracking_clearance_m,
        )
        self.dynamic_connector_start_grace_m = max(
            0.0,
            self.dynamic_connector_start_grace_m,
        )
        self.dynamic_temporary_rejoin_check_distance_m = max(
            self.dynamic_skip_lookahead_m,
            self.dynamic_temporary_rejoin_check_distance_m,
        )
        self.dynamic_temporary_rejoin_refresh_cooldown_sec = max(
            0.0,
            self.dynamic_temporary_rejoin_refresh_cooldown_sec,
        )
        self.dynamic_connector_refinement_iterations = max(
            0,
            self.dynamic_connector_refinement_iterations,
        )
        self.dynamic_connector_refinement_step_m = max(
            0.0,
            self.dynamic_connector_refinement_step_m,
        )
        self.dynamic_connector_refinement_influence_m = max(
            self._get_dynamic_collision_radius_m(),
            self.dynamic_connector_refinement_influence_m,
        )
        self.static_map_occupied_threshold = min(
            100,
            max(0, self.static_map_occupied_threshold),
        )
        self.static_reference_padding_m = max(0.0, self.static_reference_padding_m)
        self.dynamic_inscribed_cost_threshold = min(
            100,
            max(1, self.dynamic_inscribed_cost_threshold),
        )
        self.dynamic_inscribed_static_reference_padding_m = max(
            self.static_reference_padding_m,
            self.dynamic_inscribed_static_reference_padding_m,
        )
        self.max_start_distance_m = max(0.0, self.max_start_distance_m)
        self.max_nearest_path_distance_m = max(0.0, self.max_nearest_path_distance_m)
        self.max_consecutive_pose_jump_m = max(0.01, self.max_consecutive_pose_jump_m)
        self.min_path_poses = max(1, self.min_path_poses)
        self.minimum_path_length_m = max(0.0, self.minimum_path_length_m)
        self.tf_lookup_timeout_sec = max(0.0, self.tf_lookup_timeout_sec)
        self.wait_for_nav2_timeout_sec = max(0.0, self.wait_for_nav2_timeout_sec)
        self.turn_smoothing_radius_m = max(0.0, self.turn_smoothing_radius_m)
        self.max_smoothing_duration_s = max(0.0, self.max_smoothing_duration_s)
        self.dynamic_skip_lookahead_m = max(0.0, self.dynamic_skip_lookahead_m)
        self.dynamic_skip_padding_m = max(0.0, self.dynamic_skip_padding_m)
        self.dynamic_rejoin_min_clearance_m = max(
            0.0,
            self.dynamic_rejoin_min_clearance_m,
        )
        self.dynamic_rejoin_max_search_distance_m = max(
            0.10,
            self.dynamic_rejoin_max_search_distance_m,
        )
        self.dynamic_max_rejoin_candidates = max(1, self.dynamic_max_rejoin_candidates)
        self.dynamic_required_consecutive_detections = max(
            1,
            self.dynamic_required_consecutive_detections,
        )
        self.dynamic_min_blocked_pose_count = max(
            1,
            self.dynamic_min_blocked_pose_count,
        )
        self.dynamic_min_blocked_path_length_m = max(
            0.0,
            self.dynamic_min_blocked_path_length_m,
        )
        self.dynamic_detection_hysteresis_sec = max(
            0.0,
            self.dynamic_detection_hysteresis_sec,
        )
        self.dynamic_imminent_block_distance_m = max(
            0.0,
            self.dynamic_imminent_block_distance_m,
        )
        self.dynamic_resume_ignore_index_margin = max(
            0,
            self.dynamic_resume_ignore_index_margin,
        )
        self.dynamic_skip_check_rate_hz = max(0.1, self.dynamic_skip_check_rate_hz)
        self.dynamic_skip_min_remaining_poses = max(
            1,
            self.dynamic_skip_min_remaining_poses,
        )
        self.dynamic_skip_max_consecutive_failures = max(
            1,
            self.dynamic_skip_max_consecutive_failures,
        )
        self.dynamic_skip_replan_cooldown_sec = max(
            0.0,
            self.dynamic_skip_replan_cooldown_sec,
        )
        self.dynamic_progress_search_backtrack_m = max(
            0.0,
            self.dynamic_progress_search_backtrack_m,
        )
        self.dynamic_progress_search_forward_m = max(
            self.dynamic_skip_lookahead_m,
            self.dynamic_progress_search_forward_m,
        )
        self.dynamic_planner_timeout_sec = max(
            0.1,
            self.dynamic_planner_timeout_sec,
        )
        self.dynamic_connector_goal_tolerance_m = max(
            0.0,
            self.dynamic_connector_goal_tolerance_m,
        )
        self.dynamic_static_encroachment_tolerance_m = max(
            0.0,
            self.dynamic_static_encroachment_tolerance_m,
        )
        self.dynamic_detour_min_lateral_offset_m = max(
            0.0,
            self.dynamic_detour_min_lateral_offset_m,
        )
        self.dynamic_detour_max_lateral_offset_m = max(
            self.dynamic_detour_min_lateral_offset_m,
            self.dynamic_detour_max_lateral_offset_m,
        )
        self.dynamic_detour_offset_step_m = max(
            0.01,
            self.dynamic_detour_offset_step_m,
        )
        self.dynamic_detour_sample_step_m = max(
            0.01,
            self.dynamic_detour_sample_step_m,
        )

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

    def local_costmap_callback(self, msg):
        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring local costmap with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        self.local_costmap = msg
        self.local_costmap_stamp_monotonic = time.monotonic()
        if not self.local_costmap_received:
            self.local_costmap_received = True
            self.get_logger().info(
                'Local costmap received for dynamic obstacle skip: topic=%s '
                'frame=%s size=%dx%d resolution=%.3f threshold=%d '
                'detection_radius=%.3fm unknown_blocked=%s'
                % (
                    self.local_costmap_topic,
                    msg.header.frame_id or self.global_frame,
                    msg.info.width,
                    msg.info.height,
                    msg.info.resolution,
                    self.dynamic_obstacle_cost_threshold,
                    self._get_dynamic_detection_radius_m(),
                    str(self.dynamic_treat_unknown_as_blocked).lower(),
                )
            )

    def static_map_callback(self, msg):
        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring static map with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        self.static_map = msg
        self.static_map_stamp_monotonic = time.monotonic()
        if not self.static_map_received:
            self.static_map_received = True
            self.get_logger().info(
                'Static map received for dynamic obstacle reference: topic=%s '
                'frame=%s size=%dx%d resolution=%.3f occupied_threshold=%d'
                % (
                    self.static_map_topic,
                    msg.header.frame_id or self.global_frame,
                    msg.info.width,
                    msg.info.height,
                    msg.info.resolution,
                    self.static_map_occupied_threshold,
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
        return self._cancel_active_motion_service_response(
            response,
            reason='cancel',
            status=self.STATUS_CANCELED,
            no_active_message='No active SmoothPath or FollowPath goal to cancel',
        )

    def pause_service_callback(self, request, response):
        del request
        if self.execution_status == self.STATUS_PAUSED:
            self._publish_zero_velocity()
            response.success = True
            response.message = 'Coverage is already paused'
            return response

        self.coverage_pause_requested = True
        self.coverage_stopped = False
        canceled, message = self._request_cancel_active_motion('pause')
        self._publish_zero_velocity()
        self._set_status(self.STATUS_PAUSED)
        response.success = True
        response.message = (
            'Coverage paused; robot stopped at current location'
            if canceled
            else 'Coverage paused; %s' % message
        )
        return response

    def continue_service_callback(self, request, response):
        del request
        if self.coverage_stopped:
            response.success = False
            response.message = (
                'Coverage was stopped. Call /reset_coverage_follow_path before '
                'starting a new coverage run.'
            )
            return response
        if self.goal_in_flight or self.smoothing_in_flight:
            response.success = False
            response.message = 'Coverage is already active'
            return response
        if self.return_home_in_flight:
            response.success = False
            response.message = 'Return-home goal is active; wait or stop it first'
            return response

        self.coverage_pause_requested = False
        self.coverage_control_cancel_reason = None
        if self._request_execution('continue_after_pause'):
            response.success = True
            response.message = 'Coverage continuation requested'
        else:
            response.success = False
            response.message = self.latest_path_error
        return response

    def stop_service_callback(self, request, response):
        del request
        self.coverage_stopped = True
        self.coverage_pause_requested = False
        self._request_cancel_return_home()
        canceled, message = self._request_cancel_active_motion('stop')
        self._publish_zero_velocity()
        self._set_status(self.STATUS_STOPPED)
        response.success = True
        response.message = (
            'Coverage stopped; no further coverage will run until reset'
            if canceled
            else 'Coverage stopped; %s' % message
        )
        return response

    def return_home_service_callback(self, request, response):
        del request
        if self.home_pose is None:
            response.success = False
            response.message = (
                'Initial coverage pose is not available yet. Start coverage once '
                'before requesting return home.'
            )
            return response

        self.coverage_stopped = True
        self.coverage_pause_requested = False
        self._request_cancel_active_motion('return_home')
        self._publish_zero_velocity()

        if self.return_home_in_flight:
            response.success = True
            response.message = 'Return-home goal is already active'
            return response

        if not self.navigate_to_pose_client.wait_for_server(
            timeout_sec=self.wait_for_nav2_timeout_sec
        ):
            response.success = False
            response.message = (
                'NavigateToPose action server %s is not available'
                % self.navigate_to_pose_action_name
            )
            self._set_status(self.STATUS_STOPPED)
            return response

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = copy.deepcopy(self.home_pose)
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.behavior_tree = ''

        self.return_home_in_flight = True
        self.return_home_goal_handle = None
        self._set_status(self.STATUS_RETURNING_HOME)
        send_future = self.navigate_to_pose_client.send_goal_async(goal_msg)
        send_future.add_done_callback(self._return_home_goal_response_callback)
        response.success = True
        response.message = 'Return-home goal requested'
        return response

    def _cancel_active_motion_service_response(
        self,
        response,
        reason,
        status,
        no_active_message,
    ):
        canceled, message = self._request_cancel_active_motion(reason)
        if canceled:
            response.success = True
            response.message = message
        else:
            response.success = False
            response.message = no_active_message
        if status is not None and canceled:
            self._set_status(status)
        return response

    def _request_cancel_active_motion(self, reason):
        if self.smoothing_in_flight and self.current_smoothing_goal_handle is not None:
            self.cancel_requested = True
            self.coverage_control_cancel_reason = reason
            self.current_smoothing_goal_handle.cancel_goal_async()
            return True, 'Cancel request sent to active SmoothPath goal'

        if self.goal_in_flight and self.current_goal_handle is not None:
            self.cancel_requested = True
            self.coverage_control_cancel_reason = reason
            self.current_goal_handle.cancel_goal_async()
            return True, 'Cancel request sent to active FollowPath goal'

        self.smoothing_in_flight = False
        self.goal_in_flight = False
        self.current_smoothing_goal_handle = None
        self.current_goal_handle = None
        return False, 'No active SmoothPath or FollowPath goal to cancel'

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
        self.skipped_segments = []
        self.dynamic_detection_candidate = None
        self.dynamic_confirmed_marker_report = None
        self.dynamic_ignored_static_marker_poses = []
        self.dynamic_candidate_marker_path = None
        self.dynamic_skip_in_progress = False
        self.dynamic_skip_cancel_requested = False
        self.dynamic_skip_cancel_goal_handle = None
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self.dynamic_skip_counter = 0
        self.dynamic_skip_failure_counter = 0
        self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
        self.dynamic_last_nearest_index = 0
        self.dynamic_skip_pending_monitor_resume_index = None
        self.dynamic_skip_monitor_resume_index = None
        self.dynamic_active_path_is_temporary = False
        self.dynamic_skip_pending_original_rejoin_index = None
        self.dynamic_skip_pending_active_rejoin_index = None
        self.dynamic_active_original_rejoin_index = None
        self.dynamic_active_rejoin_path_index = None
        self.dynamic_last_temporary_rejoin_refresh_monotonic = 0.0
        self._clear_dynamic_planner_state()
        self.dynamic_controller_blocked_reports_count = 0
        self.selected_start_index = 0
        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self._publish_empty_paths_and_markers()
        self.home_pose = None
        self.coverage_stopped = False
        self.coverage_pause_requested = False
        self.coverage_control_cancel_reason = None
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

    def dynamic_timer_callback(self):
        if not self.enable_dynamic_obstacle_skip:
            return
        self.last_dynamic_skip_check_monotonic = time.monotonic()
        self._dynamic_obstacle_monitor_tick()

    def _request_execution(self, reason):
        if self.coverage_stopped:
            self.latest_path_error = (
                'Coverage has been stopped. Call /reset_coverage_follow_path '
                'before starting a new coverage run.'
            )
            return False

        if self.goal_in_flight or self.smoothing_in_flight:
            self.latest_path_error = 'Coverage FollowPath is already active'
            return False

        if self.cached_raw_path is None:
            self._set_status(self.STATUS_WAITING_FOR_PATH)
            self.latest_path_error = self.latest_path_error or 'No coverage path cached'
            return False

        if not self._remember_home_pose_if_needed():
            self.latest_path_error = (
                'Cannot start coverage because initial robot pose is unavailable'
            )
            return False

        self.coverage_pause_requested = False
        self.coverage_control_cancel_reason = None
        self.skipped_segments = []
        self.dynamic_detection_candidate = None
        self.dynamic_confirmed_marker_report = None
        self.dynamic_ignored_static_marker_poses = []
        self.dynamic_candidate_marker_path = None
        self.dynamic_skip_in_progress = False
        self.dynamic_skip_cancel_requested = False
        self.dynamic_skip_cancel_goal_handle = None
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self.dynamic_skip_counter = 0
        self.dynamic_skip_failure_counter = 0
        self.last_dynamic_skip_check_monotonic = 0.0
        self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
        self.dynamic_last_nearest_index = 0
        self.dynamic_skip_pending_monitor_resume_index = None
        self.dynamic_skip_monitor_resume_index = None
        self.dynamic_active_path_is_temporary = False
        self.dynamic_skip_pending_original_rejoin_index = None
        self.dynamic_skip_pending_active_rejoin_index = None
        self.dynamic_active_original_rejoin_index = None
        self.dynamic_active_rejoin_path_index = None
        self.dynamic_last_temporary_rejoin_refresh_monotonic = 0.0
        self._clear_dynamic_planner_state()
        self.dynamic_controller_blocked_reports_count = 0
        if self.publish_skipped_segments:
            self._publish_skipped_segment_markers()

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

        if self.coverage_control_cancel_reason in ('pause', 'stop', 'return_home'):
            self.get_logger().info(
                'Ignoring SmoothPath result after %s request'
                % self.coverage_control_cancel_reason
            )
            self.coverage_control_cancel_reason = None
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
            check_costmap=(
                self.check_smooth_path_for_collisions
                and not self._is_dynamic_rejoin_reason(reason)
            ),
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
        now = time.monotonic()
        self.execution_start_monotonic = now
        self.last_distance_to_goal = None
        self.latest_feedback_text = ''
        self.latest_path_error = ''
        self.dynamic_last_nearest_index = 0
        self.dynamic_controller_blocked_reports_count = 0
        if self._is_dynamic_rejoin_reason(reason):
            self.dynamic_active_path_is_temporary = True
            self.dynamic_active_original_rejoin_index = (
                self.dynamic_skip_pending_original_rejoin_index
            )
            self.dynamic_active_rejoin_path_index = (
                self.dynamic_skip_pending_active_rejoin_index
            )
            self.dynamic_skip_pending_original_rejoin_index = None
            self.dynamic_skip_pending_active_rejoin_index = None
            if self.dynamic_monitor_temporary_paths:
                self.dynamic_skip_monitor_resume_index = None
                self.dynamic_skip_pending_monitor_resume_index = None
                self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
            else:
                self.dynamic_skip_monitor_resume_index = (
                    self.dynamic_skip_pending_monitor_resume_index
                )
                self.dynamic_skip_pending_monitor_resume_index = None
                self.dynamic_skip_monitor_suppressed_until_monotonic = (
                    now + self.dynamic_skip_replan_cooldown_sec
                )
        else:
            self.dynamic_active_path_is_temporary = False
            self.dynamic_active_original_rejoin_index = None
            self.dynamic_active_rejoin_path_index = None
            self.dynamic_skip_pending_original_rejoin_index = None
            self.dynamic_skip_pending_active_rejoin_index = None
            self.dynamic_skip_monitor_resume_index = None
            self.dynamic_skip_pending_monitor_resume_index = None
            self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
        self._set_status(self.STATUS_EXECUTING)

        self._log_follow_path_send(path, report, reason)
        send_goal_future = self.follow_path_client.send_goal_async(
            goal_msg,
            feedback_callback=self._follow_path_feedback_callback,
        )
        send_goal_future.add_done_callback(
            lambda future, reason=reason: self._goal_response_callback(
                future,
                reason,
            )
        )
        return True

    def _goal_response_callback(self, future, reason=''):
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
        if self._is_dynamic_rejoin_reason(reason):
            self._clear_dynamic_skip_temporary_state()
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda result_future, goal_handle=goal_handle: self._result_callback(
                result_future,
                goal_handle,
            )
        )

    def _is_dynamic_rejoin_reason(self, reason):
        return (
            reason.startswith('dynamic_obstacle_skip_rejoin')
            or reason.startswith('dynamic_obstacle_bypass_rejoin')
        )

    def _result_callback(self, future, goal_handle=None):
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

        dynamic_cancel_goal = (
            goal_handle is not None
            and goal_handle is self.dynamic_skip_cancel_goal_handle
        )
        if dynamic_cancel_goal:
            self.get_logger().info(
                '[DYNAMIC_SKIP] ignored terminal FollowPath result from '
                'pre-skip goal'
            )
            self.dynamic_skip_cancel_goal_handle = None
            return

        if (
            goal_handle is not None
            and self.current_goal_handle is not None
            and goal_handle is not self.current_goal_handle
        ):
            self.get_logger().info(
                '[DYNAMIC_SKIP] ignored stale FollowPath result from a '
                'previous goal'
            )
            return

        if status == GoalStatus.STATUS_CANCELED and (
            self.dynamic_skip_cancel_final_status
            == self.STATUS_BLOCKED_DYNAMIC_OBJECT
            or self.execution_status == self.STATUS_BLOCKED_DYNAMIC_OBJECT
        ):
            self.get_logger().info(
                '[DYNAMIC_SKIP] ignoring cancel result because dynamic stop '
                'status is BLOCKED_DYNAMIC_OBJECT'
            )
            return

        if status == GoalStatus.STATUS_CANCELED and (
            self.dynamic_skip_cancel_requested
            or self.dynamic_skip_in_progress
        ):
            self.get_logger().info(
                '[DYNAMIC_SKIP] ignored FollowPath canceled result from '
                'dynamic skip cancel'
            )
            return

        if self.coverage_control_cancel_reason in ('pause', 'stop', 'return_home'):
            reason = self.coverage_control_cancel_reason
            self.get_logger().info(
                'Ignoring FollowPath terminal result after %s request' % reason
            )
            self.goal_in_flight = False
            self.current_goal_handle = None
            self.cancel_requested = False
            self.coverage_control_cancel_reason = None
            if reason == 'pause':
                self._set_status(self.STATUS_PAUSED)
            elif reason == 'stop':
                self._set_status(self.STATUS_STOPPED)
            return

        if status == GoalStatus.STATUS_SUCCEEDED and error_code == 0:
            self._finish_execution(self.STATUS_SUCCEEDED)
            return

        if status == GoalStatus.STATUS_CANCELED or self.cancel_requested:
            self._finish_execution(self.STATUS_CANCELED)
            return

        recoverable_error_codes = {104, 105, 106, 107}
        if error_code in recoverable_error_codes and self.enable_dynamic_obstacle_skip:
            self.dynamic_controller_blocked_reports_count += 1
            self.goal_in_flight = False
            self.current_goal_handle = None
            report = self._detect_dynamic_blocked_interval(
                self.active_path,
                force_confirm=True,
            )
            if report and report['blocked']:
                if self._start_dynamic_skip_after_failure(
                    report,
                    error_code,
                    error_label,
                ):
                    return
            text = (
                '[DYNAMIC_SKIP] recoverable FollowPath error %d %s did not '
                'match a confirmed local-only obstacle; reason=%s '
                'local_lethal_count=%d local_inscribed_count=%d '
                'dynamic_only_blocked_count=%d'
                % (
                    error_code,
                    error_label,
                    report.get('reason', 'no_detection_report') if report else 'none',
                    report.get('local_lethal_count', 0) if report else 0,
                    report.get('local_inscribed_count', 0) if report else 0,
                    report.get('dynamic_only_blocked_count', 0) if report else 0,
                )
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)

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
        final_status = status
        if status == self.STATUS_SUCCEEDED and self.skipped_segments:
            final_status = self.STATUS_COMPLETED_WITH_SKIPS

        self._clear_dynamic_planner_state()
        self.goal_in_flight = False
        self.current_goal_handle = None
        self.cancel_requested = False
        self.dynamic_skip_cancel_requested = False
        self.dynamic_skip_cancel_goal_handle = None
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self.dynamic_skip_in_progress = False
        self.dynamic_detection_candidate = None
        self.dynamic_candidate_marker_path = None
        self.dynamic_skip_pending_monitor_resume_index = None
        self.dynamic_skip_monitor_resume_index = None
        self.dynamic_skip_monitor_suppressed_until_monotonic = 0.0
        self.dynamic_active_path_is_temporary = False
        self.dynamic_skip_pending_original_rejoin_index = None
        self.dynamic_skip_pending_active_rejoin_index = None
        self.dynamic_active_original_rejoin_index = None
        self.dynamic_active_rejoin_path_index = None
        self.dynamic_last_temporary_rejoin_refresh_monotonic = 0.0
        self.execution_start_monotonic = None
        self._set_status(final_status)

        if final_status == self.STATUS_COMPLETED_WITH_SKIPS:
            summary = self._skipped_summary_text(completed_with_skips=True)
            self.get_logger().warn(
                '[COVERAGE_DONE] status=COMPLETED_WITH_SKIPS skipped_segments=%d '
                'skipped_distance_m=%.3f'
                % (len(self.skipped_segments), self._skipped_distance_m())
            )
            self._publish_dynamic_skip_status(
                '[COVERAGE_DONE] status=COMPLETED_WITH_SKIPS %s' % summary
            )
            self._publish_skipped_segment_markers()
        elif final_status == self.STATUS_BLOCKED_DYNAMIC_OBJECT:
            self._publish_dynamic_skip_status(
                '[COVERAGE_DONE] status=BLOCKED_DYNAMIC_OBJECT %s'
                % self._skipped_summary_text(completed_with_skips=False)
            )
        elif final_status == self.STATUS_SUCCEEDED:
            self._publish_debug_info(
                '[COVERAGE_DONE] SUCCEEDED %s'
                % self._skipped_summary_text(completed_with_skips=False)
            )

    def _remember_home_pose_if_needed(self):
        if self.home_pose is not None:
            return True
        pose = self._lookup_robot_pose(self.global_frame)
        if pose is None:
            return False
        self.home_pose = copy.deepcopy(pose)
        self.home_pose.header.frame_id = self.global_frame
        self.home_pose.header.stamp = self.get_clock().now().to_msg()
        self.get_logger().info(
            'Coverage home pose recorded at x=%.3f y=%.3f'
            % (
                self.home_pose.pose.position.x,
                self.home_pose.pose.position.y,
            )
        )
        return True

    def _publish_zero_velocity(self):
        if hasattr(self, 'cmd_vel_pub'):
            self.cmd_vel_pub.publish(Twist())

    def _request_cancel_return_home(self):
        if self.return_home_in_flight and self.return_home_goal_handle is not None:
            self.return_home_goal_handle.cancel_goal_async()
            return True
        return False

    def _return_home_goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.return_home_in_flight = False
            self.return_home_goal_handle = None
            self.get_logger().error('Return-home goal response failed: %s' % exc)
            self._set_status(self.STATUS_FAILED)
            return

        if not goal_handle.accepted:
            self.return_home_in_flight = False
            self.return_home_goal_handle = None
            self.get_logger().warn('Return-home goal was rejected by Nav2')
            self._set_status(self.STATUS_FAILED)
            return

        self.return_home_goal_handle = goal_handle
        self.get_logger().info('Return-home goal accepted by Nav2')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._return_home_result_callback)

    def _return_home_result_callback(self, future):
        self.return_home_in_flight = False
        self.return_home_goal_handle = None
        try:
            wrapped_result = future.result()
        except Exception as exc:
            self.get_logger().error('Return-home result failed: %s' % exc)
            self._set_status(self.STATUS_FAILED)
            return

        if wrapped_result.status == GoalStatus.STATUS_SUCCEEDED:
            self._publish_zero_velocity()
            self._set_status(self.STATUS_RETURNED_HOME)
            self.get_logger().info('Return-home completed')
        elif wrapped_result.status == GoalStatus.STATUS_CANCELED:
            self._publish_zero_velocity()
            self._set_status(self.STATUS_STOPPED)
            self.get_logger().info('Return-home canceled')
        else:
            self._publish_zero_velocity()
            self._set_status(self.STATUS_FAILED)
            self.get_logger().warn(
                'Return-home failed with status=%d' % wrapped_result.status
            )

    def _run_preflight_validation(self, path, check_costmap=True):
        report = self._validate_path_structure(path, check_costmap=check_costmap)
        if not report['valid']:
            return report

        robot_pose_stamped = self._lookup_robot_pose(self.global_frame)
        if robot_pose_stamped is None:
            report['valid'] = False
            report['status'] = self.STATUS_FAILED
            report['reason'] = (
                'TF %s -> %s unavailable'
                % (self.global_frame, self.robot_base_frame)
            )
            return report

        robot_pose = self._pose_debug_dict(robot_pose_stamped.pose)
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

    def _dynamic_obstacle_monitor_tick(self):
        if self.execution_status != self.STATUS_EXECUTING:
            return
        if not self.goal_in_flight:
            return
        if self.current_goal_handle is None:
            return
        if self.dynamic_skip_in_progress:
            return
        if self.active_path is None or len(self.active_path.poses) < 2:
            return
        if self.local_costmap is None:
            now = time.monotonic()
            if now - getattr(self, 'last_dynamic_skip_waiting_log', 0.0) >= 5.0:
                self.last_dynamic_skip_waiting_log = now
                self._publish_dynamic_skip_status(
                    'dynamic skip waiting for local costmap'
                )
            self.get_logger().info(
                'dynamic skip waiting for local costmap',
                throttle_duration_sec=5.0,
            )
            return

        now = time.monotonic()
        if now < self.dynamic_skip_monitor_suppressed_until_monotonic:
            robot_pose = self._lookup_robot_pose(self._path_frame(self.active_path))
            if robot_pose is not None:
                self._find_dynamic_monitor_nearest_path_index(
                    self.active_path,
                    robot_pose,
                )
            self.get_logger().debug(
                '[DYNAMIC_SKIP] monitor cooldown active after rejoin goal',
                throttle_duration_sec=2.0,
            )
            return

        if self._refresh_dynamic_temporary_rejoin_if_needed():
            return

        report = self._detect_dynamic_blocked_interval(self.active_path)
        if not report or not report['blocked']:
            return

        self._start_dynamic_skip(report)

    def _make_sample_pose(self, frame_id, x, y):
        pose = PoseStamped()
        pose.header.frame_id = frame_id or self.global_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.w = 1.0
        return pose

    def _validate_dynamic_candidate_against_local_costmap(self, path):
        report = {
            'valid': True,
            'reason': 'ok',
            'local_checked_samples': 0,
            'local_outside_samples': 0,
            'local_blocked_samples': 0,
            'local_unknown_samples': 0,
            'max_observed_cost': 0,
        }
        if self.local_costmap is None:
            report['valid'] = False
            report['reason'] = 'local_costmap_unavailable'
            return report

        resolution = self.local_costmap.info.resolution
        if resolution <= 0.0:
            report['valid'] = False
            report['reason'] = 'invalid_local_costmap_resolution'
            return report

        path_frame = self._path_frame(path)
        sample_step = max(0.01, resolution * 0.5)
        sample_number = 0

        def check_sample(x, y, allow_blocked_start=False):
            nonlocal sample_number
            pose = self._make_sample_pose(path_frame, x, y)
            cost_info = self._get_costmap_cost(self.local_costmap, pose)
            max_cost = self._effective_dynamic_cost(cost_info['cost'])
            report['max_observed_cost'] = max(
                report['max_observed_cost'],
                max_cost,
            )

            if not cost_info['valid']:
                if cost_info['reason'] == 'tf_unavailable':
                    report['valid'] = False
                    report['reason'] = 'local_costmap_tf_unavailable'
                    return False
                report['local_outside_samples'] += 1
                sample_number += 1
                return True

            if not cost_info['inside']:
                report['local_outside_samples'] += 1
                sample_number += 1
                return True

            report['local_checked_samples'] += 1
            if cost_info['cost'] < 0:
                report['local_unknown_samples'] += 1

            if self._is_dynamic_cost_blocked(cost_info['cost']):
                if allow_blocked_start and sample_number == 0:
                    sample_number += 1
                    return True
                report['local_blocked_samples'] += 1
                report['valid'] = False
                report['reason'] = (
                    'candidate local bypass blocked: sample=%d cost=%d '
                    'mx=%d my=%d max_observed_cost=%d'
                    % (
                        sample_number,
                        int(cost_info['cost']),
                        cost_info['mx'],
                        cost_info['my'],
                        report['max_observed_cost'],
                    )
                )
                return False

            sample_number += 1
            return True

        for index, pose_stamped in enumerate(path.poses):
            position = pose_stamped.pose.position
            if not check_sample(
                position.x,
                position.y,
                allow_blocked_start=(index == 0),
            ):
                return report

            if index == 0:
                continue

            previous = path.poses[index - 1].pose.position
            distance = self._distance_2d(
                previous.x,
                previous.y,
                position.x,
                position.y,
            )
            steps = max(1, int(math.ceil(distance / sample_step)))
            for step in range(1, steps):
                ratio = step / steps
                x = previous.x + ratio * (position.x - previous.x)
                y = previous.y + ratio * (position.y - previous.y)
                if not check_sample(x, y):
                    return report

        if report['local_checked_samples'] == 0:
            report['valid'] = False
            report['reason'] = 'candidate had no samples inside local_costmap'
        return report

    def _validate_dynamic_candidate_against_global_static_reference(self, path):
        report = {
            'valid': True,
            'reason': 'ok',
            'global_checked_samples': 0,
            'global_blocked_samples': 0,
            'global_unknown_samples': 0,
            'global_dynamic_layer_ignored_samples': 0,
            'global_static_blocked_samples': 0,
            'max_observed_cost': 0,
        }
        if self.nav_costmap is None:
            report['valid'] = not self.require_costmap_for_validation
            report['reason'] = 'global costmap has not been received'
            return report

        costmap_frame = self.nav_costmap.header.frame_id or self.global_frame
        path_frame = self._path_frame(path)
        if costmap_frame != path_frame:
            report['valid'] = False
            report['reason'] = (
                'global costmap frame "%s" does not match path frame "%s"'
                % (costmap_frame, path_frame)
            )
            return report

        resolution = self.nav_costmap.info.resolution
        if resolution <= 0.0:
            report['valid'] = False
            report['reason'] = 'invalid_global_costmap_resolution'
            return report

        sample_step = max(0.01, resolution * 0.5)

        def check_sample(x, y):
            pose = self._make_sample_pose(path_frame, x, y)
            cost_info = self._costmap_value_at(x, y)
            report['global_checked_samples'] += 1
            report['max_observed_cost'] = max(
                report['max_observed_cost'],
                int(cost_info['cost']),
            )
            if cost_info['unknown']:
                report['global_unknown_samples'] += 1

            if not cost_info['blocked']:
                return True

            report['global_blocked_samples'] += 1
            if cost_info['unknown']:
                report['valid'] = False
                report['reason'] = (
                    'candidate crosses unknown global costmap sample treated '
                    'as blocked'
                )
                return False

            static_status = self._static_reference_status_near_pose(
                pose,
                self.static_reference_padding_m,
            )
            if static_status['known_static']:
                report['global_static_blocked_samples'] += 1
                report['valid'] = False
                report['reason'] = (
                    'candidate crosses known static obstacle: cost=%d '
                    'static_max=%d'
                    % (int(cost_info['cost']), static_status['max_value'])
                )
                return False

            if static_status['free']:
                report['global_dynamic_layer_ignored_samples'] += 1
                return True

            report['valid'] = False
            report['reason'] = (
                'candidate global blocked sample is not static-map-free: '
                'cost=%d static_reason=%s'
                % (int(cost_info['cost']), static_status['reason'])
            )
            return False

        for index, pose_stamped in enumerate(path.poses):
            position = pose_stamped.pose.position
            if not check_sample(position.x, position.y):
                return report

            if index == 0:
                continue

            previous = path.poses[index - 1].pose.position
            distance = self._distance_2d(
                previous.x,
                previous.y,
                position.x,
                position.y,
            )
            steps = max(1, int(math.ceil(distance / sample_step)))
            for step in range(1, steps):
                ratio = step / steps
                x = previous.x + ratio * (position.x - previous.x)
                y = previous.y + ratio * (position.y - previous.y)
                if not check_sample(x, y):
                    return report

        if report['global_dynamic_layer_ignored_samples'] > 0:
            report['reason'] = (
                'ok_ignored_live_global_dynamic_samples=%d'
                % report['global_dynamic_layer_ignored_samples']
            )
        return report

    def _reject_dynamic_rejoin_candidate(self, report):
        text = (
            '[DYNAMIC_VALIDATE] candidate rejected before cancel reason=%s'
            % report.get('reason', 'invalid_candidate')
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        return False, report

    def _sample_path_poses(self, path, sample_step_m, include_distance=False):
        if path is None or not path.poses:
            return []

        samples = []
        step_m = max(0.01, sample_step_m)
        if include_distance:
            samples.append((copy.deepcopy(path.poses[0]), 0.0))
        else:
            samples.append(copy.deepcopy(path.poses[0]))

        distance_along = 0.0
        for index in range(1, len(path.poses)):
            previous = path.poses[index - 1].pose.position
            pose_stamped = path.poses[index]
            current = pose_stamped.pose.position
            distance = self._distance_2d(
                previous.x,
                previous.y,
                current.x,
                current.y,
            )
            if distance <= 1.0e-6:
                continue
            steps = max(1, int(math.ceil(distance / step_m)))
            for step in range(1, steps + 1):
                ratio = step / steps
                if step == steps:
                    sample = copy.deepcopy(pose_stamped)
                else:
                    sample = PoseStamped()
                    sample.header = copy.deepcopy(path.header)
                    sample.pose.position.x = (
                        previous.x + ratio * (current.x - previous.x)
                    )
                    sample.pose.position.y = (
                        previous.y + ratio * (current.y - previous.y)
                    )
                    sample.pose.position.z = 0.0
                    sample.pose.orientation.w = 1.0
                sample_distance = distance_along + distance * ratio
                if include_distance:
                    samples.append((sample, sample_distance))
                else:
                    samples.append(sample)
            distance_along += distance
        return samples

    def _get_dynamic_collision_radius_m(self):
        return max(
            self.robot_radius_m,
            self.dynamic_collision_check_radius_m,
            self.robot_radius_m + self.dynamic_object_clearance_m,
        )

    def _get_dynamic_tracking_radius_m(self):
        return self._get_dynamic_collision_radius_m() + max(
            0.0,
            self.dynamic_connector_tracking_clearance_m,
        )

    def _get_dynamic_detection_radius_m(self):
        if self.dynamic_use_corridor_for_detection:
            return self._get_dynamic_collision_radius_m()
        return self.dynamic_obstacle_distance_threshold_m

    def _check_local_corridor_at_pose(self, pose_stamped, collision_radius_m):
        if self.local_costmap is None:
            return {
                'valid': False,
                'inside': False,
                'blocked': False,
                'reason': 'local_costmap_unavailable',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_cost': 0,
            }

        costmap_frame = self.local_costmap.header.frame_id or self.global_frame
        pose_in_costmap = self._transform_pose_to_frame(pose_stamped, costmap_frame)
        if pose_in_costmap is None:
            return {
                'valid': False,
                'inside': False,
                'blocked': False,
                'reason': 'local_costmap_tf_unavailable',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_cost': 100,
            }

        position = pose_in_costmap.pose.position
        cell = self._world_to_costmap_cell(self.local_costmap, position.x, position.y)
        if cell is None:
            return {
                'valid': True,
                'inside': False,
                'blocked': False,
                'reason': 'outside_local_costmap',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_cost': 0,
            }

        resolution = self.local_costmap.info.resolution
        if resolution <= 0.0:
            return {
                'valid': False,
                'inside': True,
                'blocked': False,
                'reason': 'invalid_local_costmap_resolution',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_cost': 100,
            }

        center_mx, center_my = cell
        radius_cells = int(math.ceil(collision_radius_m / resolution))
        include_distance_m = collision_radius_m + resolution * 0.5 + 1.0e-9
        checked_cells = 0
        unknown_cells = 0
        max_cost = 0
        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                mx = center_mx + dx
                my = center_my + dy
                if not in_bounds(
                    mx,
                    my,
                    self.local_costmap.info.width,
                    self.local_costmap.info.height,
                ):
                    continue

                cell_x, cell_y = self._costmap_cell_center(
                    self.local_costmap,
                    mx,
                    my,
                )
                if (
                    self._distance_2d(position.x, position.y, cell_x, cell_y)
                    > include_distance_m
                ):
                    continue

                checked_cells += 1
                index = map_to_flat_index(mx, my, self.local_costmap.info.width)
                cost = int(self.local_costmap.data[index])
                max_cost = max(max_cost, self._effective_dynamic_cost(cost))
                if cost < 0:
                    unknown_cells += 1
                if self._is_local_lethal_dynamic_cell(cost):
                    return {
                        'valid': True,
                        'inside': True,
                        'blocked': True,
                        'reason': 'local_lethal_cell_in_robot_corridor',
                        'checked_cells': checked_cells,
                        'unknown_cells': unknown_cells,
                        'max_cost': max_cost,
                    }

        return {
            'valid': True,
            'inside': True,
            'blocked': False,
            'reason': 'local_corridor_clear',
            'checked_cells': checked_cells,
            'unknown_cells': unknown_cells,
            'max_cost': max_cost,
        }

    def _check_static_corridor_at_pose(self, pose_stamped, radius_m):
        if not self.dynamic_use_static_reference_check:
            return {
                'valid': True,
                'blocked': False,
                'reason': 'static_reference_disabled',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_value': 0,
            }
        if self.static_map is None:
            return {
                'valid': False,
                'blocked': False,
                'reason': 'static_map_unavailable',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_value': 0,
            }

        static_frame = self.static_map.header.frame_id or self.global_frame
        pose_in_static = self._transform_pose_to_frame(pose_stamped, static_frame)
        if pose_in_static is None:
            return {
                'valid': False,
                'blocked': False,
                'reason': 'static_map_tf_unavailable',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_value': 0,
            }

        position = pose_in_static.pose.position
        cell = self._world_to_costmap_cell(self.static_map, position.x, position.y)
        if cell is None:
            return {
                'valid': False,
                'blocked': False,
                'reason': 'outside_static_map',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_value': 0,
            }

        resolution = self.static_map.info.resolution
        if resolution <= 0.0:
            return {
                'valid': False,
                'blocked': False,
                'reason': 'invalid_static_map_resolution',
                'checked_cells': 0,
                'unknown_cells': 0,
                'max_value': 0,
            }

        center_mx, center_my = cell
        radius_cells = int(math.ceil(radius_m / resolution))
        include_distance_m = radius_m + resolution * 0.5 + 1.0e-9
        checked_cells = 0
        unknown_cells = 0
        max_value = 0
        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                mx = center_mx + dx
                my = center_my + dy
                if not in_bounds(
                    mx,
                    my,
                    self.static_map.info.width,
                    self.static_map.info.height,
                ):
                    continue

                cell_x, cell_y = self._costmap_cell_center(self.static_map, mx, my)
                if (
                    self._distance_2d(position.x, position.y, cell_x, cell_y)
                    > include_distance_m
                ):
                    continue

                checked_cells += 1
                index = map_to_flat_index(mx, my, self.static_map.info.width)
                value = int(self.static_map.data[index])
                if value < 0:
                    unknown_cells += 1
                    if self.dynamic_treat_unknown_as_blocked:
                        return {
                            'valid': True,
                            'blocked': True,
                            'reason': 'unknown_static_cell_in_robot_corridor',
                            'checked_cells': checked_cells,
                            'unknown_cells': unknown_cells,
                            'max_value': max_value,
                        }
                    continue

                max_value = max(max_value, value)
                if value >= self.static_map_occupied_threshold:
                    return {
                        'valid': True,
                        'blocked': True,
                        'reason': 'static_occupied_cell_in_robot_corridor',
                        'checked_cells': checked_cells,
                        'unknown_cells': unknown_cells,
                        'max_value': max_value,
                    }

        return {
            'valid': True,
            'blocked': False,
            'reason': 'static_corridor_clear',
            'checked_cells': checked_cells,
            'unknown_cells': unknown_cells,
            'max_value': max_value,
        }

    def _validate_connector_corridor(
        self,
        path,
        use_local_costmap=True,
        use_static_map=True,
    ):
        report = {
            'valid': True,
            'reason': 'ok',
            'local_checked_samples': 0,
            'local_outside_samples': 0,
            'local_blocked_samples': 0,
            'local_unknown_samples': 0,
            'tracking_clearance_blocked_samples': 0,
            'local_start_grace_blocked_samples': 0,
            'tracking_start_grace_blocked_samples': 0,
            'static_checked_samples': 0,
            'static_blocked_samples': 0,
            'static_unknown_samples': 0,
            'max_observed_cost': 0,
            'max_static_value': 0,
            'collision_radius_m': self._get_dynamic_collision_radius_m(),
            'tracking_radius_m': self._get_dynamic_tracking_radius_m(),
        }
        if path is None or len(path.poses) < 2:
            report['valid'] = False
            report['reason'] = 'connector_path_too_short'
            return report

        collision_radius = self._get_dynamic_collision_radius_m()
        tracking_radius = self._get_dynamic_tracking_radius_m()
        start_grace_m = (
            self.dynamic_connector_start_grace_m
            if self.dynamic_connector_allow_blocked_start
            else 0.0
        )
        static_radius = max(
            self.robot_radius_m,
            self.robot_radius_m + self.static_reference_padding_m,
        )
        samples = self._sample_path_poses(
            path,
            max(0.01, self.dynamic_detour_sample_step_m),
            include_distance=True,
        )
        for sample_index, (sample, distance_along) in enumerate(samples):
            inside_start_grace = (
                self.dynamic_connector_allow_blocked_start
                and distance_along <= start_grace_m + 1.0e-6
            )
            if use_local_costmap:
                local = self._check_local_corridor_at_pose(sample, collision_radius)
                report['max_observed_cost'] = max(
                    report['max_observed_cost'],
                    local.get('max_cost', 0),
                )
                if not local['valid']:
                    report['valid'] = False
                    report['reason'] = local['reason']
                    return report
                if not local['inside']:
                    report['local_outside_samples'] += 1
                else:
                    report['local_checked_samples'] += 1
                    report['local_unknown_samples'] += local.get(
                        'unknown_cells',
                        0,
                    )
                if local['blocked']:
                    report['local_blocked_samples'] += 1
                    if inside_start_grace:
                        report['local_start_grace_blocked_samples'] += 1
                    else:
                        report['valid'] = False
                        report['reason'] = (
                            '%s sample=%d distance=%.3f collision_radius=%.3f'
                            % (
                                local['reason'],
                                sample_index,
                                distance_along,
                                collision_radius,
                            )
                        )
                        return report

                if tracking_radius > collision_radius + 1.0e-6:
                    tracking = self._check_local_corridor_at_pose(
                        sample,
                        tracking_radius,
                    )
                    report['max_observed_cost'] = max(
                        report['max_observed_cost'],
                        tracking.get('max_cost', 0),
                    )
                    if not tracking['valid']:
                        report['valid'] = False
                        report['reason'] = tracking['reason']
                        return report
                    if tracking['inside'] and tracking['blocked']:
                        report['tracking_clearance_blocked_samples'] += 1
                        if inside_start_grace:
                            report[
                                'tracking_start_grace_blocked_samples'
                            ] += 1

            if use_static_map:
                static = self._check_static_corridor_at_pose(sample, static_radius)
                report['max_static_value'] = max(
                    report['max_static_value'],
                    static.get('max_value', 0),
                )
                if not static['valid']:
                    report['valid'] = False
                    report['reason'] = static['reason']
                    return report
                report['static_checked_samples'] += 1
                report['static_unknown_samples'] += static.get('unknown_cells', 0)
                if static['blocked']:
                    report['static_blocked_samples'] += 1
                    report['valid'] = False
                    report['reason'] = (
                        '%s sample=%d static_radius=%.3f'
                        % (static['reason'], sample_index, static_radius)
                    )
                    return report

        return report

    def _validate_dynamic_rejoin_candidate(self, candidate_path, connector_path=None):
        self._publish_dynamic_skip_status(
            '[DYNAMIC_VALIDATE] validating candidate before cancel'
        )
        if not self.dynamic_validate_rejoin_before_cancel:
            return True, {'valid': True, 'reason': 'validation_disabled'}

        report = self._validate_path_structure(candidate_path, check_costmap=False)
        self._publish_debug(report)
        if not report['valid']:
            return self._reject_dynamic_rejoin_candidate(report)

        corridor_path = connector_path if connector_path is not None else candidate_path
        corridor_report = self._validate_connector_corridor(
            corridor_path,
            use_local_costmap=True,
            use_static_map=True,
        )
        report.update(
            {
                'dynamic_local_checked_samples': corridor_report[
                    'local_checked_samples'
                ],
                'dynamic_local_blocked_samples': corridor_report[
                    'local_blocked_samples'
                ],
                'dynamic_local_unknown_samples': corridor_report[
                    'local_unknown_samples'
                ],
                'dynamic_local_outside_samples': corridor_report[
                    'local_outside_samples'
                ],
                'dynamic_local_max_observed_cost': corridor_report[
                    'max_observed_cost'
                ],
                'dynamic_tracking_clearance_blocked_samples': corridor_report[
                    'tracking_clearance_blocked_samples'
                ],
                'dynamic_local_start_grace_blocked_samples': corridor_report[
                    'local_start_grace_blocked_samples'
                ],
                'dynamic_tracking_start_grace_blocked_samples': corridor_report[
                    'tracking_start_grace_blocked_samples'
                ],
                'dynamic_static_checked_samples': corridor_report[
                    'static_checked_samples'
                ],
                'dynamic_static_blocked_samples': corridor_report[
                    'static_blocked_samples'
                ],
                'dynamic_static_unknown_samples': corridor_report[
                    'static_unknown_samples'
                ],
                'dynamic_collision_radius_m': corridor_report[
                    'collision_radius_m'
                ],
                'dynamic_tracking_radius_m': corridor_report[
                    'tracking_radius_m'
                ],
            }
        )
        if not corridor_report['valid']:
            report['valid'] = False
            report['reason'] = corridor_report['reason']
            self._publish_debug(report)
            return self._reject_dynamic_rejoin_candidate(report)

        report['valid'] = True
        report['status'] = 'VALID'
        report['reason'] = 'ok'
        self._publish_debug(report)
        grace_count = (
            corridor_report.get('local_start_grace_blocked_samples', 0)
            + corridor_report.get('tracking_start_grace_blocked_samples', 0)
        )
        if grace_count > 0:
            grace_text = (
                '[DYNAMIC_VALIDATE] connector allowed blocked start grace '
                'samples=%d grace_m=%.2f'
                % (grace_count, self.dynamic_connector_start_grace_m)
            )
            self.get_logger().info(grace_text)
            self._publish_dynamic_skip_status(grace_text)
        text = '[DYNAMIC_VALIDATE] candidate valid before cancel'
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)
        return True, report

    def _cancel_dynamic_planner_timeout_timer(self):
        timer = self.dynamic_planner_timeout_timer
        self.dynamic_planner_timeout_timer = None
        if timer is not None:
            timer.cancel()
            try:
                self.destroy_timer(timer)
            except Exception:
                pass

    def _clear_dynamic_planner_state(self):
        self._cancel_dynamic_planner_timeout_timer()
        self.dynamic_planner_in_flight = False
        self.dynamic_planner_goal_handle = None
        self.dynamic_planner_pending_context = None
        self.dynamic_rejoin_candidates_pending = []
        self.dynamic_connector_attempt_in_progress = False

    def _mark_dynamic_planner_failed_and_continue(self, reason):
        context = self.dynamic_planner_pending_context
        self._cancel_dynamic_planner_timeout_timer()
        self.dynamic_planner_in_flight = False
        self.dynamic_planner_goal_handle = None
        self.dynamic_connector_attempt_in_progress = False
        if context is None:
            self.dynamic_skip_in_progress = False
            return False

        context['last_reason'] = reason
        return self._try_dynamic_fallbacks_or_next(
            context['report'],
            context['original_path'],
            context['current_rejoin_index'],
            reason,
        )

    def _clear_dynamic_skip_temporary_state(self):
        self._clear_dynamic_planner_state()
        self.dynamic_skip_in_progress = False
        self.dynamic_skip_cancel_requested = False
        self.dynamic_skip_cancel_goal_handle = None
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self.dynamic_skip_failure_counter = 0
        self.dynamic_detection_candidate = None
        self.dynamic_controller_blocked_reports_count = 0

    def _dynamic_monitor_resume_index_for_rejoin(
        self,
        remaining_path,
        rejoin_pose,
    ):
        monitor_resume_index = self._find_pose_index_in_path(
            remaining_path,
            rejoin_pose,
        )
        if monitor_resume_index is not None:
            monitor_resume_index = min(
                len(remaining_path.poses) - 1,
                monitor_resume_index + self.dynamic_resume_ignore_index_margin,
            )
            if monitor_resume_index <= 0:
                monitor_resume_index = None
        return monitor_resume_index

    def _find_validated_dynamic_rejoin_path(self, path, report, rejoin_index):
        last_reason = 'no_candidate_checked'
        while rejoin_index is not None:
            remaining_path = self._build_dynamic_rejoin_path(
                path,
                report,
                rejoin_index,
            )
            if remaining_path is None:
                last_reason = 'rejoin_index=%d no_safe_temporary_detour' % (
                    rejoin_index
                )
            elif len(remaining_path.poses) < self.min_path_poses:
                return rejoin_index, remaining_path, None, 'finish_after_cancel'
            else:
                monitor_resume_index = self._dynamic_monitor_resume_index_for_rejoin(
                    remaining_path,
                    path.poses[rejoin_index],
                )
                self.dynamic_candidate_marker_path = copy.deepcopy(remaining_path)
                valid_candidate, validation_report = (
                    self._validate_dynamic_rejoin_candidate(remaining_path)
                )
                if valid_candidate:
                    return rejoin_index, remaining_path, monitor_resume_index, 'valid'

                last_reason = validation_report.get(
                    'reason',
                    'invalid_candidate',
                )
                text = (
                    '[DYNAMIC_SKIP] candidate rejoin_index=%d invalid; '
                    'trying farther rejoin: reason=%s'
                    % (rejoin_index, last_reason)
                )
                self.get_logger().warn(text)
                self._publish_dynamic_skip_status(text)

            rejoin_index, rejoin_reason = self._find_rejoin_index_after_block(
                path,
                report['blocked_end_index'],
                start_index=rejoin_index + 1,
            )
            if rejoin_index is None:
                return None, None, None, '%s; %s' % (last_reason, rejoin_reason)

        return None, None, None, last_reason

    def _begin_dynamic_bypass_search(
        self,
        path,
        report,
        after_failure=False,
        error_code=None,
        error_label='',
    ):
        original_path = copy.deepcopy(path)
        report = copy.deepcopy(report)

        if report.get('blocked_end_index', -1) >= len(original_path.poses) - 1:
            return self._handle_dynamic_blocked_to_end(
                original_path,
                report,
                after_failure,
            )

        candidates = self._find_rejoin_candidates_after_block(original_path, report)
        if not candidates:
            return self._handle_dynamic_no_valid_bypass(
                report,
                'no_rejoin_candidates',
                after_failure=after_failure,
            )

        self.dynamic_planner_pending_context = {
            'report': report,
            'original_path': original_path,
            'after_failure': after_failure,
            'error_code': error_code,
            'error_label': error_label,
            'last_reason': 'no_candidate_checked',
            'current_rejoin_index': None,
            'planner_request_id': None,
        }
        self.dynamic_rejoin_candidates_pending = list(candidates)
        return self._try_next_dynamic_rejoin_candidate()

    def _try_next_dynamic_rejoin_candidate(self):
        context = self.dynamic_planner_pending_context
        if context is None:
            self.dynamic_skip_in_progress = False
            return False

        while self.dynamic_rejoin_candidates_pending:
            rejoin_index = self.dynamic_rejoin_candidates_pending.pop(0)
            context['current_rejoin_index'] = rejoin_index

            if (
                self.dynamic_use_nav2_planner_connector
                and self._start_nav2_connector_plan(
                    context['report'],
                    context['original_path'],
                    rejoin_index,
                )
            ):
                return True

            if self._try_dynamic_fallbacks_for_candidate(
                context['report'],
                context['original_path'],
                rejoin_index,
            ):
                return True

        return self._handle_dynamic_no_valid_bypass(
            context['report'],
            context.get('last_reason', 'no_valid_connector'),
            after_failure=context.get('after_failure', False),
        )

    def _start_nav2_connector_plan(self, report, original_path, rejoin_index):
        if self.dynamic_planner_in_flight:
            return True
        if not self.compute_path_to_pose_client.wait_for_server(timeout_sec=0.0):
            text = (
                '[DYNAMIC_CONNECTOR] Nav2 connector rejected reason='
                'compute_path_to_pose_server_unavailable'
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        path_frame = self._path_frame(original_path)
        robot_pose = self._lookup_robot_pose(path_frame)
        if robot_pose is None:
            text = (
                '[DYNAMIC_CONNECTOR] Nav2 connector rejected '
                'reason=robot_pose_unavailable'
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        if rejoin_index < 0 or rejoin_index >= len(original_path.poses):
            return False

        rejoin_pose = copy.deepcopy(original_path.poses[rejoin_index])
        rejoin_pose.header.frame_id = path_frame
        goal_msg = ComputePathToPose.Goal()
        goal_msg.start = copy.deepcopy(robot_pose)
        goal_msg.goal = rejoin_pose
        goal_msg.planner_id = self.dynamic_planner_id
        goal_msg.use_start = self.dynamic_connector_start_with_robot_pose

        self.dynamic_planner_request_id += 1
        request_id = self.dynamic_planner_request_id
        if self.dynamic_planner_pending_context is not None:
            self.dynamic_planner_pending_context['planner_request_id'] = request_id

        text = (
            '[DYNAMIC_CONNECTOR] requesting Nav2 ComputePathToPose connector '
            'rejoin_index=%d'
            % rejoin_index
        )
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)

        self.dynamic_planner_in_flight = True
        self.dynamic_connector_attempt_in_progress = True
        self.dynamic_planner_goal_handle = None
        self._cancel_dynamic_planner_timeout_timer()
        self.dynamic_planner_timeout_timer = self.create_timer(
            self.dynamic_planner_timeout_sec,
            lambda request_id=request_id: self._dynamic_planner_timeout_callback(
                request_id
            ),
        )

        future = self.compute_path_to_pose_client.send_goal_async(goal_msg)
        future.add_done_callback(
            lambda future, request_id=request_id: (
                self._nav2_connector_goal_response_callback(future, request_id)
            )
        )
        return True

    def _dynamic_planner_timeout_callback(self, request_id):
        self._cancel_dynamic_planner_timeout_timer()
        context = self.dynamic_planner_pending_context
        if (
            not self.dynamic_planner_in_flight
            or context is None
            or context.get('planner_request_id') != request_id
        ):
            return

        if self.dynamic_planner_goal_handle is not None:
            self.dynamic_planner_goal_handle.cancel_goal_async()

        text = (
            '[DYNAMIC_CONNECTOR] planner connector rejected '
            'reason=planner_timeout_sec_%.2f'
            % self.dynamic_planner_timeout_sec
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        self._mark_dynamic_planner_failed_and_continue('planner_timeout')

    def _nav2_connector_goal_response_callback(self, future, request_id):
        context = self.dynamic_planner_pending_context
        if (
            not self.dynamic_planner_in_flight
            or context is None
            or context.get('planner_request_id') != request_id
        ):
            return

        try:
            goal_handle = future.result()
        except Exception as exc:
            reason = 'goal_response_failed:%s' % exc
            text = '[DYNAMIC_CONNECTOR] Nav2 connector rejected reason=%s' % reason
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            self._mark_dynamic_planner_failed_and_continue(reason)
            return

        if not goal_handle.accepted:
            text = '[DYNAMIC_CONNECTOR] Nav2 connector rejected reason=goal_rejected'
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            self._mark_dynamic_planner_failed_and_continue('goal_rejected')
            return

        self.dynamic_planner_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda future, request_id=request_id: (
                self._nav2_connector_result_callback(future, request_id)
            )
        )

    def _nav2_connector_result_callback(self, future, request_id):
        context = self.dynamic_planner_pending_context
        if (
            not self.dynamic_planner_in_flight
            or context is None
            or context.get('planner_request_id') != request_id
        ):
            return

        self._cancel_dynamic_planner_timeout_timer()
        self.dynamic_planner_in_flight = False
        self.dynamic_planner_goal_handle = None
        self.dynamic_connector_attempt_in_progress = False

        try:
            wrapped_result = future.result()
        except Exception as exc:
            reason = 'result_failed:%s' % exc
            text = '[DYNAMIC_CONNECTOR] Nav2 connector rejected reason=%s' % reason
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            self._try_dynamic_fallbacks_or_next(
                context['report'],
                context['original_path'],
                context['current_rejoin_index'],
                reason,
            )
            return

        result = wrapped_result.result
        status = wrapped_result.status
        error_code = getattr(result, 'error_code', 0)
        error_msg = getattr(result, 'error_msg', '')
        connector_path = getattr(result, 'path', Path())
        text = (
            '[DYNAMIC_CONNECTOR] Nav2 connector result status=%d '
            'error_code=%d error_msg=%s'
            % (status, error_code, error_msg)
        )
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)

        if (
            status == GoalStatus.STATUS_SUCCEEDED
            and error_code == 0
            and len(connector_path.poses) >= 2
        ):
            if not connector_path.header.frame_id:
                connector_path.header.frame_id = self._path_frame(
                    context['original_path']
                )
            self._stamp_path(connector_path)
            text = (
                '[DYNAMIC_CONNECTOR] Nav2 connector poses=%d length=%.3f'
                % (len(connector_path.poses), self._path_length(connector_path))
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
            if self._handle_dynamic_connector_path(
                context['report'],
                context['original_path'],
                context['current_rejoin_index'],
                connector_path,
                'planner connector',
            ):
                return

        reason = (
            'planner_failed_status=%d_error_code=%d_poses=%d'
            % (status, error_code, len(connector_path.poses))
        )
        text = '[DYNAMIC_CONNECTOR] planner connector rejected reason=%s' % reason
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        self._try_dynamic_fallbacks_or_next(
            context['report'],
            context['original_path'],
            context['current_rejoin_index'],
            reason,
        )

    def _try_dynamic_fallbacks_or_next(
        self,
        report,
        original_path,
        rejoin_index,
        reason,
    ):
        context = self.dynamic_planner_pending_context
        if context is not None:
            context['last_reason'] = reason

        if self._try_dynamic_fallbacks_for_candidate(
            report,
            original_path,
            rejoin_index,
        ):
            return True

        if context is not None:
            context['last_reason'] = (
                'rejoin_index=%d no_valid_connector:%s'
                % (rejoin_index, reason)
            )
        return self._try_next_dynamic_rejoin_candidate()

    def _try_dynamic_fallbacks_for_candidate(self, report, original_path, rejoin_index):
        path_frame = self._path_frame(original_path)
        robot_pose = self._lookup_robot_pose(path_frame)
        if robot_pose is None:
            if self.dynamic_planner_pending_context is not None:
                self.dynamic_planner_pending_context[
                    'last_reason'
                ] = 'robot_pose_unavailable_for_fallback'
            return False

        if self.dynamic_enable_local_astar_detour:
            text = (
                '[DYNAMIC_CONNECTOR] trying local A* fallback rejoin_index=%d'
                % rejoin_index
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
            connector = self._build_local_astar_connector_path(
                original_path,
                robot_pose,
                rejoin_index,
            )
            if connector is not None and self._handle_dynamic_connector_path(
                report,
                original_path,
                rejoin_index,
                connector,
                'local A* fallback',
            ):
                return True

        if self.dynamic_enable_local_detour:
            text = (
                '[DYNAMIC_CONNECTOR] trying lateral fallback rejoin_index=%d'
                % rejoin_index
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
            connector = self._build_lateral_detour_connector_path(
                original_path,
                report,
                robot_pose,
                rejoin_index,
            )
            if connector is not None and self._handle_dynamic_connector_path(
                report,
                original_path,
                rejoin_index,
                connector,
                'lateral fallback',
            ):
                return True

        return False

    def _nudge_pose_away_from_local_obstacle(self, pose_stamped):
        if self.local_costmap is None:
            return None, 0.0

        path_frame = pose_stamped.header.frame_id or self.global_frame
        influence_m = max(
            self._get_dynamic_tracking_radius_m(),
            self.dynamic_connector_refinement_influence_m,
        )
        obstacle_info = self._nearest_dynamic_obstacle_distance(
            self.local_costmap,
            pose_stamped,
            influence_m,
        )
        if (
            not obstacle_info.get('valid', False)
            or not math.isfinite(obstacle_info.get('distance_m', float('inf')))
            or obstacle_info.get('nearest_lethal_pose') is None
        ):
            return None, 0.0

        obstacle_pose = self._transform_pose_to_frame(
            obstacle_info['nearest_lethal_pose'],
            path_frame,
        )
        if obstacle_pose is None:
            return None, 0.0

        pose_position = pose_stamped.pose.position
        obstacle_position = obstacle_pose.pose.position
        away_x = pose_position.x - obstacle_position.x
        away_y = pose_position.y - obstacle_position.y
        distance = math.hypot(away_x, away_y)
        if distance <= 1.0e-6:
            return None, 0.0

        target_distance = self._get_dynamic_tracking_radius_m()
        if distance >= target_distance:
            return None, 0.0

        shift_m = min(
            self.dynamic_connector_refinement_step_m,
            target_distance - distance + 0.01,
        )
        if shift_m <= 0.0:
            return None, 0.0

        candidate = copy.deepcopy(pose_stamped)
        candidate.pose.position.x += (away_x / distance) * shift_m
        candidate.pose.position.y += (away_y / distance) * shift_m

        local_check = self._check_local_corridor_at_pose(
            candidate,
            self._get_dynamic_collision_radius_m(),
        )
        if (
            not local_check['valid']
            or (local_check['inside'] and local_check['blocked'])
        ):
            return None, 0.0

        static_check = self._check_static_corridor_at_pose(
            candidate,
            max(self.robot_radius_m, self.robot_radius_m + self.static_reference_padding_m),
        )
        if not static_check['valid'] or static_check['blocked']:
            return None, 0.0

        return candidate, shift_m

    def _refine_dynamic_connector_path(self, connector_path):
        if (
            not self.dynamic_refine_connector_path
            or connector_path is None
            or len(connector_path.poses) < 3
            or self.dynamic_connector_refinement_iterations <= 0
            or self.dynamic_connector_refinement_step_m <= 0.0
        ):
            return connector_path

        refined = copy.deepcopy(connector_path)
        moved_points = 0
        max_shift = 0.0
        for _ in range(self.dynamic_connector_refinement_iterations):
            updated_poses = copy.deepcopy(refined.poses)
            for index in range(1, len(refined.poses) - 1):
                nudged, shift_m = self._nudge_pose_away_from_local_obstacle(
                    refined.poses[index]
                )
                if nudged is None:
                    continue
                updated_poses[index] = nudged
                moved_points += 1
                max_shift = max(max_shift, shift_m)
            refined.poses = updated_poses

        if moved_points > 0:
            self._recompute_orientations(refined)
            self._stamp_path(refined)
            text = (
                '[DYNAMIC_CONNECTOR] refined connector away from local obstacle '
                'moved_points=%d max_step=%.3f tracking_radius=%.3f'
                % (
                    moved_points,
                    max_shift,
                    self._get_dynamic_tracking_radius_m(),
                )
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
        return refined

    def _connector_path_reaches_rejoin(self, connector_path, original_path, rejoin_index):
        if connector_path is None or not connector_path.poses:
            return False, 'empty_connector'
        path_frame = self._path_frame(original_path)
        endpoint = self._transform_pose_to_frame(
            connector_path.poses[-1],
            path_frame,
        )
        if endpoint is None:
            return False, 'connector_endpoint_tf_unavailable'
        rejoin_pose = original_path.poses[rejoin_index]
        end = endpoint.pose.position
        target = rejoin_pose.pose.position
        distance = self._distance_2d(end.x, end.y, target.x, target.y)
        if distance > self.dynamic_connector_goal_tolerance_m:
            return (
                False,
                'connector_endpoint_%.3fm_from_rejoin_tolerance_%.3fm'
                % (distance, self.dynamic_connector_goal_tolerance_m),
            )
        return True, 'ok'

    def _build_dynamic_candidate_path(self, connector_path, original_path, rejoin_index):
        if (
            connector_path is None
            or original_path is None
            or rejoin_index < 0
            or rejoin_index >= len(original_path.poses)
        ):
            return None

        path_frame = self._path_frame(original_path)
        candidate = Path()
        candidate.header = copy.deepcopy(original_path.header)
        candidate.header.frame_id = path_frame

        for pose_stamped in connector_path.poses:
            pose_in_path = self._transform_pose_to_frame(pose_stamped, path_frame)
            if pose_in_path is None:
                return None
            pose_in_path.header.frame_id = path_frame
            self._append_pose_without_duplicate(candidate, pose_in_path)

        self._append_pose_without_duplicate(candidate, original_path.poses[rejoin_index])
        for index in range(rejoin_index + 1, len(original_path.poses)):
            self._append_pose_without_duplicate(candidate, original_path.poses[index])

        if len(candidate.poses) < self.min_path_poses:
            return None

        self._recompute_orientations(candidate)
        self._stamp_path(candidate)
        return candidate

    def _build_rejoin_validation_path(self, connector_path, original_path, rejoin_index):
        if (
            connector_path is None
            or original_path is None
            or rejoin_index < 0
            or rejoin_index >= len(original_path.poses)
        ):
            return connector_path

        path_frame = self._path_frame(original_path)
        validation_path = Path()
        validation_path.header = copy.deepcopy(original_path.header)
        validation_path.header.frame_id = path_frame

        for pose_stamped in connector_path.poses:
            pose_in_path = self._transform_pose_to_frame(pose_stamped, path_frame)
            if pose_in_path is None:
                return connector_path
            pose_in_path.header.frame_id = path_frame
            self._append_pose_without_duplicate(validation_path, pose_in_path)

        guard_distance_m = max(
            self.dynamic_imminent_block_distance_m,
            self._get_dynamic_collision_radius_m(),
        )
        guard_end_index = self._index_after_distance(
            original_path,
            rejoin_index,
            guard_distance_m,
        )
        for index in range(rejoin_index, guard_end_index + 1):
            self._append_pose_without_duplicate(
                validation_path,
                original_path.poses[index],
            )

        self._recompute_orientations(validation_path)
        self._stamp_path(validation_path)
        return validation_path

    def _handle_dynamic_connector_path(
        self,
        report,
        original_path,
        rejoin_index,
        connector_path,
        source_label,
    ):
        if connector_path is None or len(connector_path.poses) < 2:
            text = (
                '[DYNAMIC_CONNECTOR] %s rejected reason=connector_path_too_short'
                % source_label
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        reaches, reach_reason = self._connector_path_reaches_rejoin(
            connector_path,
            original_path,
            rejoin_index,
        )
        if not reaches:
            text = (
                '[DYNAMIC_CONNECTOR] %s rejected reason=%s'
                % (source_label, reach_reason)
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        connector_path = self._refine_dynamic_connector_path(connector_path)
        reaches, reach_reason = self._connector_path_reaches_rejoin(
            connector_path,
            original_path,
            rejoin_index,
        )
        if not reaches:
            text = (
                '[DYNAMIC_CONNECTOR] %s rejected after refinement reason=%s'
                % (source_label, reach_reason)
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        candidate_path = self._build_dynamic_candidate_path(
            connector_path,
            original_path,
            rejoin_index,
        )
        if candidate_path is None:
            text = (
                '[DYNAMIC_CONNECTOR] %s rejected reason=failed_to_build_candidate'
                % source_label
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        active_rejoin_index = self._find_pose_index_in_path(
            candidate_path,
            original_path.poses[rejoin_index],
            tolerance_m=max(0.05, self.dynamic_connector_goal_tolerance_m),
        )
        if active_rejoin_index is None:
            active_rejoin_index = max(
                0,
                min(len(candidate_path.poses) - 1, len(connector_path.poses) - 1),
            )

        self.dynamic_candidate_marker_path = copy.deepcopy(candidate_path)
        self._publish_skipped_segment_markers()
        validation_path = self._build_rejoin_validation_path(
            connector_path,
            original_path,
            rejoin_index,
        )
        valid_candidate, validation_report = self._validate_dynamic_rejoin_candidate(
            candidate_path,
            validation_path,
        )
        if not valid_candidate:
            text = (
                '[DYNAMIC_CONNECTOR] %s rejected reason=%s'
                % (
                    source_label,
                    validation_report.get('reason', 'invalid_candidate'),
                )
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return False

        text = (
            '[DYNAMIC_CONNECTOR] %s accepted poses=%d length=%.3f'
            % (
                source_label,
                len(connector_path.poses),
                self._path_length(connector_path),
            )
        )
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)
        return self._accept_dynamic_candidate_path(
            report,
            original_path,
            rejoin_index,
            candidate_path,
            active_rejoin_index,
        )

    def _accept_dynamic_candidate_path(
        self,
        report,
        original_path,
        rejoin_index,
        candidate_path,
        active_rejoin_index,
    ):
        context = self.dynamic_planner_pending_context or {}
        after_failure = context.get('after_failure', False)
        skip_end_index = max(report['blocked_end_index'], rejoin_index - 1)
        self._record_skipped_segment(
            original_path,
            report['blocked_start_index'],
            skip_end_index,
            rejoin_index,
            report,
        )
        self._publish_skipped_segment_markers()

        monitor_resume_index = self._dynamic_monitor_resume_index_for_rejoin(
            candidate_path,
            original_path.poses[rejoin_index],
        )
        self.dynamic_skip_pending_monitor_resume_index = monitor_resume_index
        self.dynamic_skip_pending_original_rejoin_index = rejoin_index
        self.dynamic_skip_pending_active_rejoin_index = active_rejoin_index
        self.dynamic_skip_pending_report = report
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None
        self._clear_dynamic_planner_state()

        if after_failure or not self.goal_in_flight or self.current_goal_handle is None:
            remaining_distance = self._path_length(candidate_path)
            text = (
                '[DYNAMIC_SKIP] sending dynamic bypass FollowPath '
                'remaining_poses=%d remaining_distance=%.3f'
                % (len(candidate_path.poses), remaining_distance)
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
            self.dynamic_skip_in_progress = False
            return self._send_follow_path_goal(
                candidate_path,
                'dynamic_obstacle_bypass_rejoin_after_failure',
            )

        text = '[DYNAMIC_SKIP] canceling current FollowPath to send dynamic bypass'
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)
        self.dynamic_skip_pending_rejoin_path = candidate_path
        return self._cancel_current_goal_for_dynamic_skip()

    def _handle_dynamic_blocked_to_end(self, path, report, after_failure):
        self._clear_dynamic_planner_state()
        self._record_skipped_segment(
            path,
            report['blocked_start_index'],
            len(path.poses) - 1,
            len(path.poses),
            report,
        )
        self._publish_skipped_segment_markers()
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = report
        self.dynamic_skip_pending_monitor_resume_index = None
        self.dynamic_skip_finish_after_cancel = True
        if after_failure or self.current_goal_handle is None:
            self.dynamic_skip_in_progress = False
            self._finish_execution(self.STATUS_COMPLETED_WITH_SKIPS)
            return True
        return self._cancel_current_goal_for_dynamic_skip()

    def _is_dynamic_obstacle_imminent(self, report):
        nearest_index = report.get('nearest_index', -1)
        blocked_start_index = report.get('blocked_start_index', -1)
        if nearest_index < 0 or blocked_start_index < 0:
            return self.dynamic_controller_blocked_reports_count > 0

        path = self.active_path
        if path is not None and path.poses:
            distance_to_block = self._distance_along_path(
                path,
                nearest_index,
                blocked_start_index,
            )
            if distance_to_block <= self.dynamic_imminent_block_distance_m:
                return True

        if self.dynamic_controller_blocked_reports_count > 0:
            return True
        return blocked_start_index <= nearest_index + 2

    def _handle_dynamic_no_valid_bypass(self, report, reason, after_failure=False):
        self._clear_dynamic_planner_state()
        self.dynamic_skip_failure_counter += 1
        object_imminent = self._is_dynamic_obstacle_imminent(report)
        if report.get('dynamic_rejoin_refresh') and not after_failure:
            object_imminent = False
        should_stop = (
            object_imminent
            or after_failure
            or not self.dynamic_cancel_only_if_imminent_blocked
        )
        text = (
            '[DYNAMIC_SKIP] no valid bypass within %.2fm; '
            'object_imminent=%s'
            % (
                self.dynamic_rejoin_max_search_distance_m,
                str(object_imminent).lower(),
            )
        )
        if should_stop:
            text = '%s; stopping as BLOCKED_DYNAMIC_OBJECT' % text
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            self.latest_path_error = (
                'confirmed dynamic obstacle blocked path and no valid bypass '
                'within %.2fm: %s'
                % (self.dynamic_rejoin_max_search_distance_m, reason)
            )
            self.dynamic_skip_pending_rejoin_path = None
            self.dynamic_skip_pending_report = report
            self.dynamic_skip_pending_monitor_resume_index = None
            self.dynamic_skip_finish_after_cancel = False
            self.dynamic_skip_cancel_final_status = (
                self.STATUS_BLOCKED_DYNAMIC_OBJECT
            )
            if after_failure or self.current_goal_handle is None:
                self.dynamic_skip_in_progress = False
                self._finish_execution(self.STATUS_BLOCKED_DYNAMIC_OBJECT)
                return True
            return self._cancel_current_goal_for_dynamic_skip()

        text = '%s; keeping current FollowPath and monitoring' % text
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        self.latest_path_error = (
            'dynamic obstacle confirmed but no non-imminent bypass is valid yet: %s'
            % reason
        )
        self.dynamic_skip_in_progress = False
        self._set_status(self.STATUS_EXECUTING)
        return False

    def _project_temporary_block_to_original_path(self, report):
        if (
            not self.dynamic_active_path_is_temporary
            or self.cached_raw_path is None
            or not self.cached_raw_path.poses
            or self.dynamic_active_original_rejoin_index is None
        ):
            return None, None

        original_path = self.cached_raw_path
        original_rejoin_index = max(
            0,
            min(
                int(self.dynamic_active_original_rejoin_index),
                len(original_path.poses) - 1,
            ),
        )
        active_rejoin_index = self.dynamic_active_rejoin_path_index
        if active_rejoin_index is None and self.active_path is not None:
            active_rejoin_index = self._find_pose_index_in_path(
                self.active_path,
                original_path.poses[original_rejoin_index],
                tolerance_m=max(0.05, self.dynamic_connector_goal_tolerance_m),
            )

        if active_rejoin_index is None:
            active_rejoin_index = 0
        active_rejoin_index = max(0, int(active_rejoin_index))

        def active_to_original(active_index):
            active_index = max(0, int(active_index))
            if active_index < active_rejoin_index:
                return original_rejoin_index
            mapped = original_rejoin_index + (active_index - active_rejoin_index)
            return max(0, min(mapped, len(original_path.poses) - 1))

        active_nearest = report.get('nearest_index', 0)
        active_blocked_start = report.get('blocked_start_index', active_nearest)
        active_blocked_end = report.get('blocked_end_index', active_blocked_start)
        active_lookahead_end = report.get('lookahead_end_index', active_blocked_end)

        projected_report = copy.deepcopy(report)
        projected_report['active_path_nearest_index'] = active_nearest
        projected_report['active_path_blocked_start_index'] = active_blocked_start
        projected_report['active_path_blocked_end_index'] = active_blocked_end
        projected_report['active_path_rejoin_index'] = active_rejoin_index
        projected_report['original_rejoin_index'] = original_rejoin_index
        projected_report['temporary_path_refinement'] = True
        projected_report['nearest_index'] = active_to_original(active_nearest)
        projected_report['blocked_start_index'] = active_to_original(
            active_blocked_start
        )
        projected_report['blocked_end_index'] = active_to_original(active_blocked_end)
        projected_report['lookahead_end_index'] = active_to_original(
            active_lookahead_end
        )

        if active_blocked_start < active_rejoin_index:
            projected_report['nearest_index'] = original_rejoin_index
            projected_report['blocked_start_index'] = original_rejoin_index
            projected_report['blocked_end_index'] = original_rejoin_index
            projected_report['lookahead_end_index'] = min(
                len(original_path.poses) - 1,
                original_rejoin_index + max(1, self.dynamic_skip_min_remaining_poses),
            )

        if (
            projected_report['blocked_end_index']
            < projected_report['blocked_start_index']
        ):
            projected_report['blocked_end_index'] = projected_report[
                'blocked_start_index'
            ]

        projected_report['blocked_path_length_m'] = self._distance_along_path(
            original_path,
            projected_report['blocked_start_index'],
            projected_report['blocked_end_index'],
        )
        projected_report['reason'] = (
            'temporary_path_obstacle_projected_to_original_path'
        )

        text = (
            '[DYNAMIC_SKIP] refining temporary path against frozen original path '
            'active_rejoin_index=%d original_rejoin_index=%d '
            'projected_block_start=%d projected_block_end=%d'
            % (
                active_rejoin_index,
                original_rejoin_index,
                projected_report['blocked_start_index'],
                projected_report['blocked_end_index'],
            )
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        return original_path, projected_report

    def _dynamic_bypass_source_path_and_report(self, report):
        original_path, projected_report = self._project_temporary_block_to_original_path(
            report
        )
        if original_path is not None and projected_report is not None:
            return original_path, projected_report
        return self.active_path, report

    def _current_active_path_nearest_index(self):
        if self.active_path is None or not self.active_path.poses:
            return None

        robot_pose = self._lookup_robot_pose(self._path_frame(self.active_path))
        if robot_pose is None:
            return None

        nearest_index, _ = self._find_dynamic_monitor_nearest_path_index(
            self.active_path,
            robot_pose,
        )
        if nearest_index < 0:
            return None
        return nearest_index

    def _project_active_temporary_index_to_original(self, active_index):
        if self.cached_raw_path is None or not self.cached_raw_path.poses:
            return None

        original_rejoin_index = self.dynamic_active_original_rejoin_index
        if original_rejoin_index is None:
            original_rejoin_index = 0
        original_rejoin_index = max(
            0,
            min(int(original_rejoin_index), len(self.cached_raw_path.poses) - 1),
        )

        active_rejoin_index = self.dynamic_active_rejoin_path_index
        if active_rejoin_index is None:
            active_rejoin_index = 0
        active_rejoin_index = max(0, int(active_rejoin_index))
        active_index = max(0, int(active_index))

        if not self.dynamic_active_path_is_temporary:
            mapped = self.selected_start_index + active_index
        elif active_index < active_rejoin_index:
            mapped = original_rejoin_index
        else:
            mapped = original_rejoin_index + (active_index - active_rejoin_index)
        return max(0, min(mapped, len(self.cached_raw_path.poses) - 1))

    def _temporary_rejoin_refresh_report(self):
        if (
            not self.dynamic_refresh_temporary_rejoin
            or not self.dynamic_active_path_is_temporary
            or self.cached_raw_path is None
            or not self.cached_raw_path.poses
            or self.dynamic_active_original_rejoin_index is None
        ):
            return None

        nearest_active_index = self._current_active_path_nearest_index()
        if nearest_active_index is None:
            return None

        current_original_index = self._project_active_temporary_index_to_original(
            nearest_active_index
        )
        if current_original_index is None:
            return None

        start_index = max(
            int(self.dynamic_active_original_rejoin_index),
            current_original_index,
        )
        start_index = max(0, min(start_index, len(self.cached_raw_path.poses) - 1))
        end_index = self._index_after_distance(
            self.cached_raw_path,
            start_index,
            self.dynamic_temporary_rejoin_check_distance_m,
        )

        for index in range(start_index, end_index + 1):
            pose_stamped = self.cached_raw_path.poses[index]
            static_safe, static_reason = self._is_rejoin_pose_static_safe(pose_stamped)
            global_safe, global_reason = self._is_rejoin_pose_global_safe(pose_stamped)
            local_safe, local_reason = self._is_rejoin_pose_locally_clear_if_visible(
                pose_stamped
            )
            if static_safe and global_safe and local_safe:
                continue

            reason = (
                'temporary_rejoin_pose_unsafe original_index=%d '
                'static_safe=%s global_safe=%s local_safe=%s '
                'static_reason=%s global_reason=%s local_reason=%s'
                % (
                    index,
                    str(static_safe).lower(),
                    str(global_safe).lower(),
                    str(local_safe).lower(),
                    static_reason,
                    global_reason,
                    local_reason,
                )
            )
            report = {
                'blocked': True,
                'nearest_index': current_original_index,
                'nearest_distance': 0.0,
                'blocked_start_index': index,
                'blocked_end_index': index,
                'lookahead_end_index': end_index,
                'min_cost': 0,
                'max_cost': self.dynamic_obstacle_cost_threshold,
                'nearest_obstacle_distance_m': float('inf'),
                'obstacle_distance_threshold_m': self._get_dynamic_detection_radius_m(),
                'reason': reason,
                'local_costmap_frame': self.local_costmap.header.frame_id
                if self.local_costmap is not None
                else self.global_frame,
                'path_frame': self._path_frame(self.cached_raw_path),
                'local_lethal_count': 0,
                'inflated_ignored_count': 0,
                'static_known_blocked_count': 0,
                'static_unknown_blocked_count': 0,
                'dynamic_only_blocked_count': 1,
                'blocked_path_length_m': 0.0,
                'consecutive_count': self.dynamic_required_consecutive_detections,
                'dynamic_only_blocked_poses': [copy.deepcopy(pose_stamped)],
                'static_known_blocked_poses': [],
                'dynamic_rejoin_refresh': True,
            }
            text = (
                '[DYNAMIC_REPLAN] temporary coverage rejoin became unsafe; '
                'searching farther coverage pose reason=%s'
                % reason
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return report

        return None

    def _refresh_dynamic_temporary_rejoin_if_needed(self):
        if self.dynamic_skip_in_progress:
            return False

        now = time.monotonic()
        if (
            self.dynamic_last_temporary_rejoin_refresh_monotonic > 0.0
            and now - self.dynamic_last_temporary_rejoin_refresh_monotonic
            < self.dynamic_temporary_rejoin_refresh_cooldown_sec
        ):
            return False

        report = self._temporary_rejoin_refresh_report()
        if report is None:
            return False

        self.dynamic_last_temporary_rejoin_refresh_monotonic = now
        self.dynamic_skip_in_progress = True
        self._set_status(self.STATUS_SKIPPING_DYNAMIC_OBSTACLE)
        self._publish_dynamic_skip_status(
            '[DYNAMIC_REPLAN] keeping current FollowPath while planning '
            'updated temporary connector'
        )
        return self._begin_dynamic_bypass_search(
            self.cached_raw_path,
            report,
            after_failure=False,
        )

    def _start_dynamic_skip(self, report):
        if self.dynamic_skip_in_progress:
            return False

        self.dynamic_skip_in_progress = True
        self._set_status(self.STATUS_SKIPPING_DYNAMIC_OBSTACLE)
        self._log_dynamic_obstacle_detected(report)
        self._publish_dynamic_skip_status(
            '[DYNAMIC_REPLAN] keeping current FollowPath while searching '
            'next safe coverage pose and temporary connector'
        )

        path, report = self._dynamic_bypass_source_path_and_report(report)
        if path is None:
            self.dynamic_skip_in_progress = False
            self._set_status(self.STATUS_EXECUTING)
            return False

        return self._begin_dynamic_bypass_search(
            path,
            report,
            after_failure=False,
        )

    def _start_dynamic_skip_after_failure(self, report, error_code, error_label):
        if self.dynamic_skip_in_progress:
            return False

        self.dynamic_skip_in_progress = True
        self._set_status(self.STATUS_SKIPPING_DYNAMIC_OBSTACLE)
        self._log_dynamic_obstacle_detected(report)

        path, report = self._dynamic_bypass_source_path_and_report(report)
        if path is None:
            self.dynamic_skip_in_progress = False
            return False

        return self._begin_dynamic_bypass_search(
            path,
            report,
            after_failure=True,
            error_code=error_code,
            error_label=error_label,
        )

    def _cancel_current_goal_for_dynamic_skip(self):
        if self.current_goal_handle is None:
            self.dynamic_skip_failure_counter += 1
            text = (
                '[DYNAMIC_SKIP] cannot cancel FollowPath for skip; '
                'no current goal handle is available'
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            self.dynamic_skip_in_progress = False
            if self.dynamic_skip_cancel_final_status is not None:
                final_status = self.dynamic_skip_cancel_final_status
                self.dynamic_skip_cancel_final_status = None
                self.dynamic_skip_pending_monitor_resume_index = None
                self._finish_execution(final_status)
            else:
                self.dynamic_skip_pending_monitor_resume_index = None
                self._set_status(self.STATUS_EXECUTING)
            return False

        self.dynamic_skip_cancel_requested = True
        self.dynamic_skip_cancel_goal_handle = self.current_goal_handle
        cancel_future = self.current_goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(self._dynamic_skip_cancel_done_callback)
        return True

    def _dynamic_skip_cancel_done_callback(self, future):
        try:
            future.result()
        except Exception as exc:
            self.dynamic_skip_cancel_requested = False
            self.dynamic_skip_cancel_goal_handle = None
            self.dynamic_skip_pending_rejoin_path = None
            self.dynamic_skip_pending_report = None
            self.dynamic_skip_pending_monitor_resume_index = None
            self.dynamic_skip_finish_after_cancel = False
            self.dynamic_skip_cancel_final_status = None
            self.dynamic_skip_in_progress = False
            self.dynamic_skip_failure_counter += 1
            text = '[DYNAMIC_SKIP] FollowPath cancel for skip failed: %s' % exc
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            if (
                self.dynamic_skip_failure_counter
                >= self.dynamic_skip_max_consecutive_failures
            ):
                self.latest_path_error = (
                    'dynamic obstacle skip cancel failed repeatedly'
                )
                self._finish_execution(self.STATUS_FAILED)
            else:
                self._set_status(self.STATUS_EXECUTING)
            return

        self.current_goal_handle = None
        self.goal_in_flight = False
        self.dynamic_skip_cancel_requested = False

        pending_path = self.dynamic_skip_pending_rejoin_path
        finish_after_cancel = self.dynamic_skip_finish_after_cancel
        final_status_after_cancel = self.dynamic_skip_cancel_final_status
        self.dynamic_skip_pending_rejoin_path = None
        self.dynamic_skip_pending_report = None
        self.dynamic_skip_finish_after_cancel = False
        self.dynamic_skip_cancel_final_status = None

        if final_status_after_cancel is not None:
            self.dynamic_skip_in_progress = False
            self._finish_execution(final_status_after_cancel)
            return

        if finish_after_cancel or pending_path is None:
            self.dynamic_skip_in_progress = False
            self._finish_execution(self.STATUS_COMPLETED_WITH_SKIPS)
            return

        remaining_distance = self._path_length(pending_path)
        self.get_logger().info(
            '[DYNAMIC_SKIP] sending rejoin FollowPath '
            'remaining_poses=%d remaining_distance=%.3f'
            % (len(pending_path.poses), remaining_distance)
        )
        self._publish_dynamic_skip_status(
            '[DYNAMIC_SKIP] sending rejoin FollowPath remaining_poses=%d '
            'remaining_distance=%.3f'
            % (len(pending_path.poses), remaining_distance)
        )
        self.dynamic_skip_in_progress = False
        self._send_follow_path_goal(
            pending_path,
            'dynamic_obstacle_bypass_rejoin',
        )

    def _log_dynamic_obstacle_detected(self, report):
        text = (
            '[DYNAMIC_SKIP] obstacle detected on active path '
            'nearest_index=%d blocked_start_index=%d blocked_end_index=%d '
            'lookahead_end_index=%d max_cost=%d obstacle_distance=%.3f '
            'threshold=%.3f local_costmap_frame=%s path_frame=%s'
            % (
                report.get('nearest_index', -1),
                report.get('blocked_start_index', -1),
                report.get('blocked_end_index', -1),
                report.get('lookahead_end_index', -1),
                report.get('max_cost', 0),
                report.get('nearest_obstacle_distance_m', float('inf')),
                report.get(
                    'obstacle_distance_threshold_m',
                    self.dynamic_obstacle_distance_threshold_m,
                ),
                report.get('local_costmap_frame', ''),
                report.get('path_frame', ''),
            )
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)

    def _path_frame(self, path):
        if path is not None and path.header.frame_id:
            return path.header.frame_id
        return self.global_frame

    def _transform_pose_to_frame(self, pose_stamped, target_frame):
        if pose_stamped is None:
            return None

        target_frame = target_frame or self.global_frame
        source_frame = pose_stamped.header.frame_id or self.global_frame
        if source_frame == target_frame:
            transformed = copy.deepcopy(pose_stamped)
            transformed.header.frame_id = target_frame
            return transformed

        try:
            transform = self.tf_buffer.lookup_transform(
                target_frame,
                source_frame,
                Time(),
                timeout=Duration(seconds=self.tf_lookup_timeout_sec),
            )
        except TransformException as exc:
            self.get_logger().debug(
                'Could not transform pose %s -> %s: %s'
                % (source_frame, target_frame, exc),
                throttle_duration_sec=2.0,
            )
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        transform_yaw = self._yaw_from_quaternion(rotation)
        pose_yaw = self._yaw_from_quaternion(pose_stamped.pose.orientation)
        cos_yaw = math.cos(transform_yaw)
        sin_yaw = math.sin(transform_yaw)
        x = pose_stamped.pose.position.x
        y = pose_stamped.pose.position.y

        transformed = PoseStamped()
        transformed.header.frame_id = target_frame
        transformed.header.stamp = transform.header.stamp
        transformed.pose.position.x = translation.x + cos_yaw * x - sin_yaw * y
        transformed.pose.position.y = translation.y + sin_yaw * x + cos_yaw * y
        transformed.pose.position.z = (
            translation.z + pose_stamped.pose.position.z
        )
        transformed.pose.orientation = self._quaternion_from_yaw(
            self._normalize_angle(transform_yaw + pose_yaw)
        )
        return transformed

    def _world_to_costmap_cell(self, costmap, x, y):
        resolution = costmap.info.resolution
        if resolution <= 0.0:
            return None

        origin = costmap.info.origin
        origin_yaw = self._yaw_from_quaternion(origin.orientation)
        dx = x - origin.position.x
        dy = y - origin.position.y
        cos_yaw = math.cos(-origin_yaw)
        sin_yaw = math.sin(-origin_yaw)
        local_x = cos_yaw * dx - sin_yaw * dy
        local_y = sin_yaw * dx + cos_yaw * dy
        mx = int(math.floor(local_x / resolution))
        my = int(math.floor(local_y / resolution))
        if not in_bounds(mx, my, costmap.info.width, costmap.info.height):
            return None
        return mx, my

    def _get_costmap_cost(self, costmap, pose_stamped):
        costmap_frame = costmap.header.frame_id or self.global_frame
        pose_in_costmap = self._transform_pose_to_frame(
            pose_stamped,
            costmap_frame,
        )
        if pose_in_costmap is None:
            return {
                'valid': False,
                'inside': False,
                'cost': 100,
                'mx': -1,
                'my': -1,
                'reason': 'tf_unavailable',
            }

        cell = self._world_to_costmap_cell(
            costmap,
            pose_in_costmap.pose.position.x,
            pose_in_costmap.pose.position.y,
        )
        if cell is None:
            return {
                'valid': False,
                'inside': False,
                'cost': 100,
                'mx': -1,
                'my': -1,
                'reason': 'outside_costmap',
            }

        mx, my = cell
        index = map_to_flat_index(mx, my, costmap.info.width)
        cost = int(costmap.data[index])
        return {
            'valid': True,
            'inside': True,
            'cost': cost,
            'mx': mx,
            'my': my,
            'reason': 'unknown' if cost < 0 else 'ok',
        }

    def _get_costmap_cell_for_pose(self, costmap, pose_stamped):
        costmap_frame = costmap.header.frame_id or self.global_frame
        pose_in_costmap = self._transform_pose_to_frame(
            pose_stamped,
            costmap_frame,
        )
        if pose_in_costmap is None:
            return None, 'tf_unavailable'

        cell = self._world_to_costmap_cell(
            costmap,
            pose_in_costmap.pose.position.x,
            pose_in_costmap.pose.position.y,
        )
        if cell is None:
            return None, 'outside_costmap'
        return cell, 'ok'

    def _static_reference_status_near_pose(self, pose_stamped, padding_m=None):
        status = {
            'known_static': False,
            'free': False,
            'unknown_count': 0,
            'checked_count': 0,
            'max_value': 0,
            'reason': 'not_checked',
        }
        if not self.dynamic_use_static_reference_check:
            status['free'] = True
            status['reason'] = 'static_reference_disabled'
            return status

        if self.static_map is None:
            status['reason'] = 'static_map_unavailable'
            self.get_logger().warn(
                'static map not available; dynamic detection cannot distinguish walls',
                throttle_duration_sec=5.0,
            )
            return status

        static_frame = self.static_map.header.frame_id or self.global_frame
        pose_in_static = self._transform_pose_to_frame(pose_stamped, static_frame)
        if pose_in_static is None:
            status['reason'] = 'static_map_tf_unavailable'
            return status

        resolution = self.static_map.info.resolution
        if resolution <= 0.0:
            status['reason'] = 'invalid_static_map_resolution'
            return status

        position = pose_in_static.pose.position
        cell = self._world_to_costmap_cell(self.static_map, position.x, position.y)
        if cell is None:
            status['reason'] = 'outside_static_map'
            return status

        center_mx, center_my = cell
        radius_m = (
            self.static_reference_padding_m
            if padding_m is None
            else max(0.0, padding_m)
        )
        radius_cells = int(math.ceil(radius_m / resolution))
        include_distance_m = radius_m + resolution * 0.5 + 1.0e-9

        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                mx = center_mx + dx
                my = center_my + dy
                if not in_bounds(
                    mx,
                    my,
                    self.static_map.info.width,
                    self.static_map.info.height,
                ):
                    continue

                cell_x, cell_y = self._costmap_cell_center(self.static_map, mx, my)
                if (
                    self._distance_2d(position.x, position.y, cell_x, cell_y)
                    > include_distance_m
                ):
                    continue

                status['checked_count'] += 1
                index = map_to_flat_index(mx, my, self.static_map.info.width)
                value = int(self.static_map.data[index])
                if value < 0:
                    status['unknown_count'] += 1
                    continue

                status['max_value'] = max(status['max_value'], value)
                if value >= self.static_map_occupied_threshold:
                    status['known_static'] = True
                    status['reason'] = 'known_static_obstacle'
                    return status

        if status['checked_count'] == 0:
            status['reason'] = 'no_static_cells_checked'
            return status
        if status['unknown_count'] > 0:
            status['reason'] = 'unknown_static_reference_cells'
            return status

        status['free'] = True
        status['reason'] = 'static_reference_free'
        return status

    def _is_known_static_obstacle_near_pose(self, pose_stamped, padding_m=None):
        """
        Returns True if the saved/static map already contains an occupied cell
        near this pose. Used to suppress dynamic skip near known walls.
        """
        if not self.dynamic_use_static_reference_check:
            return False
        return self._static_reference_status_near_pose(pose_stamped, padding_m)[
            'known_static'
        ]

    def _is_local_lethal_dynamic_cell(self, cost):
        if cost < 0:
            return self.dynamic_treat_unknown_as_blocked
        return cost >= self.dynamic_obstacle_cost_threshold

    def _is_local_inscribed_dynamic_cell(self, cost):
        if cost < 0:
            return False
        return (
            cost >= self.dynamic_inscribed_cost_threshold
            and cost < self.dynamic_obstacle_cost_threshold
        )

    def _is_dynamic_cost_blocked(self, cost):
        if cost < 0:
            return self.dynamic_treat_unknown_as_blocked
        blocking_threshold = self.dynamic_obstacle_cost_threshold
        if self.dynamic_enable_local_only_inscribed_fallback:
            blocking_threshold = min(
                blocking_threshold,
                self.dynamic_inscribed_cost_threshold,
            )
        return cost >= blocking_threshold

    def _effective_dynamic_cost(self, cost):
        if cost < 0:
            return 100 if self.dynamic_treat_unknown_as_blocked else 0
        return cost

    def _is_local_cell_traversable(self, mx, my):
        if self.local_costmap is None:
            return False
        if not in_bounds(
            mx,
            my,
            self.local_costmap.info.width,
            self.local_costmap.info.height,
        ):
            return False
        index = map_to_flat_index(mx, my, self.local_costmap.info.width)
        cost = int(self.local_costmap.data[index])
        return not self._is_dynamic_cost_blocked(cost)

    def _is_pose_traversable_in_local_costmap(self, pose_stamped):
        if self.local_costmap is None:
            return False, 'local_costmap_unavailable', 100
        cost_info = self._get_costmap_cost(self.local_costmap, pose_stamped)
        if not cost_info['valid'] or not cost_info['inside']:
            return False, cost_info['reason'], self._effective_dynamic_cost(
                cost_info['cost']
            )
        max_cost = self._effective_dynamic_cost(cost_info['cost'])
        if self._is_dynamic_cost_blocked(cost_info['cost']):
            return False, cost_info['reason'], max_cost
        return True, 'traversable', max_cost

    def _costmap_cell_center(self, costmap, mx, my):
        resolution = costmap.info.resolution
        origin = costmap.info.origin
        origin_yaw = self._yaw_from_quaternion(origin.orientation)
        local_x = (mx + 0.5) * resolution
        local_y = (my + 0.5) * resolution
        cos_yaw = math.cos(origin_yaw)
        sin_yaw = math.sin(origin_yaw)
        return (
            origin.position.x + cos_yaw * local_x - sin_yaw * local_y,
            origin.position.y + sin_yaw * local_x + cos_yaw * local_y,
        )

    def _nearest_dynamic_obstacle_distance(
        self,
        costmap,
        pose_stamped,
        max_distance_m,
        inscribed_max_distance_m=None,
    ):
        costmap_frame = costmap.header.frame_id or self.global_frame
        pose_in_costmap = self._transform_pose_to_frame(
            pose_stamped,
            costmap_frame,
        )
        if pose_in_costmap is None:
            return {
                'valid': False,
                'blocked': False,
                'distance_m': float('inf'),
                'max_cost': 100,
                'inflated_ignored_count': 0,
                'max_ignored_inflated_cost': 0,
                'inscribed_local_only_count': 0,
                'nearest_inscribed_distance_m': float('inf'),
                'nearest_lethal_pose': None,
                'nearest_inscribed_pose': None,
                'reason': 'tf_unavailable',
            }

        position = pose_in_costmap.pose.position
        cell = self._world_to_costmap_cell(costmap, position.x, position.y)
        if cell is None:
            return {
                'valid': False,
                'blocked': False,
                'distance_m': float('inf'),
                'max_cost': 100,
                'inflated_ignored_count': 0,
                'max_ignored_inflated_cost': 0,
                'inscribed_local_only_count': 0,
                'nearest_inscribed_distance_m': float('inf'),
                'nearest_lethal_pose': None,
                'nearest_inscribed_pose': None,
                'reason': 'outside_costmap',
            }

        resolution = costmap.info.resolution
        if resolution <= 0.0:
            return {
                'valid': False,
                'blocked': False,
                'distance_m': float('inf'),
                'max_cost': 100,
                'inflated_ignored_count': 0,
                'max_ignored_inflated_cost': 0,
                'inscribed_local_only_count': 0,
                'nearest_inscribed_distance_m': float('inf'),
                'nearest_lethal_pose': None,
                'nearest_inscribed_pose': None,
                'reason': 'invalid_local_costmap_resolution',
            }

        mx, my = cell
        cell_radius = max(0, int(math.ceil(max_distance_m / resolution)))
        if inscribed_max_distance_m is None:
            inscribed_max_distance_m = max_distance_m
        inscribed_max_distance_m = max(0.0, inscribed_max_distance_m)
        nearest_distance = float('inf')
        nearest_inscribed_distance = float('inf')
        max_cost = 0
        inflated_ignored_count = 0
        max_ignored_inflated_cost = 0
        inscribed_local_only_count = 0
        nearest_lethal_pose = None
        nearest_inscribed_pose = None
        for dy in range(-cell_radius, cell_radius + 1):
            for dx in range(-cell_radius, cell_radius + 1):
                sample_mx = mx + dx
                sample_my = my + dy
                if not in_bounds(
                    sample_mx,
                    sample_my,
                    costmap.info.width,
                    costmap.info.height,
                ):
                    continue

                index = map_to_flat_index(sample_mx, sample_my, costmap.info.width)
                cost = int(costmap.data[index])
                max_cost = max(max_cost, self._effective_dynamic_cost(cost))

                cell_x, cell_y = self._costmap_cell_center(
                    costmap,
                    sample_mx,
                    sample_my,
                )
                distance = self._distance_2d(position.x, position.y, cell_x, cell_y)
                if distance > max_distance_m + 1.0e-9:
                    continue

                if self._is_local_lethal_dynamic_cell(cost):
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_lethal_pose = self._costmap_cell_to_pose(
                            costmap,
                            sample_mx,
                            sample_my,
                            costmap_frame,
                        )
                    continue

                if (
                    self._is_local_inscribed_dynamic_cell(cost)
                    and distance <= inscribed_max_distance_m + 1.0e-9
                ):
                    inscribed_local_only_count += 1
                    if distance < nearest_inscribed_distance:
                        nearest_inscribed_distance = distance
                        nearest_inscribed_pose = self._costmap_cell_to_pose(
                            costmap,
                            sample_mx,
                            sample_my,
                            costmap_frame,
                        )

                if cost > 0:
                    inflated_ignored_count += 1
                    max_ignored_inflated_cost = max(max_ignored_inflated_cost, cost)

        if math.isfinite(nearest_distance):
            return {
                'valid': True,
                'blocked': True,
                'distance_m': nearest_distance,
                'max_cost': max_cost,
                'inflated_ignored_count': inflated_ignored_count,
                'max_ignored_inflated_cost': max_ignored_inflated_cost,
                'inscribed_local_only_count': inscribed_local_only_count,
                'nearest_inscribed_distance_m': nearest_inscribed_distance,
                'nearest_lethal_pose': nearest_lethal_pose,
                'nearest_inscribed_pose': nearest_inscribed_pose,
                'reason': 'dynamic_obstacle_within_threshold',
            }

        return {
            'valid': True,
            'blocked': False,
            'distance_m': float('inf'),
            'max_cost': max_cost,
            'inflated_ignored_count': inflated_ignored_count,
            'max_ignored_inflated_cost': max_ignored_inflated_cost,
            'inscribed_local_only_count': inscribed_local_only_count,
            'nearest_inscribed_distance_m': nearest_inscribed_distance,
            'nearest_lethal_pose': nearest_lethal_pose,
            'nearest_inscribed_pose': nearest_inscribed_pose,
            'reason': (
                'inflated_or_non_lethal_local_cost'
                if inflated_ignored_count > 0
                else 'clear'
            ),
        }

    def _nearest_static_obstacle_distance(self, pose_stamped, max_distance_m):
        if self.static_map is None:
            return {
                'valid': False,
                'distance_m': float('inf'),
                'reason': 'static_map_unavailable',
            }

        static_frame = self.static_map.header.frame_id or self.global_frame
        pose_in_static = self._transform_pose_to_frame(pose_stamped, static_frame)
        if pose_in_static is None:
            return {
                'valid': False,
                'distance_m': float('inf'),
                'reason': 'static_map_tf_unavailable',
            }

        position = pose_in_static.pose.position
        cell = self._world_to_costmap_cell(self.static_map, position.x, position.y)
        if cell is None:
            return {
                'valid': False,
                'distance_m': float('inf'),
                'reason': 'outside_static_map',
            }

        resolution = self.static_map.info.resolution
        if resolution <= 0.0:
            return {
                'valid': False,
                'distance_m': float('inf'),
                'reason': 'invalid_static_map_resolution',
            }

        center_mx, center_my = cell
        cell_radius = max(0, int(math.ceil(max_distance_m / resolution)))
        nearest_distance = float('inf')
        for dy in range(-cell_radius, cell_radius + 1):
            for dx in range(-cell_radius, cell_radius + 1):
                mx = center_mx + dx
                my = center_my + dy
                if not in_bounds(
                    mx,
                    my,
                    self.static_map.info.width,
                    self.static_map.info.height,
                ):
                    continue

                index = map_to_flat_index(mx, my, self.static_map.info.width)
                value = int(self.static_map.data[index])
                if value < self.static_map_occupied_threshold:
                    continue

                cell_x, cell_y = self._costmap_cell_center(self.static_map, mx, my)
                distance = self._distance_2d(position.x, position.y, cell_x, cell_y)
                if distance <= max_distance_m + 1.0e-9:
                    nearest_distance = min(nearest_distance, distance)

        return {
            'valid': True,
            'distance_m': nearest_distance,
            'reason': (
                'static_obstacle_found'
                if math.isfinite(nearest_distance)
                else 'no_static_obstacle_within_radius'
            ),
        }

    def _dynamic_static_encroachment_detected(
        self,
        path_pose,
        local_obstacle_distance,
    ):
        if not math.isfinite(local_obstacle_distance):
            return False

        search_radius = self._get_dynamic_collision_radius_m() + 0.20
        static_info = self._nearest_static_obstacle_distance(
            path_pose,
            search_radius,
        )
        static_distance = static_info.get('distance_m', float('inf'))
        if (
            math.isfinite(static_distance)
            and static_distance - local_obstacle_distance
            > self.dynamic_static_encroachment_tolerance_m
        ):
            text = (
                '[DYNAMIC_DETECT] static object encroachment detected '
                'local_dist=%.3f static_dist=%.3f'
                % (local_obstacle_distance, static_distance)
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return True
        if (
            not math.isfinite(static_distance)
            and search_radius - local_obstacle_distance
            > self.dynamic_static_encroachment_tolerance_m
        ):
            text = (
                '[DYNAMIC_DETECT] static object encroachment detected '
                'local_dist=%.3f static_dist=unavailable'
                % local_obstacle_distance
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
            return True
        return False

    def _is_pose_safe_in_local_costmap(self, pose_stamped):
        if self.local_costmap is None:
            return False, 'local_costmap_unavailable', 100

        cost_info = self._get_costmap_cost(self.local_costmap, pose_stamped)
        max_cost = self._effective_dynamic_cost(cost_info['cost'])
        if not cost_info['valid'] or not cost_info['inside']:
            return False, cost_info['reason'], max_cost
        if self._is_dynamic_cost_blocked(cost_info['cost']):
            return False, cost_info['reason'], max_cost

        resolution = self.local_costmap.info.resolution
        if resolution <= 0.0:
            return False, 'invalid_local_costmap_resolution', max_cost

        cell_radius = int(
            math.ceil(self.dynamic_rejoin_min_clearance_m / resolution)
        )
        radius_sq = cell_radius * cell_radius
        center_mx = cost_info['mx']
        center_my = cost_info['my']

        for dy in range(-cell_radius, cell_radius + 1):
            for dx in range(-cell_radius, cell_radius + 1):
                if dx * dx + dy * dy > radius_sq:
                    continue
                mx = center_mx + dx
                my = center_my + dy
                if not in_bounds(
                    mx,
                    my,
                    self.local_costmap.info.width,
                    self.local_costmap.info.height,
                ):
                    return False, 'clearance_outside_local_costmap', max_cost
                index = map_to_flat_index(mx, my, self.local_costmap.info.width)
                cost = int(self.local_costmap.data[index])
                max_cost = max(max_cost, self._effective_dynamic_cost(cost))
                if self._is_dynamic_cost_blocked(cost):
                    return False, 'clearance_blocked', max_cost

        return True, 'safe', max_cost

    def _find_nearest_path_index(self, path, robot_pose):
        path_frame = self._path_frame(path)
        robot_in_path_frame = self._transform_pose_to_frame(robot_pose, path_frame)
        if robot_in_path_frame is None:
            return -1, float('inf')

        position = robot_in_path_frame.pose.position
        return self._nearest_path_pose(path, position.x, position.y)

    def _find_dynamic_monitor_nearest_path_index(self, path, robot_pose):
        path_frame = self._path_frame(path)
        robot_in_path_frame = self._transform_pose_to_frame(robot_pose, path_frame)
        if robot_in_path_frame is None:
            return -1, float('inf')

        pose_count = len(path.poses)
        if pose_count == 0:
            return -1, float('inf')

        seed_index = max(
            0,
            min(self.dynamic_last_nearest_index, pose_count - 1),
        )
        start_index = self._index_before_distance(
            path,
            seed_index,
            self.dynamic_progress_search_backtrack_m,
        )
        end_index = self._index_after_distance(
            path,
            seed_index,
            self.dynamic_progress_search_forward_m,
        )
        end_index = max(start_index, min(end_index, pose_count - 1))

        position = robot_in_path_frame.pose.position
        nearest_index = start_index
        nearest_distance = float('inf')
        for index in range(start_index, end_index + 1):
            path_position = path.poses[index].pose.position
            distance = self._distance_2d(
                position.x,
                position.y,
                path_position.x,
                path_position.y,
            )
            if distance < nearest_distance:
                nearest_index = index
                nearest_distance = distance

        progress_index = max(seed_index, nearest_index)
        self.dynamic_last_nearest_index = progress_index
        if progress_index != nearest_index:
            progress_position = path.poses[progress_index].pose.position
            nearest_distance = self._distance_2d(
                position.x,
                position.y,
                progress_position.x,
                progress_position.y,
            )
        return progress_index, nearest_distance

    def _distance_along_path(self, path, start_idx, end_idx):
        if path is None or len(path.poses) < 2:
            return 0.0
        start_idx = max(0, min(start_idx, len(path.poses) - 1))
        end_idx = max(0, min(end_idx, len(path.poses) - 1))
        if end_idx <= start_idx:
            return 0.0

        total = 0.0
        for index in range(start_idx + 1, end_idx + 1):
            previous = path.poses[index - 1].pose.position
            current = path.poses[index].pose.position
            total += self._distance_2d(previous.x, previous.y, current.x, current.y)
        return total

    def _index_after_distance(self, path, start_idx, distance_m):
        if path is None or not path.poses:
            return 0
        start_idx = max(0, min(start_idx, len(path.poses) - 1))
        if distance_m <= 0.0:
            return start_idx

        total = 0.0
        for index in range(start_idx + 1, len(path.poses)):
            previous = path.poses[index - 1].pose.position
            current = path.poses[index].pose.position
            total += self._distance_2d(previous.x, previous.y, current.x, current.y)
            if total >= distance_m:
                return index
        return len(path.poses) - 1

    def _index_before_distance(self, path, start_idx, distance_m):
        if path is None or not path.poses:
            return 0
        start_idx = max(0, min(start_idx, len(path.poses) - 1))
        if distance_m <= 0.0:
            return start_idx

        total = 0.0
        for index in range(start_idx - 1, -1, -1):
            previous = path.poses[index].pose.position
            current = path.poses[index + 1].pose.position
            total += self._distance_2d(previous.x, previous.y, current.x, current.y)
            if total >= distance_m:
                return index
        return 0

    def _make_dynamic_detection_report(
        self,
        blocked,
        path,
        nearest_index,
        nearest_distance,
        blocked_start_index,
        blocked_end_index,
        lookahead_end_index,
        min_cost,
        max_cost,
        nearest_obstacle_distance,
        reason,
        local_lethal_count,
        inflated_ignored_count,
        static_known_blocked_count,
        dynamic_only_blocked_count,
        blocked_path_length_m,
        consecutive_count,
        dynamic_only_blocked_poses=None,
        static_known_blocked_poses=None,
        static_unknown_blocked_count=0,
        max_ignored_inflated_cost=0,
        local_inscribed_count=0,
    ):
        return {
            'blocked': blocked,
            'nearest_index': nearest_index,
            'nearest_distance': nearest_distance,
            'blocked_start_index': blocked_start_index,
            'blocked_end_index': blocked_end_index,
            'lookahead_end_index': lookahead_end_index,
            'min_cost': int(min_cost if min_cost is not None else 0),
            'max_cost': int(max_cost),
            'nearest_obstacle_distance_m': nearest_obstacle_distance,
            'obstacle_distance_threshold_m': self._get_dynamic_detection_radius_m(),
            'reason': reason,
            'local_costmap_frame': self.local_costmap.header.frame_id
            or self.global_frame,
            'path_frame': self._path_frame(path),
            'local_lethal_count': local_lethal_count,
            'inflated_ignored_count': inflated_ignored_count,
            'static_known_blocked_count': static_known_blocked_count,
            'static_unknown_blocked_count': static_unknown_blocked_count,
            'dynamic_only_blocked_count': dynamic_only_blocked_count,
            'blocked_path_length_m': blocked_path_length_m,
            'consecutive_count': consecutive_count,
            'max_ignored_inflated_cost': int(max_ignored_inflated_cost),
            'local_inscribed_count': local_inscribed_count,
            'dynamic_only_blocked_poses': dynamic_only_blocked_poses or [],
            'static_known_blocked_poses': static_known_blocked_poses or [],
        }

    def _publish_dynamic_detection_debug(self, report):
        text = (
            '[DYNAMIC_DETECT] nearest_index=%d lookahead_end_index=%d '
            'local_lethal_count=%d local_inscribed_count=%d '
            'inflated_ignored_count=%d '
            'static_known_blocked_count=%d dynamic_only_blocked_count=%d '
            'blocked_path_length_m=%.3f consecutive_count=%d'
            % (
                report.get('nearest_index', -1),
                report.get('lookahead_end_index', -1),
                report.get('local_lethal_count', 0),
                report.get('local_inscribed_count', 0),
                report.get('inflated_ignored_count', 0),
                report.get('static_known_blocked_count', 0),
                report.get('dynamic_only_blocked_count', 0),
                report.get('blocked_path_length_m', 0.0),
                report.get('consecutive_count', 0),
            )
        )
        self.get_logger().info(text, throttle_duration_sec=1.0)
        self._publish_dynamic_skip_status(text)

    def _reset_dynamic_detection_candidate(self):
        self.dynamic_detection_candidate = None

    def _detect_dynamic_blocked_interval(self, path, force_confirm=False):
        if not self.enable_dynamic_obstacle_skip:
            return None
        if path is None or len(path.poses) < 2:
            return None
        if self.execution_status != self.STATUS_EXECUTING:
            return None
        if self.local_costmap is None:
            return None

        now = time.monotonic()
        if now < self.dynamic_skip_monitor_suppressed_until_monotonic:
            return None

        path_frame = self._path_frame(path)
        robot_pose = self._lookup_robot_pose(path_frame)
        if robot_pose is None:
            return None

        nearest_index, nearest_distance = self._find_dynamic_monitor_nearest_path_index(
            path,
            robot_pose,
        )
        if nearest_index < 0:
            return None

        if self.dynamic_skip_monitor_resume_index is not None:
            if nearest_index < self.dynamic_skip_monitor_resume_index:
                now = time.monotonic()
                if (
                    now
                    - getattr(
                        self,
                        'last_dynamic_skip_resume_wait_log',
                        0.0,
                    )
                    >= 2.0
                ):
                    self.last_dynamic_skip_resume_wait_log = now
                    self._publish_dynamic_skip_status(
                        '[DYNAMIC_SKIP] following temporary detour before '
                        'resuming obstacle checks at path_index=%d current=%d'
                        % (
                            self.dynamic_skip_monitor_resume_index,
                            nearest_index,
                        )
                    )
                return {
                    'blocked': False,
                    'nearest_index': nearest_index,
                    'nearest_distance': nearest_distance,
                    'blocked_start_index': -1,
                    'blocked_end_index': -1,
                    'lookahead_end_index': nearest_index,
                    'min_cost': 0,
                    'max_cost': 0,
                    'nearest_obstacle_distance_m': float('inf'),
                    'obstacle_distance_threshold_m': (
                        self._get_dynamic_detection_radius_m()
                    ),
                    'reason': 'temporary_detour_in_progress',
                    'local_costmap_frame': self.local_costmap.header.frame_id
                    or self.global_frame,
                    'path_frame': path_frame,
                }
            self.dynamic_skip_monitor_resume_index = None

        lookahead_end_index = self._index_after_distance(
            path,
            nearest_index,
            self.dynamic_skip_lookahead_m,
        )
        dynamic_only_blocked_indices = []
        dynamic_only_blocked_poses = []
        static_known_blocked_poses = []
        local_lethal_count = 0
        local_inscribed_count = 0
        inflated_ignored_count = 0
        static_known_blocked_count = 0
        static_unknown_blocked_count = 0
        max_ignored_inflated_cost = 0
        min_cost = None
        max_cost = 0
        nearest_obstacle_distance = float('inf')
        reason = 'clear'
        detection_radius_m = self._get_dynamic_detection_radius_m()
        distance_from_nearest = 0.0

        for index in range(nearest_index, lookahead_end_index + 1):
            if index > nearest_index:
                previous = path.poses[index - 1].pose.position
                current = path.poses[index].pose.position
                distance_from_nearest += self._distance_2d(
                    previous.x,
                    previous.y,
                    current.x,
                    current.y,
                )
            if (
                self.dynamic_active_path_is_temporary
                and self.dynamic_connector_allow_blocked_start
                and distance_from_nearest
                <= self.dynamic_connector_start_grace_m + 1.0e-6
            ):
                continue
            obstacle_info = self._nearest_dynamic_obstacle_distance(
                self.local_costmap,
                path.poses[index],
                detection_radius_m,
                inscribed_max_distance_m=self.dynamic_obstacle_distance_threshold_m,
            )
            if not obstacle_info['valid']:
                reason = obstacle_info['reason']
                continue
            inflated_ignored_count += obstacle_info.get(
                'inflated_ignored_count',
                0,
            )
            max_ignored_inflated_cost = max(
                max_ignored_inflated_cost,
                obstacle_info.get('max_ignored_inflated_cost', 0),
            )
            max_cost = max(max_cost, obstacle_info.get('max_cost', 0))
            blocked_by_lethal = obstacle_info['blocked']
            blocked_by_inscribed = (
                self.dynamic_enable_local_only_inscribed_fallback
                and obstacle_info.get('inscribed_local_only_count', 0) > 0
            )
            if not blocked_by_lethal and not blocked_by_inscribed:
                if obstacle_info.get('reason') == 'inflated_or_non_lethal_local_cost':
                    reason = obstacle_info['reason']
                continue

            if blocked_by_lethal:
                local_lethal_count += 1
                static_check_pose = (
                    obstacle_info.get('nearest_lethal_pose') or path.poses[index]
                )
                static_padding_m = self.static_reference_padding_m
                effective_cost = obstacle_info['max_cost']
                obstacle_distance = obstacle_info['distance_m']
                candidate_reason = 'local_only_dynamic_obstacle_candidate'
            else:
                local_inscribed_count += 1
                static_check_pose = (
                    obstacle_info.get('nearest_inscribed_pose') or path.poses[index]
                )
                static_padding_m = (
                    self.dynamic_inscribed_static_reference_padding_m
                )
                effective_cost = obstacle_info.get(
                    'max_ignored_inflated_cost',
                    obstacle_info.get('max_cost', 0),
                )
                obstacle_distance = obstacle_info.get(
                    'nearest_inscribed_distance_m',
                    float('inf'),
                )
                candidate_reason = (
                    'local_only_inscribed_cost_collision_risk'
                )

            static_status = self._static_reference_status_near_pose(
                static_check_pose,
                padding_m=static_padding_m,
            )
            if self.dynamic_use_static_reference_check:
                static_encroachment = False
                if static_status['known_static']:
                    static_encroachment = self._dynamic_static_encroachment_detected(
                        path.poses[index],
                        obstacle_distance,
                    )
                    if not static_encroachment:
                        static_known_blocked_count += 1
                        static_known_blocked_poses.append(
                            copy.deepcopy(path.poses[index])
                        )
                        reason = 'known_static_wall_or_corner'
                        continue
                if not static_encroachment and not static_status['free']:
                    static_unknown_blocked_count += 1
                    reason = static_status['reason']
                    continue

            min_cost = effective_cost if min_cost is None else min(
                min_cost,
                effective_cost,
            )
            max_cost = max(max_cost, effective_cost)
            nearest_obstacle_distance = min(
                nearest_obstacle_distance,
                obstacle_distance,
            )
            dynamic_only_blocked_indices.append(index)
            dynamic_only_blocked_poses.append(copy.deepcopy(path.poses[index]))
            reason = candidate_reason

        if not dynamic_only_blocked_indices:
            self._reset_dynamic_detection_candidate()
            report = self._make_dynamic_detection_report(
                False,
                path,
                nearest_index,
                nearest_distance,
                -1,
                -1,
                lookahead_end_index,
                0,
                max_cost,
                float('inf'),
                reason,
                local_lethal_count,
                inflated_ignored_count,
                static_known_blocked_count,
                0,
                0.0,
                0,
                [],
                static_known_blocked_poses,
                static_unknown_blocked_count,
                max_ignored_inflated_cost,
                local_inscribed_count,
            )
            self.dynamic_ignored_static_marker_poses = static_known_blocked_poses
            if static_known_blocked_count > 0:
                text = (
                    '[DYNAMIC_DETECT] rejected: known static wall/corner; '
                    'keeping normal FollowPath'
                )
                self.get_logger().info(text, throttle_duration_sec=1.0)
                self._publish_dynamic_skip_status(text)
                self._publish_skipped_segment_markers()
            elif inflated_ignored_count > 0:
                text = (
                    '[DYNAMIC_DETECT] rejected: inflated/non-lethal cost; '
                    'rejected inflated local cost; cost=%d threshold=%d'
                    % (
                        max_ignored_inflated_cost,
                        self.dynamic_obstacle_cost_threshold,
                    )
                )
                self.get_logger().info(text, throttle_duration_sec=1.0)
                self._publish_dynamic_skip_status(text)
            self._publish_dynamic_detection_debug(report)
            return report

        blocked_start_index = self._index_before_distance(
            path,
            dynamic_only_blocked_indices[0],
            self.dynamic_skip_padding_m,
        )
        blocked_end_index = self._index_after_distance(
            path,
            dynamic_only_blocked_indices[-1],
            self.dynamic_skip_padding_m,
        )
        blocked_path_length_m = self._distance_along_path(
            path,
            dynamic_only_blocked_indices[0],
            dynamic_only_blocked_indices[-1],
        )

        if len(dynamic_only_blocked_indices) < self.dynamic_min_blocked_pose_count:
            self._reset_dynamic_detection_candidate()
            report = self._make_dynamic_detection_report(
                False,
                path,
                nearest_index,
                nearest_distance,
                blocked_start_index,
                blocked_end_index,
                lookahead_end_index,
                min_cost,
                max_cost,
                nearest_obstacle_distance,
                'too_few_blocked_poses',
                local_lethal_count,
                inflated_ignored_count,
                static_known_blocked_count,
                len(dynamic_only_blocked_indices),
                blocked_path_length_m,
                0,
                dynamic_only_blocked_poses,
                static_known_blocked_poses,
                static_unknown_blocked_count,
                max_ignored_inflated_cost,
                local_inscribed_count,
            )
            text = (
                '[DYNAMIC_DETECT] rejected: too few blocked poses '
                'blocked_pose_count=%d required=%d'
                % (
                    len(dynamic_only_blocked_indices),
                    self.dynamic_min_blocked_pose_count,
                )
            )
            self.get_logger().info(text, throttle_duration_sec=1.0)
            self._publish_dynamic_skip_status(text)
            self._publish_dynamic_detection_debug(report)
            return report

        if blocked_path_length_m < self.dynamic_min_blocked_path_length_m:
            self._reset_dynamic_detection_candidate()
            report = self._make_dynamic_detection_report(
                False,
                path,
                nearest_index,
                nearest_distance,
                blocked_start_index,
                blocked_end_index,
                lookahead_end_index,
                min_cost,
                max_cost,
                nearest_obstacle_distance,
                'blocked_path_length_below_threshold',
                local_lethal_count,
                inflated_ignored_count,
                static_known_blocked_count,
                len(dynamic_only_blocked_indices),
                blocked_path_length_m,
                0,
                dynamic_only_blocked_poses,
                static_known_blocked_poses,
                static_unknown_blocked_count,
                max_ignored_inflated_cost,
                local_inscribed_count,
            )
            text = (
                '[DYNAMIC_DETECT] rejected: too few blocked poses '
                'blocked_path_length_m=%.3f required=%.3f'
                % (
                    blocked_path_length_m,
                    self.dynamic_min_blocked_path_length_m,
                )
            )
            self.get_logger().info(text, throttle_duration_sec=1.0)
            self._publish_dynamic_skip_status(text)
            self._publish_dynamic_detection_debug(report)
            return report

        candidate = self.dynamic_detection_candidate
        candidate_changed = False
        if candidate is not None:
            if (
                self.dynamic_detection_hysteresis_sec > 0.0
                and now - candidate.get('last_seen_time', 0.0)
                > self.dynamic_detection_hysteresis_sec
            ):
                candidate_changed = True
            index_margin = max(1, self.dynamic_resume_ignore_index_margin)
            if (
                abs(blocked_start_index - candidate.get('blocked_start_index', -1))
                > index_margin
            ):
                candidate_changed = True

        if candidate is None or candidate_changed:
            candidate = {
                'first_seen_time': now,
                'last_seen_time': now,
                'count': 0,
                'nearest_index': nearest_index,
                'blocked_start_index': blocked_start_index,
                'blocked_end_index': blocked_end_index,
                'max_cost': int(max_cost),
                'min_distance': nearest_obstacle_distance,
            }

        candidate['last_seen_time'] = now
        candidate['count'] = candidate.get('count', 0) + 1
        candidate['nearest_index'] = nearest_index
        candidate['blocked_start_index'] = blocked_start_index
        candidate['blocked_end_index'] = blocked_end_index
        candidate['max_cost'] = max(candidate.get('max_cost', 0), int(max_cost))
        candidate['min_distance'] = min(
            candidate.get('min_distance', float('inf')),
            nearest_obstacle_distance,
        )
        self.dynamic_detection_candidate = candidate
        consecutive_count = candidate['count']

        required_consecutive = (
            1 if force_confirm else self.dynamic_required_consecutive_detections
        )
        report = self._make_dynamic_detection_report(
            consecutive_count >= required_consecutive,
            path,
            nearest_index,
            nearest_distance,
            blocked_start_index,
            blocked_end_index,
            lookahead_end_index,
            min_cost,
            max_cost,
            nearest_obstacle_distance,
            reason,
            local_lethal_count,
            inflated_ignored_count,
            static_known_blocked_count,
            len(dynamic_only_blocked_indices),
            blocked_path_length_m,
            consecutive_count,
            dynamic_only_blocked_poses,
            static_known_blocked_poses,
            static_unknown_blocked_count,
            max_ignored_inflated_cost,
            local_inscribed_count,
        )
        self._publish_dynamic_detection_debug(report)

        if consecutive_count < required_consecutive:
            text = (
                '[DYNAMIC_DETECT] candidate seen count=%d/%d '
                'nearest_index=%d blocked_start_index=%d blocked_end_index=%d '
                'max_cost=%d min_distance=%.3f'
                % (
                    consecutive_count,
                    required_consecutive,
                    nearest_index,
                    blocked_start_index,
                    blocked_end_index,
                    int(max_cost),
                    nearest_obstacle_distance,
                )
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)
            report['blocked'] = False
            report['reason'] = 'candidate_pending_confirmation'
            return report

        report['reason'] = 'confirmed_local_only_dynamic_obstacle'
        self.dynamic_confirmed_marker_report = copy.deepcopy(report)
        self.dynamic_ignored_static_marker_poses = static_known_blocked_poses
        text = (
            '[DYNAMIC_DETECT] confirmed local-only dynamic obstacle '
            'nearest_index=%d blocked_start=%d blocked_end=%d'
            % (nearest_index, blocked_start_index, blocked_end_index)
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        self._publish_skipped_segment_markers()
        return report

    def _is_rejoin_pose_static_safe(self, pose_stamped):
        if not self.dynamic_use_static_reference_check:
            return True, 'static_reference_disabled'
        status = self._static_reference_status_near_pose(
            pose_stamped,
            self.static_reference_padding_m,
        )
        if status['known_static']:
            return False, 'known_static_obstacle'
        return True, status['reason']

    def _is_rejoin_pose_global_safe(self, pose_stamped):
        if self.nav_costmap is None:
            return True, 'global_costmap_unavailable'
        cost_info = self._get_costmap_cost(self.nav_costmap, pose_stamped)
        if not cost_info['valid']:
            if cost_info['reason'] == 'tf_unavailable':
                return False, 'global_costmap_tf_unavailable'
            return True, cost_info['reason']
        if not cost_info['inside']:
            return True, 'outside_global_costmap'
        cost = int(cost_info['cost'])
        if cost < 0:
            if self.dynamic_treat_unknown_as_blocked:
                return False, 'unknown_global_costmap'
            return True, 'unknown_global_costmap_allowed'
        if cost >= self.dynamic_obstacle_cost_threshold:
            return False, 'lethal_global_costmap_cell'
        return True, 'global_safe'

    def _is_pose_inside_local_costmap(self, pose_stamped):
        if self.local_costmap is None:
            return False
        cost_info = self._get_costmap_cost(self.local_costmap, pose_stamped)
        return bool(cost_info['valid'] and cost_info['inside'])

    def _is_rejoin_pose_locally_clear_if_visible(self, pose_stamped):
        if self.local_costmap is None:
            return True, 'local_costmap_unavailable'
        local = self._check_local_corridor_at_pose(
            pose_stamped,
            self._get_dynamic_collision_radius_m(),
        )
        if not local['valid']:
            return False, local['reason']
        if not local['inside']:
            return True, 'outside_local_costmap'
        if local['blocked']:
            return False, local['reason']
        return True, local['reason']

    def _find_rejoin_candidates_after_block(self, path, report):
        if path is None or not path.poses:
            return []

        blocked_end_index = max(
            0,
            min(report.get('blocked_end_index', -1), len(path.poses) - 1),
        )
        blocked_start_index = max(
            0,
            min(report.get('blocked_start_index', blocked_end_index), len(path.poses) - 1),
        )
        if blocked_end_index >= len(path.poses) - 1:
            return []

        text = (
            '[DYNAMIC_REJOIN] searching original path from index=%d '
            'max_distance=%.2fm'
            % (blocked_end_index + 1, self.dynamic_rejoin_max_search_distance_m)
        )
        self.get_logger().info(text)
        self._publish_dynamic_skip_status(text)

        candidates = []
        last_reason = 'no_candidate_checked'
        for index in range(blocked_end_index + 1, len(path.poses)):
            if index <= blocked_end_index or index <= blocked_start_index:
                last_reason = 'behind_or_inside_blocked_interval'
                continue

            distance_from_block = self._distance_along_path(
                path,
                blocked_end_index,
                index,
            )
            if distance_from_block > self.dynamic_rejoin_max_search_distance_m:
                break

            remaining_poses = len(path.poses) - index
            near_end = index >= len(path.poses) - self.dynamic_skip_min_remaining_poses
            if (
                remaining_poses < self.dynamic_skip_min_remaining_poses
                and not near_end
            ):
                last_reason = 'candidate_leaves_too_few_remaining_poses'
                continue

            inside_local = self._is_pose_inside_local_costmap(path.poses[index])
            static_safe, static_reason = self._is_rejoin_pose_static_safe(
                path.poses[index]
            )
            global_safe, global_reason = self._is_rejoin_pose_global_safe(
                path.poses[index]
            )
            local_safe, local_reason = self._is_rejoin_pose_locally_clear_if_visible(
                path.poses[index]
            )
            planner_allowed = static_safe and global_safe and local_safe
            text = (
                '[DYNAMIC_REJOIN] candidate index=%d distance_from_block=%.3f '
                'inside_local_costmap=%s static_safe=%s global_safe=%s '
                'planner_allowed=%s static_reason=%s global_reason=%s '
                'local_reason=%s'
                % (
                    index,
                    distance_from_block,
                    str(inside_local).lower(),
                    str(static_safe).lower(),
                    str(global_safe).lower(),
                    str(planner_allowed).lower(),
                    static_reason,
                    global_reason,
                    local_reason,
                )
            )
            self.get_logger().info(text)
            self._publish_dynamic_skip_status(text)

            if not planner_allowed:
                last_reason = (
                    'index=%d static_safe=%s global_safe=%s local_safe=%s'
                    % (
                        index,
                        str(static_safe).lower(),
                        str(global_safe).lower(),
                        str(local_safe).lower(),
                    )
                )
                continue

            candidates.append(index)
            if len(candidates) >= self.dynamic_max_rejoin_candidates:
                break

        if not candidates:
            text = (
                '[DYNAMIC_REJOIN] no candidate within %.2fm last_reason=%s'
                % (self.dynamic_rejoin_max_search_distance_m, last_reason)
            )
            self.get_logger().warn(text)
            self._publish_dynamic_skip_status(text)
        return candidates

    def _find_rejoin_index_after_block(self, path, blocked_end_index, start_index=None):
        report = {
            'blocked_start_index': blocked_end_index,
            'blocked_end_index': blocked_end_index,
        }
        candidates = self._find_rejoin_candidates_after_block(path, report)
        if start_index is not None:
            candidates = [index for index in candidates if index >= start_index]
        if candidates:
            return candidates[0], 'safe_rejoin'
        return (
            None,
            'no_safe_rejoin_within_%.2fm'
            % self.dynamic_rejoin_max_search_distance_m,
        )

    def _find_rejoin_index_after_block_legacy(self, path, blocked_end_index, start_index=None):
        if path is None or not path.poses:
            return None, 'path_empty'
        if blocked_end_index >= len(path.poses) - 1:
            return None, 'blocked_to_path_end'

        robot_pose = None
        if self.dynamic_require_safe_connector:
            robot_pose = self._lookup_robot_pose(self._path_frame(path))
            if robot_pose is None:
                return None, 'robot_pose_unavailable_for_connector'

        last_reason = 'no_candidate_checked'
        first_index = blocked_end_index + 1
        if start_index is not None:
            first_index = max(first_index, start_index)
        for index in range(first_index, len(path.poses)):
            distance_from_block = self._distance_along_path(
                path,
                blocked_end_index,
                index,
            )
            if distance_from_block > self.dynamic_rejoin_max_search_distance_m:
                return (
                    None,
                    'no_safe_rejoin_within_%.2fm last_reason=%s'
                    % (
                        self.dynamic_rejoin_max_search_distance_m,
                        last_reason,
                    ),
                )

            remaining_poses = len(path.poses) - index
            if (
                remaining_poses < self.dynamic_skip_min_remaining_poses
                and index < len(path.poses) - self.dynamic_skip_min_remaining_poses
            ):
                last_reason = 'candidate_leaves_too_few_remaining_poses'
                continue

            traversable, reason, _ = self._is_pose_traversable_in_local_costmap(
                path.poses[index]
            )
            if not traversable:
                last_reason = 'index=%d unsafe:%s' % (index, reason)
                continue

            if self.dynamic_require_safe_connector:
                connector_safe, connector_reason = self._is_connector_safe_to_rejoin(
                    robot_pose,
                    path.poses[index],
                )
                if not connector_safe:
                    last_reason = (
                        'index=%d connector_unsafe:%s'
                        % (index, connector_reason)
                    )
                    continue

            return index, 'safe_rejoin'

        return None, last_reason

    def _build_dynamic_rejoin_path(self, path, report, rejoin_index):
        if not self.dynamic_enable_local_detour:
            return self._build_path_from_index(path, rejoin_index)

        path_frame = self._path_frame(path)
        robot_pose = self._lookup_robot_pose(path_frame)
        if robot_pose is None:
            return None

        nearest_index = max(
            0,
            min(report.get('nearest_index', 0), len(path.poses) - 1),
        )
        blocked_start_index = max(
            nearest_index,
            min(report.get('blocked_start_index', nearest_index), rejoin_index),
        )
        min_offset = max(
            self.dynamic_detour_min_lateral_offset_m,
            self.dynamic_rejoin_min_clearance_m,
        )
        max_offset = max(min_offset, self.dynamic_detour_max_lateral_offset_m)

        offsets = []
        offset = min_offset
        while offset <= max_offset + 1.0e-6:
            offsets.append(offset)
            offset += self.dynamic_detour_offset_step_m

        if self.dynamic_enable_local_astar_detour:
            astar_candidate = self._build_local_astar_detour_path(
                path,
                robot_pose,
                rejoin_index,
            )
            if astar_candidate is not None:
                self.get_logger().info(
                    '[DYNAMIC_SKIP] local A* detour selected '
                    'rejoin_index=%d poses=%d distance=%.3f'
                    % (
                        rejoin_index,
                        len(astar_candidate.poses),
                        self._path_length(astar_candidate),
                    )
                )
                self._publish_dynamic_skip_status(
                    '[DYNAMIC_SKIP] local A* detour selected '
                    'rejoin_index=%d poses=%d distance=%.3f'
                    % (
                        rejoin_index,
                        len(astar_candidate.poses),
                        self._path_length(astar_candidate),
                    )
                )
                return astar_candidate

        for offset in offsets:
            for side in (1.0, -1.0):
                candidate = self._make_dynamic_detour_candidate(
                    path,
                    robot_pose,
                    nearest_index,
                    blocked_start_index,
                    rejoin_index,
                    side * offset,
                )
                if candidate is not None:
                    self.get_logger().info(
                        '[DYNAMIC_SKIP] temporary detour selected '
                        'rejoin_index=%d lateral_offset=%.3f poses=%d '
                        'distance=%.3f'
                        % (
                            rejoin_index,
                            side * offset,
                            len(candidate.poses),
                            self._path_length(candidate),
                        )
                    )
                    self._publish_dynamic_skip_status(
                        '[DYNAMIC_SKIP] temporary detour selected '
                        'rejoin_index=%d lateral_offset=%.3f poses=%d '
                        'distance=%.3f'
                        % (
                            rejoin_index,
                            side * offset,
                            len(candidate.poses),
                            self._path_length(candidate),
                        )
                    )
                    return candidate

        return None

    def _build_local_astar_connector_path(self, path, robot_pose, rejoin_index):
        if self.local_costmap is None or rejoin_index >= len(path.poses):
            return None

        start_cell, start_reason = self._get_costmap_cell_for_pose(
            self.local_costmap,
            robot_pose,
        )
        goal_cell, goal_reason = self._get_costmap_cell_for_pose(
            self.local_costmap,
            path.poses[rejoin_index],
        )
        if start_cell is None or goal_cell is None:
            self.get_logger().info(
                '[DYNAMIC_CONNECTOR] local A* unavailable: '
                'start_reason=%s goal_reason=%s'
                % (start_reason, goal_reason),
                throttle_duration_sec=2.0,
            )
            return None

        if not self._is_local_cell_traversable(*goal_cell):
            return None

        cell_path = self._find_local_costmap_astar(start_cell, goal_cell)
        if not cell_path:
            return None

        connector = Path()
        connector.header = copy.deepcopy(path.header)
        connector.header.frame_id = self._path_frame(path)
        self._append_pose_without_duplicate(connector, robot_pose)

        previous_pose = connector.poses[-1] if connector.poses else None
        for mx, my in cell_path:
            pose = self._costmap_cell_to_pose(
                self.local_costmap,
                mx,
                my,
                connector.header.frame_id,
            )
            if pose is None:
                return None
            if previous_pose is not None:
                previous_position = previous_pose.pose.position
                position = pose.pose.position
                if (
                    self._distance_2d(
                        previous_position.x,
                        previous_position.y,
                        position.x,
                        position.y,
                    )
                    < self.dynamic_detour_sample_step_m
                ):
                    continue
            connector.poses.append(pose)
            previous_pose = pose

        if connector.poses:
            connector.poses[-1] = copy.deepcopy(path.poses[rejoin_index])

        if len(connector.poses) < 2:
            return None

        self._recompute_orientations(connector)
        self._stamp_path(connector)
        return connector

    def _build_lateral_detour_connector_path(
        self,
        path,
        report,
        robot_pose,
        rejoin_index,
    ):
        if rejoin_index >= len(path.poses):
            return None

        nearest_index = max(
            0,
            min(report.get('nearest_index', 0), len(path.poses) - 1),
        )
        blocked_start_index = max(
            nearest_index,
            min(report.get('blocked_start_index', nearest_index), rejoin_index),
        )
        min_offset = max(
            self.dynamic_detour_min_lateral_offset_m,
            self.dynamic_rejoin_min_clearance_m,
        )
        max_offset = max(min_offset, self.dynamic_detour_max_lateral_offset_m)
        offsets = []
        offset = min_offset
        while offset <= max_offset + 1.0e-6:
            offsets.append(offset)
            offset += self.dynamic_detour_offset_step_m

        for offset in offsets:
            for side in (1.0, -1.0):
                connector = self._make_dynamic_detour_connector_candidate(
                    path,
                    robot_pose,
                    nearest_index,
                    blocked_start_index,
                    rejoin_index,
                    side * offset,
                )
                if connector is not None:
                    self.get_logger().info(
                        '[DYNAMIC_CONNECTOR] lateral connector selected '
                        'rejoin_index=%d lateral_offset=%.3f poses=%d '
                        'distance=%.3f'
                        % (
                            rejoin_index,
                            side * offset,
                            len(connector.poses),
                            self._path_length(connector),
                        )
                    )
                    return connector
        return None

    def _make_dynamic_detour_connector_candidate(
        self,
        path,
        robot_pose,
        nearest_index,
        blocked_start_index,
        rejoin_index,
        lateral_offset_m,
    ):
        if rejoin_index >= len(path.poses):
            return None

        connector = Path()
        connector.header = copy.deepcopy(path.header)
        connector.header.frame_id = self._path_frame(path)
        self._append_pose_without_duplicate(connector, robot_pose)

        prefix_end_index = max(
            nearest_index,
            min(blocked_start_index - 1, rejoin_index - 1),
        )
        for index in range(nearest_index + 1, prefix_end_index + 1):
            safe, _, _ = self._is_pose_safe_in_local_costmap(path.poses[index])
            if not safe:
                break
            self._append_pose_without_duplicate(connector, path.poses[index])

        start_anchor = connector.poses[-1]
        rejoin_pose = path.poses[rejoin_index]
        tangent = self._path_tangent_for_detour(path, nearest_index, rejoin_index)
        if tangent is None:
            return None

        tangent_x, tangent_y = tangent
        perp_x = -tangent_y
        perp_y = tangent_x
        start_offset = self._offset_pose_xy(
            start_anchor,
            perp_x * lateral_offset_m,
            perp_y * lateral_offset_m,
        )
        end_offset = self._offset_pose_xy(
            rejoin_pose,
            perp_x * lateral_offset_m,
            perp_y * lateral_offset_m,
        )

        previous = start_anchor
        for point in (start_offset, end_offset, rejoin_pose):
            if not self._append_safe_line_samples(connector, previous, point):
                return None
            previous = point

        if len(connector.poses) < 2:
            return None

        self._recompute_orientations(connector)
        self._stamp_path(connector)
        return connector

    def _build_local_astar_detour_path(self, path, robot_pose, rejoin_index):
        if self.local_costmap is None or rejoin_index >= len(path.poses):
            return None

        start_cell, start_reason = self._get_costmap_cell_for_pose(
            self.local_costmap,
            robot_pose,
        )
        goal_cell, goal_reason = self._get_costmap_cell_for_pose(
            self.local_costmap,
            path.poses[rejoin_index],
        )
        if start_cell is None or goal_cell is None:
            self.get_logger().info(
                '[DYNAMIC_SKIP] local A* detour unavailable: '
                'start_reason=%s goal_reason=%s'
                % (start_reason, goal_reason),
                throttle_duration_sec=2.0,
            )
            return None

        if not self._is_local_cell_traversable(*goal_cell):
            return None

        cell_path = self._find_local_costmap_astar(start_cell, goal_cell)
        if not cell_path:
            return None

        candidate = Path()
        candidate.header = copy.deepcopy(path.header)
        candidate.header.frame_id = self._path_frame(path)
        self._append_pose_without_duplicate(candidate, robot_pose)

        previous_pose = candidate.poses[-1] if candidate.poses else None
        for mx, my in cell_path:
            pose = self._costmap_cell_to_pose(
                self.local_costmap,
                mx,
                my,
                candidate.header.frame_id,
            )
            if pose is None:
                return None
            if previous_pose is not None:
                previous_position = previous_pose.pose.position
                position = pose.pose.position
                if (
                    self._distance_2d(
                        previous_position.x,
                        previous_position.y,
                        position.x,
                        position.y,
                    )
                    < self.dynamic_detour_sample_step_m
                ):
                    continue
            candidate.poses.append(pose)
            previous_pose = pose

        if candidate.poses:
            candidate.poses[-1] = copy.deepcopy(path.poses[rejoin_index])

        for index in range(rejoin_index + 1, len(path.poses)):
            self._append_pose_without_duplicate(candidate, path.poses[index])

        if len(candidate.poses) < self.min_path_poses:
            return None

        self._recompute_orientations(candidate)
        self._stamp_path(candidate)
        return candidate

    def _find_local_costmap_astar(self, start_cell, goal_cell):
        width = self.local_costmap.info.width
        height = self.local_costmap.info.height
        start = tuple(start_cell)
        goal = tuple(goal_cell)
        if not self._is_local_cell_traversable(*start):
            start = self._nearest_traversable_cell(start)
            if start is None:
                return None
        if not self._is_local_cell_traversable(*goal):
            return None

        open_heap = []
        heapq.heappush(open_heap, (0.0, start))
        came_from = {}
        g_score = {start: 0.0}
        visited = set()
        neighbors = (
            (-1, -1, math.sqrt(2.0)),
            (0, -1, 1.0),
            (1, -1, math.sqrt(2.0)),
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (-1, 1, math.sqrt(2.0)),
            (0, 1, 1.0),
            (1, 1, math.sqrt(2.0)),
        )

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current in visited:
                continue
            if current == goal:
                return self._reconstruct_cell_path(came_from, current)
            visited.add(current)

            for dx, dy, move_cost in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                if not in_bounds(neighbor[0], neighbor[1], width, height):
                    continue
                if not self._is_local_cell_traversable(*neighbor):
                    continue

                index = map_to_flat_index(neighbor[0], neighbor[1], width)
                cost = int(self.local_costmap.data[index])
                cost_penalty = max(0.0, self._effective_dynamic_cost(cost)) / 100.0
                tentative_g = g_score[current] + move_cost + cost_penalty
                if tentative_g >= g_score.get(neighbor, float('inf')):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heuristic = math.hypot(goal[0] - neighbor[0], goal[1] - neighbor[1])
                heapq.heappush(open_heap, (tentative_g + heuristic, neighbor))

        return None

    def _nearest_traversable_cell(self, start):
        width = self.local_costmap.info.width
        height = self.local_costmap.info.height
        max_radius = max(1, int(math.ceil(0.30 / self.local_costmap.info.resolution)))
        for radius in range(max_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    cell = (start[0] + dx, start[1] + dy)
                    if not in_bounds(cell[0], cell[1], width, height):
                        continue
                    if self._is_local_cell_traversable(*cell):
                        return cell
        return None

    def _reconstruct_cell_path(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _costmap_cell_to_pose(self, costmap, mx, my, target_frame):
        costmap_frame = costmap.header.frame_id or self.global_frame
        x, y = self._costmap_cell_center(costmap, mx, my)
        pose = PoseStamped()
        pose.header.frame_id = costmap_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.w = 1.0
        return self._transform_pose_to_frame(pose, target_frame)

    def _make_dynamic_detour_candidate(
        self,
        path,
        robot_pose,
        nearest_index,
        blocked_start_index,
        rejoin_index,
        lateral_offset_m,
    ):
        if rejoin_index >= len(path.poses):
            return None

        candidate = Path()
        candidate.header = copy.deepcopy(path.header)
        candidate.header.frame_id = self._path_frame(path)
        self._append_pose_without_duplicate(candidate, robot_pose)

        prefix_end_index = max(
            nearest_index,
            min(blocked_start_index - 1, rejoin_index - 1),
        )
        for index in range(nearest_index + 1, prefix_end_index + 1):
            safe, _, _ = self._is_pose_safe_in_local_costmap(path.poses[index])
            if not safe:
                break
            self._append_pose_without_duplicate(candidate, path.poses[index])

        start_anchor = candidate.poses[-1]
        rejoin_pose = path.poses[rejoin_index]
        tangent = self._path_tangent_for_detour(
            path,
            nearest_index,
            rejoin_index,
        )
        if tangent is None:
            return None

        tangent_x, tangent_y = tangent
        perp_x = -tangent_y
        perp_y = tangent_x
        start_offset = self._offset_pose_xy(
            start_anchor,
            perp_x * lateral_offset_m,
            perp_y * lateral_offset_m,
        )
        end_offset = self._offset_pose_xy(
            rejoin_pose,
            perp_x * lateral_offset_m,
            perp_y * lateral_offset_m,
        )

        detour_points = [start_offset, end_offset, rejoin_pose]
        previous = start_anchor
        for point in detour_points:
            if not self._append_safe_line_samples(candidate, previous, point):
                return None
            previous = point

        for index in range(rejoin_index + 1, len(path.poses)):
            self._append_pose_without_duplicate(candidate, path.poses[index])

        if len(candidate.poses) < self.min_path_poses:
            return None

        self._recompute_orientations(candidate)
        self._stamp_path(candidate)
        return candidate

    def _path_tangent_for_detour(self, path, nearest_index, rejoin_index):
        start_index = max(0, min(nearest_index, len(path.poses) - 1))
        end_index = max(0, min(rejoin_index, len(path.poses) - 1))
        start = path.poses[start_index].pose.position
        end = path.poses[end_index].pose.position
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length > 1.0e-3:
            return dx / length, dy / length

        if start_index + 1 < len(path.poses):
            next_point = path.poses[start_index + 1].pose.position
            dx = next_point.x - start.x
            dy = next_point.y - start.y
            length = math.hypot(dx, dy)
            if length > 1.0e-3:
                return dx / length, dy / length

        if start_index > 0:
            previous = path.poses[start_index - 1].pose.position
            dx = start.x - previous.x
            dy = start.y - previous.y
            length = math.hypot(dx, dy)
            if length > 1.0e-3:
                return dx / length, dy / length

        return None

    def _offset_pose_xy(self, pose_stamped, dx, dy):
        output = copy.deepcopy(pose_stamped)
        output.pose.position.x += dx
        output.pose.position.y += dy
        return output

    def _append_safe_line_samples(self, path, start_pose, end_pose):
        start = start_pose.pose.position
        end = end_pose.pose.position
        distance = self._distance_2d(start.x, start.y, end.x, end.y)
        steps = max(
            1,
            int(math.ceil(distance / self.dynamic_detour_sample_step_m)),
        )

        for step in range(1, steps + 1):
            ratio = step / steps
            sample = PoseStamped()
            sample.header = copy.deepcopy(path.header)
            sample.pose.position.x = start.x + ratio * (end.x - start.x)
            sample.pose.position.y = start.y + ratio * (end.y - start.y)
            sample.pose.position.z = 0.0
            sample.pose.orientation.w = 1.0
            traversable, _, _ = self._is_pose_traversable_in_local_costmap(sample)
            if not traversable:
                return False
            self._append_pose_without_duplicate(path, sample)
        return True

    def _is_connector_safe_to_rejoin(self, robot_pose, rejoin_pose):
        if self.local_costmap is None:
            return False, 'local_costmap_unavailable'
        path_frame = robot_pose.header.frame_id or self.global_frame
        rejoin_in_path_frame = self._transform_pose_to_frame(
            rejoin_pose,
            path_frame,
        )
        if rejoin_in_path_frame is None:
            return False, 'rejoin_transform_unavailable'

        start = robot_pose.pose.position
        end = rejoin_in_path_frame.pose.position
        distance = self._distance_2d(start.x, start.y, end.x, end.y)
        sample_step = max(0.05, self.local_costmap.info.resolution)
        steps = max(1, int(math.ceil(distance / sample_step)))
        for step in range(steps + 1):
            ratio = step / steps
            sample = PoseStamped()
            sample.header.frame_id = path_frame
            sample.header.stamp = self.get_clock().now().to_msg()
            sample.pose.position.x = start.x + ratio * (end.x - start.x)
            sample.pose.position.y = start.y + ratio * (end.y - start.y)
            sample.pose.position.z = 0.0
            sample.pose.orientation.w = 1.0
            safe, reason, _ = self._is_pose_safe_in_local_costmap(sample)
            if not safe:
                return False, reason
        return True, 'safe'

    def _build_path_from_index(self, path, start_index):
        trimmed = Path()
        trimmed.header = copy.deepcopy(path.header)
        start_index = max(0, min(start_index, len(path.poses)))
        trimmed.poses = copy.deepcopy(path.poses[start_index:])
        self._stamp_path(trimmed)
        return trimmed

    def _find_pose_index_in_path(self, path, pose_stamped, tolerance_m=0.02):
        if path is None or pose_stamped is None or not path.poses:
            return None

        path_frame = self._path_frame(path)
        pose_in_path_frame = self._transform_pose_to_frame(
            pose_stamped,
            path_frame,
        )
        if pose_in_path_frame is None:
            return None

        target = pose_in_path_frame.pose.position
        best_index = None
        best_distance = float('inf')
        for index, candidate in enumerate(path.poses):
            position = candidate.pose.position
            distance = self._distance_2d(
                target.x,
                target.y,
                position.x,
                position.y,
            )
            if distance < best_distance:
                best_index = index
                best_distance = distance

        if best_index is None or best_distance > tolerance_m:
            return None
        return best_index

    def _record_skipped_segment(self, path, start_index, end_index, rejoin_index, report):
        if path is None or not path.poses:
            return None

        start_index = max(0, min(start_index, len(path.poses) - 1))
        end_index = max(start_index, min(end_index, len(path.poses) - 1))
        rejoin_index = max(0, min(rejoin_index, len(path.poses)))
        segment_id = self.dynamic_skip_counter + 1
        pose_count = end_index - start_index + 1
        distance_m = self._distance_along_path(path, start_index, end_index)
        timestamp_sec = self.get_clock().now().nanoseconds * 1.0e-9

        skipped = {
            'id': segment_id,
            'reason': 'DYNAMIC_LOCAL_OBSTACLE',
            'source_path_frame': self._path_frame(path),
            'start_index': start_index,
            'end_index': end_index,
            'rejoin_index': rejoin_index,
            'pose_count': pose_count,
            'distance_m': distance_m,
            'timestamp_sec': timestamp_sec,
            'min_obstacle_cost': int(report.get('min_cost', 0)),
            'max_obstacle_cost': int(report.get('max_cost', 0)),
            '_poses': copy.deepcopy(path.poses[start_index : end_index + 1]),
            '_rejoin_pose': copy.deepcopy(path.poses[rejoin_index])
            if rejoin_index < len(path.poses)
            else None,
        }
        self.skipped_segments.append(skipped)
        self.dynamic_skip_counter += 1
        self.dynamic_skip_failure_counter = 0

        text = (
            '[DYNAMIC_SKIP] skipped segment recorded '
            'segment_id=%d poses=%d distance=%.3f rejoin_index=%d max_cost=%d'
            % (
                segment_id,
                pose_count,
                distance_m,
                rejoin_index,
                skipped['max_obstacle_cost'],
            )
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(
            '%s skipped_segment_count=%d skipped_pose_count=%d '
            'skipped_distance_m=%.3f mark_skipped_segments_uncovered=%s '
            'retry_skipped_segments_at_end=%s'
            % (
                text,
                len(self.skipped_segments),
                self._skipped_pose_count(),
                self._skipped_distance_m(),
                str(self.mark_skipped_segments_uncovered).lower(),
                str(self.retry_skipped_segments_at_end).lower(),
            )
        )
        return skipped

    def _publish_skipped_segment_markers(self):
        if not self.publish_skipped_segments or not hasattr(
            self,
            'skipped_segments_pub',
        ):
            return

        frame_id = self.global_frame
        if self.skipped_segments:
            frame_id = self.skipped_segments[0]['source_path_frame'] or frame_id
        elif self.dynamic_confirmed_marker_report:
            poses = self.dynamic_confirmed_marker_report.get(
                'dynamic_only_blocked_poses',
                [],
            )
            if poses:
                frame_id = poses[0].header.frame_id or frame_id
        elif self.dynamic_ignored_static_marker_poses:
            frame_id = (
                self.dynamic_ignored_static_marker_poses[0].header.frame_id
                or frame_id
            )
        elif self.dynamic_candidate_marker_path is not None:
            frame_id = self.dynamic_candidate_marker_path.header.frame_id or frame_id
        markers = self._delete_all_markers(frame_id, 'dynamic_skipped_segments')
        stamp = self.get_clock().now().to_msg()

        for segment in self.skipped_segments:
            poses = segment.get('_poses', [])
            if not poses:
                continue

            base_id = segment['id'] * 10
            segment_path = Path()
            segment_path.header.frame_id = segment['source_path_frame']
            segment_path.header.stamp = stamp
            segment_path.poses = copy.deepcopy(poses)
            markers.markers.append(
                self._make_path_line_marker(
                    segment_path,
                    stamp,
                    base_id + 1,
                    'dynamic_skipped_segments',
                    (1.0, 0.25, 0.0, 0.95),
                    0.06,
                    0.14,
                )
            )
            markers.markers.append(
                self._make_pose_marker(
                    segment['source_path_frame'],
                    stamp,
                    base_id + 2,
                    'dynamic_skipped_segments',
                    poses[0],
                    Marker.SPHERE,
                    (1.0, 0.05, 0.0, 0.95),
                    0.18,
                )
            )

            rejoin_pose = segment.get('_rejoin_pose')
            if rejoin_pose is not None:
                markers.markers.append(
                    self._make_pose_marker(
                        segment['source_path_frame'],
                        stamp,
                        base_id + 3,
                        'dynamic_skipped_segments',
                        rejoin_pose,
                        Marker.SPHERE,
                        (0.0, 0.9, 0.25, 0.95),
                        0.18,
                    )
                )
                text_pose = rejoin_pose
            else:
                text_pose = poses[-1]

            label = Marker()
            label.header.frame_id = segment['source_path_frame']
            label.header.stamp = stamp
            label.ns = 'dynamic_skipped_segments'
            label.id = base_id + 4
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose = copy.deepcopy(text_pose.pose)
            label.pose.position.z += 0.45
            label.pose.orientation.x = 0.0
            label.pose.orientation.y = 0.0
            label.pose.orientation.z = 0.0
            label.pose.orientation.w = 1.0
            label.scale.z = 0.18
            label.color.r = 1.0
            label.color.g = 0.2
            label.color.b = 0.0
            label.color.a = 0.95
            label.text = 'SKIPPED_DYNAMIC_OBSTACLE'
            markers.markers.append(label)

        confirmed_poses = []
        if self.dynamic_confirmed_marker_report:
            confirmed_poses = self.dynamic_confirmed_marker_report.get(
                'dynamic_only_blocked_poses',
                [],
            )
        if confirmed_poses:
            marker = Marker()
            marker.header.frame_id = confirmed_poses[0].header.frame_id or frame_id
            marker.header.stamp = stamp
            marker.ns = 'dynamic_confirmed_object_area'
            marker.id = 900001
            marker.type = Marker.SPHERE_LIST
            marker.action = Marker.ADD
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.14
            marker.scale.y = 0.14
            marker.scale.z = 0.14
            marker.color.r = 1.0
            marker.color.g = 0.30
            marker.color.b = 0.0
            marker.color.a = 0.95
            for pose_stamped in confirmed_poses:
                point = copy.deepcopy(pose_stamped.pose.position)
                point.z += 0.18
                marker.points.append(point)
            markers.markers.append(marker)

        if self.dynamic_ignored_static_marker_poses:
            marker = Marker()
            marker.header.frame_id = (
                self.dynamic_ignored_static_marker_poses[0].header.frame_id
                or frame_id
            )
            marker.header.stamp = stamp
            marker.ns = 'dynamic_ignored_static_wall'
            marker.id = 900002
            marker.type = Marker.SPHERE_LIST
            marker.action = Marker.ADD
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.08
            marker.scale.y = 0.08
            marker.scale.z = 0.08
            marker.color.r = 0.65
            marker.color.g = 0.65
            marker.color.b = 0.25
            marker.color.a = 0.75
            for pose_stamped in self.dynamic_ignored_static_marker_poses:
                point = copy.deepcopy(pose_stamped.pose.position)
                point.z += 0.16
                marker.points.append(point)
            markers.markers.append(marker)

        if (
            self.dynamic_candidate_marker_path is not None
            and self.dynamic_candidate_marker_path.poses
        ):
            markers.markers.append(
                self._make_path_line_marker(
                    self.dynamic_candidate_marker_path,
                    stamp,
                    900003,
                    'dynamic_candidate_rejoin_path',
                    (0.0, 0.85, 1.0, 0.9),
                    0.035,
                    0.10,
                )
            )

        self.skipped_segments_pub.publish(markers)

    def _publish_dynamic_skip_status(self, text):
        msg = String()
        msg.data = text
        if hasattr(self, 'dynamic_skip_status_pub'):
            self.dynamic_skip_status_pub.publish(msg)
        self._publish_debug_info(text)

    def _skipped_pose_count(self):
        return sum(segment['pose_count'] for segment in self.skipped_segments)

    def _skipped_distance_m(self):
        return sum(segment['distance_m'] for segment in self.skipped_segments)

    def _skipped_summary_text(self, completed_with_skips):
        return (
            'skipped_segment_count=%d skipped_pose_count=%d '
            'skipped_distance_m=%.3f completed_with_skips=%s '
            'reason=dynamic_local_obstacles skipped_sections_retried=false '
            'skipped_sections_counted_as_covered=false'
            % (
                len(self.skipped_segments),
                self._skipped_pose_count(),
                self._skipped_distance_m(),
                str(completed_with_skips).lower(),
            )
        )

    def _lookup_robot_pose(self, target_frame):
        try:
            transform = self.tf_buffer.lookup_transform(
                target_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=self.tf_lookup_timeout_sec),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not lookup TF %s -> %s: %s'
                % (target_frame, self.robot_base_frame, exc),
                throttle_duration_sec=2.0,
            )
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        pose_stamped = PoseStamped()
        pose_stamped.header.frame_id = target_frame
        pose_stamped.header.stamp = transform.header.stamp
        pose_stamped.pose.position.x = translation.x
        pose_stamped.pose.position.y = translation.y
        pose_stamped.pose.position.z = translation.z
        pose_stamped.pose.orientation = copy.deepcopy(rotation)
        return pose_stamped

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
            'nav_blocked_cells=%d nav_unknown_samples=%d max_observed_cost=%d '
            'skipped_segment_count=%d skipped_pose_count=%d '
            'skipped_distance_m=%.3f completed_with_skips=%s'
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
                len(self.skipped_segments),
                self._skipped_pose_count(),
                self._skipped_distance_m(),
                str(len(self.skipped_segments) > 0).lower(),
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
        if hasattr(self, 'skipped_segments_pub'):
            self.skipped_segments_pub.publish(
                self._delete_all_markers(self.global_frame, 'dynamic_skipped_segments')
            )

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

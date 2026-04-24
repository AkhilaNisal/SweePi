#!/usr/bin/env python3
"""Waypoint generator and optional Nav2 executor for SweePi coverage."""

import copy
import math

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point
from nav2_msgs.action import NavigateThroughPoses
from nav_msgs.msg import Path
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray


class CoverageExecutorNode(Node):
    """Convert a coverage path into Nav2-ready waypoints without executing them."""

    def __init__(self):
        super().__init__('coverage_executor_node')

        self.declare_parameter('coverage_path_topic', '/coverage_path')
        self.declare_parameter('coverage_waypoints_topic', '/coverage_waypoints')
        self.declare_parameter(
            'coverage_waypoint_markers_topic',
            '/coverage_waypoint_markers',
        )
        self.declare_parameter(
            'coverage_waypoint_stats_topic',
            '/coverage_waypoint_stats',
        )
        self.declare_parameter(
            'coverage_execution_status_topic',
            '/coverage_execution_status',
        )
        self.declare_parameter(
            'coverage_current_batch_topic',
            '/coverage_current_batch',
        )
        self.declare_parameter(
            'coverage_nav2_feedback_topic',
            '/coverage_nav2_feedback',
        )
        self.declare_parameter(
            'failed_waypoint_markers_topic',
            '/coverage_failed_waypoint_markers',
        )
        self.declare_parameter(
            'coverage_skipped_waypoints_topic',
            '/coverage_skipped_waypoints',
        )
        self.declare_parameter('waypoint_spacing_m', 0.4)
        self.declare_parameter('min_turn_angle_deg', 35.0)
        self.declare_parameter('min_waypoint_separation_m', 0.20)
        self.declare_parameter('max_waypoint_gap_m', 1.2)
        self.declare_parameter('max_batch_segment_length_m', 1.5)
        self.declare_parameter('max_waypoints', 200)
        self.declare_parameter('publish_waypoint_markers', True)
        self.declare_parameter('waypoint_publish_rate_hz', 1.0)
        self.declare_parameter('enable_nav2_execution', False)
        self.declare_parameter('nav2_action_name', '/navigate_through_poses')
        self.declare_parameter('max_waypoints_per_batch', 5)
        self.declare_parameter('max_batches_to_execute', 1)
        self.declare_parameter('wait_for_nav2_timeout_sec', 10.0)
        self.declare_parameter('behavior_tree', '')
        self.declare_parameter('recompute_waypoint_orientations', True)
        self.declare_parameter('start_from_nearest_waypoint', True)
        self.declare_parameter('retry_failed_batch', False)
        self.declare_parameter('skip_failed_batch', True)
        self.declare_parameter('continue_after_failure', True)
        self.declare_parameter('max_retries_per_batch', 0)
        self.declare_parameter('max_failed_batches', 10)
        self.declare_parameter('max_skipped_batches', 10)
        self.declare_parameter('max_total_batch_attempts', 30)
        self.declare_parameter('batch_timeout_sec', 20.0)
        self.declare_parameter('no_progress_timeout_sec', 8.0)
        self.declare_parameter('min_progress_distance_m', 0.03)
        self.declare_parameter('min_batch_poses', 2)
        self.declare_parameter('allow_waypoint0_fallback_without_tf', False)
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('robot_base_frame', 'base_link')

        self.coverage_path_topic = (
            self.get_parameter('coverage_path_topic').get_parameter_value().string_value
        )
        self.coverage_waypoints_topic = (
            self.get_parameter('coverage_waypoints_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_waypoint_markers_topic = (
            self.get_parameter('coverage_waypoint_markers_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_waypoint_stats_topic = (
            self.get_parameter('coverage_waypoint_stats_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_execution_status_topic = (
            self.get_parameter('coverage_execution_status_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_current_batch_topic = (
            self.get_parameter('coverage_current_batch_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_nav2_feedback_topic = (
            self.get_parameter('coverage_nav2_feedback_topic')
            .get_parameter_value()
            .string_value
        )
        self.failed_waypoint_markers_topic = (
            self.get_parameter('failed_waypoint_markers_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_skipped_waypoints_topic = (
            self.get_parameter('coverage_skipped_waypoints_topic')
            .get_parameter_value()
            .string_value
        )
        self.waypoint_spacing_m = (
            self.get_parameter('waypoint_spacing_m').get_parameter_value().double_value
        )
        self.min_turn_angle_deg = (
            self.get_parameter('min_turn_angle_deg').get_parameter_value().double_value
        )
        self.min_waypoint_separation_m = (
            self.get_parameter('min_waypoint_separation_m')
            .get_parameter_value()
            .double_value
        )
        self.max_waypoint_gap_m = (
            self.get_parameter('max_waypoint_gap_m').get_parameter_value().double_value
        )
        self.max_batch_segment_length_m = (
            self.get_parameter('max_batch_segment_length_m')
            .get_parameter_value()
            .double_value
        )
        self.max_waypoints = (
            self.get_parameter('max_waypoints').get_parameter_value().integer_value
        )
        self.publish_waypoint_markers = (
            self.get_parameter('publish_waypoint_markers')
            .get_parameter_value()
            .bool_value
        )
        self.waypoint_publish_rate_hz = (
            self.get_parameter('waypoint_publish_rate_hz')
            .get_parameter_value()
            .double_value
        )
        self.enable_nav2_execution = (
            self.get_parameter('enable_nav2_execution').get_parameter_value().bool_value
        )
        self.nav2_action_name = (
            self.get_parameter('nav2_action_name').get_parameter_value().string_value
        )
        self.max_waypoints_per_batch = (
            self.get_parameter('max_waypoints_per_batch')
            .get_parameter_value()
            .integer_value
        )
        self.max_batches_to_execute = (
            self.get_parameter('max_batches_to_execute')
            .get_parameter_value()
            .integer_value
        )
        self.wait_for_nav2_timeout_sec = (
            self.get_parameter('wait_for_nav2_timeout_sec')
            .get_parameter_value()
            .double_value
        )
        self.behavior_tree = (
            self.get_parameter('behavior_tree').get_parameter_value().string_value
        )
        self.recompute_waypoint_orientations = (
            self.get_parameter('recompute_waypoint_orientations')
            .get_parameter_value()
            .bool_value
        )
        self.start_from_nearest_waypoint = (
            self.get_parameter('start_from_nearest_waypoint')
            .get_parameter_value()
            .bool_value
        )
        self.retry_failed_batch = (
            self.get_parameter('retry_failed_batch').get_parameter_value().bool_value
        )
        self.skip_failed_batch = (
            self.get_parameter('skip_failed_batch').get_parameter_value().bool_value
        )
        self.continue_after_failure = (
            self.get_parameter('continue_after_failure').get_parameter_value().bool_value
        )
        self.max_retries_per_batch = (
            self.get_parameter('max_retries_per_batch')
            .get_parameter_value()
            .integer_value
        )
        self.max_failed_batches = (
            self.get_parameter('max_failed_batches').get_parameter_value().integer_value
        )
        self.max_skipped_batches = (
            self.get_parameter('max_skipped_batches')
            .get_parameter_value()
            .integer_value
        )
        self.max_total_batch_attempts = (
            self.get_parameter('max_total_batch_attempts')
            .get_parameter_value()
            .integer_value
        )
        self.batch_timeout_sec = (
            self.get_parameter('batch_timeout_sec').get_parameter_value().double_value
        )
        self.no_progress_timeout_sec = (
            self.get_parameter('no_progress_timeout_sec')
            .get_parameter_value()
            .double_value
        )
        self.min_progress_distance_m = (
            self.get_parameter('min_progress_distance_m')
            .get_parameter_value()
            .double_value
        )
        self.min_batch_poses = (
            self.get_parameter('min_batch_poses').get_parameter_value().integer_value
        )
        self.allow_waypoint0_fallback_without_tf = (
            self.get_parameter('allow_waypoint0_fallback_without_tf')
            .get_parameter_value()
            .bool_value
        )
        self.global_frame = (
            self.get_parameter('global_frame').get_parameter_value().string_value
        )
        self.robot_base_frame = (
            self.get_parameter('robot_base_frame').get_parameter_value().string_value
        )

        self._sanitize_parameters()

        self.execution_state = 'DISABLED'
        if self.enable_nav2_execution:
            self.nav2_action_client = ActionClient(
                self,
                NavigateThroughPoses,
                self.nav2_action_name,
            )
            self.nav2_wait_start_time = self.get_clock().now()
            self.nav2_ready = False
            self.execution_status = 'WAITING_FOR_NAV2'
            self.execution_state = 'WAITING_FOR_NAV2'
        else:
            self.nav2_action_client = None
            self.nav2_wait_start_time = None
            self.nav2_ready = False
            self.execution_status = 'EXECUTION_DISABLED'

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.latest_input_path = None
        self.latest_path_checksum = None
        self.waypoints_dirty = False
        self.latest_waypoints = self._make_empty_path('map')
        self.latest_execution_waypoints = self._make_empty_path('map')
        self.latest_waypoints_checksum = None
        self.pending_waypoints = None
        self.pending_waypoints_checksum = None
        self.latest_markers = self._make_delete_markers('map')
        self.latest_stats_msg = String()
        self.latest_stats_msg.data = 'input_poses=0 waypoints=0 input_empty=true'
        self.latest_base_stats_text = self.latest_stats_msg.data
        self.latest_status_msg = String()
        self.latest_status_msg.data = self.execution_status
        self.latest_current_batch = self._make_empty_path('map')
        self.execution_batches = []
        self.execution_batch_start_indices = []
        self.current_batch_index = 0
        self.executed_batch_count = 0
        self.attempted_batch_count = 0
        self.execution_active = False
        self.execution_goal_in_flight = False
        self.replan_received_during_execution = False
        self.executed_waypoints_checksum = None
        self.active_goal_signature = None
        self.nav2_timeout_reported = False
        self.selected_start_index = 0
        self.current_batch_retry_count = 0
        self.failed_batch_count = 0
        self.skipped_batch_count = 0
        self.current_goal_handle = None
        self.cancel_in_progress = False
        self.cancel_reason = ''
        self.cancel_batch_number = 0
        self.cancel_total_batches = 0
        self.batch_start_time = None
        self.last_feedback_time = None
        self.best_distance_remaining = None
        self.last_progress_time = None
        self.last_distance_remaining = None
        self.last_poses_remaining = None
        self.skipped_waypoints = self._make_empty_path('map')
        self.failed_waypoint_markers = self._make_failed_waypoint_markers('map')
        self.min_start_index_after_failure = 0
        self.last_handled_failure_signature = None
        self.waiting_for_tf = False
        self.current_start_index = 0
        self.use_nearest_start_for_next_plan = True
        self.skipped_start_indices = set()

        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.coverage_path_sub = self.create_subscription(
            Path,
            self.coverage_path_topic,
            self.coverage_path_callback,
            qos,
        )
        self.coverage_waypoints_sub = self.create_subscription(
            Path,
            self.coverage_waypoints_topic,
            self.coverage_waypoints_callback,
            qos,
        )
        self.coverage_waypoints_pub = self.create_publisher(
            Path,
            self.coverage_waypoints_topic,
            qos,
        )
        self.coverage_waypoint_markers_pub = self.create_publisher(
            MarkerArray,
            self.coverage_waypoint_markers_topic,
            qos,
        )
        self.coverage_waypoint_stats_pub = self.create_publisher(
            String,
            self.coverage_waypoint_stats_topic,
            qos,
        )
        self.coverage_execution_status_pub = self.create_publisher(
            String,
            self.coverage_execution_status_topic,
            qos,
        )
        self.coverage_current_batch_pub = self.create_publisher(
            Path,
            self.coverage_current_batch_topic,
            qos,
        )
        self.coverage_nav2_feedback_pub = self.create_publisher(
            String,
            self.coverage_nav2_feedback_topic,
            qos,
        )
        self.coverage_skipped_waypoints_pub = self.create_publisher(
            Path,
            self.coverage_skipped_waypoints_topic,
            qos,
        )
        self.failed_waypoint_markers_pub = self.create_publisher(
            MarkerArray,
            self.failed_waypoint_markers_topic,
            qos,
        )

        publish_period = 1.0 / self.waypoint_publish_rate_hz
        self.timer = self.create_timer(publish_period, self.publish_outputs)

        self.get_logger().info(
            'Coverage waypoint generator started: path=%s, waypoints=%s, '
            'markers=%s, stats=%s, execution_status=%s, current_batch=%s, '
            'nav2_feedback=%s, skipped_waypoints=%s, failed_markers=%s'
            % (
                self.coverage_path_topic,
                self.coverage_waypoints_topic,
                self.coverage_waypoint_markers_topic,
                self.coverage_waypoint_stats_topic,
                self.coverage_execution_status_topic,
                self.coverage_current_batch_topic,
                self.coverage_nav2_feedback_topic,
                self.coverage_skipped_waypoints_topic,
                self.failed_waypoint_markers_topic,
            )
        )

    def coverage_path_callback(self, msg):
        """Store new coverage path input and regenerate waypoints when it changes."""
        checksum = self._path_checksum(msg)
        if checksum == self.latest_path_checksum:
            return

        self.latest_path_checksum = checksum
        self.latest_input_path = msg
        self.waypoints_dirty = True

    def coverage_waypoints_callback(self, msg):
        """Store latest waypoint path for optional Nav2 batch execution."""
        checksum = self._path_checksum(msg)
        if checksum == self.latest_waypoints_checksum:
            return

        if self.execution_goal_in_flight:
            self.pending_waypoints = copy.deepcopy(msg)
            self.pending_waypoints_checksum = checksum
            self.replan_received_during_execution = True
            self._set_execution_status('REPLAN_RECEIVED_DURING_EXECUTION')
            return

        self.latest_waypoints_checksum = checksum
        self.latest_execution_waypoints = copy.deepcopy(msg)

        if self.enable_nav2_execution:
            self.execution_active = False
            self.execution_batches = []
            self.execution_batch_start_indices = []
            self.current_batch_index = 0
            self.executed_batch_count = 0
            self.attempted_batch_count = 0
            self.executed_waypoints_checksum = None
            self.current_start_index = 0
            self.use_nearest_start_for_next_plan = True
            self.skipped_start_indices.clear()
            if self.execution_state in ('COMPLETED', 'FAILED'):
                self.execution_state = 'WAITING_FOR_NAV2'

    def publish_outputs(self):
        """Regenerate dirty waypoints and republish the latest debug outputs."""
        if self.waypoints_dirty and self.latest_input_path is not None:
            result = self.generate_waypoints(self.latest_input_path)
            self.latest_waypoints = result['waypoints']
            self.latest_markers = result['markers']
            self.latest_base_stats_text = result['stats_text']
            self.latest_stats_msg.data = self.latest_base_stats_text
            self.waypoints_dirty = False
            self.get_logger().info('Coverage waypoints: %s' % result['stats_text'])
            self._store_execution_waypoints(self.latest_waypoints)

        self._update_execution()

        stamp = self.get_clock().now().to_msg()
        self.latest_waypoints.header.stamp = stamp
        self.coverage_waypoints_pub.publish(self.latest_waypoints)

        self.latest_current_batch.header.stamp = stamp
        self.coverage_current_batch_pub.publish(self.latest_current_batch)

        self.skipped_waypoints.header.stamp = stamp
        self.coverage_skipped_waypoints_pub.publish(self.skipped_waypoints)

        for marker in self.failed_waypoint_markers.markers:
            marker.header.stamp = stamp
        self.failed_waypoint_markers_pub.publish(self.failed_waypoint_markers)

        if self.publish_waypoint_markers:
            for marker in self.latest_markers.markers:
                marker.header.stamp = stamp
            self.coverage_waypoint_markers_pub.publish(self.latest_markers)

        self.coverage_waypoint_stats_pub.publish(self.latest_stats_msg)
        self.latest_status_msg.data = self.execution_status
        self.coverage_execution_status_pub.publish(self.latest_status_msg)

    def _store_execution_waypoints(self, waypoints):
        checksum = self._path_checksum(waypoints)
        if checksum == self.latest_waypoints_checksum:
            return

        if self.execution_goal_in_flight:
            self.pending_waypoints = copy.deepcopy(waypoints)
            self.pending_waypoints_checksum = checksum
            self.replan_received_during_execution = True
            self._set_execution_status('REPLAN_RECEIVED_DURING_EXECUTION')
            return

        self.latest_waypoints_checksum = checksum
        self.latest_execution_waypoints = copy.deepcopy(waypoints)
        self.execution_active = False
        self.execution_batches = []
        self.execution_batch_start_indices = []
        self.current_batch_index = 0
        self.executed_batch_count = 0
        self.attempted_batch_count = 0
        self.executed_waypoints_checksum = None
        self.current_start_index = 0
        self.use_nearest_start_for_next_plan = True
        self.skipped_start_indices.clear()
        if self.enable_nav2_execution and self.execution_state in (
            'COMPLETED',
            'FAILED',
        ):
            self.execution_state = 'WAITING_FOR_NAV2'

    def _apply_pending_waypoints(self):
        if self.pending_waypoints is None:
            return

        self.latest_execution_waypoints = copy.deepcopy(self.pending_waypoints)
        self.latest_waypoints_checksum = self.pending_waypoints_checksum
        self.pending_waypoints = None
        self.pending_waypoints_checksum = None
        self.replan_received_during_execution = False
        self.execution_active = False
        self.execution_batches = []
        self.execution_batch_start_indices = []
        self.current_batch_index = 0
        self.executed_waypoints_checksum = None
        if self.enable_nav2_execution and self.execution_state in (
            'COMPLETED',
            'FAILED',
        ):
            self.execution_state = 'WAITING_FOR_NAV2'

    def _update_execution(self):
        if not self.enable_nav2_execution:
            self.execution_state = 'DISABLED'
            self._update_disabled_preview_batch()
            self._set_execution_status('EXECUTION_DISABLED')
            return

        if self.execution_state in ('COMPLETED', 'FAILED'):
            return

        waypoint_count = len(self.latest_execution_waypoints.poses)
        if waypoint_count == 0:
            self.execution_state = 'WAITING_FOR_WAYPOINTS'
            self.latest_current_batch = self._make_empty_path('map')
            self._set_execution_status('WAITING_FOR_WAYPOINTS')
            return

        if not self._nav2_server_ready():
            return

        if self.execution_goal_in_flight:
            self._monitor_active_batch()
            return

        if (
            not self.execution_active
            and self.latest_waypoints_checksum == self.executed_waypoints_checksum
        ):
            return

        if not self.execution_active:
            self.execution_batches = self._make_execution_batches(
                self.latest_execution_waypoints,
                require_tf=True,
            )
            self.current_batch_index = 0
            self.execution_active = bool(self.execution_batches)
            if not self.execution_active:
                if self.waiting_for_tf:
                    self.execution_state = 'WAITING_FOR_TF'
                    self.latest_current_batch = self._make_preview_batch(
                        self.latest_execution_waypoints
                    )
                    self._set_execution_status(
                        'WAITING_FOR_TF %s->%s'
                        % (self.global_frame, self.robot_base_frame)
                    )
                    return

                self.executed_waypoints_checksum = self.latest_waypoints_checksum
                self.execution_state = 'FAILED'
                self._set_execution_status('EXECUTION_COMPLETED no_valid_batch_remaining')
                return
            self.execution_state = 'READY'
            self.latest_current_batch = copy.deepcopy(self.execution_batches[0])
            self._set_execution_status(
                'READY_TO_EXECUTE batches=%d start_index=%d'
                % (self._allowed_batch_count(), self.selected_start_index)
            )
            return

        if self._execution_batch_limit_reached():
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self.execution_active = False
            self.execution_state = 'COMPLETED'
            self._set_execution_status(
                'EXECUTION_COMPLETED success_count=%d' % self.executed_batch_count
            )
            return

        stop_reason = self._execution_stop_limit_reached()
        if stop_reason:
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self.execution_active = False
            self.execution_state = 'FAILED'
            self._set_execution_status('EXECUTION_STOPPED %s' % stop_reason)
            return

        if self.current_batch_index >= len(self.execution_batches):
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self.execution_active = False
            self.execution_state = 'COMPLETED'
            self._set_execution_status('EXECUTION_COMPLETED no_valid_batch_remaining')
            return

        self._send_current_batch()

    def _update_disabled_preview_batch(self):
        batch = self._make_preview_batch(self.latest_execution_waypoints)
        self.latest_current_batch = batch
        if batch.poses:
            self.latest_stats_msg.data = (
                '%s execution_preview=EXECUTION_DISABLED_PREVIEW_BATCH poses=%d'
                % (self.latest_base_stats_text, len(batch.poses))
            )
        else:
            self.latest_stats_msg.data = (
                '%s execution_preview=EXECUTION_DISABLED_PREVIEW_BATCH poses=0'
                % self.latest_base_stats_text
            )

    def _make_preview_batch(self, waypoints):
        if waypoints is None or not waypoints.poses:
            frame_id = 'map'
            if waypoints is not None and waypoints.header.frame_id:
                frame_id = waypoints.header.frame_id
            return self._make_empty_path(frame_id)

        batches = self._make_execution_batches(
            waypoints,
            require_tf=False,
            publish_status=False,
        )
        if not batches:
            return self._make_empty_path(waypoints.header.frame_id or 'map')

        preview_index = 0
        if self.max_batches_to_execute > 0:
            preview_index = min(preview_index, self.max_batches_to_execute - 1)
        return copy.deepcopy(batches[preview_index])

    def _nav2_server_ready(self):
        if self.nav2_ready:
            return True

        if self.nav2_action_client.server_is_ready():
            self.nav2_ready = True
            self.execution_state = 'READY'
            return True

        self.execution_state = 'WAITING_FOR_NAV2'
        self._set_execution_status('WAITING_FOR_NAV2')
        elapsed_sec = (
            self.get_clock().now() - self.nav2_wait_start_time
        ).nanoseconds / 1.0e9
        if elapsed_sec > self.wait_for_nav2_timeout_sec:
            if not self.nav2_timeout_reported:
                self.get_logger().warn(
                    'Nav2 action server %s was not available after %.1f seconds'
                    % (self.nav2_action_name, elapsed_sec)
                )
                self.nav2_timeout_reported = True
            self.execution_state = 'FAILED'
            self._set_execution_status('EXECUTION_FAILED reason=nav2_timeout')
        return False

    def _make_execution_batches(
        self,
        waypoints,
        require_tf=False,
        publish_status=True,
    ):
        self.waiting_for_tf = False
        frame_id = waypoints.header.frame_id
        if not frame_id:
            self.get_logger().warn(
                'Waypoint path frame is empty; refusing to send Nav2 goals'
            )
            return []

        source_poses = waypoints.poses
        start_index = self._get_start_waypoint_index(source_poses, require_tf)
        if start_index is None:
            self.waiting_for_tf = True
            return []

        first_batch = self._find_valid_batch_near_start(
            source_poses,
            frame_id,
            start_index,
            publish_status,
        )
        if first_batch is None:
            if publish_status:
                self._set_execution_status('NO_VALID_BATCH_FOUND')
            return []

        start_index, batch = first_batch
        self.selected_start_index = start_index
        self.execution_batch_start_indices = [start_index]
        if publish_status:
            self._set_execution_status(
                'VALID_BATCH_FOUND start_index=%d poses=%d largest_segment=%.2f'
                % (
                    start_index,
                    len(batch.poses),
                    self._largest_output_gap(batch.poses),
                )
            )

        batches = [batch]
        batch_start_index = start_index + len(batch.poses)
        while batch_start_index < len(source_poses):
            if batch_start_index in self.skipped_start_indices:
                batch_start_index += 1
                continue
            next_batch = self._build_batch_from_start(
                source_poses,
                frame_id,
                batch_start_index,
            )
            if next_batch is None:
                batch_start_index += 1
                continue
            batches.append(next_batch)
            self.execution_batch_start_indices.append(batch_start_index)
            batch_start_index += len(next_batch.poses)

        return batches

    def _get_start_waypoint_index(self, poses, require_tf=False):
        if not poses:
            return 0

        if not self.use_nearest_start_for_next_plan:
            return min(self.current_start_index, max(0, len(poses) - 1))

        if not self.start_from_nearest_waypoint:
            if require_tf and not self.allow_waypoint0_fallback_without_tf:
                try:
                    self.tf_buffer.lookup_transform(
                        self.global_frame,
                        self.robot_base_frame,
                        Time(),
                        timeout=Duration(seconds=0.1),
                    )
                except TransformException as exc:
                    self.get_logger().warn(
                        'Could not get TF %s -> %s before execution: %s'
                        % (self.global_frame, self.robot_base_frame, exc),
                        throttle_duration_sec=5.0,
                    )
                    self._set_execution_status(
                        'WAITING_FOR_TF %s->%s'
                        % (self.global_frame, self.robot_base_frame)
                    )
                    return None
            return min(self.min_start_index_after_failure, max(0, len(poses) - 1))

        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=0.1),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not get TF %s -> %s for nearest waypoint start: %s; '
                'using waypoint 0 only if fallback is allowed'
                % (self.global_frame, self.robot_base_frame, exc),
                throttle_duration_sec=5.0,
            )
            if require_tf and not self.allow_waypoint0_fallback_without_tf:
                self._set_execution_status(
                    'WAITING_FOR_TF %s->%s'
                    % (self.global_frame, self.robot_base_frame)
                )
                return None
            return min(self.min_start_index_after_failure, max(0, len(poses) - 1))

        robot_x = transform.transform.translation.x
        robot_y = transform.transform.translation.y
        max_start_index = max(0, len(poses) - self.max_waypoints_per_batch)
        nearest_index = 0
        nearest_cost = None
        for index, pose in enumerate(poses[:max_start_index + 1]):
            dx = pose.pose.position.x - robot_x
            dy = pose.pose.position.y - robot_y
            cost = dx * dx + dy * dy
            if self._is_sharp_turn_index(poses, index):
                cost += self.min_waypoint_separation_m ** 2
            if nearest_cost is None or cost < nearest_cost:
                nearest_index = index
                nearest_cost = cost

        self.get_logger().info(
            'Selected coverage waypoint start_index=%d' % nearest_index,
            throttle_duration_sec=2.0,
        )
        if self.min_start_index_after_failure > 0:
            bounded_index = min(self.min_start_index_after_failure, max_start_index)
            if bounded_index > nearest_index:
                nearest_index = bounded_index
                self.get_logger().info(
                    'Advancing start_index to %d after skipped batch'
                    % nearest_index,
                    throttle_duration_sec=2.0,
                )

        return nearest_index

    def _find_valid_batch_near_start(
        self,
        poses,
        frame_id,
        preferred_start_index,
        publish_status=True,
    ):
        if publish_status:
            self._set_execution_status('BATCH_INVALID_SEARCHING_ALTERNATE')
        max_start_index = max(0, len(poses) - self.min_batch_poses)
        preferred_start_index = min(max(preferred_start_index, 0), max_start_index)
        search_radius = min(
            max_start_index,
            max(self.max_waypoints_per_batch * 4, 20),
        )

        candidate_indices = [preferred_start_index]
        for offset in range(1, search_radius + 1):
            previous_index = preferred_start_index - offset
            next_index = preferred_start_index + offset
            if (
                previous_index >= 0
                and self.use_nearest_start_for_next_plan
            ):
                candidate_indices.append(previous_index)
            if next_index <= max_start_index:
                candidate_indices.append(next_index)

        seen_indices = set()
        for start_index in candidate_indices:
            if start_index in seen_indices:
                continue
            if start_index in self.skipped_start_indices:
                continue
            if (
                not self.use_nearest_start_for_next_plan
                and start_index < self.current_start_index
            ):
                continue
            seen_indices.add(start_index)
            batch = self._build_batch_from_start(poses, frame_id, start_index)
            if batch is not None:
                return start_index, batch

        return None

    def _build_batch_from_start(self, poses, frame_id, start_index):
        if start_index < 0 or start_index >= len(poses):
            return None

        stamp = self.get_clock().now().to_msg()
        batch = Path()
        batch.header.frame_id = frame_id
        batch.header.stamp = stamp

        for index in range(start_index, len(poses)):
            candidate_pose = copy.deepcopy(poses[index])
            candidate_pose.header.frame_id = frame_id
            candidate_pose.header.stamp = stamp

            if batch.poses:
                segment_length = self._pose_distance(batch.poses[-1], candidate_pose)
                if segment_length > self.max_batch_segment_length_m:
                    break

            batch.poses.append(candidate_pose)
            if len(batch.poses) >= self.max_waypoints_per_batch:
                break

        batch.poses = self._remove_close_waypoints(batch.poses, preserve_last=True)
        if len(batch.poses) < self.min_batch_poses:
            return None
        if self._validate_batch_for_execution(batch):
            return None

        return batch

    def _execution_batch_limit_reached(self):
        return (
            self.max_batches_to_execute > 0
            and self.executed_batch_count >= self.max_batches_to_execute
        )

    def _execution_stop_limit_reached(self):
        if self.failed_batch_count >= self.max_failed_batches:
            return 'max_failed_batches_reached'
        if self.skipped_batch_count >= self.max_skipped_batches:
            return 'max_skipped_batches_reached'
        if self.attempted_batch_count >= self.max_total_batch_attempts:
            return 'max_total_batch_attempts_reached'
        return ''

    def _allowed_batch_count(self):
        if self.max_batches_to_execute > 0:
            return self.max_batches_to_execute
        return len(self.execution_batches)

    def _send_current_batch(self):
        if self.execution_goal_in_flight:
            return

        batch = self.execution_batches[self.current_batch_index]
        batch_number = self.attempted_batch_count + 1
        total_batches = self._allowed_batch_count()
        if self.current_batch_index < len(self.execution_batch_start_indices):
            self.selected_start_index = self.execution_batch_start_indices[
                self.current_batch_index
            ]

        invalid_reason = self._validate_batch_for_execution(batch)
        if invalid_reason:
            alternate = self._find_valid_batch_near_start(
                self.latest_execution_waypoints.poses,
                self.latest_execution_waypoints.header.frame_id
                or self.global_frame
                or 'map',
                self.selected_start_index,
            )
            if alternate is None:
                self._set_execution_status(
                    'BATCH_INVALID %d/%d reason=%s'
                    % (batch_number, total_batches, invalid_reason)
                )
                self._handle_current_batch_failure(
                    invalid_reason,
                    batch_number,
                    total_batches,
                )
                return
            self.selected_start_index, batch = alternate
            self.execution_batches[self.current_batch_index] = batch
            if self.current_batch_index < len(self.execution_batch_start_indices):
                self.execution_batch_start_indices[
                    self.current_batch_index
                ] = self.selected_start_index

        batch.poses = self._remove_close_waypoints(batch.poses, preserve_last=True)
        for pose in batch.poses:
            pose.header.frame_id = batch.header.frame_id or self.global_frame

        invalid_reason = self._validate_batch_for_execution(batch)
        if invalid_reason:
            alternate = self._find_valid_batch_near_start(
                self.latest_execution_waypoints.poses,
                self.latest_execution_waypoints.header.frame_id
                or self.global_frame
                or 'map',
                self.selected_start_index,
            )
            if alternate is None:
                self._set_execution_status(
                    'BATCH_INVALID %d/%d reason=%s'
                    % (batch_number, total_batches, invalid_reason)
                )
                self._handle_current_batch_failure(
                    invalid_reason,
                    batch_number,
                    total_batches,
                )
                return
            self.selected_start_index, batch = alternate
            self.execution_batches[self.current_batch_index] = batch
            if self.current_batch_index < len(self.execution_batch_start_indices):
                self.execution_batch_start_indices[
                    self.current_batch_index
                ] = self.selected_start_index

        if self._batch_has_sharp_backtracking(batch.poses):
            self.get_logger().warn(
                'Batch %d/%d contains a sharp backtracking turn'
                % (batch_number, total_batches),
                throttle_duration_sec=5.0,
            )

        self._warn_if_batch_segments_are_long(batch.poses)
        self.latest_current_batch = copy.deepcopy(batch)
        self.coverage_current_batch_pub.publish(self.latest_current_batch)

        goal_msg = NavigateThroughPoses.Goal()
        goal_msg.poses = [copy.deepcopy(pose) for pose in batch.poses]
        goal_msg.behavior_tree = self.behavior_tree

        self.attempted_batch_count += 1
        self.execution_goal_in_flight = True
        self.execution_state = 'EXECUTING'
        self.current_goal_handle = None
        self.cancel_in_progress = False
        self.cancel_reason = ''
        self.cancel_batch_number = batch_number
        self.cancel_total_batches = total_batches
        self.batch_start_time = self.get_clock().now()
        self.last_feedback_time = self.batch_start_time
        self.last_progress_time = self.batch_start_time
        self.best_distance_remaining = None
        self.last_distance_remaining = None
        self.last_poses_remaining = None
        self.last_handled_failure_signature = None
        self.active_goal_signature = (
            self.latest_waypoints_checksum,
            self.current_batch_index,
        )
        self._set_execution_status(
            'EXECUTING_BATCH attempt=%d success_count=%d poses=%d start_index=%d'
            % (
                batch_number,
                self.executed_batch_count,
                len(batch.poses),
                self.selected_start_index,
            )
        )

        send_goal_future = self.nav2_action_client.send_goal_async(
            goal_msg,
            feedback_callback=self._nav2_feedback_callback,
        )
        send_goal_future.add_done_callback(
            lambda future: self._nav2_goal_response_callback(
                future,
                batch_number,
                total_batches,
            )
        )

    def _nav2_goal_response_callback(self, future, batch_number, total_batches):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._set_execution_status(
                'BATCH_FAILED %d/%d error=%s'
                % (batch_number, total_batches, exc)
            )
            self._handle_current_batch_failure(
                'goal_response_error',
                batch_number,
                total_batches,
            )
            return

        if not goal_handle.accepted:
            self._set_execution_status(
                'BATCH_REJECTED %d/%d'
                % (batch_number, total_batches)
            )
            self._handle_current_batch_failure(
                'goal_rejected',
                batch_number,
                total_batches,
            )
            return

        self.current_goal_handle = goal_handle
        self._set_execution_status(
            'BATCH_ACCEPTED %d/%d' % (batch_number, total_batches)
        )
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda future: self._nav2_result_callback(
                future,
                batch_number,
                total_batches,
            )
        )

    def _nav2_result_callback(self, future, batch_number, total_batches):
        if not self.execution_goal_in_flight:
            return

        self.execution_goal_in_flight = False

        try:
            wrapped_result = future.result()
        except Exception as exc:
            self._set_execution_status(
                'BATCH_FAILED %d/%d error=%s'
                % (batch_number, total_batches, exc)
            )
            self._handle_current_batch_failure(
                'result_error',
                batch_number,
                total_batches,
            )
            return

        result = wrapped_result.result
        status = wrapped_result.status
        error_code = getattr(result, 'error_code', 0)
        error_msg = getattr(result, 'error_msg', '')

        if status == GoalStatus.STATUS_SUCCEEDED and error_code == 0:
            completed_batch_len = 0
            if self.current_batch_index < len(self.execution_batches):
                completed_batch_len = len(
                    self.execution_batches[self.current_batch_index].poses
                )
            self.current_start_index = max(
                self.current_start_index,
                self.selected_start_index + completed_batch_len,
            )
            self.use_nearest_start_for_next_plan = False

            self.executed_batch_count += 1
            self._set_execution_status(
                'BATCH_SUCCEEDED %d success_count=%d attempts=%d skipped=%d failed=%d'
                % (
                    batch_number,
                    self.executed_batch_count,
                    self.attempted_batch_count,
                    self.skipped_batch_count,
                    self.failed_batch_count,
                )
            )
            self.current_goal_handle = None
            self.cancel_in_progress = False
            self.batch_start_time = None
            self.current_batch_index += 1

            if self.replan_received_during_execution:
                self._apply_pending_waypoints()
            self.execution_state = 'READY'
            return

        if not error_msg:
            error_msg = 'status=%d error_code=%d' % (status, error_code)
        self._set_execution_status(
            'BATCH_FAILED %d/%d error=%s'
            % (batch_number, total_batches, error_msg)
        )
        self._handle_current_batch_failure(error_msg, batch_number, total_batches)

    def _monitor_active_batch(self):
        if not self.execution_goal_in_flight or self.cancel_in_progress:
            return

        batch_number = self.attempted_batch_count
        total_batches = self._allowed_batch_count()
        elapsed_sec = self._elapsed_since(self.batch_start_time)

        if elapsed_sec > self.batch_timeout_sec:
            self._set_execution_status(
                'BATCH_TIMEOUT attempt=%d elapsed=%.1f'
                % (batch_number, elapsed_sec)
            )
            self._cancel_current_batch('timeout', batch_number, total_batches)
            return

        if self.best_distance_remaining is not None:
            no_progress_sec = self._elapsed_since(self.last_progress_time)
            if no_progress_sec > self.no_progress_timeout_sec:
                self._set_execution_status(
                    'BATCH_NO_PROGRESS attempt=%d' % batch_number
                )
                self._cancel_current_batch(
                    'no_progress',
                    batch_number,
                    total_batches,
                )
                return

        self._publish_feedback_status(batch_number)

    def _cancel_current_batch(self, reason, batch_number, total_batches):
        if self.cancel_in_progress:
            return

        self.cancel_in_progress = True
        self.cancel_reason = reason
        self.cancel_batch_number = batch_number
        self.cancel_total_batches = total_batches
        self._set_execution_status(
            'CANCELING_BATCH %d/%d' % (batch_number, total_batches)
        )

        if self.current_goal_handle is None:
            self._handle_current_batch_failure(reason, batch_number, total_batches)
            return

        try:
            cancel_future = self.current_goal_handle.cancel_goal_async()
        except Exception as exc:
            self.get_logger().warn(
                'Failed to request Nav2 cancel for batch %d/%d: %s'
                % (batch_number, total_batches, exc)
            )
            self._handle_current_batch_failure(reason, batch_number, total_batches)
            return

        cancel_future.add_done_callback(
            lambda future: self._cancel_done_callback(
                future,
                reason,
                batch_number,
                total_batches,
            )
        )

    def _cancel_done_callback(self, future, reason, batch_number, total_batches):
        try:
            future.result()
        except Exception as exc:
            self.get_logger().warn(
                'Nav2 cancel result failed for batch %d/%d: %s'
                % (batch_number, total_batches, exc)
            )

        self._handle_current_batch_failure(reason, batch_number, total_batches)

    def _handle_current_batch_failure(self, reason, batch_number, total_batches):
        if not self.execution_active and not self.execution_goal_in_flight:
            return

        failure_signature = (
            self.latest_waypoints_checksum,
            self.selected_start_index,
            batch_number,
            total_batches,
        )
        if failure_signature == self.last_handled_failure_signature:
            return
        self.last_handled_failure_signature = failure_signature

        self.execution_goal_in_flight = False
        self.current_goal_handle = None
        self.cancel_in_progress = False
        self.batch_start_time = None
        self.failed_batch_count += 1

        failed_batch = None
        failed_batch_len = 0
        if self.current_batch_index < len(self.execution_batches):
            failed_batch = copy.deepcopy(self.execution_batches[self.current_batch_index])
            failed_batch_len = len(failed_batch.poses)
        elif self.latest_current_batch.poses:
            failed_batch = copy.deepcopy(self.latest_current_batch)
            failed_batch_len = len(failed_batch.poses)

        if failed_batch is not None:
            self._record_skipped_batch(failed_batch)

        self.skipped_start_indices.add(self.selected_start_index)
        self.current_start_index = max(
            self.current_start_index,
            self.selected_start_index + max(1, failed_batch_len),
        )
        self.use_nearest_start_for_next_plan = False
        self.min_start_index_after_failure = max(
            self.min_start_index_after_failure,
            self.current_start_index,
        )

        self._set_execution_status(
            'BATCH_FAILED attempt=%d failed=%d'
            % (batch_number, self.failed_batch_count)
        )

        if self.failed_batch_count >= self.max_failed_batches:
            self.execution_active = False
            self.execution_state = 'FAILED'
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self._set_execution_status('EXECUTION_STOPPED max_failed_batches_reached')
            return

        should_retry = (
            self.retry_failed_batch
            and self.current_batch_retry_count < self.max_retries_per_batch
        )
        if should_retry:
            self.current_batch_retry_count += 1
            self.execution_state = 'READY'
            self._set_execution_status(
                'EXECUTION_CONTINUING next_start_index=%d'
                % self.selected_start_index
            )
            return

        self.current_batch_retry_count = 0

        if self.skip_failed_batch:
            self.skipped_batch_count += 1
            self._set_execution_status(
                'BATCH_SKIPPED skipped=%d next_start_index=%d'
                % (self.skipped_batch_count, self.current_start_index)
            )

        stop_reason = self._execution_stop_limit_reached()
        if stop_reason:
            self.execution_active = False
            self.execution_state = 'FAILED'
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self._set_execution_status('EXECUTION_STOPPED %s' % stop_reason)
            return

        if not self.continue_after_failure:
            self.execution_active = False
            self.execution_state = 'FAILED'
            self.executed_waypoints_checksum = self.latest_waypoints_checksum
            self._set_execution_status(
                'EXECUTION_FAILED reason=%s' % reason
            )
            return

        self.current_batch_index += 1

        if self.replan_received_during_execution:
            self._apply_pending_waypoints()

        self.execution_state = 'READY'
        self._set_execution_status(
            'EXECUTION_CONTINUING success_count=%d failed=%d skipped=%d next_start_index=%d'
            % (
                self.executed_batch_count,
                self.failed_batch_count,
                self.skipped_batch_count,
                self.current_start_index,
            )
        )

    def _record_skipped_batch(self, batch):
        frame_id = batch.header.frame_id or self.global_frame or 'map'
        self.skipped_waypoints.header.frame_id = frame_id
        self.skipped_waypoints.header.stamp = self.get_clock().now().to_msg()
        for pose in batch.poses:
            skipped_pose = copy.deepcopy(pose)
            skipped_pose.header.frame_id = frame_id
            skipped_pose.header.stamp = self.skipped_waypoints.header.stamp
            self.skipped_waypoints.poses.append(skipped_pose)

        self.failed_waypoint_markers = self._make_failed_waypoint_markers(frame_id)

    def _validate_batch_for_execution(self, batch):
        if len(batch.poses) < self.min_batch_poses:
            return 'too_few_poses'

        frame_id = self.global_frame or batch.header.frame_id or 'map'
        batch.header.frame_id = frame_id
        for pose in batch.poses:
            pose.header.frame_id = frame_id

        largest_gap = self._largest_output_gap(batch.poses)
        if largest_gap > self.max_batch_segment_length_m:
            return 'segment_too_long'

        if len(batch.poses) > 1 and self._path_length(batch.poses) <= 0.0:
            return 'zero_length_batch'

        return ''

    def _nav2_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        distance_remaining = getattr(feedback, 'distance_remaining', None)
        poses_remaining = getattr(feedback, 'number_of_poses_remaining', None)
        recoveries = getattr(feedback, 'number_of_recoveries', None)

        now = self.get_clock().now()
        self.last_feedback_time = now

        if distance_remaining is not None:
            if (
                self.best_distance_remaining is None
                or distance_remaining
                < self.best_distance_remaining - self.min_progress_distance_m
            ):
                self.best_distance_remaining = distance_remaining
                self.last_progress_time = now
            self.last_distance_remaining = distance_remaining

        if poses_remaining is not None:
            if (
                self.last_poses_remaining is None
                or poses_remaining < self.last_poses_remaining
            ):
                self.last_progress_time = now
            self.last_poses_remaining = poses_remaining

        fields = []
        fields.append('batch_attempt=%d' % self.attempted_batch_count)
        fields.append('success=%d' % self.executed_batch_count)
        fields.append('failed=%d' % self.failed_batch_count)
        fields.append('skipped=%d' % self.skipped_batch_count)
        if distance_remaining is not None:
            fields.append('distance_remaining=%.2f' % distance_remaining)
        if self.best_distance_remaining is not None:
            fields.append('best=%.2f' % self.best_distance_remaining)
        if poses_remaining is not None:
            fields.append('poses_remaining=%d' % poses_remaining)
        if recoveries is not None:
            fields.append('recoveries=%d' % recoveries)
        fields.append('elapsed=%.1f' % self._elapsed_since(self.batch_start_time))
        fields.append('no_progress_time=%.1f' % self._elapsed_since(self.last_progress_time))

        if not fields:
            fields.append('feedback_received=true')

        msg = String()
        msg.data = ' '.join(fields)
        self.coverage_nav2_feedback_pub.publish(msg)

    def _publish_feedback_status(self, batch_number):
        if self.batch_start_time is None:
            return

        fields = [
            'batch_attempt=%d' % batch_number,
            'success=%d' % self.executed_batch_count,
            'failed=%d' % self.failed_batch_count,
            'skipped=%d' % self.skipped_batch_count,
        ]
        if self.last_distance_remaining is not None:
            fields.append('distance_remaining=%.2f' % self.last_distance_remaining)
        if self.best_distance_remaining is not None:
            fields.append('best=%.2f' % self.best_distance_remaining)
        if self.last_poses_remaining is not None:
            fields.append('poses_remaining=%d' % self.last_poses_remaining)
        fields.append('elapsed=%.1f' % self._elapsed_since(self.batch_start_time))
        fields.append('no_progress_time=%.1f' % self._elapsed_since(self.last_progress_time))

        msg = String()
        msg.data = ' '.join(fields)
        self.coverage_nav2_feedback_pub.publish(msg)

    def _set_execution_status(self, status):
        if status != self.execution_status:
            self.get_logger().info('Coverage execution status: %s' % status)
        self.execution_status = status
        self.latest_status_msg.data = status
        if hasattr(self, 'coverage_execution_status_pub'):
            self.coverage_execution_status_pub.publish(self.latest_status_msg)

    def generate_waypoints(self, path_msg):
        """Simplify a nav_msgs/Path into sparse waypoint poses."""
        frame_id = path_msg.header.frame_id
        if not frame_id:
            self.get_logger().warn(
                'Input coverage path frame is empty; using "map"',
                throttle_duration_sec=5.0,
            )
            frame_id = 'map'

        input_pose_count = len(path_msg.poses)
        if input_pose_count == 0:
            waypoints = self._make_empty_path(frame_id)
            markers = self._make_delete_markers(frame_id)
            stats = {
                'input_poses': 0,
                'waypoints': 0,
                'distance_kept': 0,
                'turns_kept': 0,
                'input_path_length_m': 0.0,
                'waypoint_path_length_m': 0.0,
                'largest_output_gap_m': 0.0,
                'input_empty': True,
            }
            return {
                'waypoints': waypoints,
                'markers': markers,
                'stats_text': self._format_stats(stats),
            }

        kept_poses, keep_counts = self._select_waypoint_poses(path_msg.poses)
        kept_poses = self._remove_close_waypoints(kept_poses)
        kept_poses = self._ensure_first_and_last(
            kept_poses,
            path_msg.poses[0],
            path_msg.poses[-1],
        )
        kept_poses = self._enforce_max_waypoint_gap(kept_poses, path_msg.poses)

        if len(kept_poses) > self.max_waypoints:
            self.get_logger().warn(
                'Waypoint count %d exceeds max_waypoints=%d; downsampling while '
                'preserving max gap'
                % (len(kept_poses), self.max_waypoints),
                throttle_duration_sec=5.0,
            )
            kept_poses = self._downsample_waypoints(kept_poses, self.max_waypoints)
            kept_poses = self._ensure_first_and_last(
                kept_poses,
                path_msg.poses[0],
                path_msg.poses[-1],
            )
            kept_poses = self._enforce_max_waypoint_gap(kept_poses, path_msg.poses)

        kept_poses = self._remove_close_waypoints(
            kept_poses,
            preserve_last=True,
        )
        kept_poses = self._ensure_first_and_last(
            kept_poses,
            path_msg.poses[0],
            path_msg.poses[-1],
        )
        kept_poses = self._enforce_max_waypoint_gap(kept_poses, path_msg.poses)

        if not kept_poses:
            self.get_logger().warn(
                'Input coverage path is non-empty, but no waypoints were generated'
            )
            kept_poses = [copy.deepcopy(path_msg.poses[0])]

        waypoints = Path()
        waypoints.header.frame_id = frame_id
        waypoints.header.stamp = self.get_clock().now().to_msg()
        for pose in kept_poses:
            waypoint_pose = copy.deepcopy(pose)
            waypoint_pose.header.frame_id = frame_id
            waypoint_pose.header.stamp = waypoints.header.stamp
            waypoints.poses.append(waypoint_pose)

        if self.recompute_waypoint_orientations:
            self._recompute_waypoint_orientations(waypoints.poses)

        self._validate_waypoints(waypoints, path_msg)
        largest_output_gap_m = self._largest_output_gap(waypoints.poses)
        if largest_output_gap_m > self.max_waypoint_gap_m * 1.25:
            self.get_logger().warn(
                'Largest waypoint gap %.2f m exceeds allowed %.2f m'
                % (largest_output_gap_m, self.max_waypoint_gap_m),
                throttle_duration_sec=5.0,
            )

        stats = {
            'input_poses': input_pose_count,
            'waypoints': len(waypoints.poses),
            'distance_kept': keep_counts['distance'],
            'gap_kept': keep_counts['gap'],
            'turns_kept': keep_counts['turn'],
            'input_path_length_m': self._path_length(path_msg.poses),
            'waypoint_path_length_m': self._path_length(waypoints.poses),
            'largest_output_gap_m': largest_output_gap_m,
            'input_empty': False,
        }
        markers = self._make_waypoint_markers(waypoints)

        return {
            'waypoints': waypoints,
            'markers': markers,
            'stats_text': self._format_stats(stats),
        }

    def _select_waypoint_poses(self, poses):
        if len(poses) <= 2:
            return [copy.deepcopy(pose) for pose in poses], {
                'distance': 0,
                'gap': 0,
                'turn': 0,
            }

        keep_counts = {
            'distance': 0,
            'gap': 0,
            'turn': 0,
        }
        candidate_indices = {0, len(poses) - 1}
        distance_since_last_candidate = 0.0
        last_distance_candidate_index = 0

        for index in range(1, len(poses) - 1):
            previous_pose = poses[index - 1]
            current_pose = poses[index]
            next_pose = poses[index + 1]
            distance_since_last_candidate += self._pose_distance(
                previous_pose,
                current_pose,
            )

            turn_angle = self._turn_angle_deg(previous_pose, current_pose, next_pose)
            keep_for_gap = (
                self._pose_distance(poses[last_distance_candidate_index], current_pose)
                >= self.max_waypoint_gap_m
            )
            keep_for_distance = distance_since_last_candidate >= self.waypoint_spacing_m
            keep_for_turn = turn_angle >= self.min_turn_angle_deg

            if keep_for_turn:
                # Preserve the local shape around row ends and obstacle connectors.
                candidate_indices.update((index - 1, index, index + 1))
                keep_counts['turn'] += 1
                last_distance_candidate_index = index
                distance_since_last_candidate = 0.0
                continue

            if keep_for_gap or keep_for_distance:
                candidate_indices.add(index)
                last_distance_candidate_index = index
                distance_since_last_candidate = 0.0
                if keep_for_gap:
                    keep_counts['gap'] += 1
                if keep_for_distance:
                    keep_counts['distance'] += 1

        kept_poses = [
            copy.deepcopy(poses[index])
            for index in sorted(candidate_indices)
        ]

        return kept_poses, keep_counts

    def _remove_close_waypoints(self, poses, preserve_last=False):
        if len(poses) <= 1:
            return poses

        filtered = [poses[0]]
        last_index = len(poses) - 1
        for index, pose in enumerate(poses[1:], start=1):
            is_last = index == last_index
            if (
                is_last
                and preserve_last
                and self._pose_distance(filtered[-1], pose)
                < self.min_waypoint_separation_m
            ):
                filtered[-1] = pose
                continue

            if self._pose_distance(filtered[-1], pose) >= self.min_waypoint_separation_m:
                filtered.append(pose)

        return filtered

    def _ensure_first_and_last(self, poses, first_pose, last_pose):
        if not poses:
            return [copy.deepcopy(first_pose), copy.deepcopy(last_pose)]

        ensured = list(poses)
        if self._pose_distance(ensured[0], first_pose) > 1.0e-6:
            ensured.insert(0, copy.deepcopy(first_pose))
        else:
            ensured[0] = copy.deepcopy(first_pose)

        if self._pose_distance(ensured[-1], last_pose) > 1.0e-6:
            ensured.append(copy.deepcopy(last_pose))
        else:
            ensured[-1] = copy.deepcopy(last_pose)

        return ensured

    def _downsample_waypoints(self, poses, max_waypoints):
        if len(poses) <= max_waypoints:
            return poses
        if max_waypoints <= 1:
            return [copy.deepcopy(poses[0])]
        if max_waypoints == 2:
            return [copy.deepcopy(poses[0]), copy.deepcopy(poses[-1])]

        selected = [copy.deepcopy(poses[0])]
        interior_count = max_waypoints - 2
        step = (len(poses) - 2) / float(interior_count + 1)

        for index in range(1, interior_count + 1):
            source_index = int(round(index * step))
            source_index = min(max(source_index, 1), len(poses) - 2)
            selected.append(copy.deepcopy(poses[source_index]))

        selected.append(copy.deepcopy(poses[-1]))
        return selected

    def _enforce_max_waypoint_gap(self, kept_poses, source_poses):
        if len(kept_poses) <= 1 or not source_poses:
            return kept_poses

        repaired = [copy.deepcopy(kept_poses[0])]
        source_start_index = self._find_pose_index(source_poses, kept_poses[0], 0)

        for target_pose in kept_poses[1:]:
            source_end_index = self._find_pose_index(
                source_poses,
                target_pose,
                source_start_index,
            )
            if source_end_index < source_start_index:
                source_end_index = source_start_index

            for source_index in range(source_start_index + 1, source_end_index + 1):
                source_pose = source_poses[source_index]
                is_target = source_index == source_end_index
                distance = self._pose_distance(repaired[-1], source_pose)

                if distance > self.max_waypoint_gap_m:
                    previous_source_pose = source_poses[source_index - 1]
                    if (
                        self._pose_distance(repaired[-1], previous_source_pose)
                        > 1.0e-6
                    ):
                        repaired.append(copy.deepcopy(previous_source_pose))
                        distance = self._pose_distance(repaired[-1], source_pose)

                if (
                    distance > self.max_waypoint_gap_m
                    or is_target
                    or distance >= self.waypoint_spacing_m
                ):
                    if self._pose_distance(repaired[-1], source_pose) > 1.0e-6:
                        repaired.append(copy.deepcopy(source_pose))

            source_start_index = source_end_index

        return repaired

    def _find_pose_index(self, poses, target_pose, start_index):
        target_x = target_pose.pose.position.x
        target_y = target_pose.pose.position.y

        for index in range(start_index, len(poses)):
            pose = poses[index]
            if (
                abs(pose.pose.position.x - target_x) < 1.0e-6
                and abs(pose.pose.position.y - target_y) < 1.0e-6
            ):
                return index

        best_index = start_index
        best_distance = None
        for index in range(start_index, len(poses)):
            pose = poses[index]
            dx = pose.pose.position.x - target_x
            dy = pose.pose.position.y - target_y
            distance = dx * dx + dy * dy
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = index

        return best_index

    def _validate_waypoints(self, waypoints, input_path):
        if waypoints.header.frame_id != (input_path.header.frame_id or 'map'):
            self.get_logger().warn(
                'Waypoint frame "%s" does not match input path frame "%s"'
                % (waypoints.header.frame_id, input_path.header.frame_id)
            )

        if len(input_path.poses) > 0 and len(waypoints.poses) == 0:
            self.get_logger().warn('Non-empty input path produced zero waypoints')

        for index in range(1, len(waypoints.poses)):
            distance = self._pose_distance(
                waypoints.poses[index - 1],
                waypoints.poses[index],
            )
            if distance < self.min_waypoint_separation_m:
                self.get_logger().warn(
                    'Consecutive waypoints %d and %d are only %.3f m apart'
                    % (index - 1, index, distance),
                    throttle_duration_sec=5.0,
                )
                break

        if len(waypoints.poses) > self.max_waypoints:
            self.get_logger().warn(
                'Waypoint count %d exceeds max_waypoints=%d'
                % (len(waypoints.poses), self.max_waypoints),
                throttle_duration_sec=5.0,
            )

    def _recompute_waypoint_orientations(self, poses):
        if len(poses) < 2:
            return

        for index, pose in enumerate(poses):
            if index + 1 < len(poses):
                yaw = self._yaw_between_poses(pose, poses[index + 1])
            else:
                yaw = self._yaw_between_poses(poses[index - 1], pose)

            pose.pose.orientation.x = 0.0
            pose.pose.orientation.y = 0.0
            pose.pose.orientation.z = math.sin(yaw * 0.5)
            pose.pose.orientation.w = math.cos(yaw * 0.5)

    def _make_waypoint_markers(self, waypoints):
        frame_id = waypoints.header.frame_id or 'map'
        markers = self._make_delete_markers(frame_id)
        if not self.publish_waypoint_markers:
            return markers

        sphere_marker = Marker()
        sphere_marker.header.frame_id = frame_id
        sphere_marker.header.stamp = self.get_clock().now().to_msg()
        sphere_marker.ns = 'coverage_waypoints'
        sphere_marker.id = 0
        sphere_marker.type = Marker.SPHERE_LIST
        sphere_marker.action = Marker.ADD
        sphere_marker.pose.orientation.w = 1.0
        sphere_marker.scale.x = 0.12
        sphere_marker.scale.y = 0.12
        sphere_marker.scale.z = 0.12
        sphere_marker.color.r = 1.0
        sphere_marker.color.g = 0.65
        sphere_marker.color.b = 0.05
        sphere_marker.color.a = 0.95

        for waypoint in waypoints.poses:
            point = Point()
            point.x = waypoint.pose.position.x
            point.y = waypoint.pose.position.y
            point.z = waypoint.pose.position.z + 0.05
            sphere_marker.points.append(point)

        markers.markers.append(sphere_marker)

        for index, waypoint in enumerate(waypoints.poses):
            label = Marker()
            label.header.frame_id = frame_id
            label.header.stamp = sphere_marker.header.stamp
            label.ns = 'coverage_waypoint_labels'
            label.id = index
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position.x = waypoint.pose.position.x
            label.pose.position.y = waypoint.pose.position.y
            label.pose.position.z = waypoint.pose.position.z + 0.20
            label.pose.orientation.w = 1.0
            label.scale.z = 0.16
            label.color.r = 1.0
            label.color.g = 1.0
            label.color.b = 1.0
            label.color.a = 0.9
            label.text = str(index)
            markers.markers.append(label)

        return markers

    def _make_delete_markers(self, frame_id):
        marker = Marker()
        marker.header.frame_id = frame_id or 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'coverage_waypoint_cleanup'
        marker.id = 0
        marker.action = Marker.DELETEALL
        markers = MarkerArray()
        markers.markers.append(marker)
        return markers

    def _make_failed_waypoint_markers(self, frame_id):
        markers = self._make_delete_markers(frame_id)
        marker_id = 0
        stamp = self.get_clock().now().to_msg()
        for index, pose in enumerate(self.skipped_waypoints.poses):
            marker = Marker()
            marker.header.frame_id = frame_id or 'map'
            marker.header.stamp = stamp
            marker.ns = 'coverage_failed_waypoints'
            marker.id = marker_id
            marker_id += 1
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose = copy.deepcopy(pose.pose)
            marker.pose.position.z += 0.08
            marker.scale.x = 0.16
            marker.scale.y = 0.16
            marker.scale.z = 0.16
            marker.color.r = 1.0
            marker.color.g = 0.05
            marker.color.b = 0.05
            marker.color.a = 0.95
            markers.markers.append(marker)

            label = Marker()
            label.header.frame_id = frame_id or 'map'
            label.header.stamp = stamp
            label.ns = 'coverage_failed_waypoint_labels'
            label.id = index
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose = copy.deepcopy(pose.pose)
            label.pose.position.z += 0.26
            label.scale.z = 0.16
            label.color.r = 1.0
            label.color.g = 0.2
            label.color.b = 0.2
            label.color.a = 0.95
            label.text = 'skip'
            markers.markers.append(label)

        return markers

    def _make_empty_path(self, frame_id):
        path = Path()
        path.header.frame_id = frame_id or 'map'
        path.header.stamp = self.get_clock().now().to_msg()
        return path

    def _format_stats(self, stats):
        if stats.get('input_empty', False):
            return (
                'input_poses=0 waypoints=0 input_empty=true '
                'spacing=%.2fm turns_kept=0 distance_kept=0 '
                'max_waypoint_gap_m=%.2f largest_output_gap_m=0.00 '
                'path_length_m=0.00 waypoint_path_length_m=0.00'
                % (self.waypoint_spacing_m, self.max_waypoint_gap_m)
            )

        return (
            'input_poses=%d waypoints=%d spacing=%.2fm turns_kept=%d '
            'distance_kept=%d gap_kept=%d max_waypoint_gap_m=%.2f '
            'largest_output_gap_m=%.2f path_length_m=%.2f '
            'waypoint_path_length_m=%.2f'
            % (
                stats['input_poses'],
                stats['waypoints'],
                self.waypoint_spacing_m,
                stats['turns_kept'],
                stats['distance_kept'],
                stats['gap_kept'],
                self.max_waypoint_gap_m,
                stats['largest_output_gap_m'],
                stats['input_path_length_m'],
                stats['waypoint_path_length_m'],
            )
        )

    def _sanitize_parameters(self):
        if self.waypoint_spacing_m <= 0.0:
            self.get_logger().warn(
                'waypoint_spacing_m must be positive; using 0.75 m'
            )
            self.waypoint_spacing_m = 0.75

        if self.min_turn_angle_deg < 0.0:
            self.get_logger().warn(
                'min_turn_angle_deg must not be negative; using 0.0 deg'
            )
            self.min_turn_angle_deg = 0.0

        if self.min_waypoint_separation_m < 0.0:
            self.get_logger().warn(
                'min_waypoint_separation_m must not be negative; using 0.0 m'
            )
            self.min_waypoint_separation_m = 0.0

        if self.max_waypoint_gap_m <= 0.0:
            self.get_logger().warn(
                'max_waypoint_gap_m must be positive; using waypoint_spacing_m'
            )
            self.max_waypoint_gap_m = self.waypoint_spacing_m

        if self.max_batch_segment_length_m <= 0.0:
            self.get_logger().warn(
                'max_batch_segment_length_m must be positive; using '
                'max_waypoint_gap_m'
            )
            self.max_batch_segment_length_m = self.max_waypoint_gap_m

        if self.max_waypoints < 1:
            self.get_logger().warn('max_waypoints must be at least 1; using 1')
            self.max_waypoints = 1

        if self.max_waypoints_per_batch < 1:
            self.get_logger().warn(
                'max_waypoints_per_batch must be at least 1; using 1'
            )
            self.max_waypoints_per_batch = 1

        if self.max_batches_to_execute < 0:
            self.get_logger().warn(
                'max_batches_to_execute must be 0 or positive; using 1'
            )
            self.max_batches_to_execute = 1

        if self.max_retries_per_batch < 0:
            self.get_logger().warn(
                'max_retries_per_batch must not be negative; using 0'
            )
            self.max_retries_per_batch = 0

        if self.max_failed_batches < 1:
            self.get_logger().warn(
                'max_failed_batches must be at least 1; using 1'
            )
            self.max_failed_batches = 1

        if self.max_skipped_batches < 1:
            self.get_logger().warn(
                'max_skipped_batches must be at least 1; using 1'
            )
            self.max_skipped_batches = 1

        if self.max_total_batch_attempts < 1:
            self.get_logger().warn(
                'max_total_batch_attempts must be at least 1; using 1'
            )
            self.max_total_batch_attempts = 1

        if self.batch_timeout_sec <= 0.0:
            self.get_logger().warn(
                'batch_timeout_sec must be positive; using 20.0 sec'
            )
            self.batch_timeout_sec = 20.0

        if self.no_progress_timeout_sec <= 0.0:
            self.get_logger().warn(
                'no_progress_timeout_sec must be positive; using 6.0 sec'
            )
            self.no_progress_timeout_sec = 6.0

        if self.min_progress_distance_m < 0.0:
            self.get_logger().warn(
                'min_progress_distance_m must not be negative; using 0.0 m'
            )
            self.min_progress_distance_m = 0.0

        if self.min_batch_poses < 1:
            self.get_logger().warn('min_batch_poses must be at least 1; using 1')
            self.min_batch_poses = 1

        if self.wait_for_nav2_timeout_sec <= 0.0:
            self.get_logger().warn(
                'wait_for_nav2_timeout_sec must be positive; using 10.0 sec'
            )
            self.wait_for_nav2_timeout_sec = 10.0

        if self.waypoint_publish_rate_hz <= 0.0:
            self.get_logger().warn(
                'waypoint_publish_rate_hz must be positive; using 1.0 Hz'
            )
            self.waypoint_publish_rate_hz = 1.0

    def _path_checksum(self, path_msg):
        checksum_data = [
            path_msg.header.frame_id,
            len(path_msg.poses),
        ]
        for pose_stamped in path_msg.poses:
            pose = pose_stamped.pose
            checksum_data.extend([
                pose.position.x,
                pose.position.y,
                pose.position.z,
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w,
            ])
        return hash(tuple(checksum_data))

    def _elapsed_since(self, start_time):
        if start_time is None:
            return 0.0
        return (self.get_clock().now() - start_time).nanoseconds / 1.0e9

    def _path_length(self, poses):
        if len(poses) < 2:
            return 0.0

        length = 0.0
        previous_pose = poses[0]
        for pose in poses[1:]:
            length += self._pose_distance(previous_pose, pose)
            previous_pose = pose
        return length

    def _largest_output_gap(self, poses):
        largest_gap = 0.0
        for index in range(1, len(poses)):
            largest_gap = max(
                largest_gap,
                self._pose_distance(poses[index - 1], poses[index]),
            )
        return largest_gap

    def _pose_distance(self, first, second):
        dx = first.pose.position.x - second.pose.position.x
        dy = first.pose.position.y - second.pose.position.y
        return math.hypot(dx, dy)

    def _yaw_between_poses(self, first, second):
        return math.atan2(
            second.pose.position.y - first.pose.position.y,
            second.pose.position.x - first.pose.position.x,
        )

    def _is_sharp_turn_index(self, poses, index):
        if index <= 0 or index >= len(poses) - 1:
            return False
        return (
            self._turn_angle_deg(poses[index - 1], poses[index], poses[index + 1])
            >= self.min_turn_angle_deg
        )

    def _batch_has_sharp_backtracking(self, poses):
        for index in range(1, len(poses) - 1):
            if self._turn_angle_deg(
                poses[index - 1],
                poses[index],
                poses[index + 1],
            ) >= 135.0:
                return True
        return False

    def _warn_if_batch_segments_are_long(self, poses):
        largest_batch_gap = self._largest_output_gap(poses)
        if largest_batch_gap > self.max_batch_segment_length_m:
            self.get_logger().warn(
                'Current batch has segment gap %.2f m above '
                'max_batch_segment_length_m=%.2f'
                % (largest_batch_gap, self.max_batch_segment_length_m),
                throttle_duration_sec=5.0,
            )

    def _turn_angle_deg(self, previous_pose, current_pose, next_pose):
        first_heading = math.atan2(
            current_pose.pose.position.y - previous_pose.pose.position.y,
            current_pose.pose.position.x - previous_pose.pose.position.x,
        )
        second_heading = math.atan2(
            next_pose.pose.position.y - current_pose.pose.position.y,
            next_pose.pose.position.x - current_pose.pose.position.x,
        )

        delta = second_heading - first_heading
        while delta > math.pi:
            delta -= 2.0 * math.pi
        while delta < -math.pi:
            delta += 2.0 * math.pi

        return abs(math.degrees(delta))


def main(args=None):
    rclpy.init(args=args)
    node = CoverageExecutorNode()

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

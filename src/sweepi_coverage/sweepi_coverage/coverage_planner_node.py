#!/usr/bin/env python3
"""Coverage path planner node for Step 3 of the SweePi coverage system."""

from collections import deque
import heapq
import math

import rclpy
from geometry_msgs.msg import Point, PoseStamped
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import Float32, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

from sweepi_coverage.coverage_utils import (
    in_bounds,
    map_to_flat_index,
    map_to_world,
    meters_to_cell_radius,
    meters_to_cells,
    world_to_map,
)


OBSTACLE = 0
UNCOVERED = 50
COVERED = 100
UNKNOWN = -1


class CoveragePlannerNode(Node):
    """Generate an obstacle-aware visualization path through uncovered cells."""

    def __init__(self):
        super().__init__('coverage_planner_node')

        self.declare_parameter('coverage_map_topic', '/coverage_map')
        self.declare_parameter('nav_costmap_topic', '/global_costmap/costmap')
        self.declare_parameter('coverage_path_topic', '/coverage_path')
        self.declare_parameter('planning_mask_topic', '/coverage_planning_mask')
        self.declare_parameter('coverage_percentage_topic', '/coverage_percentage')
        self.declare_parameter('coverage_stats_topic', '/coverage_stats')
        self.declare_parameter('coverage_cell_value', UNCOVERED)
        self.declare_parameter('coverage_spacing_m', 0.25)
        self.declare_parameter('min_segment_length_m', 0.30)
        self.declare_parameter('path_publish_rate_hz', 1.0)
        self.declare_parameter('inflation_radius_m', 0.28)
        self.declare_parameter('min_region_area_m2', 0.20)
        self.declare_parameter('planning_direction', 'auto')
        self.declare_parameter('publish_debug_mask', True)
        self.declare_parameter('publish_debug_markers', True)
        self.declare_parameter('replan_on_map_change', True)
        self.declare_parameter('republish_last_path', True)
        self.declare_parameter('freeze_path_after_first_valid_plan', False)
        self.declare_parameter('robot_radius_m', 0.20)
        self.declare_parameter('coverage_safety_margin_m', 0.10)
        self.declare_parameter('connect_disjoint_segments', True)
        self.declare_parameter('connector_step_m', 0.10)
        self.declare_parameter('max_consecutive_pose_jump_m', 0.50)
        self.declare_parameter('connector_check_obstacles', True)
        self.declare_parameter('connector_allow_simple_straight_line', True)
        self.declare_parameter('optimize_segment_order', True)
        self.declare_parameter('allow_segment_reversal', True)
        self.declare_parameter('start_near_robot_if_tf_available', True)
        self.declare_parameter('debug_path_continuity', True)
        self.declare_parameter('robot_base_frame', 'base_link')
        self.declare_parameter('tf_lookup_timeout_sec', 0.2)
        self.declare_parameter('use_nav_costmap_for_planning', True)
        self.declare_parameter('use_global_costmap_for_planning', True)
        self.declare_parameter('max_allowed_nav_cost', 99)
        self.declare_parameter('treat_unknown_cost_as_blocked', True)
        self.declare_parameter('nav_costmap_timeout_sec', 2.0)
        self.declare_parameter('wait_for_nav_costmap_before_planning', False)
        self.declare_parameter('wait_for_robot_pose_before_planning', False)
        self.declare_parameter('plan_only_reachable_from_robot', True)
        self.declare_parameter('cleanup_after_main_path', True)
        self.declare_parameter('cleanup_max_passes', 1)
        self.declare_parameter('coverage_execution_status_topic', '/coverage_execution_status')

        self.coverage_map_topic = (
            self.get_parameter('coverage_map_topic').get_parameter_value().string_value
        )
        self.nav_costmap_topic = (
            self.get_parameter('nav_costmap_topic').get_parameter_value().string_value
        )
        self.coverage_path_topic = (
            self.get_parameter('coverage_path_topic').get_parameter_value().string_value
        )
        self.planning_mask_topic = (
            self.get_parameter('planning_mask_topic').get_parameter_value().string_value
        )
        self.coverage_percentage_topic = (
            self.get_parameter('coverage_percentage_topic')
            .get_parameter_value()
            .string_value
        )
        self.coverage_stats_topic = (
            self.get_parameter('coverage_stats_topic').get_parameter_value().string_value
        )
        self.coverage_cell_value = (
            self.get_parameter('coverage_cell_value').get_parameter_value().integer_value
        )
        self.coverage_spacing_m = (
            self.get_parameter('coverage_spacing_m').get_parameter_value().double_value
        )
        self.min_segment_length_m = (
            self.get_parameter('min_segment_length_m').get_parameter_value().double_value
        )
        self.path_publish_rate_hz = (
            self.get_parameter('path_publish_rate_hz').get_parameter_value().double_value
        )
        self.inflation_radius_m = (
            self.get_parameter('inflation_radius_m').get_parameter_value().double_value
        )
        self.min_region_area_m2 = (
            self.get_parameter('min_region_area_m2').get_parameter_value().double_value
        )
        self.planning_direction = (
            self.get_parameter('planning_direction').get_parameter_value().string_value
        )
        self.publish_debug_mask = (
            self.get_parameter('publish_debug_mask').get_parameter_value().bool_value
        )
        self.publish_debug_markers = (
            self.get_parameter('publish_debug_markers').get_parameter_value().bool_value
        )
        self.replan_on_map_change = (
            self.get_parameter('replan_on_map_change').get_parameter_value().bool_value
        )
        self.republish_last_path = (
            self.get_parameter('republish_last_path').get_parameter_value().bool_value
        )
        self.freeze_path_after_first_valid_plan = (
            self.get_parameter('freeze_path_after_first_valid_plan')
            .get_parameter_value()
            .bool_value
        )
        self.robot_radius_m = (
            self.get_parameter('robot_radius_m').get_parameter_value().double_value
        )
        self.coverage_safety_margin_m = (
            self.get_parameter('coverage_safety_margin_m')
            .get_parameter_value()
            .double_value
        )
        self.connect_disjoint_segments = (
            self.get_parameter('connect_disjoint_segments')
            .get_parameter_value()
            .bool_value
        )
        self.connector_step_m = (
            self.get_parameter('connector_step_m').get_parameter_value().double_value
        )
        self.max_consecutive_pose_jump_m = (
            self.get_parameter('max_consecutive_pose_jump_m')
            .get_parameter_value()
            .double_value
        )
        self.connector_check_obstacles = (
            self.get_parameter('connector_check_obstacles')
            .get_parameter_value()
            .bool_value
        )
        self.connector_allow_simple_straight_line = (
            self.get_parameter('connector_allow_simple_straight_line')
            .get_parameter_value()
            .bool_value
        )
        self.optimize_segment_order = (
            self.get_parameter('optimize_segment_order').get_parameter_value().bool_value
        )
        self.allow_segment_reversal = (
            self.get_parameter('allow_segment_reversal').get_parameter_value().bool_value
        )
        self.start_near_robot_if_tf_available = (
            self.get_parameter('start_near_robot_if_tf_available')
            .get_parameter_value()
            .bool_value
        )
        self.debug_path_continuity = (
            self.get_parameter('debug_path_continuity').get_parameter_value().bool_value
        )
        self.robot_base_frame = (
            self.get_parameter('robot_base_frame').get_parameter_value().string_value
        )
        self.tf_lookup_timeout_sec = (
            self.get_parameter('tf_lookup_timeout_sec')
            .get_parameter_value()
            .double_value
        )
        self.use_nav_costmap_for_planning = (
            self.get_parameter('use_nav_costmap_for_planning')
            .get_parameter_value()
            .bool_value
        )
        self.use_global_costmap_for_planning = (
            self.get_parameter('use_global_costmap_for_planning')
            .get_parameter_value()
            .bool_value
        )
        self.max_allowed_nav_cost = (
            self.get_parameter('max_allowed_nav_cost')
            .get_parameter_value()
            .integer_value
        )
        self.treat_unknown_cost_as_blocked = (
            self.get_parameter('treat_unknown_cost_as_blocked')
            .get_parameter_value()
            .bool_value
        )
        self.nav_costmap_timeout_sec = (
            self.get_parameter('nav_costmap_timeout_sec')
            .get_parameter_value()
            .double_value
        )
        self.wait_for_nav_costmap_before_planning = (
            self.get_parameter('wait_for_nav_costmap_before_planning')
            .get_parameter_value()
            .bool_value
        )
        self.wait_for_robot_pose_before_planning = (
            self.get_parameter('wait_for_robot_pose_before_planning')
            .get_parameter_value()
            .bool_value
        )
        self.plan_only_reachable_from_robot = (
            self.get_parameter('plan_only_reachable_from_robot')
            .get_parameter_value()
            .bool_value
        )
        self.cleanup_after_main_path = (
            self.get_parameter('cleanup_after_main_path')
            .get_parameter_value()
            .bool_value
        )
        self.cleanup_max_passes = (
            self.get_parameter('cleanup_max_passes')
            .get_parameter_value()
            .integer_value
        )
        self.coverage_execution_status_topic = (
            self.get_parameter('coverage_execution_status_topic')
            .get_parameter_value()
            .string_value
        )

        self._sanitize_startup_parameters()

        self.coverage_map = None
        self.coverage_map_checksum = None
        self.nav_costmap = None
        self.nav_costmap_checksum = None
        self.nav_costmap_received_once = False
        self.plan_dirty = False
        self.path_frozen = False
        self.latest_path = Path()
        self.latest_debug_mask = None
        self.latest_markers = MarkerArray()
        self.latest_percentage_msg = Float32()
        self.latest_stats_msg = String()
        self.latest_plan_stats = self._make_empty_stats()
        self.connector_count = 0
        self.connector_pose_count = 0
        self.connector_failure_count = 0
        self.cleanup_pass_count = 0
        self.last_execution_status = ''

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        path_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        nav_costmap_qos = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.coverage_map_sub = self.create_subscription(
            OccupancyGrid,
            self.coverage_map_topic,
            self.coverage_map_callback,
            map_qos,
        )
        self.nav_costmap_sub = self.create_subscription(
            OccupancyGrid,
            self.nav_costmap_topic,
            self.nav_costmap_callback,
            nav_costmap_qos,
        )
        self.execution_status_sub = self.create_subscription(
            String,
            self.coverage_execution_status_topic,
            self.execution_status_callback,
            path_qos,
        )
        self.coverage_path_pub = self.create_publisher(
            Path,
            self.coverage_path_topic,
            path_qos,
        )
        self.planning_mask_pub = self.create_publisher(
            OccupancyGrid,
            self.planning_mask_topic,
            path_qos,
        )
        self.marker_pub = self.create_publisher(
            MarkerArray,
            '/coverage_path_markers',
            path_qos,
        )
        self.coverage_percentage_pub = self.create_publisher(
            Float32,
            self.coverage_percentage_topic,
            path_qos,
        )
        self.coverage_stats_pub = self.create_publisher(
            String,
            self.coverage_stats_topic,
            path_qos,
        )
        self.reset_service = self.create_service(
            Trigger,
            '/reset_coverage_planner',
            self.reset_service_callback,
        )

        publish_period = 1.0 / self.path_publish_rate_hz
        self.timer = self.create_timer(publish_period, self.publish_outputs)

        self.get_logger().info(
            'Coverage planner started: coverage_map=%s, nav_costmap=%s, path=%s, '
            'mask=%s, percentage=%s, stats=%s, direction=%s, '
            'use_nav_costmap=%s, robot_radius=%.2fm, safety_margin=%.2fm, '
            'inflation_radius=%.2fm'
            % (
                self.coverage_map_topic,
                self.nav_costmap_topic,
                self.coverage_path_topic,
                self.planning_mask_topic,
                self.coverage_percentage_topic,
                self.coverage_stats_topic,
                self.planning_direction,
                str(self._nav_costmap_enabled()).lower(),
                self.robot_radius_m,
                self.coverage_safety_margin_m,
                self.inflation_radius_m,
            )
        )

    def reset_service_callback(self, request, response):
        del request
        self.coverage_map = None
        self.coverage_map_checksum = None
        self.plan_dirty = False
        self.path_frozen = False
        self.latest_path = self._make_empty_path()
        self.latest_debug_mask = None
        self.latest_markers = self._make_delete_markers()
        self.latest_percentage_msg = Float32()
        self.latest_stats_msg = String()
        self.latest_stats_msg.data = self._format_coverage_stats(
            self._make_empty_stats()
        )
        self.latest_plan_stats = self._make_empty_stats()
        self.connector_count = 0
        self.connector_pose_count = 0
        self.connector_failure_count = 0
        self.cleanup_pass_count = 0
        self.last_execution_status = ''

        stamp = self.get_clock().now().to_msg()
        self.latest_path.header.stamp = stamp
        self.coverage_path_pub.publish(self.latest_path)

        empty_mask = OccupancyGrid()
        empty_mask.header.frame_id = 'map'
        empty_mask.header.stamp = stamp
        self.planning_mask_pub.publish(empty_mask)

        for marker in self.latest_markers.markers:
            marker.header.stamp = stamp
        self.marker_pub.publish(self.latest_markers)
        self.coverage_percentage_pub.publish(self.latest_percentage_msg)
        self.coverage_stats_pub.publish(self.latest_stats_msg)

        response.success = True
        response.message = 'Coverage planner reset; /coverage_path cleared'
        self.get_logger().info(response.message)
        return response

    def coverage_map_callback(self, msg):
        """Store the latest coverage map and regenerate visualization outputs."""
        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring coverage map with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        new_checksum = self._coverage_map_checksum(msg)
        map_changed = new_checksum != self.coverage_map_checksum

        self.coverage_map = msg

        # Path freezing only freezes the generated route. Live progress must
        # continue tracking the latest /coverage_map as the robot moves.
        if map_changed:
            live_stats = dict(self.latest_plan_stats)
            live_stats.update(self._compute_coverage_counts(msg))
            self.latest_plan_stats = live_stats
            self.latest_percentage_msg.data = float(
                live_stats.get('percentage', 0.0)
            )
            self.latest_stats_msg.data = self._format_coverage_stats(live_stats)
            self.coverage_map_checksum = new_checksum

        if self.path_frozen:
            return

        if map_changed or not self.replan_on_map_change:
            self.plan_dirty = True

    def nav_costmap_callback(self, msg):
        """Store the latest Nav2 costmap so planning avoids undrivable cells."""
        if not self._nav_costmap_enabled():
            return

        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring nav costmap with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        new_checksum = self._occupancy_grid_checksum(msg)
        costmap_changed = new_checksum != self.nav_costmap_checksum
        self.nav_costmap = msg
        if not self.nav_costmap_received_once:
            self.nav_costmap_received_once = True
            self.get_logger().info(
                'Global costmap received for coverage planning: topic=%s frame=%s '
                'size=%dx%d resolution=%.3f max_allowed_nav_cost=%d '
                'unknown_blocked=%s'
                % (
                    self.nav_costmap_topic,
                    msg.header.frame_id or 'map',
                    msg.info.width,
                    msg.info.height,
                    msg.info.resolution,
                    self.max_allowed_nav_cost,
                    str(self.treat_unknown_cost_as_blocked).lower(),
                )
            )
        if self.path_frozen:
            return

        if costmap_changed or not self.replan_on_map_change:
            self.nav_costmap_checksum = new_checksum
            self.plan_dirty = True

    def execution_status_callback(self, msg):
        status = str(msg.data or '').strip()
        previous_status = self.last_execution_status
        self.last_execution_status = status

        terminal_statuses = ('SUCCEEDED', 'COMPLETED_WITH_SKIPS')
        if previous_status == status or status not in terminal_statuses:
            return
        if not self.cleanup_after_main_path:
            return
        if self.cleanup_pass_count >= self.cleanup_max_passes:
            return
        if self.coverage_map is None:
            return

        self.cleanup_pass_count += 1
        self.path_frozen = False
        self.plan_dirty = True
        self.get_logger().info(
            'Coverage main path completed; planning cleanup pass %d/%d for '
            'currently reachable uncovered cells'
            % (self.cleanup_pass_count, self.cleanup_max_passes)
        )

    def publish_outputs(self):
        """Replan when needed, then publish visualization and stats outputs."""
        if self.coverage_map is None:
            return

        if self.plan_dirty:
            if not self._planning_inputs_ready():
                return

            plan = self.generate_plan(self.coverage_map)
            self.latest_path = plan['path']
            self.latest_debug_mask = plan['debug_mask']
            self.latest_markers = plan['markers']
            self.latest_plan_stats = plan['stats']
            self.latest_percentage_msg.data = float(plan['stats']['percentage'])
            self.latest_stats_msg.data = self._format_coverage_stats(plan['stats'])
            self.plan_dirty = False
            self._log_replan_summary(plan['stats'])
            if self._should_freeze_plan(plan):
                self.path_frozen = True
                self.get_logger().info(
                    'Coverage path frozen after first valid plan: poses=%d '
                    'path_length=%.2fm'
                    % (
                        plan['stats']['poses'],
                        plan['stats']['length_m'],
                    )
                )
        elif not self.republish_last_path:
            return

        stamp = self.get_clock().now().to_msg()
        self.latest_path.header.stamp = stamp
        self.coverage_path_pub.publish(self.latest_path)

        if self.publish_debug_mask and self.latest_debug_mask is not None:
            self.latest_debug_mask.header.stamp = stamp
            self.planning_mask_pub.publish(self.latest_debug_mask)

        if self.publish_debug_markers:
            for marker in self.latest_markers.markers:
                marker.header.stamp = stamp
            self.marker_pub.publish(self.latest_markers)

        self.coverage_percentage_pub.publish(self.latest_percentage_msg)
        self.coverage_stats_pub.publish(self.latest_stats_msg)

    def generate_plan(self, msg):
        """Generate and validate all Step 3 visualization outputs."""
        path = self._make_empty_path()
        empty_markers = self._make_delete_markers()
        stats = self._make_empty_stats()

        resolution = msg.info.resolution
        if resolution <= 0.0:
            self.get_logger().warn('Coverage map resolution must be positive')
            return {
                'path': path,
                'debug_mask': None,
                'markers': empty_markers,
                'stats': stats,
            }

        stats.update(self._compute_coverage_counts(msg))
        base_planning_mask = self._build_planning_mask(msg)
        planning_mask, nav_stats = self._apply_nav_costmap_mask(
            base_planning_mask,
            msg,
        )
        travel_mask = self._build_travel_mask(msg)
        travel_mask = self._apply_nav_costmap_filter_to_travel_mask(
            travel_mask,
            msg,
        )
        planning_mask, reachability_stats = self._apply_reachability_mask(
            planning_mask,
            msg,
            travel_mask,
        )
        debug_mask = self._make_planning_mask_msg(msg, planning_mask)
        valid_cell_count = sum(1 for is_valid in planning_mask if is_valid)
        stats['valid_cells'] = valid_cell_count
        stats.update(nav_stats)
        stats.update(reachability_stats)
        self.connector_count = 0
        self.connector_pose_count = 0
        self.connector_failure_count = 0

        if valid_cell_count == 0:
            self.get_logger().warn(
                'No valid uncovered planning cells are available after inflation',
                throttle_duration_sec=5.0,
            )
            stats['valid'] = True
            return {
                'path': path,
                'debug_mask': debug_mask,
                'markers': empty_markers,
                'stats': stats,
            }

        components = self._find_connected_components(planning_mask, msg.info)
        stats['regions'] = len(components)
        if not components:
            self.get_logger().warn(
                'No valid uncovered regions remain after area filtering',
                throttle_duration_sec=5.0,
            )
            stats['valid'] = True
            return {
                'path': path,
                'debug_mask': debug_mask,
                'markers': empty_markers,
                'stats': stats,
            }

        region_paths = []
        all_segments = []
        directions = []
        robot_cell = self._get_robot_cell(msg.header.frame_id or 'map', msg.info)
        stats['robot_start_used'] = robot_cell is not None
        for component in components:
            region_plan = self._generate_region_plan(
                component,
                planning_mask,
                msg.info,
                robot_cell,
            )
            if len(region_plan['cells']) >= 2:
                region_paths.append(region_plan['cells'])
                all_segments.extend(region_plan['segments'])
                directions.append(region_plan['direction'])

        stats['segments'] = len(all_segments)
        stats['direction'] = self._summarize_directions(directions)

        if not region_paths:
            self.get_logger().warn(
                'Generated coverage path is empty',
                throttle_duration_sec=5.0,
            )
            stats['valid'] = True
            return {
                'path': path,
                'debug_mask': debug_mask,
                'markers': empty_markers,
                'stats': stats,
            }

        ordered_cells = self._order_region_paths(
            region_paths,
            travel_mask,
            msg.info,
            robot_cell,
        )
        self._fill_path_from_cells(path, ordered_cells, msg.info)
        stats['poses'] = len(path.poses)
        stats['length_m'] = self._estimate_path_length_m(path)
        continuity = self._path_continuity_report(path)
        stats.update(continuity)
        stats['segments_before_ordering'] = len(all_segments)
        stats['segments_after_ordering'] = len(all_segments)
        stats['connector_count'] = self.connector_count
        stats['connector_pose_count'] = self.connector_pose_count
        stats['connector_failure_count'] = self.connector_failure_count
        stats['follow_path_ready'] = (
            continuity['max_consecutive_jump_m']
            <= self.max_consecutive_pose_jump_m
            and self.connector_failure_count == 0
        )

        validation = self._validate_path(path, travel_mask, msg.info)
        stats.update(validation)
        if validation['outside_map_poses'] > 0 or validation['blocked_poses'] > 0:
            self.get_logger().warn(
                'Generated path failed validation: outside_map=%d, blocked=%d; '
                'publishing an empty path'
                % (
                    validation['outside_map_poses'],
                    validation['blocked_poses'],
                ),
                throttle_duration_sec=5.0,
            )
            path = self._make_empty_path()
            stats['poses'] = 0
            stats['length_m'] = 0.0
            stats['valid'] = False
        elif len(path.poses) == 0:
            self.get_logger().warn(
                'Generated coverage path is empty',
                throttle_duration_sec=5.0,
            )

        markers = self._make_segment_markers(all_segments, msg.info, path.header)
        if self.debug_path_continuity:
            self._log_path_continuity_report(stats, path)
        return {
            'path': path,
            'debug_mask': debug_mask,
            'markers': markers,
            'stats': stats,
        }

    def _should_freeze_plan(self, plan):
        if not self.freeze_path_after_first_valid_plan:
            return False

        stats = plan.get('stats', {})
        path = plan.get('path')
        if path is None or len(path.poses) == 0:
            return False

        if (
            self.wait_for_nav_costmap_before_planning
            and self._nav_costmap_enabled()
            and not stats.get('nav_costmap_used', False)
        ):
            return False

        if (
            self.wait_for_robot_pose_before_planning
            and self.start_near_robot_if_tf_available
            and not stats.get('robot_start_used', False)
        ):
            return False

        return (
            stats.get('valid', False)
            and stats.get('follow_path_ready', False)
            and stats.get('max_consecutive_jump_m', 0.0)
            <= self.max_consecutive_pose_jump_m
        )

    def _planning_inputs_ready(self):
        if (
            self.wait_for_nav_costmap_before_planning
            and self._nav_costmap_enabled()
        ):
            if self.nav_costmap is None:
                self.get_logger().info(
                    'Waiting for %s before generating frozen coverage path'
                    % self.nav_costmap_topic,
                    throttle_duration_sec=2.0,
                )
                return False
            if self._nav_costmap_is_stale():
                self.get_logger().info(
                    'Waiting for a fresh %s before generating frozen coverage path'
                    % self.nav_costmap_topic,
                    throttle_duration_sec=2.0,
                )
                return False

        if (
            self.wait_for_robot_pose_before_planning
            and self.start_near_robot_if_tf_available
        ):
            robot_cell = self._get_robot_cell(
                self.coverage_map.header.frame_id or 'map',
                self.coverage_map.info,
            )
            if robot_cell is None:
                self.get_logger().info(
                    'Waiting for robot pose before generating frozen coverage path',
                    throttle_duration_sec=2.0,
                )
                return False

        return True

    def _sanitize_startup_parameters(self):
        if self.path_publish_rate_hz <= 0.0:
            self.get_logger().warn(
                'path_publish_rate_hz must be positive; using 1.0 Hz'
            )
            self.path_publish_rate_hz = 1.0

        if self.min_segment_length_m < 0.0:
            self.get_logger().warn(
                'min_segment_length_m must not be negative; using 0.0 m'
            )
            self.min_segment_length_m = 0.0

        if self.inflation_radius_m < 0.0:
            self.get_logger().warn(
                'inflation_radius_m must not be negative; using 0.0 m'
            )
            self.inflation_radius_m = 0.0

        if self.robot_radius_m <= 0.0:
            self.get_logger().warn(
                'robot_radius_m must be positive; using real SweePi radius 0.20 m'
            )
            self.robot_radius_m = 0.20

        if self.coverage_safety_margin_m < 0.0:
            self.get_logger().warn(
                'coverage_safety_margin_m must not be negative; using 0.10 m'
            )
            self.coverage_safety_margin_m = 0.10

        if self.min_region_area_m2 < 0.0:
            self.get_logger().warn(
                'min_region_area_m2 must not be negative; using 0.0 m^2'
            )
            self.min_region_area_m2 = 0.0

        if self.connector_step_m <= 0.0:
            self.get_logger().warn(
                'connector_step_m must be positive; using 0.10 m'
            )
            self.connector_step_m = 0.10

        if self.max_consecutive_pose_jump_m <= 0.0:
            self.get_logger().warn(
                'max_consecutive_pose_jump_m must be positive; using 0.50 m'
            )
            self.max_consecutive_pose_jump_m = 0.50

        if self.tf_lookup_timeout_sec < 0.0:
            self.get_logger().warn(
                'tf_lookup_timeout_sec must not be negative; using 0.0 s'
            )
            self.tf_lookup_timeout_sec = 0.0

        if self.max_allowed_nav_cost < 0:
            self.get_logger().warn(
                'max_allowed_nav_cost must not be negative; using 0'
            )
            self.max_allowed_nav_cost = 0
        if self.max_allowed_nav_cost > 100:
            self.get_logger().warn(
                'max_allowed_nav_cost must not exceed 100; using 100'
            )
            self.max_allowed_nav_cost = 100

        if self.nav_costmap_timeout_sec < 0.0:
            self.get_logger().warn(
                'nav_costmap_timeout_sec must not be negative; using 0.0 s'
            )
            self.nav_costmap_timeout_sec = 0.0

        if self.cleanup_max_passes < 0:
            self.get_logger().warn(
                'cleanup_max_passes must not be negative; using 0'
            )
            self.cleanup_max_passes = 0

        if self.planning_direction not in ('horizontal', 'vertical', 'auto'):
            self.get_logger().warn(
                'Unsupported planning_direction "%s"; using "auto"'
                % self.planning_direction
            )
            self.planning_direction = 'auto'

    def _effective_spacing_m(self, resolution):
        if self.coverage_spacing_m <= 0.0:
            self.get_logger().warn(
                'coverage_spacing_m must be positive; using map resolution %.3f m'
                % resolution,
                throttle_duration_sec=5.0,
            )
            return resolution
        return self.coverage_spacing_m

    def _build_planning_mask(self, msg):
        """Return a bool mask of uncovered cells after obstacle inflation."""
        width = msg.info.width
        height = msg.info.height
        resolution = msg.info.resolution
        planning_mask = [
            cell_value == self.coverage_cell_value for cell_value in msg.data
        ]

        inflation_cells = meters_to_cell_radius(
            self.inflation_radius_m,
            resolution,
        )
        if inflation_cells == 0:
            return planning_mask

        inflation_offsets = []
        for dy in range(-inflation_cells, inflation_cells + 1):
            for dx in range(-inflation_cells, inflation_cells + 1):
                distance = math.hypot(dx * resolution, dy * resolution)
                if distance <= self.inflation_radius_m:
                    inflation_offsets.append((dx, dy))

        for y in range(height):
            for x in range(width):
                index = map_to_flat_index(x, y, width)
                if msg.data[index] not in (OBSTACLE, UNKNOWN):
                    continue

                for dx, dy in inflation_offsets:
                    inflated_x = x + dx
                    inflated_y = y + dy
                    if not in_bounds(inflated_x, inflated_y, width, height):
                        continue

                    inflated_index = map_to_flat_index(inflated_x, inflated_y, width)
                    planning_mask[inflated_index] = False

        return planning_mask

    def _apply_nav_costmap_mask(self, planning_mask, coverage_msg):
        stats = {
            'nav_costmap_used': False,
            'nav_costmap_blocked_cells': 0,
            'nav_costmap_unknown_cells': 0,
            'nav_costmap_filtered_cells': 0,
            'nav_costmap_stale': False,
            'nav_costmap_frame_mismatch': False,
        }

        if not self._nav_costmap_enabled():
            return planning_mask, stats

        if self.nav_costmap is None:
            self.get_logger().warn(
                'Nav costmap planning is enabled, but no %s message has arrived; '
                'using coverage-map-only planning for now'
                % self.nav_costmap_topic,
                throttle_duration_sec=5.0,
            )
            return planning_mask, stats

        if self._nav_costmap_is_stale():
            stats['nav_costmap_stale'] = True
            self.get_logger().warn(
                'Nav costmap is stale; using coverage-map-only planning for now',
                throttle_duration_sec=5.0,
            )
            return planning_mask, stats

        coverage_frame = coverage_msg.header.frame_id or 'map'
        costmap_frame = self.nav_costmap.header.frame_id or coverage_frame
        if costmap_frame != coverage_frame:
            stats['nav_costmap_frame_mismatch'] = True
            self.get_logger().warn(
                'Nav costmap frame "%s" does not match coverage frame "%s"; '
                'ignoring nav costmap for coverage planning'
                % (costmap_frame, coverage_frame),
                throttle_duration_sec=5.0,
            )
            return planning_mask, stats

        filtered_mask = list(planning_mask)
        width = coverage_msg.info.width
        height = coverage_msg.info.height
        for y in range(height):
            for x in range(width):
                coverage_index = map_to_flat_index(x, y, width)
                if not filtered_mask[coverage_index]:
                    continue

                world_x, world_y = map_to_world(x, y, coverage_msg.info)
                try:
                    costmap_x, costmap_y = world_to_map(
                        world_x,
                        world_y,
                        self.nav_costmap.info,
                    )
                except ValueError:
                    filtered_mask[coverage_index] = False
                    stats['nav_costmap_blocked_cells'] += 1
                    stats['nav_costmap_filtered_cells'] += 1
                    continue

                if not in_bounds(
                    costmap_x,
                    costmap_y,
                    self.nav_costmap.info.width,
                    self.nav_costmap.info.height,
                ):
                    filtered_mask[coverage_index] = False
                    stats['nav_costmap_blocked_cells'] += 1
                    stats['nav_costmap_filtered_cells'] += 1
                    continue

                costmap_index = map_to_flat_index(
                    costmap_x,
                    costmap_y,
                    self.nav_costmap.info.width,
                )
                cost = self.nav_costmap.data[costmap_index]
                if cost < 0:
                    stats['nav_costmap_unknown_cells'] += 1
                    if self.treat_unknown_cost_as_blocked:
                        filtered_mask[coverage_index] = False
                        stats['nav_costmap_filtered_cells'] += 1
                    continue
                if cost > self.max_allowed_nav_cost:
                    filtered_mask[coverage_index] = False
                    stats['nav_costmap_blocked_cells'] += 1
                    stats['nav_costmap_filtered_cells'] += 1

        stats['nav_costmap_used'] = True
        self.get_logger().info(
            'Nav costmap filtered %d coverage planning cells '
            '(blocked_by_cost=%d, unknown=%d, unknown_blocked=%s, '
            'max_allowed_nav_cost=%d)'
            % (
                stats['nav_costmap_filtered_cells'],
                stats['nav_costmap_blocked_cells'],
                stats['nav_costmap_unknown_cells'],
                str(self.treat_unknown_cost_as_blocked).lower(),
                self.max_allowed_nav_cost,
            ),
            throttle_duration_sec=2.0,
        )
        return filtered_mask, stats

    def _apply_reachability_mask(self, planning_mask, coverage_msg, travel_mask=None):
        stats = {
            'reachability_used': False,
            'reachable_cells': 0,
            'unreachable_filtered_cells': 0,
            'robot_reachability_start_available': False,
        }
        if not self.plan_only_reachable_from_robot:
            return planning_mask, stats

        frame_id = coverage_msg.header.frame_id or 'map'
        robot_cell = self._get_robot_cell(frame_id, coverage_msg.info)
        if robot_cell is None:
            self.get_logger().warn(
                'Reachability filtering is enabled, but robot pose is unavailable; '
                'keeping all currently safe planning cells',
                throttle_duration_sec=5.0,
            )
            return planning_mask, stats

        if travel_mask is None:
            travel_mask = self._build_travel_mask(coverage_msg)
            travel_mask = self._apply_nav_costmap_filter_to_travel_mask(
                travel_mask,
                coverage_msg,
            )
        start_cell = self._nearest_travel_cell(
            robot_cell,
            travel_mask,
            coverage_msg.info,
        )
        if start_cell is None:
            self.get_logger().warn(
                'Could not find a safe reachable start cell near the robot; '
                'keeping all currently safe planning cells',
                throttle_duration_sec=5.0,
            )
            return planning_mask, stats

        reachable_mask = self._flood_reachable_cells(
            start_cell,
            travel_mask,
            coverage_msg.info,
        )
        filtered_mask = list(planning_mask)
        unreachable_filtered = 0
        reachable_planning_cells = 0
        for index, is_valid in enumerate(planning_mask):
            if not is_valid:
                continue
            if reachable_mask[index]:
                reachable_planning_cells += 1
            else:
                filtered_mask[index] = False
                unreachable_filtered += 1

        stats['reachability_used'] = True
        stats['robot_reachability_start_available'] = True
        stats['reachable_cells'] = reachable_planning_cells
        stats['unreachable_filtered_cells'] = unreachable_filtered
        if unreachable_filtered > 0:
            self.get_logger().info(
                'Reachability filter removed %d uncovered cells that are not '
                'safely connected to the robot start'
                % unreachable_filtered,
                throttle_duration_sec=2.0,
            )
        return filtered_mask, stats

    def _build_travel_mask(self, coverage_msg):
        width = coverage_msg.info.width
        height = coverage_msg.info.height
        resolution = coverage_msg.info.resolution
        travel_mask = [
            cell_value not in (OBSTACLE, UNKNOWN)
            for cell_value in coverage_msg.data
        ]

        inflation_radius = max(
            self.inflation_radius_m,
            self.robot_radius_m + self.coverage_safety_margin_m,
        )
        inflation_cells = meters_to_cell_radius(inflation_radius, resolution)
        if inflation_cells == 0:
            return travel_mask

        inflation_offsets = []
        for dy in range(-inflation_cells, inflation_cells + 1):
            for dx in range(-inflation_cells, inflation_cells + 1):
                if math.hypot(dx * resolution, dy * resolution) <= inflation_radius:
                    inflation_offsets.append((dx, dy))

        for y in range(height):
            for x in range(width):
                index = map_to_flat_index(x, y, width)
                if coverage_msg.data[index] not in (OBSTACLE, UNKNOWN):
                    continue

                for dx, dy in inflation_offsets:
                    inflated_x = x + dx
                    inflated_y = y + dy
                    if not in_bounds(inflated_x, inflated_y, width, height):
                        continue
                    inflated_index = map_to_flat_index(inflated_x, inflated_y, width)
                    travel_mask[inflated_index] = False

        return travel_mask

    def _apply_nav_costmap_filter_to_travel_mask(self, travel_mask, coverage_msg):
        if not self._nav_costmap_enabled():
            return travel_mask
        if self.nav_costmap is None or self._nav_costmap_is_stale():
            return travel_mask

        coverage_frame = coverage_msg.header.frame_id or 'map'
        costmap_frame = self.nav_costmap.header.frame_id or coverage_frame
        if costmap_frame != coverage_frame:
            return travel_mask

        filtered_mask = list(travel_mask)
        width = coverage_msg.info.width
        height = coverage_msg.info.height
        for y in range(height):
            for x in range(width):
                coverage_index = map_to_flat_index(x, y, width)
                if not filtered_mask[coverage_index]:
                    continue

                world_x, world_y = map_to_world(x, y, coverage_msg.info)
                try:
                    costmap_x, costmap_y = world_to_map(
                        world_x,
                        world_y,
                        self.nav_costmap.info,
                    )
                except ValueError:
                    filtered_mask[coverage_index] = False
                    continue

                if not in_bounds(
                    costmap_x,
                    costmap_y,
                    self.nav_costmap.info.width,
                    self.nav_costmap.info.height,
                ):
                    filtered_mask[coverage_index] = False
                    continue

                costmap_index = map_to_flat_index(
                    costmap_x,
                    costmap_y,
                    self.nav_costmap.info.width,
                )
                cost = self.nav_costmap.data[costmap_index]
                if cost < 0:
                    if self.treat_unknown_cost_as_blocked:
                        filtered_mask[coverage_index] = False
                    continue
                if cost > self.max_allowed_nav_cost:
                    filtered_mask[coverage_index] = False

        return filtered_mask

    def _nearest_travel_cell(self, robot_cell, travel_mask, map_info):
        width = map_info.width
        height = map_info.height
        start_x, start_y = robot_cell
        if in_bounds(start_x, start_y, width, height):
            start_index = map_to_flat_index(start_x, start_y, width)
            if travel_mask[start_index]:
                return robot_cell

        max_radius = max(
            1,
            meters_to_cells(
                self.robot_radius_m + self.coverage_safety_margin_m,
                map_info.resolution,
            ),
        )
        best_cell = None
        best_distance = None
        for radius in range(1, max_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x = start_x + dx
                    y = start_y + dy
                    if not in_bounds(x, y, width, height):
                        continue
                    index = map_to_flat_index(x, y, width)
                    if not travel_mask[index]:
                        continue
                    distance = dx * dx + dy * dy
                    if best_distance is None or distance < best_distance:
                        best_distance = distance
                        best_cell = (x, y)
            if best_cell is not None:
                return best_cell
        return None

    def _flood_reachable_cells(self, start_cell, travel_mask, map_info):
        width = map_info.width
        height = map_info.height
        reachable = [False] * len(travel_mask)
        start_index = map_to_flat_index(start_cell[0], start_cell[1], width)
        if not travel_mask[start_index]:
            return reachable

        queue = deque([start_cell])
        reachable[start_index] = True
        while queue:
            cell_x, cell_y = queue.popleft()
            for neighbor_x, neighbor_y in self._neighbors_4(
                cell_x,
                cell_y,
                width,
                height,
            ):
                neighbor_index = map_to_flat_index(neighbor_x, neighbor_y, width)
                if reachable[neighbor_index] or not travel_mask[neighbor_index]:
                    continue
                reachable[neighbor_index] = True
                queue.append((neighbor_x, neighbor_y))
        return reachable

    def _nav_costmap_enabled(self):
        return self.use_nav_costmap_for_planning or self.use_global_costmap_for_planning

    def _nav_costmap_is_stale(self):
        if self.nav_costmap_timeout_sec <= 0.0:
            return False

        stamp = Time.from_msg(self.nav_costmap.header.stamp)
        if stamp.nanoseconds == 0:
            return False

        age_sec = (self.get_clock().now() - stamp).nanoseconds / 1.0e9
        return age_sec > self.nav_costmap_timeout_sec

    def _make_planning_mask_msg(self, source_msg, planning_mask):
        debug_msg = OccupancyGrid()
        debug_msg.header.frame_id = 'map'
        debug_msg.header.stamp = self.get_clock().now().to_msg()
        debug_msg.info = source_msg.info
        debug_msg.data = [100 if is_valid else 0 for is_valid in planning_mask]
        return debug_msg

    def _find_connected_components(self, planning_mask, map_info):
        """Find 4-connected valid-cell regions and drop tiny regions."""
        width = map_info.width
        height = map_info.height
        visited = [False] * len(planning_mask)
        components = []
        min_region_cells = max(
            1,
            int(math.ceil(self.min_region_area_m2 / (map_info.resolution ** 2))),
        )

        for y in range(height):
            for x in range(width):
                start_index = map_to_flat_index(x, y, width)
                if visited[start_index] or not planning_mask[start_index]:
                    continue

                component = []
                queue = deque([(x, y)])
                visited[start_index] = True

                while queue:
                    cell_x, cell_y = queue.popleft()
                    component.append((cell_x, cell_y))

                    for neighbor_x, neighbor_y in self._neighbors_4(
                        cell_x,
                        cell_y,
                        width,
                        height,
                    ):
                        neighbor_index = map_to_flat_index(
                            neighbor_x,
                            neighbor_y,
                            width,
                        )
                        if visited[neighbor_index] or not planning_mask[neighbor_index]:
                            continue

                        visited[neighbor_index] = True
                        queue.append((neighbor_x, neighbor_y))

                if len(component) >= min_region_cells:
                    components.append(component)

        return components

    def _generate_region_plan(self, component, planning_mask, map_info, robot_cell):
        direction, segments = self._select_region_segments(component, map_info)
        if not segments:
            return {
                'direction': direction,
                'segments': [],
                'cells': [],
            }

        ordered_cells = self._order_segments_nearest_neighbor(
            segments,
            planning_mask,
            map_info,
            robot_cell,
        )
        return {
            'direction': direction,
            'segments': segments,
            'cells': ordered_cells,
        }

    def _select_region_segments(self, component, map_info):
        if self.planning_direction in ('horizontal', 'vertical'):
            segments = self._generate_segments_for_region(
                component,
                map_info,
                self.planning_direction,
            )
            return self.planning_direction, segments

        horizontal_segments = self._generate_segments_for_region(
            component,
            map_info,
            'horizontal',
        )
        vertical_segments = self._generate_segments_for_region(
            component,
            map_info,
            'vertical',
        )

        if not vertical_segments:
            return 'horizontal', horizontal_segments
        if not horizontal_segments:
            return 'vertical', vertical_segments

        horizontal_cost = self._estimate_segment_order_cost(
            horizontal_segments,
            map_info.resolution,
        )
        vertical_cost = self._estimate_segment_order_cost(
            vertical_segments,
            map_info.resolution,
        )
        if vertical_cost < horizontal_cost:
            return 'vertical', vertical_segments
        return 'horizontal', horizontal_segments

    def _generate_segments_for_region(self, component, map_info, direction):
        component_cells = set(component)
        min_x = min(cell[0] for cell in component)
        max_x = max(cell[0] for cell in component)
        min_y = min(cell[1] for cell in component)
        max_y = max(cell[1] for cell in component)
        sweep_step_cells = meters_to_cells(
            self._effective_spacing_m(map_info.resolution),
            map_info.resolution,
        )
        min_segment_cells = max(
            1,
            int(math.ceil(self.min_segment_length_m / map_info.resolution)),
        )

        if direction == 'vertical':
            return self._generate_vertical_segments(
                component_cells,
                min_x,
                max_x,
                min_y,
                max_y,
                sweep_step_cells,
                min_segment_cells,
            )

        return self._generate_horizontal_segments(
            component_cells,
            min_x,
            max_x,
            min_y,
            max_y,
            sweep_step_cells,
            min_segment_cells,
        )

    def _generate_horizontal_segments(
        self,
        component_cells,
        min_x,
        max_x,
        min_y,
        max_y,
        sweep_step_cells,
        min_segment_cells,
    ):
        segments = []
        left_to_right = True

        for y in range(min_y, max_y + 1, sweep_step_cells):
            row_segments = self._find_axis_segments(
                component_cells,
                fixed_value=y,
                variable_min=min_x,
                variable_max=max_x,
                min_segment_cells=min_segment_cells,
                horizontal=True,
            )
            if not row_segments:
                continue

            if left_to_right:
                segments.extend(row_segments)
            else:
                segments.extend(
                    ((end, start) for start, end in reversed(row_segments))
                )
            left_to_right = not left_to_right

        return segments

    def _generate_vertical_segments(
        self,
        component_cells,
        min_x,
        max_x,
        min_y,
        max_y,
        sweep_step_cells,
        min_segment_cells,
    ):
        segments = []
        bottom_to_top = True

        for x in range(min_x, max_x + 1, sweep_step_cells):
            column_segments = self._find_axis_segments(
                component_cells,
                fixed_value=x,
                variable_min=min_y,
                variable_max=max_y,
                min_segment_cells=min_segment_cells,
                horizontal=False,
            )
            if not column_segments:
                continue

            if bottom_to_top:
                segments.extend(column_segments)
            else:
                segments.extend(
                    ((end, start) for start, end in reversed(column_segments))
                )
            bottom_to_top = not bottom_to_top

        return segments

    def _find_axis_segments(
        self,
        component_cells,
        fixed_value,
        variable_min,
        variable_max,
        min_segment_cells,
        horizontal,
    ):
        segments = []
        segment_start = None

        for variable_value in range(variable_min, variable_max + 1):
            cell = (
                (variable_value, fixed_value)
                if horizontal
                else (fixed_value, variable_value)
            )
            is_valid = cell in component_cells

            if is_valid and segment_start is None:
                segment_start = variable_value
            elif not is_valid and segment_start is not None:
                self._append_axis_segment_if_long_enough(
                    segments,
                    fixed_value,
                    segment_start,
                    variable_value - 1,
                    min_segment_cells,
                    horizontal,
                )
                segment_start = None

        if segment_start is not None:
            self._append_axis_segment_if_long_enough(
                segments,
                fixed_value,
                segment_start,
                variable_max,
                min_segment_cells,
                horizontal,
            )

        return segments

    def _append_axis_segment_if_long_enough(
        self,
        segments,
        fixed_value,
        start_value,
        end_value,
        min_segment_cells,
        horizontal,
    ):
        if end_value - start_value + 1 < min_segment_cells:
            return

        if horizontal:
            segments.append(((start_value, fixed_value), (end_value, fixed_value)))
        else:
            segments.append(((fixed_value, start_value), (fixed_value, end_value)))

    def _order_segments_nearest_neighbor(
        self,
        segments,
        planning_mask,
        map_info,
        robot_cell=None,
    ):
        remaining_segments = list(segments)
        ordered_cells = []
        current_cell = None

        while remaining_segments:
            if current_cell is None:
                start_index, reverse_start = self._select_initial_segment(
                    remaining_segments,
                    robot_cell,
                )
                start, end = remaining_segments.pop(start_index)
                if reverse_start:
                    start, end = end, start
            else:
                best_index, best_reverse = self._select_next_segment(
                    remaining_segments,
                    current_cell,
                )
                start, end = remaining_segments.pop(best_index)
                if best_reverse:
                    start, end = end, start

            if (
                not self.connect_disjoint_segments
                and current_cell is not None
                and current_cell != start
            ):
                connector = self._find_grid_path(
                    current_cell,
                    start,
                    planning_mask,
                    map_info.width,
                    map_info.height,
                )
                if connector:
                    self._extend_cells_without_duplicates(ordered_cells, connector[1:])
                else:
                    self._append_cell_without_duplicate(ordered_cells, start)
            else:
                self._connect_or_append_cell(
                    ordered_cells,
                    start,
                    planning_mask,
                    map_info,
                    'segment',
                )

            segment_cells = self._cells_along_axis_segment(start, end)
            self._extend_cells_without_duplicates(ordered_cells, segment_cells)
            current_cell = end

        return ordered_cells

    def _order_region_paths(self, region_paths, connector_mask, map_info, robot_cell=None):
        remaining_paths = [list(region_path) for region_path in region_paths]
        ordered_cells = []
        current_cell = None
        selection_cell = robot_cell

        if robot_cell is not None:
            start_cell = self._nearest_travel_cell(
                robot_cell,
                connector_mask,
                map_info,
            )
            if start_cell is not None:
                self._append_cell_without_duplicate(ordered_cells, start_cell)
                current_cell = start_cell
                selection_cell = start_cell

        while remaining_paths:
            if current_cell is None:
                path_index, reverse_start = self._select_initial_path(
                    remaining_paths,
                    selection_cell,
                )
                path = remaining_paths.pop(path_index)
                if reverse_start:
                    path = list(reversed(path))
            else:
                best_index, best_reverse = self._select_next_path(
                    remaining_paths,
                    current_cell,
                )
                path = remaining_paths.pop(best_index)
                if best_reverse:
                    path = list(reversed(path))

            if ordered_cells and path:
                self._connect_or_append_cell(
                    ordered_cells,
                    path[0],
                    connector_mask,
                    map_info,
                    'region',
                )
            self._extend_cells_without_duplicates(ordered_cells, path)
            current_cell = ordered_cells[-1]

        return ordered_cells

    def _select_initial_segment(self, segments, robot_cell=None):
        if (
            self.start_near_robot_if_tf_available
            and robot_cell is not None
            and self.optimize_segment_order
        ):
            return self._select_segment_closest_to_cell(segments, robot_cell)
        return 0, False

    def _select_next_segment(self, segments, current_cell):
        if not self.optimize_segment_order:
            return 0, False
        return self._select_segment_closest_to_cell(segments, current_cell)

    def _select_segment_closest_to_cell(self, segments, target_cell):
        best_index = 0
        best_reverse = False
        best_distance = None

        for index, (candidate_start, candidate_end) in enumerate(segments):
            start_distance = self._cell_distance_squared(target_cell, candidate_start)
            end_distance = self._cell_distance_squared(target_cell, candidate_end)

            if best_distance is None or start_distance < best_distance:
                best_index = index
                best_reverse = False
                best_distance = start_distance
            if self.allow_segment_reversal and end_distance < best_distance:
                best_index = index
                best_reverse = True
                best_distance = end_distance

        return best_index, best_reverse

    def _select_initial_path(self, paths, robot_cell=None):
        if (
            self.start_near_robot_if_tf_available
            and robot_cell is not None
            and self.optimize_segment_order
        ):
            return self._select_path_closest_to_cell(paths, robot_cell)
        return 0, False

    def _select_next_path(self, paths, current_cell):
        if not self.optimize_segment_order:
            return 0, False
        return self._select_path_closest_to_cell(paths, current_cell)

    def _select_path_closest_to_cell(self, paths, target_cell):
        best_index = 0
        best_reverse = False
        best_distance = None

        for index, candidate_path in enumerate(paths):
            start_distance = self._cell_distance_squared(target_cell, candidate_path[0])
            end_distance = self._cell_distance_squared(target_cell, candidate_path[-1])

            if best_distance is None or start_distance < best_distance:
                best_index = index
                best_reverse = False
                best_distance = start_distance
            if self.allow_segment_reversal and end_distance < best_distance:
                best_index = index
                best_reverse = True
                best_distance = end_distance

        return best_index, best_reverse

    def _cells_along_axis_segment(self, start, end):
        dx = self._sign(end[0] - start[0])
        dy = self._sign(end[1] - start[1])
        cells = [start]
        current = start

        while current != end:
            current = (current[0] + dx, current[1] + dy)
            cells.append(current)

        return cells

    def _connect_or_append_cell(
        self,
        ordered_cells,
        target_cell,
        planning_mask,
        map_info,
        connector_label,
    ):
        if not ordered_cells:
            self._append_cell_without_duplicate(ordered_cells, target_cell)
            return

        current_cell = ordered_cells[-1]
        if current_cell == target_cell:
            return

        distance_m = self._cell_distance(current_cell, target_cell) * map_info.resolution
        if distance_m <= self.max_consecutive_pose_jump_m:
            self._append_cell_without_duplicate(ordered_cells, target_cell)
            return

        connector = self._make_connector_cells(
            current_cell,
            target_cell,
            planning_mask,
            map_info,
            connector_label,
        )
        if connector:
            self.connector_count += 1
            self.connector_pose_count += max(0, len(connector) - 1)
            self._extend_cells_without_duplicates(ordered_cells, connector[1:])
            return

        self.connector_failure_count += 1
        self.get_logger().warn(
            'No valid %s connector from %s to %s; publishing remaining '
            'discontinuity distance=%.2fm'
            % (connector_label, current_cell, target_cell, distance_m),
            throttle_duration_sec=5.0,
        )
        self._append_cell_without_duplicate(ordered_cells, target_cell)

    def _make_connector_cells(
        self,
        start,
        goal,
        planning_mask,
        map_info,
        connector_label,
    ):
        if self.connector_allow_simple_straight_line:
            straight_connector = self._make_straight_connector_cells(
                start,
                goal,
                map_info,
            )
            blocked_cell = self._first_blocked_connector_cell(
                straight_connector,
                planning_mask,
                map_info,
            )
            if not self.connector_check_obstacles or blocked_cell is None:
                if blocked_cell is not None:
                    self.get_logger().warn(
                        'Using unchecked %s straight connector through blocked '
                        'cell %s because connector_check_obstacles=false'
                        % (connector_label, blocked_cell),
                        throttle_duration_sec=5.0,
                    )
                return straight_connector

            self.get_logger().warn(
                '%s straight connector from %s to %s is blocked at cell %s; '
                'trying grid connector'
                % (connector_label, start, goal, blocked_cell),
                throttle_duration_sec=5.0,
            )

        grid_connector = self._find_grid_path(
            start,
            goal,
            planning_mask,
            map_info.width,
            map_info.height,
        )
        if grid_connector:
            return grid_connector

        return []

    def _make_straight_connector_cells(self, start, goal, map_info):
        start_x, start_y = map_to_world(start[0], start[1], map_info)
        goal_x, goal_y = map_to_world(goal[0], goal[1], map_info)
        distance = math.hypot(goal_x - start_x, goal_y - start_y)
        steps = max(1, int(math.ceil(distance / self.connector_step_m)))
        cells = []

        for step in range(steps + 1):
            ratio = step / steps
            world_x = start_x + ratio * (goal_x - start_x)
            world_y = start_y + ratio * (goal_y - start_y)
            try:
                cell = world_to_map(world_x, world_y, map_info)
            except ValueError:
                continue
            self._append_cell_without_duplicate(cells, cell)

        if not cells or cells[0] != start:
            cells.insert(0, start)
        if cells[-1] != goal:
            cells.append(goal)
        return cells

    def _first_blocked_connector_cell(self, connector, planning_mask, map_info):
        for cell in connector:
            if not in_bounds(cell[0], cell[1], map_info.width, map_info.height):
                return cell
            index = map_to_flat_index(cell[0], cell[1], map_info.width)
            if not planning_mask[index]:
                return cell
        return None

    def _estimate_segment_order_cost(self, segments, resolution):
        remaining_segments = list(segments)
        current_cell = None
        estimated_cells = 0.0
        turn_penalty_cells = max(1.0, self._effective_spacing_m(resolution) / resolution)
        previous_direction = None

        while remaining_segments:
            if current_cell is None:
                start, end = remaining_segments.pop(0)
            else:
                best_index = 0
                best_reverse = False
                best_distance = None

                for index, (candidate_start, candidate_end) in enumerate(
                    remaining_segments
                ):
                    start_distance = self._cell_distance(current_cell, candidate_start)
                    end_distance = self._cell_distance(current_cell, candidate_end)

                    if best_distance is None or start_distance < best_distance:
                        best_index = index
                        best_reverse = False
                        best_distance = start_distance
                    if self.allow_segment_reversal and end_distance < best_distance:
                        best_index = index
                        best_reverse = True
                        best_distance = end_distance

                estimated_cells += best_distance
                start, end = remaining_segments.pop(best_index)
                if best_reverse:
                    start, end = end, start

            segment_direction = self._segment_axis_direction(start, end)
            if (
                previous_direction is not None
                and segment_direction != previous_direction
            ):
                estimated_cells += turn_penalty_cells

            estimated_cells += self._cell_distance(start, end)
            previous_direction = segment_direction
            current_cell = end

        return estimated_cells * resolution

    def _find_grid_path(self, start, goal, planning_mask, width, height):
        if start == goal:
            return [start]

        start_index = map_to_flat_index(start[0], start[1], width)
        goal_index = map_to_flat_index(goal[0], goal[1], width)
        if not planning_mask[start_index] or not planning_mask[goal_index]:
            return []

        frontier = []
        heapq.heappush(frontier, (0.0, start))
        came_from = {start: None}
        cost_so_far = {start: 0.0}

        while frontier:
            _priority, current = heapq.heappop(frontier)
            if current == goal:
                break

            for neighbor in self._neighbors_4(current[0], current[1], width, height):
                neighbor_index = map_to_flat_index(neighbor[0], neighbor[1], width)
                if not planning_mask[neighbor_index]:
                    continue

                new_cost = cost_so_far[current] + 1.0
                if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                    continue

                cost_so_far[neighbor] = new_cost
                priority = new_cost + self._manhattan_distance(neighbor, goal)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

        if goal not in came_from:
            return []

        path = []
        current = goal
        while current is not None:
            path.append(current)
            current = came_from[current]

        return list(reversed(path))

    def _validate_path(self, path, planning_mask, map_info):
        outside_map_poses = 0
        blocked_poses = 0

        for pose in path.poses:
            try:
                map_x, map_y = world_to_map(
                    pose.pose.position.x,
                    pose.pose.position.y,
                    map_info,
                )
            except ValueError:
                outside_map_poses += 1
                continue

            if not in_bounds(map_x, map_y, map_info.width, map_info.height):
                outside_map_poses += 1
                continue

            index = map_to_flat_index(map_x, map_y, map_info.width)
            if not planning_mask[index]:
                blocked_poses += 1

        if outside_map_poses:
            self.get_logger().warn(
                '%d generated path poses are outside map bounds' % outside_map_poses,
                throttle_duration_sec=5.0,
            )
        if blocked_poses:
            self.get_logger().warn(
                '%d generated path poses fall on blocked travel-mask cells'
                % blocked_poses,
                throttle_duration_sec=5.0,
            )

        return {
            'outside_map_poses': outside_map_poses,
            'blocked_poses': blocked_poses,
            'valid': outside_map_poses == 0 and blocked_poses == 0,
        }

    def _get_robot_cell(self, frame_id, map_info):
        if not self.start_near_robot_if_tf_available:
            return None

        try:
            transform = self.tf_buffer.lookup_transform(
                frame_id or 'map',
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=self.tf_lookup_timeout_sec),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not use robot pose for coverage path start ordering: %s'
                % exc,
                throttle_duration_sec=5.0,
            )
            return None

        robot_x = transform.transform.translation.x
        robot_y = transform.transform.translation.y

        try:
            cell = world_to_map(robot_x, robot_y, map_info)
        except ValueError as exc:
            self.get_logger().warn(
                'Robot pose is outside map for coverage path start ordering: %s'
                % exc,
                throttle_duration_sec=5.0,
            )
            return None

        if not in_bounds(cell[0], cell[1], map_info.width, map_info.height):
            return None
        return cell

    def _fill_path_from_cells(self, path, cells, map_info):
        for index, cell in enumerate(cells):
            if index + 1 < len(cells):
                yaw = self._yaw_between_cells(cell, cells[index + 1])
            elif index > 0:
                yaw = self._yaw_between_cells(cells[index - 1], cell)
            else:
                yaw = 0.0

            self._append_pose(path, map_info, cell[0], cell[1], yaw)

    def _append_pose(self, path, map_info, map_x, map_y, yaw):
        world_x, world_y = map_to_world(map_x, map_y, map_info)

        pose = PoseStamped()
        pose.header = path.header
        pose.pose.position.x = world_x
        pose.pose.position.y = world_y
        pose.pose.position.z = 0.0
        pose.pose.orientation = self._quaternion_from_yaw(yaw)
        path.poses.append(pose)

    def _make_segment_markers(self, segments, map_info, header):
        markers = self._make_delete_markers()
        if not self.publish_debug_markers:
            return markers

        marker = Marker()
        marker.header = header
        marker.ns = 'coverage_segment_endpoints'
        marker.id = 0
        marker.type = Marker.SPHERE_LIST
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x = max(0.04, map_info.resolution * 1.5)
        marker.scale.y = marker.scale.x
        marker.scale.z = marker.scale.x
        marker.color.r = 0.1
        marker.color.g = 0.7
        marker.color.b = 1.0
        marker.color.a = 0.9

        for start, end in segments:
            for cell in (start, end):
                world_x, world_y = map_to_world(cell[0], cell[1], map_info)
                point = Point()
                point.x = world_x
                point.y = world_y
                point.z = 0.04
                marker.points.append(point)

        markers.markers.append(marker)
        return markers

    def _make_delete_markers(self):
        marker = Marker()
        marker.header.frame_id = 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'coverage_marker_cleanup'
        marker.id = 0
        marker.action = Marker.DELETEALL
        markers = MarkerArray()
        markers.markers.append(marker)
        return markers

    def _make_empty_path(self):
        path = Path()
        path.header.frame_id = 'map'
        path.header.stamp = self.get_clock().now().to_msg()
        return path

    def _make_empty_stats(self):
        return {
            'direction': 'none',
            'regions': 0,
            'segments': 0,
            'segments_before_ordering': 0,
            'segments_after_ordering': 0,
            'connector_count': 0,
            'connector_pose_count': 0,
            'connector_failure_count': 0,
            'poses': 0,
            'length_m': 0.0,
            'max_consecutive_jump_m': 0.0,
            'max_jump_index': -1,
            'follow_path_ready': True,
            'nav_costmap_used': False,
            'nav_costmap_blocked_cells': 0,
            'nav_costmap_unknown_cells': 0,
            'nav_costmap_filtered_cells': 0,
            'nav_costmap_stale': False,
            'nav_costmap_frame_mismatch': False,
            'reachability_used': False,
            'reachable_cells': 0,
            'unreachable_filtered_cells': 0,
            'robot_reachability_start_available': False,
            'robot_start_used': False,
            'valid_cells': 0,
            'coverable': 0,
            'covered': 0,
            'uncovered': 0,
            'percentage': 0.0,
            'outside_map_poses': 0,
            'blocked_poses': 0,
            'valid': True,
        }

    def _log_plan_summary(self, stats):
        self.get_logger().info(
            'Coverage plan: direction=%s, regions=%d, segments=%d, poses=%d, '
            'length=%.2fm, valid_cells=%d'
            % (
                stats['direction'],
                stats['regions'],
                stats['segments'],
                stats['poses'],
                stats['length_m'],
                stats['valid_cells'],
            )
        )

    def _log_path_continuity_report(self, stats, path):
        first_pose = 'unavailable'
        last_pose = 'unavailable'
        if path.poses:
            first_pose = self._format_pose_for_log(path.poses[0].pose)
            last_pose = self._format_pose_for_log(path.poses[-1].pose)

        self.get_logger().info(
            'Coverage path continuity report: '
            'segments_before_ordering=%d segments_after_ordering=%d '
            'connector_count=%d connector_pose_count=%d total_poses=%d '
            'path_length_m=%.2f max_consecutive_jump_m=%.3f max_jump_index=%d '
            'first_pose=%s last_pose=%s follow_path_ready=%s robot_start_used=%s '
            'nav_costmap_used=%s nav_blocked_cells=%d nav_filtered_cells=%d '
            'reachability_used=%s reachable_cells=%d unreachable_filtered_cells=%d'
            % (
                stats['segments_before_ordering'],
                stats['segments_after_ordering'],
                stats['connector_count'],
                stats['connector_pose_count'],
                stats['poses'],
                stats['length_m'],
                stats['max_consecutive_jump_m'],
                stats['max_jump_index'],
                first_pose,
                last_pose,
                str(stats['follow_path_ready']).lower(),
                str(stats.get('robot_start_used', False)).lower(),
                str(stats.get('nav_costmap_used', False)).lower(),
                stats.get('nav_costmap_blocked_cells', 0),
                stats.get('nav_costmap_filtered_cells', 0),
                str(stats.get('reachability_used', False)).lower(),
                stats.get('reachable_cells', 0),
                stats.get('unreachable_filtered_cells', 0),
            )
        )

        if stats['max_consecutive_jump_m'] > self.max_consecutive_pose_jump_m:
            self.get_logger().warn(
                'Published /coverage_path is not continuous enough for FollowPath.'
            )

    def _log_replan_summary(self, stats):
        self.get_logger().info(
            'Coverage replan: percentage=%.1f%%, uncovered=%d, segments=%d, '
            'poses=%d, path_length=%.2fm, unreachable_filtered=%d'
            % (
                stats['percentage'],
                stats['uncovered'],
                stats['segments'],
                stats['poses'],
                stats['length_m'],
                stats.get('unreachable_filtered_cells', 0),
            )
        )

    def _format_coverage_stats(self, stats):
        return (
            'covered=%d uncovered=%d total=%d percentage=%.1f '
            'path_length_m=%.2f segments=%d poses=%d max_jump_m=%.3f '
            'follow_path_ready=%s robot_start_used=%s nav_costmap_used=%s '
            'nav_blocked_cells=%d nav_filtered_cells=%d reachability_used=%s '
            'reachable_cells=%d unreachable_filtered_cells=%d cleanup_pass=%d'
            % (
                stats['covered'],
                stats['uncovered'],
                stats['coverable'],
                stats['percentage'],
                stats['length_m'],
                stats['segments'],
                stats['poses'],
                stats.get('max_consecutive_jump_m', 0.0),
                str(stats.get('follow_path_ready', True)).lower(),
                str(stats.get('robot_start_used', False)).lower(),
                str(stats.get('nav_costmap_used', False)).lower(),
                stats.get('nav_costmap_blocked_cells', 0),
                stats.get('nav_costmap_filtered_cells', 0),
                str(stats.get('reachability_used', False)).lower(),
                stats.get('reachable_cells', 0),
                stats.get('unreachable_filtered_cells', 0),
                self.cleanup_pass_count,
            )
        )

    def _compute_coverage_counts(self, msg):
        covered_cells = 0
        uncovered_cells = 0

        for cell_value in msg.data:
            if cell_value == COVERED:
                covered_cells += 1
            elif cell_value == self.coverage_cell_value:
                uncovered_cells += 1

        coverable_cells = covered_cells + uncovered_cells
        percentage = 0.0
        if coverable_cells > 0:
            percentage = (covered_cells / coverable_cells) * 100.0

        return {
            'coverable': coverable_cells,
            'covered': covered_cells,
            'uncovered': uncovered_cells,
            'percentage': percentage,
        }

    def _coverage_map_checksum(self, msg):
        return self._occupancy_grid_checksum(msg)

    def _occupancy_grid_checksum(self, msg):
        origin = msg.info.origin
        return hash((
            msg.header.frame_id,
            msg.info.width,
            msg.info.height,
            msg.info.resolution,
            origin.position.x,
            origin.position.y,
            origin.position.z,
            origin.orientation.x,
            origin.orientation.y,
            origin.orientation.z,
            origin.orientation.w,
            tuple(msg.data),
        ))

    def _estimate_path_length_m(self, path):
        if len(path.poses) < 2:
            return 0.0

        length = 0.0
        previous = path.poses[0].pose.position
        for pose in path.poses[1:]:
            current = pose.pose.position
            length += math.hypot(current.x - previous.x, current.y - previous.y)
            previous = current
        return length

    def _path_continuity_report(self, path):
        max_jump = 0.0
        max_jump_index = -1

        for index in range(1, len(path.poses)):
            previous = path.poses[index - 1].pose.position
            current = path.poses[index].pose.position
            jump = math.hypot(current.x - previous.x, current.y - previous.y)
            if jump > max_jump:
                max_jump = jump
                max_jump_index = index - 1

        return {
            'max_consecutive_jump_m': max_jump,
            'max_jump_index': max_jump_index,
        }

    def _format_pose_for_log(self, pose):
        return 'x=%.3f y=%.3f yaw=%.2f' % (
            pose.position.x,
            pose.position.y,
            self._yaw_from_quaternion(pose.orientation),
        )

    def _summarize_directions(self, directions):
        if not directions:
            return 'none'
        unique_directions = sorted(set(directions))
        if len(unique_directions) == 1:
            return unique_directions[0]
        return 'mixed'

    def _neighbors_4(self, x, y, width, height):
        for neighbor_x, neighbor_y in (
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        ):
            if in_bounds(neighbor_x, neighbor_y, width, height):
                yield neighbor_x, neighbor_y

    def _extend_cells_without_duplicates(self, cells, new_cells):
        for cell in new_cells:
            self._append_cell_without_duplicate(cells, cell)

    def _append_cell_without_duplicate(self, cells, cell):
        if not cells or cells[-1] != cell:
            cells.append(cell)

    def _segment_axis_direction(self, start, end):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if abs(dx) >= abs(dy):
            return 'horizontal'
        return 'vertical'

    def _yaw_between_cells(self, start, end):
        return math.atan2(end[1] - start[1], end[0] - start[0])

    def _cell_distance_squared(self, first, second):
        dx = first[0] - second[0]
        dy = first[1] - second[1]
        return dx * dx + dy * dy

    def _cell_distance(self, first, second):
        return math.sqrt(self._cell_distance_squared(first, second))

    def _manhattan_distance(self, first, second):
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

    def _sign(self, value):
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

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


def main(args=None):
    rclpy.init(args=args)
    node = CoveragePlannerNode()

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

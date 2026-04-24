#!/usr/bin/env python3
"""Coverage path planner node for Step 3 of the SweePi coverage system."""

from collections import deque
import heapq
import math

import rclpy
from geometry_msgs.msg import Point, PoseStamped
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32, String
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

        self.coverage_map_topic = (
            self.get_parameter('coverage_map_topic').get_parameter_value().string_value
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

        self._sanitize_startup_parameters()

        self.coverage_map = None
        self.coverage_map_checksum = None
        self.plan_dirty = False
        self.latest_path = Path()
        self.latest_debug_mask = None
        self.latest_markers = MarkerArray()
        self.latest_percentage_msg = Float32()
        self.latest_stats_msg = String()
        self.latest_plan_stats = self._make_empty_stats()

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

        self.coverage_map_sub = self.create_subscription(
            OccupancyGrid,
            self.coverage_map_topic,
            self.coverage_map_callback,
            map_qos,
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

        publish_period = 1.0 / self.path_publish_rate_hz
        self.timer = self.create_timer(publish_period, self.publish_outputs)

        self.get_logger().info(
            'Coverage planner started: coverage_map=%s, path=%s, mask=%s, '
            'percentage=%s, stats=%s, direction=%s'
            % (
                self.coverage_map_topic,
                self.coverage_path_topic,
                self.planning_mask_topic,
                self.coverage_percentage_topic,
                self.coverage_stats_topic,
                self.planning_direction,
            )
        )

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
        if map_changed or not self.replan_on_map_change:
            self.coverage_map_checksum = new_checksum
            self.plan_dirty = True

    def publish_outputs(self):
        """Replan when needed, then publish visualization and stats outputs."""
        if self.coverage_map is None:
            return

        if self.plan_dirty:
            plan = self.generate_plan(self.coverage_map)
            self.latest_path = plan['path']
            self.latest_debug_mask = plan['debug_mask']
            self.latest_markers = plan['markers']
            self.latest_plan_stats = plan['stats']
            self.latest_percentage_msg.data = float(plan['stats']['percentage'])
            self.latest_stats_msg.data = self._format_coverage_stats(plan['stats'])
            self.plan_dirty = False
            self._log_replan_summary(plan['stats'])
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
        planning_mask = self._build_planning_mask(msg)
        debug_mask = self._make_planning_mask_msg(msg, planning_mask)
        valid_cell_count = sum(1 for is_valid in planning_mask if is_valid)
        stats['valid_cells'] = valid_cell_count

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
        for component in components:
            region_plan = self._generate_region_plan(
                component,
                planning_mask,
                msg.info,
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

        ordered_cells = self._order_region_paths(region_paths)
        self._fill_path_from_cells(path, ordered_cells, msg.info)
        stats['poses'] = len(path.poses)
        stats['length_m'] = self._estimate_path_length_m(path)

        validation = self._validate_path(path, planning_mask, msg.info)
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
        return {
            'path': path,
            'debug_mask': debug_mask,
            'markers': markers,
            'stats': stats,
        }

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

        if self.min_region_area_m2 < 0.0:
            self.get_logger().warn(
                'min_region_area_m2 must not be negative; using 0.0 m^2'
            )
            self.min_region_area_m2 = 0.0

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

    def _generate_region_plan(self, component, planning_mask, map_info):
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

    def _order_segments_nearest_neighbor(self, segments, planning_mask, map_info):
        remaining_segments = list(segments)
        ordered_cells = []
        current_cell = None

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
                    start_distance = self._cell_distance_squared(
                        current_cell,
                        candidate_start,
                    )
                    end_distance = self._cell_distance_squared(
                        current_cell,
                        candidate_end,
                    )

                    if best_distance is None or start_distance < best_distance:
                        best_index = index
                        best_reverse = False
                        best_distance = start_distance
                    if end_distance < best_distance:
                        best_index = index
                        best_reverse = True
                        best_distance = end_distance

                start, end = remaining_segments.pop(best_index)
                if best_reverse:
                    start, end = end, start

            if current_cell is not None and current_cell != start:
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
                self._append_cell_without_duplicate(ordered_cells, start)

            self._append_cell_without_duplicate(ordered_cells, end)
            current_cell = end

        return ordered_cells

    def _order_region_paths(self, region_paths):
        remaining_paths = [list(region_path) for region_path in region_paths]
        ordered_cells = []
        current_cell = None

        while remaining_paths:
            if current_cell is None:
                path = remaining_paths.pop(0)
            else:
                best_index = 0
                best_reverse = False
                best_distance = None

                for index, candidate_path in enumerate(remaining_paths):
                    start_distance = self._cell_distance_squared(
                        current_cell,
                        candidate_path[0],
                    )
                    end_distance = self._cell_distance_squared(
                        current_cell,
                        candidate_path[-1],
                    )

                    if best_distance is None or start_distance < best_distance:
                        best_index = index
                        best_reverse = False
                        best_distance = start_distance
                    if end_distance < best_distance:
                        best_index = index
                        best_reverse = True
                        best_distance = end_distance

                path = remaining_paths.pop(best_index)
                if best_reverse:
                    path = list(reversed(path))

            self._extend_cells_without_duplicates(ordered_cells, path)
            current_cell = ordered_cells[-1]

        return ordered_cells

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
                    if end_distance < best_distance:
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
                '%d generated path poses fall on blocked planning-mask cells'
                % blocked_poses,
                throttle_duration_sec=5.0,
            )

        return {
            'outside_map_poses': outside_map_poses,
            'blocked_poses': blocked_poses,
            'valid': outside_map_poses == 0 and blocked_poses == 0,
        }

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
            'poses': 0,
            'length_m': 0.0,
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

    def _log_replan_summary(self, stats):
        self.get_logger().info(
            'Coverage replan: percentage=%.1f%%, uncovered=%d, segments=%d, '
            'poses=%d, path_length=%.2fm'
            % (
                stats['percentage'],
                stats['uncovered'],
                stats['segments'],
                stats['poses'],
                stats['length_m'],
            )
        )

    def _format_coverage_stats(self, stats):
        return (
            'covered=%d uncovered=%d total=%d percentage=%.1f '
            'path_length_m=%.2f segments=%d poses=%d'
            % (
                stats['covered'],
                stats['uncovered'],
                stats['coverable'],
                stats['percentage'],
                stats['length_m'],
                stats['segments'],
                stats['poses'],
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
        origin = msg.info.origin
        return hash((
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

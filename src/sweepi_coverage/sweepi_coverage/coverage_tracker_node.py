#!/usr/bin/env python3
"""Coverage tracker node for Step 2 of the SweePi coverage system."""

import copy
import math

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener

from sweepi_coverage.coverage_utils import (
    in_bounds,
    map_to_flat_index,
    meters_to_cell_radius,
    world_to_map,
)


OBSTACLE = 0
UNCOVERED = 50
COVERED = 100
UNKNOWN = -1


class CoverageTrackerNode(Node):
    """Track which free map cells have been covered by the robot footprint."""

    def __init__(self):
        super().__init__('coverage_tracker_node')

        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('robot_base_frame', 'base_link')
        self.declare_parameter('robot_radius_m', 0.18)
        self.declare_parameter('occupied_threshold', 50)
        self.declare_parameter('coverage_update_rate_hz', 2.0)
        self.declare_parameter('coverage_topic', '/coverage_map')

        self.global_frame = (
            self.get_parameter('global_frame').get_parameter_value().string_value
        )
        self.robot_base_frame = (
            self.get_parameter('robot_base_frame').get_parameter_value().string_value
        )
        self.robot_radius_m = (
            self.get_parameter('robot_radius_m').get_parameter_value().double_value
        )
        self.occupied_threshold = (
            self.get_parameter('occupied_threshold').get_parameter_value().integer_value
        )
        self.coverage_update_rate_hz = (
            self.get_parameter('coverage_update_rate_hz')
            .get_parameter_value()
            .double_value
        )
        self.coverage_topic = (
            self.get_parameter('coverage_topic').get_parameter_value().string_value
        )

        self.map_info = None
        self.coverage_frame = self.global_frame
        self.coverage_data = None
        self.coverage_msg = None

        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        self.map_sub = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            map_qos,
        )
        self.coverage_pub = self.create_publisher(
            OccupancyGrid,
            self.coverage_topic,
            map_qos,
        )

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        update_period = 1.0 / max(self.coverage_update_rate_hz, 0.1)
        self.timer = self.create_timer(update_period, self.update_coverage)

        self.get_logger().info(
            'Coverage tracker started: map=/map, coverage=%s, TF=%s -> %s'
            % (self.coverage_topic, self.global_frame, self.robot_base_frame)
        )

    def map_callback(self, msg):
        """Initialize or refresh coverage data from the source occupancy map."""
        expected_cells = msg.info.width * msg.info.height
        if len(msg.data) != expected_cells:
            self.get_logger().warn(
                'Ignoring /map with %d cells, expected %d'
                % (len(msg.data), expected_cells),
                throttle_duration_sec=5.0,
            )
            return

        if self.coverage_data is None or self._map_metadata_changed(msg):
            self._initialize_coverage_map(msg)
            self.publish_coverage_map()
            return

        self._refresh_static_cells(msg)

    def update_coverage(self):
        """Lookup the robot pose and mark the covered footprint area."""
        if self.coverage_data is None or self.map_info is None:
            return

        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=0.1),
            )
        except TransformException as exc:
            self.get_logger().warn(
                'Could not get TF %s -> %s: %s'
                % (self.global_frame, self.robot_base_frame, exc),
                throttle_duration_sec=5.0,
            )
            return

        robot_x = transform.transform.translation.x
        robot_y = transform.transform.translation.y

        try:
            map_x, map_y = world_to_map(robot_x, robot_y, self.map_info)
        except ValueError as exc:
            self.get_logger().warn(str(exc), throttle_duration_sec=5.0)
            return

        if not in_bounds(map_x, map_y, self.map_info.width, self.map_info.height):
            self.get_logger().warn(
                'Robot pose is outside the map: (%.3f, %.3f)' % (robot_x, robot_y),
                throttle_duration_sec=5.0,
            )
            return

        if self._mark_robot_footprint(map_x, map_y):
            self.publish_coverage_map()

    def publish_coverage_map(self):
        """Publish the latest coverage grid."""
        if self.coverage_msg is None or self.coverage_data is None:
            return

        self.coverage_msg.header.stamp = self.get_clock().now().to_msg()
        self.coverage_msg.header.frame_id = self.coverage_frame
        self.coverage_msg.data = list(self.coverage_data)
        self.coverage_pub.publish(self.coverage_msg)

    def _initialize_coverage_map(self, msg):
        self.map_info = copy.deepcopy(msg.info)
        self.coverage_frame = msg.header.frame_id or self.global_frame
        self.coverage_data = [
            self._coverage_value_from_map_cell(cell_value) for cell_value in msg.data
        ]

        self.coverage_msg = OccupancyGrid()
        self.coverage_msg.header.frame_id = self.coverage_frame
        self.coverage_msg.info = copy.deepcopy(msg.info)

        if self.coverage_frame != self.global_frame:
            self.get_logger().warn(
                'Map frame "%s" differs from global_frame "%s"; coverage assumes '
                'both frames use the same coordinates.'
                % (self.coverage_frame, self.global_frame),
                throttle_duration_sec=10.0,
            )

        self.get_logger().info(
            'Initialized coverage map: %dx%d at %.3f m/cell'
            % (msg.info.width, msg.info.height, msg.info.resolution)
        )

    def _refresh_static_cells(self, msg):
        changed = False
        for index, cell_value in enumerate(msg.data):
            static_value = self._coverage_value_from_map_cell(cell_value)

            if static_value in (OBSTACLE, UNKNOWN):
                if self.coverage_data[index] != static_value:
                    self.coverage_data[index] = static_value
                    changed = True
            elif self.coverage_data[index] in (OBSTACLE, UNKNOWN):
                self.coverage_data[index] = UNCOVERED
                changed = True

        if changed:
            self.publish_coverage_map()

    def _map_metadata_changed(self, msg):
        return (
            self.map_info is None
            or msg.info.width != self.map_info.width
            or msg.info.height != self.map_info.height
            or msg.info.resolution != self.map_info.resolution
            or msg.info.origin != self.map_info.origin
        )

    def _coverage_value_from_map_cell(self, cell_value):
        if cell_value == UNKNOWN:
            return UNKNOWN
        if cell_value > self.occupied_threshold:
            return OBSTACLE
        return UNCOVERED

    def _mark_robot_footprint(self, center_x, center_y):
        width = self.map_info.width
        height = self.map_info.height
        resolution = self.map_info.resolution
        cell_radius = meters_to_cell_radius(self.robot_radius_m, resolution)
        changed = False

        for dy in range(-cell_radius, cell_radius + 1):
            for dx in range(-cell_radius, cell_radius + 1):
                if math.hypot(dx * resolution, dy * resolution) > self.robot_radius_m:
                    continue

                map_x = center_x + dx
                map_y = center_y + dy
                if not in_bounds(map_x, map_y, width, height):
                    continue

                index = map_to_flat_index(map_x, map_y, width)
                if self.coverage_data[index] == UNCOVERED:
                    self.coverage_data[index] = COVERED
                    changed = True

        return changed


def main(args=None):
    rclpy.init(args=args)
    node = CoverageTrackerNode()

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

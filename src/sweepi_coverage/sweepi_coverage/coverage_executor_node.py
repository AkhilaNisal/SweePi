#!/usr/bin/env python3
"""Waypoint generator for Step 5 of the SweePi coverage system."""

import copy
import math

import rclpy
from geometry_msgs.msg import Point
from nav_msgs.msg import Path
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
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
        self.declare_parameter('waypoint_spacing_m', 0.75)
        self.declare_parameter('min_turn_angle_deg', 45.0)
        self.declare_parameter('min_waypoint_separation_m', 0.20)
        self.declare_parameter('max_waypoints', 300)
        self.declare_parameter('publish_waypoint_markers', True)
        self.declare_parameter('waypoint_publish_rate_hz', 1.0)
        self.declare_parameter('enable_nav2_execution', False)

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

        self._sanitize_parameters()

        if self.enable_nav2_execution:
            self.get_logger().warn(
                'enable_nav2_execution is true, but Step 5 does not implement Nav2 '
                'execution. No goals will be sent.'
            )

        self.latest_input_path = None
        self.latest_path_checksum = None
        self.waypoints_dirty = False
        self.latest_waypoints = self._make_empty_path('map')
        self.latest_markers = self._make_delete_markers('map')
        self.latest_stats_msg = String()
        self.latest_stats_msg.data = 'input_poses=0 waypoints=0 input_empty=true'

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

        publish_period = 1.0 / self.waypoint_publish_rate_hz
        self.timer = self.create_timer(publish_period, self.publish_outputs)

        self.get_logger().info(
            'Coverage waypoint generator started: path=%s, waypoints=%s, '
            'markers=%s, stats=%s'
            % (
                self.coverage_path_topic,
                self.coverage_waypoints_topic,
                self.coverage_waypoint_markers_topic,
                self.coverage_waypoint_stats_topic,
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

    def publish_outputs(self):
        """Regenerate dirty waypoints and republish the latest debug outputs."""
        if self.waypoints_dirty and self.latest_input_path is not None:
            result = self.generate_waypoints(self.latest_input_path)
            self.latest_waypoints = result['waypoints']
            self.latest_markers = result['markers']
            self.latest_stats_msg.data = result['stats_text']
            self.waypoints_dirty = False
            self.get_logger().info('Coverage waypoints: %s' % result['stats_text'])

        stamp = self.get_clock().now().to_msg()
        self.latest_waypoints.header.stamp = stamp
        self.coverage_waypoints_pub.publish(self.latest_waypoints)

        if self.publish_waypoint_markers:
            for marker in self.latest_markers.markers:
                marker.header.stamp = stamp
            self.coverage_waypoint_markers_pub.publish(self.latest_markers)

        self.coverage_waypoint_stats_pub.publish(self.latest_stats_msg)

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

        if len(kept_poses) > self.max_waypoints:
            self.get_logger().warn(
                'Waypoint count %d exceeds max_waypoints=%d; downsampling'
                % (len(kept_poses), self.max_waypoints),
                throttle_duration_sec=5.0,
            )
            kept_poses = self._downsample_waypoints(kept_poses, self.max_waypoints)
            kept_poses = self._ensure_first_and_last(
                kept_poses,
                path_msg.poses[0],
                path_msg.poses[-1],
            )

        kept_poses = self._remove_close_waypoints(
            kept_poses,
            preserve_last=True,
        )
        kept_poses = self._ensure_first_and_last(
            kept_poses,
            path_msg.poses[0],
            path_msg.poses[-1],
        )

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

        self._validate_waypoints(waypoints, path_msg)

        stats = {
            'input_poses': input_pose_count,
            'waypoints': len(waypoints.poses),
            'distance_kept': keep_counts['distance'],
            'turns_kept': keep_counts['turn'],
            'input_path_length_m': self._path_length(path_msg.poses),
            'waypoint_path_length_m': self._path_length(waypoints.poses),
            'input_empty': False,
        }
        markers = self._make_waypoint_markers(waypoints)

        return {
            'waypoints': waypoints,
            'markers': markers,
            'stats_text': self._format_stats(stats),
        }

    def _select_waypoint_poses(self, poses):
        kept_poses = [copy.deepcopy(poses[0])]
        keep_counts = {
            'distance': 0,
            'turn': 0,
        }

        last_kept_pose = poses[0]
        for index in range(1, len(poses) - 1):
            previous_pose = poses[index - 1]
            current_pose = poses[index]
            next_pose = poses[index + 1]

            distance_from_last = self._pose_distance(last_kept_pose, current_pose)
            turn_angle = self._turn_angle_deg(previous_pose, current_pose, next_pose)
            keep_for_distance = distance_from_last >= self.waypoint_spacing_m
            keep_for_turn = turn_angle >= self.min_turn_angle_deg

            if keep_for_distance or keep_for_turn:
                kept_poses.append(copy.deepcopy(current_pose))
                last_kept_pose = current_pose
                if keep_for_distance:
                    keep_counts['distance'] += 1
                if keep_for_turn:
                    keep_counts['turn'] += 1

        if len(poses) > 1:
            kept_poses.append(copy.deepcopy(poses[-1]))

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
                'path_length_m=0.00 waypoint_path_length_m=0.00'
                % self.waypoint_spacing_m
            )

        return (
            'input_poses=%d waypoints=%d spacing=%.2fm turns_kept=%d '
            'distance_kept=%d path_length_m=%.2f waypoint_path_length_m=%.2f'
            % (
                stats['input_poses'],
                stats['waypoints'],
                self.waypoint_spacing_m,
                stats['turns_kept'],
                stats['distance_kept'],
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

        if self.max_waypoints < 1:
            self.get_logger().warn('max_waypoints must be at least 1; using 1')
            self.max_waypoints = 1

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

    def _path_length(self, poses):
        if len(poses) < 2:
            return 0.0

        length = 0.0
        previous_pose = poses[0]
        for pose in poses[1:]:
            length += self._pose_distance(previous_pose, pose)
            previous_pose = pose
        return length

    def _pose_distance(self, first, second):
        dx = first.pose.position.x - second.pose.position.x
        dy = first.pose.position.y - second.pose.position.y
        return math.hypot(dx, dy)

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

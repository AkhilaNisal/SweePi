#!/usr/bin/env python3
"""
SweePi Exploration Manager
===========================
Autonomous frontier-based exploration using Nav2 for path planning and
obstacle avoidance. Subscribes to the /map topic published by sweepi_slam
and sends NavigateToPose goals to Nav2.

Architecture
------------
  sweepi_slam  -->  /map  -->  ExplorationManager  -->  Nav2 NavigateToPose
                                    |                         |
                              frontier detection        collision-free path
                              + reachability check      + obstacle avoidance
"""

import math
from datetime import datetime

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point, PoseStamped
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray


class ExplorationManager(Node):
    """Frontier-based exploration using Nav2 for navigation."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self):
        super().__init__('exploration_manager')

        # ---------- Parameters ----------
        self.declare_parameter('frontier_min_size', 5)          # cells
        self.declare_parameter('cluster_distance', 0.5)         # metres
        self.declare_parameter('goal_tolerance', 0.3)           # metres
        self.declare_parameter('exploration_frequency', 3.0)    # seconds
        self.declare_parameter('nav_timeout', 30.0)             # seconds
        self.declare_parameter('use_sim_time', True)

        self.frontier_min_size = self.get_parameter('frontier_min_size').value
        self.cluster_distance = self.get_parameter('cluster_distance').value
        self.goal_tolerance = self.get_parameter('goal_tolerance').value
        self.exploration_frequency = self.get_parameter('exploration_frequency').value
        self.nav_timeout = self.get_parameter('nav_timeout').value

        # ---------- State ----------
        self.map_data = None
        self.map_info = None
        self.failed_frontiers: list = []          # frontiers that nav2 failed on
        self.nav_goal_handle = None               # active Nav2 goal handle
        self.navigating = False
        self.exploration_active = False
        self.goals_attempted = 0
        self.goals_reached = 0
        self.start_time = None
        self.no_frontier_count = 0

        # ---------- Subscribers ----------
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self._map_callback, 10)

        # ---------- Publishers ----------
        self.frontier_marker_pub = self.create_publisher(
            MarkerArray, '/exploration/frontiers', 10)
        self.goal_marker_pub = self.create_publisher(
            Marker, '/exploration/goal', 10)

        # ---------- Nav2 action clients ----------
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.path_client = ActionClient(self, ComputePathToPose, 'compute_path_to_pose')

        # ---------- Timer ----------
        self.explore_timer = self.create_timer(
            self.exploration_frequency, self._explore_callback)

        self.get_logger().info('🤖 SweePi Exploration Manager started')
        self.get_logger().info(
            f'   frontier_min_size={self.frontier_min_size} cells, '
            f'cluster_distance={self.cluster_distance} m, '
            f'nav_timeout={self.nav_timeout} s')
        self.get_logger().info('   Waiting for /map and Nav2...')

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------

    def _map_callback(self, msg: OccupancyGrid):
        self.map_data = np.array(msg.data, dtype=np.int8).reshape(
            (msg.info.height, msg.info.width))
        self.map_info = msg.info

    # ------------------------------------------------------------------
    # Main exploration loop
    # ------------------------------------------------------------------

    def _explore_callback(self):
        if self.map_data is None or self.map_info is None:
            self.get_logger().info('Waiting for map...', throttle_duration_sec=5.0)
            return

        if self.navigating:
            return  # Wait until the current goal finishes

        if not self.nav_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warn(
                'Nav2 navigate_to_pose action server not available. '
                'Is Nav2 running?', throttle_duration_sec=10.0)
            return

        frontiers = self._detect_frontiers()
        self._publish_frontier_markers(frontiers)

        # Filter out previously failed frontiers (within 0.5 m)
        frontiers = self._filter_failed(frontiers)

        if not frontiers:
            self.no_frontier_count += 1
            self.get_logger().info(
                f'No reachable frontiers found (count={self.no_frontier_count})')
            if self.no_frontier_count >= 3 and self.exploration_active:
                self._finish_exploration()
            return

        self.no_frontier_count = 0
        if not self.exploration_active:
            self.exploration_active = True
            self.start_time = datetime.now()
            self.get_logger().info('🚀 Autonomous exploration started')

        goal_pose = self._select_frontier(frontiers)
        if goal_pose is not None:
            self._publish_goal_marker(goal_pose)
            self._send_nav_goal(goal_pose)

    # ------------------------------------------------------------------
    # Frontier detection
    # ------------------------------------------------------------------

    def _detect_frontiers(self) -> list:
        """Return list of (world_x, world_y) frontier cluster centroids."""
        grid = self.map_data
        info = self.map_info
        height, width = grid.shape

        # A frontier cell is a free cell (0) adjacent to an unknown cell (-1)
        free = (grid == 0)
        unknown = (grid == -1)

        frontier_cells = []
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if not free[y, x]:
                    continue
                neighbours = unknown[y-1:y+2, x-1:x+2]
                if neighbours.any():
                    world_x = info.origin.position.x + (x + 0.5) * info.resolution
                    world_y = info.origin.position.y + (y + 0.5) * info.resolution
                    frontier_cells.append((world_x, world_y))

        clusters = self._cluster_frontiers(frontier_cells)

        # Return centroids of clusters that meet minimum size requirement
        centroids = []
        for cluster in clusters:
            if len(cluster) >= self.frontier_min_size:
                cx = sum(p[0] for p in cluster) / len(cluster)
                cy = sum(p[1] for p in cluster) / len(cluster)
                centroids.append((cx, cy))

        self.get_logger().info(
            f'Frontiers: {len(frontier_cells)} cells → '
            f'{len(clusters)} clusters → {len(centroids)} valid',
            throttle_duration_sec=5.0)
        return centroids

    def _cluster_frontiers(self, points: list, distance: float = None) -> list:
        """Simple greedy clustering of frontier cells."""
        if distance is None:
            distance = self.cluster_distance
        if not points:
            return []

        used = [False] * len(points)
        clusters = []

        for i, pt in enumerate(points):
            if used[i]:
                continue
            cluster = [pt]
            used[i] = True
            for j, other in enumerate(points):
                if used[j]:
                    continue
                if math.hypot(pt[0] - other[0], pt[1] - other[1]) < distance:
                    cluster.append(other)
                    used[j] = True
            clusters.append(cluster)

        return clusters

    # ------------------------------------------------------------------
    # Frontier selection with reachability check
    # ------------------------------------------------------------------

    def _filter_failed(self, frontiers: list) -> list:
        """Remove frontiers too close to previously failed goals."""
        result = []
        for fx, fy in frontiers:
            failed = any(
                math.hypot(fx - ex, fy - ey) < self.cluster_distance
                for ex, ey in self.failed_frontiers
            )
            if not failed:
                result.append((fx, fy))
        return result

    def _select_frontier(self, frontiers: list):
        """Select the closest reachable frontier."""
        if not frontiers:
            return None

        # Sort by distance from map center (approximation for robot position since
        # we don't subscribe to /odom to keep the node lightweight)
        info = self.map_info
        origin_x = info.origin.position.x + (info.width / 2.0) * info.resolution
        origin_y = info.origin.position.y + (info.height / 2.0) * info.resolution

        sorted_frontiers = sorted(
            frontiers,
            key=lambda f: math.hypot(f[0] - origin_x, f[1] - origin_y)
        )

        # Check reachability using Nav2 ComputePathToPose (synchronous spin)
        for fx, fy in sorted_frontiers:
            if self._is_reachable(fx, fy):
                self.get_logger().info(f'🎯 Selected frontier: ({fx:.2f}, {fy:.2f})')
                return (fx, fy)
            else:
                self.get_logger().info(
                    f'⛔ Frontier ({fx:.2f}, {fy:.2f}) is not reachable, skipping')
                self.failed_frontiers.append((fx, fy))

        return None

    def _is_reachable(self, x: float, y: float) -> bool:
        """Use Nav2 ComputePathToPose to verify reachability."""
        if not self.path_client.wait_for_server(timeout_sec=2.0):
            # If path planner not available, assume reachable
            return True

        goal_msg = ComputePathToPose.Goal()
        goal_msg.goal = self._make_pose_stamped(x, y)
        goal_msg.planner_id = ''
        goal_msg.use_start = False

        future = self.path_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            return False

        goal_handle = future.result()
        if not goal_handle.accepted:
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=10.0)

        if not result_future.done():
            return False

        result = result_future.result()
        return result.status == GoalStatus.STATUS_SUCCEEDED

    # ------------------------------------------------------------------
    # Nav2 goal sending
    # ------------------------------------------------------------------

    def _send_nav_goal(self, frontier):
        fx, fy = frontier
        self.get_logger().info(f'📍 Sending Nav2 goal: ({fx:.2f}, {fy:.2f})')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(fx, fy)
        goal_msg.behavior_tree = ''

        self.navigating = True
        self.goals_attempted += 1

        send_future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._nav_feedback_callback)
        send_future.add_done_callback(
            lambda f: self._nav_goal_response_callback(f, (fx, fy)))

    def _nav_goal_response_callback(self, future, frontier):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Nav2 rejected the goal')
            self.failed_frontiers.append(frontier)
            self.navigating = False
            return

        self.nav_goal_handle = goal_handle
        self.get_logger().info('Nav2 accepted goal – navigating...')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda f: self._nav_result_callback(f, frontier))

    def _nav_feedback_callback(self, feedback_msg):
        dist = feedback_msg.feedback.distance_remaining
        self.get_logger().info(
            f'   distance remaining: {dist:.2f} m',
            throttle_duration_sec=5.0)

    def _nav_result_callback(self, future, frontier):
        result = future.result()
        status = result.status

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.goals_reached += 1
            self.get_logger().info(
                f'✅ Reached frontier ({frontier[0]:.2f}, {frontier[1]:.2f}) | '
                f'reached={self.goals_reached}/{self.goals_attempted}')
        else:
            self.get_logger().warn(
                f'⚠️  Navigation to ({frontier[0]:.2f}, {frontier[1]:.2f}) '
                f'failed (status={status}) – marking as failed')
            self.failed_frontiers.append(frontier)

        self.nav_goal_handle = None
        self.navigating = False

    # ------------------------------------------------------------------
    # Exploration complete
    # ------------------------------------------------------------------

    def _finish_exploration(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.get_logger().info('✅ ========== EXPLORATION COMPLETE ==========')
        self.get_logger().info(f'   ⏱️  Time:  {elapsed:.1f} s')
        self.get_logger().info(
            f'   🏁 Goals: {self.goals_reached} reached / '
            f'{self.goals_attempted} attempted')
        self.get_logger().info('============================================')
        self.exploration_active = False
        self.explore_timer.cancel()
        self._save_map()

    def _save_map(self):
        """Save map via nav2_map_server map_saver_cli."""
        import os
        import subprocess
        self.get_logger().info('💾 Saving map...')
        try:
            from ament_index_python.packages import get_package_share_directory
            pkg_dir = get_package_share_directory('sweepi_exploration')
            import os
            maps_dir = os.path.join(pkg_dir, 'maps')
            os.makedirs(maps_dir, exist_ok=True)
            map_path = os.path.join(maps_dir, 'sweepi_map')
            cmd = f'ros2 run nav2_map_server map_saver_cli -f {map_path}'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self.get_logger().info(f'✅ Map saved to {map_path}')
            else:
                self.get_logger().warn(f'Map save failed: {result.stderr}')
        except Exception as e:
            self.get_logger().error(f'Error saving map: {e}')

    # ------------------------------------------------------------------
    # Visualisation helpers
    # ------------------------------------------------------------------

    def _publish_frontier_markers(self, frontiers: list):
        marker_array = MarkerArray()
        for i, (fx, fy) in enumerate(frontiers):
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = self.get_clock().now().to_msg()
            m.ns = 'frontiers'
            m.id = i
            m.type = Marker.CYLINDER
            m.action = Marker.ADD
            m.pose.position.x = fx
            m.pose.position.y = fy
            m.pose.position.z = 0.1
            m.pose.orientation.w = 1.0
            m.scale.x = 0.2
            m.scale.y = 0.2
            m.scale.z = 0.3
            m.color.r = 1.0
            m.color.g = 0.5
            m.color.b = 0.0
            m.color.a = 0.8
            m.lifetime = Duration(seconds=5).to_msg()
            marker_array.markers.append(m)

        # Delete stale markers
        if not frontiers:
            delete_m = Marker()
            delete_m.header.frame_id = 'map'
            delete_m.action = Marker.DELETEALL
            marker_array.markers.append(delete_m)

        self.frontier_marker_pub.publish(marker_array)

    def _publish_goal_marker(self, goal):
        fx, fy = goal
        m = Marker()
        m.header.frame_id = 'map'
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = 'goal'
        m.id = 0
        m.type = Marker.ARROW
        m.action = Marker.ADD
        m.pose.position.x = fx
        m.pose.position.y = fy
        m.pose.position.z = 0.3
        m.pose.orientation.w = 1.0
        m.scale.x = 0.4
        m.scale.y = 0.08
        m.scale.z = 0.08
        m.color.r = 0.0
        m.color.g = 1.0
        m.color.b = 0.0
        m.color.a = 0.9
        m.lifetime = Duration(seconds=10).to_msg()
        self.goal_marker_pub.publish(m)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _make_pose_stamped(self, x: float, y: float) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.w = 1.0  # Face forward (yaw = 0)
        return pose


# ---------------------------------------------------------------------------

def main(args=None):
    rclpy.init(args=args)
    node = ExplorationManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Exploration interrupted by user')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
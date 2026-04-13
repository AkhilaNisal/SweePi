#!/usr/bin/env python3
"""
Wavefront-Based Frontier Explorer for SweePi (FINAL FIX)
=========================================================
"""

import math
from collections import deque
from datetime import datetime

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray


class WavefrontExplorer(Node):
    """Wavefront-based autonomous frontier explorer."""

    def __init__(self):
        super().__init__('wavefront_explorer')

        # Parameters
        self.declare_parameter('exploration_frequency', 3.0)
        self.declare_parameter('frontier_min_size', 15)
        self.declare_parameter('cluster_distance', 1.5)
        self.declare_parameter('nav_timeout', 30.0)

        self.exploration_frequency = self.get_parameter('exploration_frequency').value
        self.frontier_min_size = self.get_parameter('frontier_min_size').value
        self.cluster_distance = self.get_parameter('cluster_distance').value
        self.nav_timeout = self.get_parameter('nav_timeout').value

        # State
        self.map_data = None
        self.map_info = None
        self.navigating = False
        self.exploration_active = False
        self.failed_frontiers = []
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.no_frontier_count = 0

        # Subscribers
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.map_callback, 10)

        # Publishers
        self.frontier_pub = self.create_publisher(
            MarkerArray, '/exploration/frontiers', 10)
        self.goal_pub = self.create_publisher(
            Marker, '/exploration/goal', 10)

        # Action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Timer
        self.timer = self.create_timer(self.exploration_frequency, self.explore)

        self.get_logger().info('🤖 Wavefront Explorer READY')
        self.get_logger().info(f'   frontier_min_size={self.frontier_min_size}')
        self.get_logger().info(f'   cluster_distance={self.cluster_distance}')

    def map_callback(self, msg):
        """Receive occupancy grid map."""
        self.map_data = np.array(msg.data, dtype=np.int8).reshape(
            (msg.info.height, msg.info.width))
        self.map_info = msg.info

    def wavefront_frontier_detection(self):
        """Detect frontiers using wavefront algorithm."""
        if self.map_data is None:
            return []

        height, width = self.map_data.shape
        visited = np.zeros((height, width), dtype=bool)
        frontier_cells = []

        queue = deque()

        # Initialize with all free cells
        for y in range(height):
            for x in range(width):
                if self.map_data[y, x] == 0:
                    queue.append((x, y))
                    visited[y, x] = True

        # BFS to find frontiers
        while queue:
            x, y = queue.popleft()

            for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
                nx, ny = x + dx, y + dy

                if 0 <= nx < width and 0 <= ny < height:
                    cell = self.map_data[ny, nx]

                    if cell == -1:
                        frontier_cells.append((x, y))
                    elif cell == 0 and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))

        frontiers = self._cluster_frontiers(frontier_cells)
        self.get_logger().info(
            f'📊 Frontiers: {len(frontier_cells)} cells → {len(frontiers)} clusters',
            throttle_duration_sec=5.0)
        return frontiers

    def _cluster_frontiers(self, cells):
        """Cluster frontier cells."""
        if not cells:
            return []

        clusters = []
        used = set()

        for i, cell in enumerate(cells):
            if i in used:
                continue

            cluster = [cell]
            used.add(i)

            for j, other in enumerate(cells):
                if j not in used:
                    dist = math.sqrt((cell[0] - other[0])**2 + (cell[1] - other[1])**2)
                    if dist < self.cluster_distance:
                        cluster.append(other)
                        used.add(j)

            if len(cluster) >= self.frontier_min_size:
                cx = sum(c[0] for c in cluster) / len(cluster)
                cy = sum(c[1] for c in cluster) / len(cluster)

                world_x = self.map_info.origin.position.x + (cx + 0.5) * self.map_info.resolution
                world_y = self.map_info.origin.position.y + (cy + 0.5) * self.map_info.resolution

                clusters.append((world_x, world_y))

        return clusters

    def select_best_frontier(self, frontiers):
        """Select closest frontier."""
        if not frontiers:
            return None

        map_center_x = self.map_info.origin.position.x + (self.map_info.width / 2.0) * self.map_info.resolution
        map_center_y = self.map_info.origin.position.y + (self.map_info.height / 2.0) * self.map_info.resolution

        best = min(frontiers, key=lambda f: math.hypot(f[0] - map_center_x, f[1] - map_center_y))
        self.get_logger().info(f'🎯 Selected: ({best[0]:.2f}, {best[1]:.2f})')
        return best

    def explore(self):
        """Main exploration loop."""
        if self.map_data is None:
            self.get_logger().info('⏳ Waiting for map...', throttle_duration_sec=5.0)
            return

        if self.navigating:
            return

        if not self.nav_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().info('⏳ Waiting for Nav2...', throttle_duration_sec=10.0)
            return

        frontiers = self.wavefront_frontier_detection()
        self._publish_frontier_markers(frontiers)

        if not frontiers:
            self.no_frontier_count += 1
            if self.no_frontier_count >= 3 and self.exploration_active:
                self._finish_exploration()
            return

        self.no_frontier_count = 0

        if not self.exploration_active:
            self.exploration_active = True
            self.start_time = datetime.now()
            self.get_logger().info('🚀 Exploration started!')

        goal = self.select_best_frontier(frontiers)
        if goal:
            self._send_nav_goal(goal)

    def _send_nav_goal(self, goal):
        """Send navigation goal to Nav2."""
        x, y = goal
        self.get_logger().info(f'📍 Goal: ({x:.2f}, {y:.2f})')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(x, y)
        goal_msg.behavior_tree = ''

        self.navigating = True
        self.goals_attempted += 1

        send_future = self.nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(self._goal_response)

    def _goal_response(self, future):
        """Handle goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().warn('❌ Goal rejected')
                self.navigating = False
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._goal_result)
        except Exception as e:
            self.get_logger().error(f'Goal error: {e}')
            self.navigating = False

    def _goal_result(self, future):
        """Handle goal result."""
        try:
            result = future.result()
            if result.status == GoalStatus.STATUS_SUCCEEDED:
                self.goals_reached += 1
                self.get_logger().info(f'✅ Goal reached! ({self.goals_reached}/{self.goals_attempted})')
            else:
                self.get_logger().warn(f'⚠️  Goal failed (status={result.status})')
        except Exception as e:
            self.get_logger().error(f'Result error: {e}')
        finally:
            self.navigating = False

    def _finish_exploration(self):
        """Complete exploration."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.get_logger().info('✅ EXPLORATION COMPLETE')
        self.get_logger().info(f'   Time: {elapsed:.1f}s | Goals: {self.goals_reached}/{self.goals_attempted}')
        self.exploration_active = False

    def _publish_frontier_markers(self, frontiers):
        """Visualize frontiers."""
        marker_array = MarkerArray()
        for i, (x, y) in enumerate(frontiers):
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = self.get_clock().now().to_msg()
            m.id = i
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.1
            m.scale.x = 0.3
            m.scale.y = 0.3
            m.scale.z = 0.3
            m.color.b = 1.0
            m.color.a = 0.8
            marker_array.markers.append(m)
        self.frontier_pub.publish(marker_array)

    def _make_pose_stamped(self, x, y):
        """Create PoseStamped with CORRECT current timestamp."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        # CRITICAL: Use current ROS time, not wall clock time
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.w = 1.0
        return pose


def main(args=None):
    rclpy.init(args=args)
    node = WavefrontExplorer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Stopped')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()


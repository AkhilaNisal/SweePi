#!/usr/bin/env python3
"""
Wavefront-Based Frontier Explorer for SweePi
FIXED: Detects and skips stuck-in-loop frontiers
"""

import math
import os
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
    """Wavefront-based autonomous frontier explorer - STUCK FRONTIER FIX."""

    def __init__(self):
        super().__init__('wavefront_explorer')

        # Declare Frontier Detection Parameters
        self.declare_parameter('frontier_min_size', 15)
        self.declare_parameter('cluster_distance', 1.5)
        self.declare_parameter('exploration_frequency', 3.0)
        self.declare_parameter('nav_timeout', 30.0)

        # Declare Speed Control Parameters
        self.declare_parameter('max_velocity', 0.3)
        self.declare_parameter('max_angular_velocity', 0.5)
        self.declare_parameter('acceleration_limit', 0.3)

        # Get Parameters
        self.frontier_min_size = int(self.get_parameter('frontier_min_size').value)
        self.cluster_distance = float(self.get_parameter('cluster_distance').value)
        self.exploration_frequency = float(self.get_parameter('exploration_frequency').value)
        self.nav_timeout = float(self.get_parameter('nav_timeout').value)

        self.max_velocity = float(self.get_parameter('max_velocity').value)
        self.max_angular_velocity = float(self.get_parameter('max_angular_velocity').value)
        self.acceleration_limit = float(self.get_parameter('acceleration_limit').value)

        # State
        self.map_data = None
        self.map_info = None
        self.navigating = False
        self.exploration_active = False
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.no_frontier_count = 0
        self.current_goal_start_time = None
        
        # ============================================================
        # CRITICAL FIX: Track frontier attempts to detect stuck loops
        # ============================================================
        self.frontier_attempts = {}  # {frontier_id: count}
        self.frontier_successes = {}  # {frontier_id: success_count}
        self.unreachable_frontiers = set()
        self.failed_frontiers = {}
        self.timeout_frontiers = {}
        
        # Tuning parameters
        self.max_attempts_per_frontier = 3  # Skip after 3 attempts
        self.max_retries = 2  # Skip after 2 normal failures
        self.max_timeouts = 3  # Skip after 3 timeouts
        self.consecutive_timeout_count = 0
        self.max_consecutive_timeouts = 5
        self.total_timeout_count = 0
        self.max_total_timeouts = 10

        # Setup maps directory
        self.maps_dir = self._setup_maps_directory()

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

        # Log Configuration
        self.get_logger().info('🤖 Wavefront Explorer READY (STUCK-FRONTIER FIX)')
        self.get_logger().info('   📋 FRONTIER DETECTION:')
        self.get_logger().info(f'      frontier_min_size: {self.frontier_min_size}')
        self.get_logger().info(f'      cluster_distance: {self.cluster_distance}m')
        self.get_logger().info('   ⚡ SPEED CONSTRAINTS:')
        self.get_logger().info(f'      max_velocity: {self.max_velocity}m/s')
        self.get_logger().info('   🔧 STUCK HANDLING:')
        self.get_logger().info(f'      max_attempts_per_frontier: {self.max_attempts_per_frontier}')
        self.get_logger().info(f'      max_retries: {self.max_retries}')
        self.get_logger().info(f'   📁 Maps directory: {self.maps_dir}')

    def _setup_maps_directory(self):
        """Setup maps directory in SweePi root."""
        home = os.path.expanduser('~')
        maps_dir = os.path.join(home, 'SweePi', 'maps')
        
        try:
            os.makedirs(maps_dir, exist_ok=True)
        except Exception as e:
            self.get_logger().warn(f'⚠️  Could not create maps directory: {e}')
            maps_dir = '/tmp/swepi_maps'
            os.makedirs(maps_dir, exist_ok=True)
        
        return maps_dir

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

        for y in range(height):
            for x in range(width):
                if self.map_data[y, x] == 0:
                    queue.append((x, y))
                    visited[y, x] = True

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
            f'📊 Frontiers: {len(frontier_cells)} → {len(frontiers)} | Unreachable: {len(self.unreachable_frontiers)}',
            throttle_duration_sec=5.0)
        return frontiers

    def _cluster_frontiers(self, cells):
        """Cluster frontier cells with optimized merging."""
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

                frontier_id = f"{world_x:.2f}_{world_y:.2f}"
                
                # Skip unreachable frontiers
                if frontier_id not in self.unreachable_frontiers:
                    clusters.append((world_x, world_y, len(cluster), frontier_id))

        clusters.sort(key=lambda c: c[2], reverse=True)
        
        return clusters

    def select_best_frontier(self, frontiers):
        """Select best frontier - AVOID STUCK ONES."""
        if not frontiers:
            return None

        map_center_x = self.map_info.origin.position.x + (self.map_info.width / 2.0) * self.map_info.resolution
        map_center_y = self.map_info.origin.position.y + (self.map_info.height / 2.0) * self.map_info.resolution

        def frontier_score(f):
            x, y, size, frontier_id = f
            distance = math.hypot(f[0] - map_center_x, f[1] - map_center_y)
            attempts = self.frontier_attempts.get(frontier_id, 0)
            
            # ============================================================
            # CRITICAL: Heavily penalize frontiers with many attempts
            # ============================================================
            attempt_penalty = attempts * 500  # Huge penalty for repeated attempts
            score = (size * 10) - distance - attempt_penalty
            return -score
        
        best = min(frontiers, key=frontier_score)
        x, y, size, frontier_id = best
        attempts = self.frontier_attempts.get(frontier_id, 0)
        successes = self.frontier_successes.get(frontier_id, 0)
        
        self.get_logger().info(f'🎯 Selected: ({x:.2f}, {y:.2f}) | Size: {size} | Attempts: {attempts} | Success: {successes}')
        return best

    def explore(self):
        """Main exploration loop."""
        if self.map_data is None:
            self.get_logger().info('⏳ Waiting for map...', throttle_duration_sec=5.0)
            return

        if self.navigating:
            elapsed = (datetime.now() - self.current_goal_start_time).total_seconds()
            if elapsed > self.nav_timeout:
                self.get_logger().warn(f'⏱️  Goal timeout after {elapsed:.1f}s - aborting')
                self.nav_client.cancel_goal_async()
                self.navigating = False
                self.consecutive_timeout_count += 1
                self.total_timeout_count += 1
                
                if self.total_timeout_count >= self.max_total_timeouts:
                    self.get_logger().warn(f'🛑 Max total timeouts - FORCE FINISHING')
                    self._finish_exploration()
                    return
                
                if self.consecutive_timeout_count >= self.max_consecutive_timeouts:
                    self.get_logger().warn(f'🛑 Max consecutive timeouts - FORCE FINISHING')
                    self._finish_exploration()
                    return
            return

        if not self.nav_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().info('⏳ Waiting for Nav2...', throttle_duration_sec=10.0)
            return

        frontiers = self.wavefront_frontier_detection()
        self._publish_frontier_markers(frontiers)

        if not frontiers:
            self.no_frontier_count += 1
            self.get_logger().info(f'ℹ️  No frontiers found ({self.no_frontier_count}/3)')
            
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
        x, y, size, frontier_id = goal
        
        # ============================================================
        # Track attempt BEFORE sending
        # ============================================================
        if frontier_id not in self.frontier_attempts:
            self.frontier_attempts[frontier_id] = 0
        self.frontier_attempts[frontier_id] += 1
        
        attempts = self.frontier_attempts[frontier_id]
        self.get_logger().info(f'📍 Goal: ({x:.2f}, {y:.2f}) | Attempt: {attempts}/{self.max_attempts_per_frontier}')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(x, y)
        goal_msg.behavior_tree = ''

        self.navigating = True
        self.goals_attempted += 1
        self.current_goal_start_time = datetime.now()

        send_future = self.nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(lambda f: self._goal_response(f, frontier_id))

    def _goal_response(self, future, frontier_id):
        """Handle goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().warn(f'❌ Goal rejected: {frontier_id}')
                self._mark_frontier_failed(frontier_id)
                self.navigating = False
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(lambda f: self._goal_result(f, frontier_id))
        except Exception as e:
            self.get_logger().error(f'Goal error: {e}')
            self._mark_frontier_failed(frontier_id)
            self.navigating = False

    def _goal_result(self, future, frontier_id):
        """Handle goal result."""
        try:
            result = future.result()
            if result.status == GoalStatus.STATUS_SUCCEEDED:
                self.goals_reached += 1
                self.consecutive_timeout_count = 0
                
                # ============================================================
                # Track SUCCESS for this frontier
                # ============================================================
                if frontier_id not in self.frontier_successes:
                    self.frontier_successes[frontier_id] = 0
                self.frontier_successes[frontier_id] += 1
                
                self.get_logger().info(f'✅ Goal reached! ({self.goals_reached}/{self.goals_attempted})')
                if frontier_id in self.failed_frontiers:
                    del self.failed_frontiers[frontier_id]
                if frontier_id in self.timeout_frontiers:
                    del self.timeout_frontiers[frontier_id]
            else:
                self.get_logger().warn(f'⚠️  Goal failed: {frontier_id} (status={result.status})')
                self._mark_frontier_failed(frontier_id)
        except Exception as e:
            self.get_logger().error(f'Result error: {e}')
            self._mark_frontier_failed(frontier_id)
        finally:
            self.navigating = False

    def _mark_frontier_failed(self, frontier_id):
        """Track failed frontier attempts."""
        if frontier_id not in self.failed_frontiers:
            self.failed_frontiers[frontier_id] = 0
        
        self.failed_frontiers[frontier_id] += 1
        
        # ============================================================
        # CRITICAL: Check if frontier is stuck (many attempts, no success)
        # ============================================================
        attempts = self.frontier_attempts.get(frontier_id, 0)
        successes = self.frontier_successes.get(frontier_id, 0)
        
        # If more attempts than threshold AND no success, mark as unreachable
        if attempts >= self.max_attempts_per_frontier and successes == 0:
            self.unreachable_frontiers.add(frontier_id)
            self.get_logger().warn(f'🚫 STUCK FRONTIER DETECTED: {frontier_id}')
            self.get_logger().warn(f'   Attempts: {attempts} | Success: {successes} - BLACKLIST')
            return
        
        # Normal failure tracking
        if self.failed_frontiers[frontier_id] >= self.max_retries:
            self.unreachable_frontiers.add(frontier_id)
            self.get_logger().info(f'🚫 Frontier {frontier_id} marked unreachable (failed {self.max_retries}x)')

    def _finish_exploration(self):
        """Complete exploration and save map."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.get_logger().info('=' * 70)
        self.get_logger().info('✅ EXPLORATION COMPLETE')
        self.get_logger().info(f'   ⏱️  Time: {elapsed:.1f}s')
        self.get_logger().info(f'   🎯 Goals: {self.goals_reached}/{self.goals_attempted}')
        self.get_logger().info(f'   🚫 Unreachable frontiers: {len(self.unreachable_frontiers)}')
        self.get_logger().info(f'   ⏰ Total timeouts: {self.total_timeout_count}')
        self.get_logger().info('=' * 70)
        
        self._save_map(elapsed)
        
        self.exploration_active = False

    def _save_map(self, exploration_time):
        """Save map to SweePi/maps directory."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            map_name = f'swepi_exploration_map_{timestamp}'
            pgm_file = os.path.join(self.maps_dir, f'{map_name}.pgm')
            yaml_file = os.path.join(self.maps_dir, f'{map_name}.yaml')
            
            self._save_pgm_file(pgm_file)
            self._save_yaml_file(yaml_file, pgm_file, exploration_time)
            
            self.get_logger().info('=' * 70)
            self.get_logger().info('✅ MAP SAVED SUCCESSFULLY!')
            self.get_logger().info(f'   📄 PGM: {pgm_file}')
            self.get_logger().info(f'   📄 YAML: {yaml_file}')
            self.get_logger().info('=' * 70)
            
        except Exception as e:
            self.get_logger().error(f'❌ Failed to save map: {e}')

    def _save_pgm_file(self, filename):
        """Save map as PGM image file."""
        height, width = self.map_data.shape
        image_data = np.zeros((height, width), dtype=np.uint8)
        
        for y in range(height):
            for x in range(width):
                cell = self.map_data[y, x]
                if cell == -1:
                    image_data[y, x] = 128
                elif cell == 0:
                    image_data[y, x] = 255
                else:
                    image_data[y, x] = 0
        
        with open(filename, 'wb') as f:
            f.write(b'P5\n')
            f.write(f'{width} {height}\n'.encode())
            f.write(b'255\n')
            f.write(image_data.tobytes())
        
        self.get_logger().info(f'   💾 Saved PGM: {width}x{height}')

    def _save_yaml_file(self, filename, pgm_file, exploration_time):
        """Save map metadata as YAML file."""
        yaml_content = f"""image: {os.path.basename(pgm_file)}
resolution: {self.map_info.resolution}
origin: [{self.map_info.origin.position.x}, {self.map_info.origin.position.y}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196

# SweePi Exploration Metadata
swepi_metadata:
  timestamp: {datetime.now().isoformat()}
  exploration_time: {exploration_time:.2f}
  goals_reached: {self.goals_reached}
  goals_attempted: {self.goals_attempted}
  unreachable_frontiers: {len(self.unreachable_frontiers)}
  total_timeouts: {self.total_timeout_count}
  frontier_min_size: {self.frontier_min_size}
  cluster_distance: {self.cluster_distance}
  map_width: {self.map_info.width}
  map_height: {self.map_info.height}
  max_velocity: {self.max_velocity}
"""
        
        with open(filename, 'w') as f:
            f.write(yaml_content)
        
        self.get_logger().info(f'   💾 Saved YAML metadata')

    def _publish_frontier_markers(self, frontiers):
        """Visualize frontiers."""
        marker_array = MarkerArray()
        for i, frontier in enumerate(frontiers):
            x, y, size, frontier_id = frontier
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = self.get_clock().now().to_msg()
            m.id = i
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.1
            m.scale.x = 0.3 + (size / 1000.0)
            m.scale.y = 0.3 + (size / 1000.0)
            m.scale.z = 0.3
            m.color.g = 0.5
            m.color.b = 1.0
            m.color.a = 0.9
            marker_array.markers.append(m)
        self.frontier_pub.publish(marker_array)

    def _make_pose_stamped(self, x, y):
        """Create PoseStamped with correct timestamp."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
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


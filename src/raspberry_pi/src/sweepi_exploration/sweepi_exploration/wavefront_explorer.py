#!/usr/bin/env python3
"""
Wavefront-Based Frontier Explorer for SweePi
CRITICAL FIX: Smarter proximity blocking + connectivity check
"""

import json
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
from std_msgs.msg import String
from std_srvs.srv import Trigger
from visualization_msgs.msg import Marker, MarkerArray


class WavefrontExplorer(Node):
    """Wavefront explorer with intelligent proximity blocking."""

    def __init__(self):
        super().__init__('wavefront_explorer')

        # ============================================================
        # FRONTIER DETECTION PARAMETERS
        # ============================================================
        self.declare_parameter('frontier_min_size', 8)
        self.declare_parameter('cluster_distance', 1.5)
        self.declare_parameter('exploration_frequency', 5.0)
        self.declare_parameter('nav_timeout', 25.0)

        # ============================================================
        # SPEED CONTROL PARAMETERS
        # ============================================================
        self.declare_parameter('max_velocity', 0.05)
        self.declare_parameter('max_angular_velocity', 0.5)
        self.declare_parameter('acceleration_limit', 0.3)

        # ============================================================
        # ATTEMPT LIMITING
        # ============================================================
        self.declare_parameter('max_attempts_per_frontier', 3)
        self.declare_parameter('max_consecutive_timeouts', 3)
        self.declare_parameter('max_exploration_time', 600)

        # ============================================================
        # WALL OFFSET PARAMETERS
        # ============================================================
        self.declare_parameter('goal_offset_distance', 0.5)
        self.declare_parameter('robot_radius', 0.25)
        self.declare_parameter('safety_margin', 0.15)

        # ============================================================
        # NEW: SMARTER PROXIMITY BLOCKING
        # ============================================================
        self.declare_parameter('unreachable_region_radius', 0.5)  # REDUCED - only very close
        self.declare_parameter('smart_blocking_enabled', True)    # NEW: Check connectivity

        # Get Parameters
        self.frontier_min_size = int(self.get_parameter('frontier_min_size').value)
        self.cluster_distance = float(self.get_parameter('cluster_distance').value)
        self.exploration_frequency = float(self.get_parameter('exploration_frequency').value)
        self.nav_timeout = float(self.get_parameter('nav_timeout').value)

        self.max_velocity = float(self.get_parameter('max_velocity').value)
        self.max_angular_velocity = float(self.get_parameter('max_angular_velocity').value)
        self.acceleration_limit = float(self.get_parameter('acceleration_limit').value)

        self.max_attempts_per_frontier = int(self.get_parameter('max_attempts_per_frontier').value)
        self.max_consecutive_timeouts = int(self.get_parameter('max_consecutive_timeouts').value)
        self.max_exploration_time = int(self.get_parameter('max_exploration_time').value)

        self.goal_offset_distance = float(self.get_parameter('goal_offset_distance').value)
        self.robot_radius = float(self.get_parameter('robot_radius').value)
        self.safety_margin = float(self.get_parameter('safety_margin').value)
        self.min_clearance = self.robot_radius + self.safety_margin
        
        self.unreachable_region_radius = float(self.get_parameter('unreachable_region_radius').value)
        self.smart_blocking_enabled = bool(self.get_parameter('smart_blocking_enabled').value)

        # ============================================================
        # STATE VARIABLES
        # ============================================================
        self.map_data = None
        self.map_info = None
        self.navigating = False
        self.exploration_active = False
        self.exploration_state = 'idle'
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.exploration_start_time = None
        self.no_frontier_count = 0
        self.current_goal_start_time = None
        self.current_goal_handle = None
        self.frontiers_remaining = 0
        self.last_goal = None
        self.status_message = 'Exploration idle'

        # ============================================================
        # REGION-BASED TRACKING
        # ============================================================
        self.region_grid_size = 0.5
        self.region_attempts = {}
        self.region_successes = {}
        self.blocked_regions = set()
        self.current_goal_region = None
        
        # ============================================================
        # NEW: UNREACHABLE AREAS WITH CONNECTIVITY INFO
        # ============================================================
        self.unreachable_areas = []  # [(x, y, timestamp, reachable_regions), ...]
        self.unreachable_region_map = {}  # region -> bool (is reachable)

        # ============================================================
        # TIMEOUT TRACKING
        # ============================================================
        self.consecutive_timeout_count = 0
        self.total_timeout_count = 0
        self.max_total_timeouts = 10

        # Subscribers
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.map_callback, 10)

        # Publishers
        self.frontier_pub = self.create_publisher(
            MarkerArray, '/exploration/frontiers', 10)
        self.blocked_regions_pub = self.create_publisher(
            MarkerArray, '/exploration/blocked_regions', 10)
        self.unreachable_pub = self.create_publisher(
            MarkerArray, '/exploration/unreachable_areas', 10)
        self.status_pub = self.create_publisher(
            String, '/exploration/status_json', 10)

        # Services
        self.start_service = self.create_service(
            Trigger, '/exploration/start', self._start_exploration_callback)
        self.stop_service = self.create_service(
            Trigger, '/exploration/stop', self._stop_exploration_callback)

        # Action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Timer
        self.timer = self.create_timer(self.exploration_frequency, self.explore)
        self.status_timer = self.create_timer(1.0, self._publish_status)

        # Log Configuration
        self.get_logger().info('=' * 70)
        self.get_logger().info('🤖 WAVEFRONT EXPLORER (SMART BLOCKING FIX)')
        self.get_logger().info('=' * 70)
        self.get_logger().info('   📋 FRONTIER DETECTION:')
        self.get_logger().info(f'      frontier_min_size: {self.frontier_min_size}')
        self.get_logger().info('   🔧 ATTEMPT LIMITS:')
        self.get_logger().info(f'      max_attempts_per_frontier: {self.max_attempts_per_frontier}')
        self.get_logger().info(f'      max_consecutive_timeouts: {self.max_consecutive_timeouts}')
        self.get_logger().info('   📏 SMART BLOCKING:')
        self.get_logger().info(f'      unreachable_region_radius: {self.unreachable_region_radius}m')
        self.get_logger().info(f'      smart_blocking_enabled: {self.smart_blocking_enabled}')
        self.get_logger().info('   HTTP/API control: idle until /exploration/start is called')
        self.get_logger().info('=' * 70)

    def map_callback(self, msg):
        """Receive occupancy grid map."""
        self.map_data = np.array(msg.data, dtype=np.int8).reshape(
            (msg.info.height, msg.info.width))
        self.map_info = msg.info

    # ============================================================
    # API CONTROL SERVICES
    # ============================================================
    def _start_exploration_callback(self, _request, response):
        """Start exploration when requested by the API bridge."""
        if self.exploration_state == 'exploring':
            response.success = False
            response.message = 'Exploration is already running'
            return response

        self._reset_exploration_run()
        self.exploration_state = 'exploring'
        self.status_message = 'Exploration started'
        self.get_logger().info('🚀 Exploration enabled by /exploration/start')
        self._publish_status()

        response.success = True
        response.message = 'Exploration started'
        return response

    def _stop_exploration_callback(self, _request, response):
        """Stop exploration when requested by the API bridge."""
        if self.current_goal_handle is not None:
            self.current_goal_handle.cancel_goal_async()

        self.navigating = False
        self.current_goal_handle = None
        self.current_goal_region = None
        self.exploration_active = False
        self.exploration_state = 'idle'
        self.status_message = 'Exploration stopped'
        self.get_logger().info('🛑 Exploration stopped by /exploration/stop')
        self._publish_status()

        response.success = True
        response.message = 'Exploration stopped'
        return response

    def _reset_exploration_run(self):
        """Reset per-run exploration state while keeping the latest live map."""
        self.navigating = False
        self.exploration_active = False
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.exploration_start_time = None
        self.no_frontier_count = 0
        self.current_goal_start_time = None
        self.current_goal_handle = None
        self.current_goal_region = None
        self.frontiers_remaining = 0
        self.last_goal = None
        self.region_attempts = {}
        self.region_successes = {}
        self.blocked_regions = set()
        self.unreachable_areas = []
        self.unreachable_region_map = {}
        self.consecutive_timeout_count = 0
        self.total_timeout_count = 0

    def _publish_status(self):
        """Publish reliable exploration state for the API bridge."""
        payload = {
            'state': self.exploration_state,
            'map_available': self.map_data is not None,
            'frontiers_remaining': int(self.frontiers_remaining),
            'last_goal': (
                {'x': self.last_goal[0], 'y': self.last_goal[1]}
                if self.last_goal is not None else None
            ),
            'goals_reached': int(self.goals_reached),
            'goals_attempted': int(self.goals_attempted),
            'message': self.status_message,
        }
        message = String()
        message.data = json.dumps(payload)
        self.status_pub.publish(message)

    # ============================================================
    # COORDINATE CONVERSION
    # ============================================================
    def _world_to_map(self, world_x, world_y):
        """Convert world to map coordinates."""
        map_x = int((world_x - self.map_info.origin.position.x) / self.map_info.resolution)
        map_y = int((world_y - self.map_info.origin.position.y) / self.map_info.resolution)
        return map_x, map_y

    def _map_to_world(self, map_x, map_y):
        """Convert map to world coordinates."""
        world_x = self.map_info.origin.position.x + (map_x + 0.5) * self.map_info.resolution
        world_y = self.map_info.origin.position.y + (map_y + 0.5) * self.map_info.resolution
        return world_x, world_y

    # ============================================================
    # NEW: CONNECTIVITY-AWARE BLOCKING
    # ============================================================
    def _check_connectivity(self, frontier_x, frontier_y, unreachable_x, unreachable_y):
        """
        Check if frontier is in SAME disconnected region as unreachable area.
        If they're separated by obstacles, allow exploration.
        """
        if not self.smart_blocking_enabled:
            return False
        
        # Convert to map coordinates
        fx, fy = self._world_to_map(frontier_x, frontier_y)
        ux, uy = self._world_to_map(unreachable_x, unreachable_y)
        
        height, width = self.map_data.shape
        fx = max(0, min(fx, width - 1))
        fy = max(0, min(fy, height - 1))
        ux = max(0, min(ux, width - 1))
        uy = max(0, min(uy, height - 1))
        
        # BFS to check if there's a path between them
        visited = set()
        queue = deque([(fx, fy)])
        visited.add((fx, fy))
        
        while queue:
            x, y = queue.popleft()
            
            # Found unreachable point - they're connected
            if x == ux and y == uy:
                return True  # Same connected region, block
            
            # Explore neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                    if self.map_data[ny, nx] == 0:  # Free space
                        visited.add((nx, ny))
                        queue.append((nx, ny))
        
        return False  # Separated by obstacles, allow exploration

    def _is_near_unreachable_area(self, world_x, world_y):
        """Check if frontier is near unreachable area AND in same connected region."""
        for unreachable_x, unreachable_y, _ in self.unreachable_areas:
            distance = math.hypot(world_x - unreachable_x, world_y - unreachable_y)
            
            # Close enough to check connectivity
            if distance < self.unreachable_region_radius * 2:
                # Check if they're in same connected region
                if self._check_connectivity(world_x, world_y, unreachable_x, unreachable_y):
                    self.get_logger().info(
                        f'🚫 Frontier ({world_x:.2f}, {world_y:.2f}) in same unreachable region '
                        f'as ({unreachable_x:.2f}, {unreachable_y:.2f}) - distance: {distance:.2f}m',
                        throttle_duration_sec=5.0)
                    return True
        
        return False

    def _add_unreachable_area(self, world_x, world_y):
        """Record a failed frontier location."""
        self.unreachable_areas.append((world_x, world_y, datetime.now()))
        self.get_logger().warn(f'📍 Unreachable area recorded: ({world_x:.2f}, {world_y:.2f})')

    # ============================================================
    # WALL OFFSET ALGORITHM
    # ============================================================
    def _offset_goal_from_walls(self, frontier_x, frontier_y):
        """Offset goal away from walls."""
        fx, fy = self._world_to_map(frontier_x, frontier_y)
        height, width = self.map_data.shape
        fx = max(0, min(fx, width - 1))
        fy = max(0, min(fy, height - 1))

        offset_cells = int(self.goal_offset_distance / self.map_info.resolution)
        if offset_cells < 1:
            offset_cells = 1

        best_position = None
        best_distance_to_wall = 0

        for distance in range(offset_cells, offset_cells + 10):
            for angle_idx in range(8):
                angle = (angle_idx * 2 * math.pi) / 8
                offset_x = int(fx + distance * math.cos(angle))
                offset_y = int(fy + distance * math.sin(angle))

                if not (0 <= offset_x < width and 0 <= offset_y < height):
                    continue

                if self.map_data[offset_y, offset_x] != 0:
                    continue

                if not self._has_clearance(offset_x, offset_y):
                    continue

                world_x, world_y = self._map_to_world(offset_x, offset_y)
                dist_to_wall = self._distance_to_wall(offset_x, offset_y)

                if dist_to_wall > best_distance_to_wall:
                    best_distance_to_wall = dist_to_wall
                    best_position = (world_x, world_y)

            if best_position is not None:
                self.get_logger().info(
                    f'✓ Offset goal: ({frontier_x:.2f}, {frontier_y:.2f}) → '
                    f'({best_position[0]:.2f}, {best_position[1]:.2f})')
                return best_position

        return (frontier_x, frontier_y)

    def _has_clearance(self, x, y):
        """Check if position has enough clearance."""
        clearance_cells = int(self.min_clearance / self.map_info.resolution) + 1
        height, width = self.map_data.shape

        for dx in range(-clearance_cells, clearance_cells + 1):
            for dy in range(-clearance_cells, clearance_cells + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if self.map_data[ny, nx] != 0:
                        return False
        return True

    def _distance_to_wall(self, x, y):
        """Calculate distance to nearest wall."""
        height, width = self.map_data.shape
        min_distance = float('inf')

        search_range = 20
        for dx in range(-search_range, search_range + 1):
            for dy in range(-search_range, search_range + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if self.map_data[ny, nx] != 0:
                        distance = math.sqrt(dx*dx + dy*dy)
                        min_distance = min(min_distance, distance)

        return min_distance if min_distance != float('inf') else search_range

    # ============================================================
    # REGION KEY GENERATION
    # ============================================================
    def _get_region_key(self, world_x, world_y):
        """Get stable region key."""
        region_x = int(world_x / self.region_grid_size) * self.region_grid_size
        region_y = int(world_y / self.region_grid_size) * self.region_grid_size
        return f"{region_x:.1f}_{region_y:.1f}"

    def _get_region_attempts(self, region_key):
        """Get attempts for region."""
        return self.region_attempts.get(region_key, 0)

    def _get_region_successes(self, region_key):
        """Get successes for region."""
        return self.region_successes.get(region_key, 0)

    def _is_region_blocked(self, world_x, world_y):
        """Check if region is blocked."""
        region_key = self._get_region_key(world_x, world_y)
        return region_key in self.blocked_regions

    # ============================================================
    # FRONTIER DETECTION
    # ============================================================
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
            f'📊 Frontiers: {len(frontier_cells)} raw → {len(frontiers)} clustered | '
            f'Unreachable areas: {len(self.unreachable_areas)}',
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

                # Filter 1: Blocked regions
                if self._is_region_blocked(world_x, world_y):
                    continue

                # Filter 2: Near unreachable areas (WITH CONNECTIVITY CHECK)
                if self._is_near_unreachable_area(world_x, world_y):
                    continue

                region_key = self._get_region_key(world_x, world_y)
                clusters.append((world_x, world_y, len(cluster), region_key))

        clusters.sort(key=lambda c: c[2], reverse=True)
        return clusters

    def select_best_frontier(self, frontiers):
        """Select best frontier."""
        if not frontiers:
            return None

        map_center_x = self.map_info.origin.position.x + (self.map_info.width / 2.0) * self.map_info.resolution
        map_center_y = self.map_info.origin.position.y + (self.map_info.height / 2.0) * self.map_info.resolution

        def frontier_score(f):
            x, y, size, region_key = f
            distance = math.hypot(x - map_center_x, y - map_center_y)
            attempts = self._get_region_attempts(region_key)
            attempt_penalty = attempts * 500  # REDUCED penalty - allow more retries
            score = (size * 10) - distance - attempt_penalty
            return -score

        best = min(frontiers, key=frontier_score)
        x, y, size, region_key = best
        attempts = self._get_region_attempts(region_key)

        self.get_logger().info(
            f'🎯 Selected: ({x:.2f}, {y:.2f}) | Size: {size} | Attempts: {attempts}/{self.max_attempts_per_frontier}')
        return best

    # ============================================================
    # MAIN EXPLORATION LOOP
    # ============================================================
    def explore(self):
        """Main exploration loop."""
        if self.exploration_state != 'exploring':
            return

        if self.map_data is None:
            self.status_message = 'Waiting for /map from SLAM Toolbox'
            self.get_logger().info('⏳ Waiting for map...', throttle_duration_sec=5.0)
            return

        if self.exploration_active and self.exploration_start_time:
            elapsed = (datetime.now() - self.exploration_start_time).total_seconds()
            if elapsed > self.max_exploration_time:
                self.get_logger().warn(f'⏰ MAX EXPLORATION TIME')
                self.status_message = 'Exploration completed: max exploration time reached'
                self._finish_exploration()
                return

        if self.navigating:
            elapsed = (datetime.now() - self.current_goal_start_time).total_seconds()
            if elapsed > self.nav_timeout:
                self.get_logger().warn(f'⏱️  Navigation timeout after {elapsed:.1f}s')

                if self.current_goal_handle is not None:
                    self.current_goal_handle.cancel_goal_async()

                self.navigating = False
                self.consecutive_timeout_count += 1
                self.total_timeout_count += 1

                if self.current_goal_region:
                    self.blocked_regions.add(self.current_goal_region)

                if self.total_timeout_count >= self.max_total_timeouts:
                    self.get_logger().warn(f'🛑 Max total timeouts')
                    self.status_message = 'Exploration completed: max total timeouts reached'
                    self._finish_exploration()
                    return

                if self.consecutive_timeout_count >= self.max_consecutive_timeouts:
                    self.get_logger().warn(f'🛑 Max consecutive timeouts')
                    self.status_message = 'Exploration completed: max consecutive timeouts reached'
                    self._finish_exploration()
                    return
            return

        if not self.nav_client.wait_for_server(timeout_sec=0.5):
            self.status_message = 'Waiting for Nav2 navigate_to_pose action'
            self.get_logger().info('⏳ Waiting for Nav2...', throttle_duration_sec=10.0)
            return

        frontiers = self.wavefront_frontier_detection()
        self.frontiers_remaining = len(frontiers)
        self._publish_frontier_markers(frontiers)
        self._publish_unreachable_areas()

        if not frontiers:
            self.no_frontier_count += 1
            self.status_message = f'No valid frontiers ({self.no_frontier_count}/3)'
            self.get_logger().info(f'ℹ️  No valid frontiers ({self.no_frontier_count}/3)')

            if self.no_frontier_count >= 3:
                self.status_message = 'Exploration completed: no valid frontiers remaining'
                self._finish_exploration()
            return

        self.no_frontier_count = 0
        self.status_message = f'Exploring; {self.frontiers_remaining} frontiers remaining'

        if not self.exploration_active:
            self.exploration_active = True
            self.start_time = datetime.now()
            self.exploration_start_time = datetime.now()
            self.get_logger().info('🚀 Exploration started!')

        goal = self.select_best_frontier(frontiers)
        if goal:
            self._send_nav_goal(goal)

    def _send_nav_goal(self, goal):
        """Send navigation goal to Nav2."""
        frontier_x, frontier_y, size, region_key = goal

        goal_x, goal_y = self._offset_goal_from_walls(frontier_x, frontier_y)

        if region_key not in self.region_attempts:
            self.region_attempts[region_key] = 0
        self.region_attempts[region_key] += 1

        self.current_goal_region = region_key
        attempts = self.region_attempts[region_key]
        self.last_goal = (goal_x, goal_y)

        self.get_logger().info(
            f'📍 Goal: ({goal_x:.2f}, {goal_y:.2f}) | Attempt: {attempts}/{self.max_attempts_per_frontier}')
        self.status_message = f'Navigating to frontier ({goal_x:.2f}, {goal_y:.2f})'

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(goal_x, goal_y)
        goal_msg.behavior_tree = ''

        self.navigating = True
        self.goals_attempted += 1
        self.current_goal_start_time = datetime.now()

        send_future = self.nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(lambda f: self._goal_response(f, region_key, frontier_x, frontier_y))

    def _goal_response(self, future, region_key, frontier_x, frontier_y):
        """Handle goal response."""
        try:
            goal_handle = future.result()
            self.current_goal_handle = goal_handle

            if not goal_handle.accepted:
                self.get_logger().warn(f'❌ Goal rejected')
                self._mark_frontier_failed(region_key, frontier_x, frontier_y)
                self.navigating = False
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda f: self._goal_result(f, region_key, frontier_x, frontier_y))
        except Exception as e:
            self.get_logger().error(f'Goal error: {e}')
            self._mark_frontier_failed(region_key, frontier_x, frontier_y)
            self.navigating = False

    def _goal_result(self, future, region_key, frontier_x, frontier_y):
        """Handle goal result."""
        try:
            result = future.result()
            if result.status == GoalStatus.STATUS_SUCCEEDED:
                self.goals_reached += 1
                self.consecutive_timeout_count = 0

                if region_key not in self.region_successes:
                    self.region_successes[region_key] = 0
                self.region_successes[region_key] += 1

                self.get_logger().info(
                    f'✅ Goal reached! ({self.goals_reached}/{self.goals_attempted})')
                self.status_message = 'Goal reached; selecting next frontier'
            else:
                self.get_logger().warn(f'⚠️  Goal failed')
                self.status_message = 'Goal failed; selecting another frontier'
                self._mark_frontier_failed(region_key, frontier_x, frontier_y)
        except Exception as e:
            self.get_logger().error(f'Result error: {e}')
            self._mark_frontier_failed(region_key, frontier_x, frontier_y)
        finally:
            self.navigating = False
            self.current_goal_handle = None

    def _mark_frontier_failed(self, region_key, frontier_x, frontier_y):
        """Mark frontier as failed."""
        attempts = self._get_region_attempts(region_key)
        successes = self._get_region_successes(region_key)

        # Record unreachable location
        self._add_unreachable_area(frontier_x, frontier_y)

        if attempts >= self.max_attempts_per_frontier and successes == 0:
            self.get_logger().warn(f'🚫 BLOCKING REGION: {region_key}')
            self.blocked_regions.add(region_key)

    # ============================================================
    # COMPLETION
    # ============================================================
    def _finish_exploration(self):
        """Complete exploration and save map."""
        if self.exploration_state != 'exploring':
            return

        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        self.get_logger().info('=' * 70)
        self.get_logger().info('✅ EXPLORATION COMPLETE')
        self.get_logger().info(f'   ⏱️  Time: {elapsed:.1f}s')
        self.get_logger().info(f'   🎯 Goals: {self.goals_reached}/{self.goals_attempted}')
        self.get_logger().info(f'   📍 Unreachable areas: {len(self.unreachable_areas)}')
        self.get_logger().info('=' * 70)

        self.exploration_active = False
        self.exploration_state = 'completed'
        self._publish_status()

    # ============================================================
    # VISUALIZATION
    # ============================================================
    def _publish_frontier_markers(self, frontiers):
        """Visualize frontiers (GREEN)."""
        marker_array = MarkerArray()
        for i, frontier in enumerate(frontiers):
            x, y, size, region_key = frontier
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = self.get_clock().now().to_msg()
            m.id = i
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.1
            m.scale.x = 0.4
            m.scale.y = 0.4
            m.scale.z = 0.4
            m.color.g = 1.0
            m.color.a = 0.7
            marker_array.markers.append(m)
        self.frontier_pub.publish(marker_array)

    def _publish_unreachable_areas(self):
        """Visualize unreachable areas (ORANGE)."""
        marker_array = MarkerArray()
        for i, (x, y, _) in enumerate(self.unreachable_areas):
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = self.get_clock().now().to_msg()
            m.id = i + 20000
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.15
            m.scale.x = 0.2
            m.scale.y = 0.2
            m.scale.z = 0.2
            m.color.r = 1.0
            m.color.g = 0.6
            m.color.b = 0.0
            m.color.a = 1.0
            marker_array.markers.append(m)

        self.unreachable_pub.publish(marker_array)

    def _make_pose_stamped(self, x, y):
        """Create PoseStamped."""
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

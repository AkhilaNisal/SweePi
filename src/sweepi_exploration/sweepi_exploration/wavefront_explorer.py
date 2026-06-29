#!/usr/bin/env python3
"""
Wavefront-Based Frontier Explorer for SweePi
CRITICAL FIX: Smarter proximity blocking + connectivity check
"""

import math
import os
from collections import deque
from datetime import datetime

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import SaveMap
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger
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
        self.declare_parameter('max_total_timeouts', 10)
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
        self.declare_parameter('unreachable_region_radius', 0.6)
        self.declare_parameter('smart_blocking_enabled', True)    # NEW: Check connectivity

        # ============================================================
        # MANUAL / AUTO CONTROL PARAMETERS
        # ============================================================
        self.declare_parameter('map_name', '')
        self.declare_parameter('start_mode', 'auto')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')

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
        self.max_total_timeouts = int(self.get_parameter('max_total_timeouts').value)
        self.max_exploration_time = int(self.get_parameter('max_exploration_time').value)

        self.goal_offset_distance = float(self.get_parameter('goal_offset_distance').value)
        self.robot_radius = float(self.get_parameter('robot_radius').value)
        self.safety_margin = float(self.get_parameter('safety_margin').value)
        self.min_clearance = self.robot_radius + self.safety_margin
        
        self.unreachable_region_radius = float(self.get_parameter('unreachable_region_radius').value)
        self.smart_blocking_enabled = bool(self.get_parameter('smart_blocking_enabled').value)
        self.configured_map_name = self._sanitize_map_name(
            self.get_parameter('map_name').value)
        self.start_mode = str(self.get_parameter('start_mode').value).strip().lower()
        self.cmd_vel_topic = str(self.get_parameter('cmd_vel_topic').value)

        # ============================================================
        # STATE VARIABLES
        # ============================================================
        self.map_data = None
        self.map_info = None
        self.navigating = False
        self.exploration_active = False
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.exploration_start_time = None
        self.no_frontier_count = 0
        self.current_goal_start_time = None
        self.current_goal_handle = None
        self.current_goal_frontier = None
        self.current_goal_sequence = None
        self.goal_sequence = 0
        self.ignored_goal_sequences = set()
        self.exploration_mode = self.start_mode if self.start_mode in ('auto', 'manual', 'stopped') else 'auto'
        self.stop_reason = None

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

        # Setup maps directory
        self.maps_dir = self._setup_maps_directory()

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
        self.mode_pub = self.create_publisher(
            String, '/exploration/mode', 10)
        self.cmd_vel_pub = self.create_publisher(
            Twist, self.cmd_vel_topic, 10)

        # Action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Manual/automatic mode control services
        self.set_manual_srv = self.create_service(
            SetBool, '/set_manual_control', self._set_manual_control_callback)
        self.manual_srv = self.create_service(
            Trigger, '/switch_to_manual_control', self._switch_to_manual_callback)
        self.auto_srv = self.create_service(
            Trigger, '/switch_to_auto_exploration', self._switch_to_auto_callback)
        self.stop_srv = self.create_service(
            Trigger, '/stop_exploration', self._stop_exploration_callback)
        self.stop_save_srv = self.create_service(
            SaveMap, '/stop_exploration_and_save', self._stop_and_save_callback)
        self.save_srv = self.create_service(
            SaveMap, '/save_exploration_map', self._save_map_callback)

        # Timer
        self.timer_period = self._timer_period_from_frequency(self.exploration_frequency)
        self.timer = self.create_timer(self.timer_period, self.explore)

        # Log Configuration
        self.get_logger().info('=' * 70)
        self.get_logger().info('🤖 WAVEFRONT EXPLORER (SMART BLOCKING FIX)')
        self.get_logger().info('=' * 70)
        self.get_logger().info('   📋 FRONTIER DETECTION:')
        self.get_logger().info(f'      frontier_min_size: {self.frontier_min_size}')
        self.get_logger().info(
            f'      exploration_frequency: {self.exploration_frequency} Hz '
            f'(timer period: {self.timer_period:.2f}s)')
        self.get_logger().info('   🔧 ATTEMPT LIMITS:')
        self.get_logger().info(f'      max_attempts_per_frontier: {self.max_attempts_per_frontier}')
        self.get_logger().info(f'      max_consecutive_timeouts: {self.max_consecutive_timeouts}')
        self.get_logger().info(f'      max_total_timeouts: {self.max_total_timeouts}')
        self.get_logger().info('   📏 SMART BLOCKING:')
        self.get_logger().info(f'      unreachable_region_radius: {self.unreachable_region_radius}m')
        self.get_logger().info(f'      smart_blocking_enabled: {self.smart_blocking_enabled}')
        self.get_logger().info('   CONTROL:')
        self.get_logger().info(f'      map_name: {self.configured_map_name or "(missing)"}')
        self.get_logger().info(f'      start_mode: {self.exploration_mode}')
        self.get_logger().info(f'      cmd_vel_topic: {self.cmd_vel_topic}')
        self.get_logger().info('      /set_manual_control true=manual false=auto')
        self.get_logger().info('      /stop_exploration_and_save map_url=<name>')
        self.get_logger().info('=' * 70)
        if not self.configured_map_name:
            self.get_logger().error(
                'map_name is required. Automatic and manual exploration will not save '
                'a map until a valid name is provided.')
        self._publish_mode_status()

    def _setup_maps_directory(self):
        """Setup maps directory."""
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

    def _timer_period_from_frequency(self, frequency_hz):
        """Convert configured Hz into a ROS timer period in seconds."""
        if frequency_hz <= 0.0:
            self.get_logger().warn(
                'exploration_frequency must be positive; using 1.0 Hz')
            frequency_hz = 1.0
        return 1.0 / frequency_hz

    # ============================================================
    # MANUAL / AUTO CONTROL
    # ============================================================
    def _set_manual_control_callback(self, request, response):
        """Switch between manual teleop and automatic frontier exploration."""
        if request.data:
            response.success, response.message = self._set_exploration_mode(
                'manual', 'manual control requested')
        else:
            response.success, response.message = self._set_exploration_mode(
                'auto', 'automatic exploration requested')
        return response

    def _switch_to_manual_callback(self, request, response):
        """Pause autonomous exploration so a teleop node can drive /cmd_vel."""
        del request
        response.success, response.message = self._set_exploration_mode(
            'manual', 'manual control requested')
        return response

    def _switch_to_auto_callback(self, request, response):
        """Resume autonomous frontier exploration."""
        del request
        response.success, response.message = self._set_exploration_mode(
            'auto', 'automatic exploration requested')
        return response

    def _stop_exploration_callback(self, request, response):
        """Stop further autonomous exploration without saving a map."""
        del request
        response.success, response.message = self._set_exploration_mode(
            'stopped', 'stop requested')
        return response

    def _stop_and_save_callback(self, request, response):
        """Stop further exploration and save the current map with the requested name."""
        map_name = self._map_name_from_save_request(request)
        if not map_name:
            self.get_logger().error(
                'Map save rejected: provide map_url in the request or launch with map_name.')
            response.result = False
            return response

        mode_success, _ = self._set_exploration_mode(
            'stopped', 'stop and save requested')
        save_success, _ = self._save_map(
            self._elapsed_exploration_time(), map_name)
        response.result = mode_success and save_success
        return response

    def _save_map_callback(self, request, response):
        """Save the current map without changing the current mode."""
        map_name = self._map_name_from_save_request(request)
        if not map_name:
            self.get_logger().error(
                'Map save rejected: provide map_url in the request or launch with map_name.')
            response.result = False
            return response

        save_success, _ = self._save_map(
            self._elapsed_exploration_time(), map_name)
        response.result = save_success
        return response

    def _set_exploration_mode(self, mode, reason):
        """Apply a control mode and cancel autonomous motion when leaving auto."""
        if mode not in ('auto', 'manual', 'stopped'):
            return False, f'Unsupported exploration mode: {mode}'

        if mode == 'auto' and not self.configured_map_name:
            message = 'Automatic exploration requires a non-empty map_name.'
            self.get_logger().error(message)
            return False, message

        previous_mode = self.exploration_mode
        self.exploration_mode = mode
        self.stop_reason = reason if mode == 'stopped' else None

        if mode in ('manual', 'stopped'):
            self._cancel_current_goal()
            self._publish_zero_velocity()
            self.exploration_active = False
            self.no_frontier_count = 0
            if mode == 'manual':
                message = (
                    'Manual control enabled. Autonomous goals are paused; '
                    f'publish teleop commands to {self.cmd_vel_topic}.')
            else:
                message = 'Exploration stopped. Use /switch_to_auto_exploration to explore again.'
        else:
            self.exploration_active = True
            self.no_frontier_count = 0
            self.start_time = datetime.now()
            self.exploration_start_time = datetime.now()
            message = 'Automatic exploration enabled.'

        self.get_logger().info(
            f'Exploration mode changed: {previous_mode} -> {mode} ({reason})')
        self._publish_mode_status()
        return True, message

    def _cancel_current_goal(self):
        """Cancel the current Nav2 goal if one is active."""
        if self.current_goal_handle is not None:
            try:
                if self.current_goal_sequence is not None:
                    self.ignored_goal_sequences.add(self.current_goal_sequence)
                self.current_goal_handle.cancel_goal_async()
            except Exception as e:
                self.get_logger().warn(f'Could not cancel current goal: {e}')
        self.current_goal_handle = None
        self.current_goal_region = None
        self.current_goal_frontier = None
        self.current_goal_sequence = None
        self.current_goal_start_time = None
        self.navigating = False

    def _publish_zero_velocity(self):
        """Send a stop command when autonomous control is paused/stopped."""
        self.cmd_vel_pub.publish(Twist())

    def _publish_mode_status(self):
        """Publish the current exploration control mode."""
        msg = String()
        msg.data = self.exploration_mode
        self.mode_pub.publish(msg)

    def _elapsed_exploration_time(self):
        if self.start_time is None:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()

    def _sanitize_map_name(self, requested_name):
        """Convert a user-provided map name into a safe filename stem."""
        name = str(requested_name or '').strip()
        if name.startswith('file://'):
            name = name[len('file://'):]
        if name.endswith('.yaml') or name.endswith('.pgm'):
            name = os.path.splitext(name)[0]
        name = os.path.basename(name)
        safe_chars = []
        for char in name:
            if char.isalnum() or char in ('_', '-'):
                safe_chars.append(char)
            elif char in (' ', '.'):
                safe_chars.append('_')
        sanitized = ''.join(safe_chars).strip('_')
        if sanitized:
            return sanitized
        return ''

    def _map_name_from_save_request(self, request):
        """Use nav2 SaveMap's map_url field as the requested map name."""
        return self._sanitize_map_name(request.map_url) or self.configured_map_name

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
    def _nearest_free_cell(self, map_x, map_y, max_radius_cells=4):
        """Return a nearby free map cell, or None if noise made it non-free."""
        height, width = self.map_data.shape
        map_x = max(0, min(map_x, width - 1))
        map_y = max(0, min(map_y, height - 1))

        if self.map_data[map_y, map_x] == 0:
            return map_x, map_y

        for radius in range(1, max_radius_cells + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = map_x + dx, map_y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if self.map_data[ny, nx] == 0:
                            return nx, ny
        return None

    def _check_connectivity(self, frontier_x, frontier_y, unreachable_x, unreachable_y):
        """Check if two nearby frontiers belong to the same free-space patch."""
        if not self.smart_blocking_enabled:
            return True

        fx, fy = self._world_to_map(frontier_x, frontier_y)
        ux, uy = self._world_to_map(unreachable_x, unreachable_y)
        start = self._nearest_free_cell(fx, fy)
        target = self._nearest_free_cell(ux, uy)

        # If either endpoint flickered out of free space, treat the nearby failed
        # patch as still blocked instead of reopening it because of map noise.
        if start is None or target is None:
            return True

        height, width = self.map_data.shape
        visited = {start}
        queue = deque([start])

        while queue:
            x, y = queue.popleft()
            if (x, y) == target:
                return True

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                    if self.map_data[ny, nx] == 0:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        return False

    def _is_near_unreachable_area(self, world_x, world_y):
        """Check whether a frontier is part of a recently failed patch."""
        for unreachable_x, unreachable_y, _ in self.unreachable_areas:
            distance = math.hypot(world_x - unreachable_x, world_y - unreachable_y)

            if distance <= self.unreachable_region_radius:
                self.get_logger().info(
                    f'🚫 Frontier ({world_x:.2f}, {world_y:.2f}) too close to failed area '
                    f'({unreachable_x:.2f}, {unreachable_y:.2f}) - distance: {distance:.2f}m',
                    throttle_duration_sec=5.0)
                return True

            if distance <= self.unreachable_region_radius * 2.0:
                if self._check_connectivity(world_x, world_y, unreachable_x, unreachable_y):
                    self.get_logger().info(
                        f'🚫 Frontier ({world_x:.2f}, {world_y:.2f}) in same unreachable region '
                        f'as ({unreachable_x:.2f}, {unreachable_y:.2f}) - distance: {distance:.2f}m',
                        throttle_duration_sec=5.0)
                    return True

        return False

    def _add_unreachable_area(self, world_x, world_y):
        """Record a failed frontier location."""
        for existing_x, existing_y, _ in self.unreachable_areas:
            distance = math.hypot(world_x - existing_x, world_y - existing_y)
            if distance <= self.unreachable_region_radius * 0.5:
                return

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
        region_x = math.floor(world_x / self.region_grid_size) * self.region_grid_size
        region_y = math.floor(world_y / self.region_grid_size) * self.region_grid_size
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
        if self.map_data is None:
            self.get_logger().info('⏳ Waiting for map...', throttle_duration_sec=5.0)
            return

        self._publish_mode_status()

        if self.exploration_mode == 'manual':
            self.get_logger().info(
                'Manual control active; automatic frontier goals are paused.',
                throttle_duration_sec=10.0)
            return

        if self.exploration_mode == 'stopped':
            self.get_logger().info(
                'Exploration stopped; no further frontier goals will be sent.',
                throttle_duration_sec=10.0)
            return

        if not self.configured_map_name:
            self.get_logger().error(
                'Automatic exploration is blocked because map_name is missing.',
                throttle_duration_sec=10.0)
            return

        if self.exploration_active and self.exploration_start_time:
            elapsed = (datetime.now() - self.exploration_start_time).total_seconds()
            if elapsed > self.max_exploration_time:
                self.get_logger().warn(f'⏰ MAX EXPLORATION TIME')
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
                if self.current_goal_frontier:
                    frontier_x, frontier_y = self.current_goal_frontier
                    self._mark_frontier_failed(
                        self.current_goal_region, frontier_x, frontier_y)

                if self.current_goal_sequence is not None:
                    self.ignored_goal_sequences.add(self.current_goal_sequence)
                self.current_goal_handle = None
                self.current_goal_frontier = None
                self.current_goal_sequence = None

                if self.total_timeout_count >= self.max_total_timeouts:
                    self.get_logger().warn(f'🛑 Max total timeouts')
                    self._finish_exploration()
                    return

                if self.consecutive_timeout_count >= self.max_consecutive_timeouts:
                    self.get_logger().warn(
                        '🛑 Consecutive navigation timeouts reached; continuing with failed areas blocked')
                    self.consecutive_timeout_count = 0
            return

        if not self.nav_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().info('⏳ Waiting for Nav2...', throttle_duration_sec=10.0)
            return

        if not self.exploration_active:
            self.exploration_active = True
            self.start_time = datetime.now()
            self.exploration_start_time = datetime.now()
            self.get_logger().info('🚀 Exploration started!')

        frontiers = self.wavefront_frontier_detection()
        self._publish_frontier_markers(frontiers)
        self._publish_unreachable_areas()

        if not frontiers:
            self.no_frontier_count += 1
            self.get_logger().info(f'ℹ️  No valid frontiers ({self.no_frontier_count}/3)')

            if self.no_frontier_count >= 3 and self.exploration_active:
                self._finish_exploration()
            return

        self.no_frontier_count = 0

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

        self.goal_sequence += 1
        goal_sequence = self.goal_sequence
        self.current_goal_region = region_key
        self.current_goal_frontier = (frontier_x, frontier_y)
        self.current_goal_sequence = goal_sequence
        attempts = self.region_attempts[region_key]

        self.get_logger().info(
            f'📍 Goal: ({goal_x:.2f}, {goal_y:.2f}) | Attempt: {attempts}/{self.max_attempts_per_frontier}')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(goal_x, goal_y)
        goal_msg.behavior_tree = ''

        self.navigating = True
        self.goals_attempted += 1
        self.current_goal_start_time = datetime.now()

        send_future = self.nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(
            lambda f: self._goal_response(
                f, region_key, frontier_x, frontier_y, goal_sequence))

    def _goal_response(self, future, region_key, frontier_x, frontier_y, goal_sequence):
        """Handle goal response."""
        try:
            goal_handle = future.result()
            if (goal_sequence in self.ignored_goal_sequences
                    or self.current_goal_sequence != goal_sequence):
                self.ignored_goal_sequences.discard(goal_sequence)
                if goal_handle.accepted:
                    goal_handle.cancel_goal_async()
                return

            self.current_goal_handle = goal_handle

            if not goal_handle.accepted:
                self.get_logger().warn(f'❌ Goal rejected')
                if self.exploration_mode == 'auto':
                    self._mark_frontier_failed(region_key, frontier_x, frontier_y)
                self.navigating = False
                self.current_goal_handle = None
                self.current_goal_frontier = None
                self.current_goal_sequence = None
                return

            if self.exploration_mode != 'auto':
                self.get_logger().info(
                    'Goal accepted after auto exploration was paused; canceling it.')
                goal_handle.cancel_goal_async()
                self.current_goal_handle = None
                self.current_goal_frontier = None
                self.current_goal_sequence = None
                self.navigating = False
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda f: self._goal_result(
                    f, region_key, frontier_x, frontier_y, goal_sequence))
        except Exception as e:
            self.get_logger().error(f'Goal error: {e}')
            if self.exploration_mode == 'auto':
                self._mark_frontier_failed(region_key, frontier_x, frontier_y)
            self.navigating = False
            self.current_goal_frontier = None
            self.current_goal_sequence = None

    def _goal_result(self, future, region_key, frontier_x, frontier_y, goal_sequence):
        """Handle goal result."""
        try:
            result = future.result()
            if goal_sequence in self.ignored_goal_sequences:
                self.ignored_goal_sequences.discard(goal_sequence)
                self.get_logger().info('Ignoring late Nav2 result for timed-out goal.')
                return

            if self.exploration_mode != 'auto':
                self.get_logger().info(
                    'Ignoring Nav2 goal result because automatic exploration is not active.')
                return

            if result.status == GoalStatus.STATUS_SUCCEEDED:
                self.goals_reached += 1
                self.consecutive_timeout_count = 0

                if region_key not in self.region_successes:
                    self.region_successes[region_key] = 0
                self.region_successes[region_key] += 1

                self.get_logger().info(
                    f'✅ Goal reached! ({self.goals_reached}/{self.goals_attempted})')
            else:
                self.get_logger().warn(f'⚠️  Goal failed')
                self._mark_frontier_failed(region_key, frontier_x, frontier_y)
        except Exception as e:
            self.get_logger().error(f'Result error: {e}')
            if self.exploration_mode == 'auto':
                self._mark_frontier_failed(region_key, frontier_x, frontier_y)
        finally:
            if self.current_goal_sequence == goal_sequence:
                self.navigating = False
                self.current_goal_handle = None
                self.current_goal_frontier = None
                self.current_goal_sequence = None

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
        if not self.exploration_active:
            return

        elapsed = self._elapsed_exploration_time()

        self.get_logger().info('=' * 70)
        self.get_logger().info('✅ EXPLORATION COMPLETE')
        self.get_logger().info(f'   ⏱️  Time: {elapsed:.1f}s')
        self.get_logger().info(f'   🎯 Goals: {self.goals_reached}/{self.goals_attempted}')
        self.get_logger().info(f'   📍 Unreachable areas: {len(self.unreachable_areas)}')
        self.get_logger().info('=' * 70)

        save_success, _ = self._save_map(elapsed, self.configured_map_name)
        self.exploration_active = False
        self.exploration_mode = 'stopped'
        self.stop_reason = 'exploration complete' if save_success else 'map save failed'
        self._publish_mode_status()

    def _save_map(self, exploration_time, map_name=None):
        """Save map to file."""
        if self.map_data is None or self.map_info is None:
            message = 'No map has been received yet; cannot save.'
            self.get_logger().warn(message)
            return False, message

        map_name = self._sanitize_map_name(map_name)
        if not map_name:
            message = 'A non-empty map name is required before saving.'
            self.get_logger().error(message)
            return False, message

        try:
            pgm_file = os.path.join(self.maps_dir, f'{map_name}.pgm')
            yaml_file = os.path.join(self.maps_dir, f'{map_name}.yaml')

            self._save_pgm_file(pgm_file)
            self._save_yaml_file(yaml_file, pgm_file, exploration_time)

            self.get_logger().info('=' * 70)
            self.get_logger().info('💾 MAP SAVED SUCCESSFULLY')
            self.get_logger().info(f'   📄 PGM: {pgm_file}')
            self.get_logger().info(f'   📄 YAML: {yaml_file}')
            self.get_logger().info('=' * 70)
            return True, f'Map saved: {yaml_file}'

        except Exception as e:
            message = f'Failed to save map: {e}'
            self.get_logger().error(f'❌ {message}')
            return False, message

    def _save_pgm_file(self, filename):
        """Save map as PGM."""
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

    def _save_yaml_file(self, filename, pgm_file, exploration_time):
        """Save metadata."""
        yaml_content = f"""image: {os.path.basename(pgm_file)}
resolution: {self.map_info.resolution}
origin: [{self.map_info.origin.position.x}, {self.map_info.origin.position.y}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196

swepi_metadata:
  timestamp: {datetime.now().isoformat()}
  exploration_time: {exploration_time:.2f}
  goals_reached: {self.goals_reached}
  goals_attempted: {self.goals_attempted}
  unreachable_areas: {len(self.unreachable_areas)}
"""

        with open(filename, 'w') as f:
            f.write(yaml_content)

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

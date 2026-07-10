#!/usr/bin/env python3
"""
Wavefront-Based Frontier Explorer for SweePi
CRITICAL FIX: Smarter proximity blocking + connectivity check
"""

import copy
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
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray


class WavefrontExplorer(Node):
    """Wavefront explorer with intelligent proximity blocking."""

    def __init__(self):
        super().__init__('wavefront_explorer')

        # ============================================================
        # FRONTIER DETECTION PARAMETERS
        # ============================================================
        self.declare_parameter('frontier_min_size', 3)
        self.declare_parameter('cluster_distance', 1.5)
        self.declare_parameter('min_unknown_region_area_m2', 0.25)
        self.declare_parameter('exploration_frequency', 5.0)
        self.declare_parameter('nav_timeout', 25.0)
        self.declare_parameter('max_frontier_candidates', 0)
        self.declare_parameter('no_frontier_finish_count', 10)
        self.declare_parameter('robot_base_frame', 'base_footprint')
        self.declare_parameter('far_exploration_goal_count', 8)
        self.declare_parameter('far_min_distance', 1.0)
        self.declare_parameter('far_distance_weight', 80.0)
        self.declare_parameter('frontier_size_weight', 2.0)
        self.declare_parameter('safe_goal_clearance_weight', 250.0)
        self.declare_parameter('cleanup_size_weight', 5.0)
        self.declare_parameter('cleanup_distance_weight', 20.0)

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
        self.declare_parameter('max_consecutive_timeouts', 4)
        self.declare_parameter('max_total_timeouts', 35)
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
        self.declare_parameter('failed_frontier_retry_sec', 30.0)
        self.declare_parameter('completion_retry_cycles', 3)
        self.declare_parameter('frontier_goal_search_radius', 1.4)
        self.declare_parameter('frontier_goal_unknown_radius', 0.8)
        self.declare_parameter('save_map_padding_m', 0.50)
        self.declare_parameter('close_saved_map_boundary', True)
        self.declare_parameter('saved_map_boundary_thickness_m', 0.10)

        # ============================================================
        # MANUAL / AUTO CONTROL PARAMETERS
        # ============================================================
        self.declare_parameter('map_name', '')
        self.declare_parameter('start_mode', 'auto')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('source_map_topic', '/map')
        self.declare_parameter('repaired_map_topic', '')
        self.declare_parameter('publish_live_repaired_map', False)

        # Get Parameters
        self.frontier_min_size = int(self.get_parameter('frontier_min_size').value)
        self.cluster_distance = float(self.get_parameter('cluster_distance').value)
        self.min_unknown_region_area_m2 = float(
            self.get_parameter('min_unknown_region_area_m2').value)
        self.exploration_frequency = float(self.get_parameter('exploration_frequency').value)
        self.nav_timeout = float(self.get_parameter('nav_timeout').value)
        self.max_frontier_candidates = int(
            self.get_parameter('max_frontier_candidates').value)
        self.no_frontier_finish_count = int(
            self.get_parameter('no_frontier_finish_count').value)
        self.robot_base_frame = str(self.get_parameter('robot_base_frame').value)
        self.far_exploration_goal_count = int(
            self.get_parameter('far_exploration_goal_count').value)
        self.far_min_distance = float(self.get_parameter('far_min_distance').value)
        self.far_distance_weight = float(self.get_parameter('far_distance_weight').value)
        self.frontier_size_weight = float(self.get_parameter('frontier_size_weight').value)
        self.safe_goal_clearance_weight = float(
            self.get_parameter('safe_goal_clearance_weight').value)
        self.cleanup_size_weight = float(self.get_parameter('cleanup_size_weight').value)
        self.cleanup_distance_weight = float(
            self.get_parameter('cleanup_distance_weight').value)

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
        self.failed_frontier_retry_sec = float(
            self.get_parameter('failed_frontier_retry_sec').value)
        self.completion_retry_cycles = int(
            self.get_parameter('completion_retry_cycles').value)
        self.frontier_goal_search_radius = float(
            self.get_parameter('frontier_goal_search_radius').value)
        self.frontier_goal_unknown_radius = float(
            self.get_parameter('frontier_goal_unknown_radius').value)
        self.save_map_padding_m = float(
            self.get_parameter('save_map_padding_m').value)
        self.close_saved_map_boundary = bool(
            self.get_parameter('close_saved_map_boundary').value)
        self.saved_map_boundary_thickness_m = float(
            self.get_parameter('saved_map_boundary_thickness_m').value)
        self.configured_map_name = self._sanitize_map_name(
            self.get_parameter('map_name').value)
        self.start_mode = str(self.get_parameter('start_mode').value).strip().lower()
        self.cmd_vel_topic = str(self.get_parameter('cmd_vel_topic').value)
        self.source_map_topic = str(self.get_parameter('source_map_topic').value)
        self.repaired_map_topic = str(self.get_parameter('repaired_map_topic').value)
        self.publish_live_repaired_map = bool(
            self.get_parameter('publish_live_repaired_map').value)
        if self.source_map_topic == self.repaired_map_topic:
            self.get_logger().warn(
                'Live repaired map disabled because source_map_topic and '
                'repaired_map_topic are the same.')
            self.publish_live_repaired_map = False

        # ============================================================
        # STATE VARIABLES
        # ============================================================
        self.map_data = None
        self.map_info = None
        self.map_header = None
        self.navigating = False
        self.exploration_active = False
        self.goals_reached = 0
        self.goals_attempted = 0
        self.start_time = None
        self.exploration_start_time = None
        self.no_frontier_count = 0
        self.failure_recovery_used = False
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
        self.blocked_region_times = {}
        self.current_goal_region = None
        
        # ============================================================
        # NEW: UNREACHABLE AREAS WITH CONNECTIVITY INFO
        # ============================================================
        self.unreachable_areas = []  # [(x, y, timestamp, reachable_regions), ...]
        self.unreachable_region_map = {}  # region -> bool (is reachable)
        self.last_raw_frontier_count = 0
        self.last_large_frontier_count = 0
        self.last_filtered_frontier_count = 0
        self.last_small_frontier_count = 0
        self.completion_retry_count = 0

        # ============================================================
        # TIMEOUT TRACKING
        # ============================================================
        self.consecutive_timeout_count = 0
        self.total_timeout_count = 0

        # Setup maps directory
        self.maps_dir = self._setup_maps_directory()

        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        # Subscribers
        self.map_sub = self.create_subscription(
            OccupancyGrid, self.source_map_topic, self.map_callback, map_qos)

        # Publishers
        self.repaired_map_pub = None
        if self.publish_live_repaired_map and self.repaired_map_topic:
            self.repaired_map_pub = self.create_publisher(
                OccupancyGrid,
                self.repaired_map_topic,
                map_qos,
            )
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
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

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
            f'      min_unknown_region_area_m2: {self.min_unknown_region_area_m2:.2f}')
        self.get_logger().info(
            f'      exploration_frequency: {self.exploration_frequency} Hz '
            f'(timer period: {self.timer_period:.2f}s)')
        self.get_logger().info(f'      max_frontier_candidates: {self.max_frontier_candidates}')
        self.get_logger().info(f'      no_frontier_finish_count: {self.no_frontier_finish_count}')
        self.get_logger().info(f'      robot_base_frame: {self.robot_base_frame}')
        self.get_logger().info(
            f'      far_goals: {self.far_exploration_goal_count}, '
            f'far_min_distance: {self.far_min_distance:.2f}m')
        self.get_logger().info(
            f'      safe_goal_clearance_weight: {self.safe_goal_clearance_weight:.1f}')
        self.get_logger().info('   🔧 ATTEMPT LIMITS:')
        self.get_logger().info(f'      max_attempts_per_frontier: {self.max_attempts_per_frontier}')
        self.get_logger().info(f'      max_consecutive_timeouts: {self.max_consecutive_timeouts}')
        self.get_logger().info(f'      max_total_timeouts: {self.max_total_timeouts}')
        self.get_logger().info('   📏 SMART BLOCKING:')
        self.get_logger().info(f'      unreachable_region_radius: {self.unreachable_region_radius}m')
        self.get_logger().info(f'      smart_blocking_enabled: {self.smart_blocking_enabled}')
        self.get_logger().info(f'      failed_frontier_retry_sec: {self.failed_frontier_retry_sec}s')
        self.get_logger().info(f'      completion_retry_cycles: {self.completion_retry_cycles}')
        self.get_logger().info(
            f'      frontier_goal_search_radius: {self.frontier_goal_search_radius}m')
        self.get_logger().info(f'      save_map_padding_m: {self.save_map_padding_m:.2f}m')
        self.get_logger().info(
            f'      close_saved_map_boundary: {self.close_saved_map_boundary} '
            f'thickness={self.saved_map_boundary_thickness_m:.2f}m')
        self.get_logger().info('   CONTROL:')
        self.get_logger().info(f'      map_name: {self.configured_map_name or "(missing)"}')
        self.get_logger().info(f'      start_mode: {self.exploration_mode}')
        self.get_logger().info(f'      cmd_vel_topic: {self.cmd_vel_topic}')
        self.get_logger().info(f'      source_map_topic: {self.source_map_topic}')
        self.get_logger().info(
            f'      repaired_map_topic: {self.repaired_map_topic or "(disabled)"}')
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
        self.map_info = copy.deepcopy(msg.info)
        self.map_header = copy.deepcopy(msg.header)
        self._publish_live_repaired_map()

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
        self._prune_failed_frontier_blocks()
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

    def _prune_failed_frontier_blocks(self):
        """Let failed frontier blocks expire so final sweeps can retry changed maps."""
        if self.failed_frontier_retry_sec <= 0.0:
            return

        now = datetime.now()
        self.unreachable_areas = [
            area for area in self.unreachable_areas
            if (now - area[2]).total_seconds() <= self.failed_frontier_retry_sec
        ]

        expired_regions = [
            region_key for region_key, blocked_at in self.blocked_region_times.items()
            if (now - blocked_at).total_seconds() > self.failed_frontier_retry_sec
        ]
        for region_key in expired_regions:
            self.blocked_regions.discard(region_key)
            self.blocked_region_times.pop(region_key, None)

    def _block_region(self, region_key):
        """Block a failed region for a limited time."""
        if not region_key:
            return
        self.blocked_regions.add(region_key)
        self.blocked_region_times[region_key] = datetime.now()

    def _open_completion_retry_sweep(self):
        """Clear temporary filters so remaining frontiers get another chance."""
        self.completion_retry_count += 1
        self.no_frontier_count = 0
        self.blocked_regions.clear()
        self.blocked_region_times.clear()
        self.unreachable_areas.clear()
        self.get_logger().warn(
            'Remaining raw frontiers are only blocked by retry filters. '
            f'Opening completion retry sweep {self.completion_retry_count}/'
            f'{self.completion_retry_cycles}.')

    # ============================================================
    # WALL OFFSET ALGORITHM
    # ============================================================
    def _find_safe_goal_from_walls(self, frontier_x, frontier_y, log=True):
        """Find a nearby free-space goal and its obstacle/unknown clearance."""
        fx, fy = self._world_to_map(frontier_x, frontier_y)
        height, width = self.map_data.shape
        fx = max(0, min(fx, width - 1))
        fy = max(0, min(fy, height - 1))

        min_offset_cells = max(1, int(self.goal_offset_distance / self.map_info.resolution))
        search_cells = max(
            min_offset_cells,
            int(self.frontier_goal_search_radius / self.map_info.resolution),
        )

        best_position = None
        best_score = float('-inf')
        best_distance_to_wall = 0.0

        for distance in range(min_offset_cells, search_cells + 1):
            for angle_idx in range(16):
                angle = (angle_idx * 2 * math.pi) / 16
                offset_x = int(round(fx + distance * math.cos(angle)))
                offset_y = int(round(fy + distance * math.sin(angle)))

                if not (0 <= offset_x < width and 0 <= offset_y < height):
                    continue

                if self.map_data[offset_y, offset_x] != 0:
                    continue

                if not self._has_clearance(offset_x, offset_y):
                    continue

                world_x, world_y = self._map_to_world(offset_x, offset_y)
                dist_to_wall = self._distance_to_wall(offset_x, offset_y)
                unknown_score = self._count_unknown_cells_near(offset_x, offset_y)
                dist_to_frontier = math.hypot(offset_x - fx, offset_y - fy)

                if unknown_score <= 0:
                    continue

                score = (unknown_score * 20.0) + (dist_to_wall * 2.0) - dist_to_frontier
                if score > best_score:
                    best_score = score
                    best_position = (world_x, world_y)
                    best_distance_to_wall = dist_to_wall

            if best_position is not None:
                clearance_m = best_distance_to_wall * self.map_info.resolution
                if log:
                    self.get_logger().info(
                        f'✓ Safe goal: ({frontier_x:.2f}, {frontier_y:.2f}) -> '
                        f'({best_position[0]:.2f}, {best_position[1]:.2f}) | '
                        f'clearance={clearance_m:.2f}m')
                return best_position[0], best_position[1], clearance_m

        return frontier_x, frontier_y, 0.0

    def _offset_goal_from_walls(self, frontier_x, frontier_y):
        """Backward-compatible wrapper for older call sites."""
        goal_x, goal_y, _clearance_m = self._find_safe_goal_from_walls(
            frontier_x, frontier_y, log=True)
        return goal_x, goal_y

    def _count_unknown_cells_near(self, x, y):
        """Count nearby unknown cells to prefer goals that reveal new map area."""
        height, width = self.map_data.shape
        radius_cells = max(
            1,
            int(self.frontier_goal_unknown_radius / self.map_info.resolution),
        )
        count = 0
        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                if dx * dx + dy * dy > radius_cells * radius_cells:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if self.map_data[ny, nx] == -1:
                        count += 1
        return count

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
        self._prune_failed_frontier_blocks()
        region_key = self._get_region_key(world_x, world_y)
        return region_key in self.blocked_regions

    # ============================================================
    # FRONTIER DETECTION
    # ============================================================
    def wavefront_frontier_detection(self):
        """Detect all frontier cells in linear time across the current map."""
        if self.map_data is None:
            return []

        height, width = self.map_data.shape
        frontier_cells = []
        frontier_seen = set()
        candidate_limit = self.max_frontier_candidates

        for y in range(height):
            for x in range(width):
                if self.map_data[y, x] != 0:
                    continue

                is_frontier = False
                for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                               (0, 1), (1, -1), (1, 0), (1, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and self.map_data[ny, nx] == -1:
                        is_frontier = True
                        break

                if not is_frontier or (x, y) in frontier_seen:
                    continue

                frontier_seen.add((x, y))
                frontier_cells.append((x, y))
                if candidate_limit > 0 and len(frontier_cells) >= candidate_limit:
                    break
            if candidate_limit > 0 and len(frontier_cells) >= candidate_limit:
                break

        frontiers = self._cluster_frontiers(frontier_cells, apply_filters=True)
        self.get_logger().info(
            f'📊 Frontiers: {len(frontier_cells)} cells, '
            f'{self.last_raw_frontier_count} raw clusters, '
            f'{self.last_large_frontier_count} large -> '
            f'{len(frontiers)} large usable | ignored small: '
            f'{self.last_small_frontier_count} | Unreachable areas: '
            f'{len(self.unreachable_areas)}',
            throttle_duration_sec=5.0)
        return frontiers

    def _cluster_frontiers(self, cells, apply_filters=True):
        """Cluster adjacent frontier cells without an O(n^2) all-pairs pass."""
        if not cells:
            if apply_filters:
                self.last_raw_frontier_count = 0
                self.last_large_frontier_count = 0
                self.last_filtered_frontier_count = 0
                self.last_small_frontier_count = 0
            return []

        cell_set = set(cells)
        visited = set()
        clusters = []
        raw_cluster_count = 0
        large_cluster_count = 0
        small_cluster_count = 0

        for cell in cells:
            if cell in visited:
                continue

            cluster = []
            queue = deque([cell])
            visited.add(cell)

            while queue:
                x, y = queue.popleft()
                cluster.append((x, y))

                for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                               (0, 1), (1, -1), (1, 0), (1, 1)]:
                    neighbor = (x + dx, y + dy)
                    if neighbor in cell_set and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            raw_cluster_count += 1
            if len(cluster) < self.frontier_min_size:
                small_cluster_count += 1
                continue
            large_cluster_count += 1

            cx = sum(c[0] for c in cluster) / len(cluster)
            cy = sum(c[1] for c in cluster) / len(cluster)
            goal_cell = min(
                cluster,
                key=lambda c: (c[0] - cx) * (c[0] - cx) + (c[1] - cy) * (c[1] - cy))

            frontier_x = self.map_info.origin.position.x + (goal_cell[0] + 0.5) * self.map_info.resolution
            frontier_y = self.map_info.origin.position.y + (goal_cell[1] + 0.5) * self.map_info.resolution
            goal_x, goal_y, clearance_m = self._find_safe_goal_from_walls(
                frontier_x, frontier_y, log=False)
            goal_mx, goal_my = self._world_to_map(goal_x, goal_y)
            unknown_area_m2 = (
                self._count_unknown_cells_near(goal_mx, goal_my)
                * self.map_info.resolution
                * self.map_info.resolution
            )
            if apply_filters and unknown_area_m2 < self.min_unknown_region_area_m2:
                small_cluster_count += 1
                continue

            if self._is_region_blocked(goal_x, goal_y):
                continue

            if self._is_near_unreachable_area(frontier_x, frontier_y):
                continue

            region_key = self._get_region_key(goal_x, goal_y)
            clusters.append((frontier_x, frontier_y, len(cluster), region_key,
                             goal_x, goal_y, clearance_m))

        clusters.sort(key=lambda c: (c[4], c[2]), reverse=True)
        if apply_filters:
            self.last_raw_frontier_count = raw_cluster_count
            self.last_large_frontier_count = large_cluster_count
            self.last_filtered_frontier_count = len(clusters)
            self.last_small_frontier_count = small_cluster_count
        return clusters

    def _get_robot_position(self):
        """Return the robot pose in map frame for frontier scoring."""
        try:
            transform = self.tf_buffer.lookup_transform(
                'map',
                self.robot_base_frame,
                Time())
            return (
                transform.transform.translation.x,
                transform.transform.translation.y)
        except TransformException as exc:
            self.get_logger().warn(
                f'Could not get map -> {self.robot_base_frame} TF for frontier scoring: {exc}',
                throttle_duration_sec=5.0)
            return None

    def _frontier_fields(self, frontier):
        """Return frontier and safe-goal fields for old/new tuple formats."""
        if len(frontier) >= 7:
            return frontier[:7]

        x, y, size, region_key = frontier
        goal_x, goal_y, clearance_m = self._find_safe_goal_from_walls(x, y, log=False)
        return x, y, size, region_key, goal_x, goal_y, clearance_m

    def select_best_frontier(self, frontiers):
        """Select a far frontier first, then refine nearby smaller regions later."""
        if not frontiers:
            return None

        robot_position = self._get_robot_position()
        if robot_position is None:
            robot_position = (
                self.map_info.origin.position.x + (self.map_info.width / 2.0) * self.map_info.resolution,
                self.map_info.origin.position.y + (self.map_info.height / 2.0) * self.map_info.resolution)

        robot_x, robot_y = robot_position
        far_phase = self.goals_reached < self.far_exploration_goal_count

        def frontier_score(frontier):
            x, y, size, region_key, goal_x, goal_y, clearance_m = self._frontier_fields(frontier)
            distance = math.hypot(goal_x - robot_x, goal_y - robot_y)
            attempts = self._get_region_attempts(region_key)
            attempt_penalty = attempts * 250.0
            size_score = min(float(size), 800.0)

            if far_phase:
                near_penalty = max(0.0, self.far_min_distance - distance) * 300.0
                score = (
                    distance * self.far_distance_weight
                    + size_score * self.frontier_size_weight
                    + clearance_m * self.safe_goal_clearance_weight
                    - attempt_penalty
                    - near_penalty)
            else:
                score = (
                    size_score * self.cleanup_size_weight
                    + clearance_m * self.safe_goal_clearance_weight
                    - distance * self.cleanup_distance_weight
                    - attempt_penalty)
            return -score

        best = min(frontiers, key=frontier_score)
        x, y, size, region_key, goal_x, goal_y, clearance_m = self._frontier_fields(best)
        attempts = self._get_region_attempts(region_key)
        distance = math.hypot(goal_x - robot_x, goal_y - robot_y)
        phase = 'far' if far_phase else 'cleanup'

        self.get_logger().info(
            f'🎯 Selected {phase}: frontier=({x:.2f}, {y:.2f}) goal=({goal_x:.2f}, {goal_y:.2f}) | '
            f'Size: {size} | Distance: {distance:.2f}m | Clearance: {clearance_m:.2f}m | '
            f'Attempts: {attempts}/{self.max_attempts_per_frontier}')
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
            if (self.last_large_frontier_count > 0
                    and self.completion_retry_count < self.completion_retry_cycles):
                self._open_completion_retry_sweep()
                return

            self.no_frontier_count += 1
            self.get_logger().info(
                f'ℹ️  No valid frontiers ({self.no_frontier_count}/{self.no_frontier_finish_count})')

            if (self.unreachable_areas or self.blocked_regions) and not self.failure_recovery_used:
                self.get_logger().warn(
                    'No valid frontiers remain after failure filtering; clearing temporary failed areas once.')
                self.unreachable_areas.clear()
                self.blocked_regions.clear()
                self.failure_recovery_used = True
                self.no_frontier_count = 0
                return

            if self.no_frontier_count >= self.no_frontier_finish_count and self.exploration_active:
                self._finish_exploration()
            return

        self.no_frontier_count = 0

        goal = self.select_best_frontier(frontiers)
        if goal:
            self._send_nav_goal(goal)

    def _send_nav_goal(self, goal):
        """Send navigation goal to Nav2."""
        frontier_x, frontier_y, size, region_key, goal_x, goal_y, clearance_m = self._frontier_fields(goal)

        if clearance_m > 0.0:
            self.get_logger().info(
                f'✓ Using safe goal: ({frontier_x:.2f}, {frontier_y:.2f}) -> '
                f'({goal_x:.2f}, {goal_y:.2f}) | clearance={clearance_m:.2f}m')
        else:
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
            f'📍 Goal: ({goal_x:.2f}, {goal_y:.2f}) | '
            f'Unknown area: {self._cells_to_area_m2(unknown_cells):.2f} m² | '
            f'Attempt: {attempts}/{self.max_attempts_per_frontier}')

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
                self.get_logger().warn(
                    'Goal rejected; Nav2 may still be activating. Will retry frontier selection.',
                    throttle_duration_sec=5.0)
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
                self.completion_retry_count = 0

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
        """Mark a frontier as failed only after repeated unsuccessful attempts."""
        attempts = self._get_region_attempts(region_key)
        successes = self._get_region_successes(region_key)

        if attempts < self.max_attempts_per_frontier:
            self.get_logger().warn(
                f'Frontier attempt failed but will remain available: '
                f'{attempts}/{self.max_attempts_per_frontier}')
            return

        if successes == 0:
            self._add_unreachable_area(frontier_x, frontier_y)
            self.get_logger().warn(f'🚫 BLOCKING REGION: {region_key}')
            self._block_region(region_key)

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
            map_data, origin_x, origin_y = self._saved_map_snapshot()

            self._save_pgm_file(pgm_file, map_data)
            self._save_yaml_file(
                yaml_file,
                pgm_file,
                exploration_time,
                origin_x,
                origin_y,
            )

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

    def _saved_map_snapshot(self):
        return self._processed_map_snapshot(include_padding=True, log=True)

    def _processed_map_snapshot(self, include_padding, log=False):
        map_data = np.array(self.map_data, copy=True)
        origin_x = float(self.map_info.origin.position.x)
        origin_y = float(self.map_info.origin.position.y)
        resolution = float(self.map_info.resolution)
        map_data = self._close_saved_map_boundary(map_data, resolution, log=log)
        if not include_padding:
            return map_data, origin_x, origin_y

        if self.save_map_padding_m <= 0.0 or resolution <= 0.0:
            return map_data, origin_x, origin_y

        padding_cells = int(math.ceil(self.save_map_padding_m / resolution))
        if padding_cells <= 0:
            return map_data, origin_x, origin_y

        padded = np.full(
            (
                map_data.shape[0] + padding_cells * 2,
                map_data.shape[1] + padding_cells * 2,
            ),
            -1,
            dtype=np.int8,
        )
        padded[
            padding_cells:padding_cells + map_data.shape[0],
            padding_cells:padding_cells + map_data.shape[1],
        ] = map_data
        origin_x -= padding_cells * resolution
        origin_y -= padding_cells * resolution
        if log:
            self.get_logger().info(
                f'Adding {padding_cells} unknown padding cells '
                f'({padding_cells * resolution:.2f}m) around saved map.')
        return padded, origin_x, origin_y

    def _publish_live_repaired_map(self):
        if self.repaired_map_pub is None or self.map_header is None:
            return
        if self.map_data is None or self.map_info is None:
            return

        map_data, origin_x, origin_y = self._processed_map_snapshot(
            include_padding=True,
            log=False,
        )
        msg = OccupancyGrid()
        msg.header = copy.deepcopy(self.map_header)
        msg.info = copy.deepcopy(self.map_info)
        msg.info.width = int(map_data.shape[1])
        msg.info.height = int(map_data.shape[0])
        msg.info.origin.position.x = origin_x
        msg.info.origin.position.y = origin_y
        msg.data = [int(value) for value in map_data.reshape(-1)]
        self.repaired_map_pub.publish(msg)

    def _close_saved_map_boundary(self, map_data, resolution, log=False):
        if not self.close_saved_map_boundary or resolution <= 0.0:
            return map_data

        known_y, known_x = np.where(map_data != -1)
        if known_x.size == 0 or known_y.size == 0:
            return map_data

        min_x = int(known_x.min())
        max_x = int(known_x.max())
        min_y = int(known_y.min())
        max_y = int(known_y.max())
        if max_x <= min_x or max_y <= min_y:
            return map_data

        thickness = max(
            1,
            int(math.ceil(max(0.0, self.saved_map_boundary_thickness_m) / resolution)),
        )
        repaired = np.array(map_data, copy=True)
        for offset in range(thickness):
            left = min_x + offset
            right = max_x - offset
            bottom = min_y + offset
            top = max_y - offset
            if left > right or bottom > top:
                break
            repaired[bottom, left:right + 1] = 100
            repaired[top, left:right + 1] = 100
            repaired[bottom:top + 1, left] = 100
            repaired[bottom:top + 1, right] = 100

        if log:
            self.get_logger().info(
                'Closed saved map outer boundary: '
                f'x=[{min_x},{max_x}] y=[{min_y},{max_y}] '
                f'thickness={thickness} cells ({thickness * resolution:.2f}m).')
        return repaired

    def _save_pgm_file(self, filename, map_data):
        """Save map as PGM."""
        height, width = map_data.shape
        image_data = np.zeros((height, width), dtype=np.uint8)

        for y in range(height):
            for x in range(width):
                cell = map_data[y, x]
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
            f.write(np.flipud(image_data).tobytes())

    def _save_yaml_file(self, filename, pgm_file, exploration_time, origin_x, origin_y):
        """Save metadata."""
        yaml_content = f"""image: {os.path.basename(pgm_file)}
resolution: {self.map_info.resolution}
origin: [{origin_x}, {origin_y}, 0.0]
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
            x, y, size, region_key, _goal_x, _goal_y, _clearance_m = self._frontier_fields(frontier)
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

#!/usr/bin/env python3
"""
Nav Goal Publisher Node for SweePi
Publishes navigation goals using pre-saved maps and Nav2
No coverage algorithm yet - just basic navigation
"""

import os
import sys
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from map_loader import MapLoader
except ImportError:
    from sweepi_coverage.map_loader import MapLoader


class NavGoalPublisher(Node):
    """Main navigation goal publisher node."""

    def __init__(self):
        super().__init__('nav_goal_publisher')
        
        # ============================================================
        # PARAMETERS
        # ============================================================
        self.declare_parameter('map_name', '')
        self.declare_parameter('nav_timeout', 30.0)
        self.declare_parameter('max_velocity', 0.05)
        
        self.map_name = self.get_parameter('map_name').value
        self.nav_timeout = self.get_parameter('nav_timeout').value
        self.max_velocity = self.get_parameter('max_velocity').value
        
        # ============================================================
        # STATE VARIABLES
        # ============================================================
        self.map_data = None
        self.map_info = None
        self.map_loaded = False
        self.navigating = False
        self.current_goal_handle = None
        self.current_goal_start_time = None
        self.goal_received = False
        
        # Setup maps directory
        self.maps_dir = self._setup_maps_directory()
        self.map_loader = MapLoader(self.maps_dir)
        
        # ============================================================
        # SUBSCRIBERS
        # ============================================================
        self.goal_sub = self.create_subscription(
            PoseStamped, '/goal_pose', self.goal_pose_callback, 10)
        
        # ============================================================
        # PUBLISHERS
        # ============================================================
        self.map_pub = self.create_publisher(
            OccupancyGrid, '/map', 10)
        
        self.goal_marker_pub = self.create_publisher(
            Marker, '/nav_goal_marker', 10)
        
        # ============================================================
        # ACTION CLIENT
        # ============================================================
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # ============================================================
        # TIMERS
        # ============================================================
        self.timer = self.create_timer(1.0, self.update_loop)
        
        # ============================================================
        # LOGGING
        # ============================================================
        self.get_logger().info('=' * 70)
        self.get_logger().info('NAV GOAL PUBLISHER INITIALIZED')
        self.get_logger().info('=' * 70)
        self.get_logger().info('Nav Timeout: ' + str(self.nav_timeout) + 's')
        self.get_logger().info('Max Velocity: ' + str(self.max_velocity) + 'm/s')
        self.get_logger().info('=' * 70)

    def _setup_maps_directory(self):
        """Setup maps directory."""
        home = os.path.expanduser('~')
        maps_dir = os.path.join(home, 'SweePi', 'maps')
        try:
            os.makedirs(maps_dir, exist_ok=True)
        except Exception as e:
            self.get_logger().warn('Could not create maps directory: ' + str(e))
            maps_dir = '/tmp/swepi_maps'
            os.makedirs(maps_dir, exist_ok=True)
        return maps_dir

    def update_loop(self):
        """Main update loop."""
        # Load map once
        if not self.map_loaded:
            self._load_map()
        
        # Check for navigation timeout
        if self.navigating and self.current_goal_start_time:
            elapsed = (datetime.now() - self.current_goal_start_time).total_seconds()
            if elapsed > self.nav_timeout:
                self.get_logger().warn('Navigation timeout after {:.1f}s'.format(elapsed))
                if self.current_goal_handle:
                    self.current_goal_handle.cancel_goal_async()
                self.navigating = False
        
        # Publish goal marker
        if self.goal_received:
            self._publish_goal_marker()

    def _load_map(self):
        """Load pre-saved map."""
        available_maps = self.map_loader.list_available_maps()
        
        if not available_maps:
            self.get_logger().info('No maps found in ' + self.maps_dir)
            return
        
        # Determine which map to load
        if self.map_name:
            if self.map_name in available_maps:
                load_name = self.map_name
            else:
                self.get_logger().warn('Map not found: ' + self.map_name)
                load_name = self.map_loader.get_latest_map()
        else:
            load_name = self.map_loader.get_latest_map()
        
        if load_name:
            self.get_logger().info('Loading map: ' + load_name)
            pgm_array, metadata = self.map_loader.load_map(load_name)
            
            if pgm_array is not None:
                self.map_data = pgm_array
                self.map_loaded = True
                
                from nav_msgs.msg import MapMetaData
                from geometry_msgs.msg import Pose
                
                self.map_info = MapMetaData()
                self.map_info.resolution = float(metadata.get('resolution', 0.05))
                self.map_info.width = pgm_array.shape[1]
                self.map_info.height = pgm_array.shape[0]
                
                origin = metadata.get('origin', [0, 0, 0])
                self.map_info.origin = Pose()
                self.map_info.origin.position.x = float(origin[0])
                self.map_info.origin.position.y = float(origin[1])
                self.map_info.origin.position.z = 0.0
                self.map_info.origin.orientation.w = 1.0
                
                cells = pgm_array.shape
                res = self.map_info.resolution
                self.get_logger().info('Map loaded: {} cells @ {}m/cell'.format(cells, res))
                
                # Publish map continuously
                self._publish_map()
            else:
                self.get_logger().error('Failed to load map')

    def _publish_map(self):
        """Publish pre-saved map to /map topic."""
        if self.map_data is None or self.map_info is None:
            return
        
        grid = OccupancyGrid()
        grid.header.frame_id = 'map'
        grid.header.stamp = self.get_clock().now().to_msg()
        
        grid.info = self.map_info
        grid.info.map_load_time = self.get_clock().now().to_msg()
        
        grid.data = self.map_data.flatten().tolist()
        
        self.map_pub.publish(grid)

    def goal_pose_callback(self, msg):
        """Handle goal pose from RViz2 or other source."""
        x = msg.pose.position.x
        y = msg.pose.position.y
        self.get_logger().info('Goal received: ({:.2f}, {:.2f})'.format(x, y))
        
        self.goal_received = True
        self._send_nav_goal(x, y)

    def _send_nav_goal(self, goal_x, goal_y):
        """Send navigation goal to Nav2."""
        if not self.nav_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().info('Waiting for Nav2...')
            return
        
        self.get_logger().info('Sending goal to Nav2: ({:.2f}, {:.2f})'.format(goal_x, goal_y))
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose_stamped(goal_x, goal_y)
        goal_msg.behavior_tree = ''
        
        self.navigating = True
        self.current_goal_start_time = datetime.now()
        
        send_future = self.nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(self._goal_response)

    def _goal_response(self, future):
        """Handle goal response."""
        try:
            goal_handle = future.result()
            self.current_goal_handle = goal_handle
            
            if not goal_handle.accepted:
                self.get_logger().warn('Goal rejected by Nav2')
                self.navigating = False
                return
            
            self.get_logger().info('Goal accepted by Nav2')
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._goal_result)
        except Exception as e:
            self.get_logger().error('Goal error: ' + str(e))
            self.navigating = False

    def _goal_result(self, future):
        """Handle goal result."""
        try:
            result = future.result()
            if result.status == GoalStatus.STATUS_SUCCEEDED:
                self.get_logger().info('Goal reached successfully!')
            else:
                self.get_logger().warn('Goal failed with status {}'.format(result.status))
        except Exception as e:
            self.get_logger().error('Result error: ' + str(e))
        finally:
            self.navigating = False

    def _publish_goal_marker(self):
        """Publish goal marker for visualization."""
        if not self.goal_received:
            return
        
        marker = Marker()
        marker.header.frame_id = 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.id = 0
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        
        # Get last goal position
        marker.scale.x = 0.2
        marker.scale.y = 0.2
        marker.scale.z = 0.2
        
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
        marker.color.a = 0.8
        
        self.goal_marker_pub.publish(marker)

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
    node = NavGoalPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Stopped')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
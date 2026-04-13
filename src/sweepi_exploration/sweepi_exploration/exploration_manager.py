#!/usr/bin/env python3

import os
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, Odometry
from geometry_msgs.msg import Twist, Point
from visualization_msgs.msg import Marker, MarkerArray
import numpy as np
from datetime import datetime
import math
import time
import subprocess

class SimpleExplorationManager(Node):
    """
    Simplified exploration without Nav2
    Publishes cmd_vel directly to move robot towards frontiers
    """
    
    def __init__(self):
        super().__init__('exploration_manager')
        
        # Parameters
        self.declare_parameter('frontier_min_size', 0.5)
        self.declare_parameter('exploration_mode', 'autonomous')
        
        self.frontier_min_size = self.get_parameter('frontier_min_size').value
        self.exploration_mode = self.get_parameter('exploration_mode').value
        
        # State
        self.map_data = None
        self.map_metadata = None
        self.robot_pose = None
        self.current_frontiers = []
        self.exploration_active = False
        self.goal_frontier = None
        self.no_frontier_count = 0
        self.exploration_start_time = None
        self.progress_counter = 0
        
        # Subscribers
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.map_callback, 10)
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.frontier_marker_pub = self.create_publisher(MarkerArray, '/exploration/frontiers', 10)
        self.goal_marker_pub = self.create_publisher(Marker, '/exploration/goal', 10)
        
        # Timers
        self.create_timer(2.0, self.exploration_callback)
        self.create_timer(0.1, self.movement_callback)
        
        self.get_logger().info('🤖 ========== SIMPLE EXPLORATION MANAGER INITIALIZED ==========')
        self.get_logger().info(f'   📍 Mode: {self.exploration_mode}')
        self.get_logger().info(f'   🔍 Frontier min size: {self.frontier_min_size}m')
        self.get_logger().info('================================================================')
    
    def map_callback(self, msg):
        """Store map data"""
        self.map_data = msg.data
        self.map_metadata = msg.info
    
    def odom_callback(self, msg):
        """Store robot pose"""
        self.robot_pose = msg.pose.pose
    
    def exploration_callback(self):
        """Detect frontiers and select goals"""
        if self.exploration_mode != 'autonomous':
            return
        
        if self.map_data is None or self.robot_pose is None:
            return
        
        # Detect frontiers
        frontiers = self.detect_frontiers()
        self.current_frontiers = frontiers
        self.publish_frontier_markers(frontiers)
        
        if frontiers and len(frontiers) > 0:
            self.no_frontier_count = 0
            
            if not self.exploration_active:
                self.get_logger().info('🚀 ========== STARTING AUTONOMOUS EXPLORATION ==========')
                self.exploration_active = True
                self.exploration_start_time = datetime.now()
            
            # Select new frontier if none active
            if self.goal_frontier is None:
                self.goal_frontier = self.select_best_frontier(frontiers)
                if self.goal_frontier:
                    self.get_logger().info(f'🎯 Target: ({self.goal_frontier[0]:.2f}, {self.goal_frontier[1]:.2f})')
                    self.progress_counter += 1
        else:
            self.no_frontier_count += 1
            
            if self.no_frontier_count >= 3 and self.exploration_active:
                self.get_logger().info('✅ ========== EXPLORATION COMPLETE! ==========')
                elapsed = (datetime.now() - self.exploration_start_time).total_seconds()
                self.get_logger().info(f'   📊 Goals reached: {self.progress_counter}')
                self.get_logger().info(f'   ⏱️  Total time: {elapsed:.1f}s')
                self.get_logger().info('============================================')
                self.exploration_active = False
                self.stop_robot()
                self.save_map()
    
    def movement_callback(self):
        """Move robot towards frontier goal"""
        if self.goal_frontier is None or self.robot_pose is None:
            self.stop_robot()
            return
        
        # Calculate direction to goal
        dx = self.goal_frontier[0] - self.robot_pose.position.x
        dy = self.goal_frontier[1] - self.robot_pose.position.y
        dist = math.sqrt(dx**2 + dy**2)
        
        # Stop if reached goal
        if dist < 0.4:
            self.goal_frontier = None
            self.stop_robot()
            self.get_logger().info('✅ Reached frontier')
            return
        
        # Create movement command
        twist = Twist()
        
        # Forward velocity
        twist.linear.x = 0.2
        
        # Calculate angle to goal
        goal_angle = math.atan2(dy, dx)
        current_angle = self.get_yaw(self.robot_pose.orientation)
        angle_diff = goal_angle - current_angle
        
        # Normalize angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Proportional angular control
        twist.angular.z = 0.5 * angle_diff
        
        # Publish command
        self.cmd_vel_pub.publish(twist)
        
        # Publish goal marker
        self.publish_goal_marker()
    
    def detect_frontiers(self):
        """Detect frontiers in map"""
        if self.map_data is None or self.map_metadata is None:
            return []
        
        width = self.map_metadata.width
        height = self.map_metadata.height
        resolution = self.map_metadata.resolution
        origin_x = self.map_metadata.origin.position.x
        origin_y = self.map_metadata.origin.position.y
        
        try:
            grid = np.array(self.map_data, dtype=np.int8).reshape((height, width))
        except ValueError:
            return []
        
        frontiers = []
        
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if grid[y, x] == 0:
                    neighbors = [
                        grid[y-1, x-1], grid[y-1, x], grid[y-1, x+1],
                        grid[y, x-1],                 grid[y, x+1],
                        grid[y+1, x-1], grid[y+1, x], grid[y+1, x+1]
                    ]
                    
                    if -1 in neighbors:
                        world_x = origin_x + (x + 0.5) * resolution
                        world_y = origin_y + (y + 0.5) * resolution
                        frontiers.append((world_x, world_y))
        
        if frontiers:
            clusters = self.cluster_frontiers(frontiers)
            return clusters
        
        return []
    
    def cluster_frontiers(self, points, cluster_distance=0.3):
        """Cluster frontier points"""
        if not points:
            return []
        
        points = list(points)
        clusters = []
        used = set()
        
        for i, point in enumerate(points):
            if i in used:
                continue
            
            cluster = [point]
            used.add(i)
            
            for j, other in enumerate(points):
                if j not in used:
                    dist = math.sqrt((point[0] - other[0])**2 + (point[1] - other[1])**2)
                    if dist < cluster_distance:
                        cluster.append(other)
                        used.add(j)
            
            if cluster:
                clusters.append(cluster)
        
        return clusters
    
    def select_best_frontier(self, frontier_clusters):
        """Select closest frontier"""
        if not frontier_clusters or self.robot_pose is None:
            return None
        
        robot_x = self.robot_pose.position.x
        robot_y = self.robot_pose.position.y
        
        best_frontier = None
        best_distance = float('inf')
        
        for cluster in frontier_clusters:
            cx = sum(p[0] for p in cluster) / len(cluster)
            cy = sum(p[1] for p in cluster) / len(cluster)
            
            dist = math.sqrt((robot_x - cx)**2 + (robot_y - cy)**2)
            if dist < best_distance:
                best_distance = dist
                best_frontier = (cx, cy)
        
        return best_frontier
    
    def publish_frontier_markers(self, frontier_clusters):
        """Visualize frontiers"""
        marker_array = MarkerArray()
        
        for i, cluster in enumerate(frontier_clusters):
            marker = Marker()
            marker.header.frame_id = 'map'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.id = i
            marker.type = Marker.POINTS
            marker.action = Marker.ADD
            marker.scale.x = 0.08
            marker.scale.y = 0.08
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0
            marker.color.a = 0.8
            
            for point in cluster:
                p = Point()
                p.x = point[0]
                p.y = point[1]
                marker.points.append(p)
            
            marker_array.markers.append(marker)
        
        self.frontier_marker_pub.publish(marker_array)
    
    def publish_goal_marker(self):
        """Visualize current goal"""
        if self.goal_frontier is None:
            return
        
        marker = Marker()
        marker.header.frame_id = 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.id = 999
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position.x = self.goal_frontier[0]
        marker.pose.position.y = self.goal_frontier[1]
        marker.pose.position.z = 0.0
        marker.scale.x = 0.2
        marker.scale.y = 0.2
        marker.scale.z = 0.2
        marker.color.g = 1.0
        marker.color.a = 0.8
        
        self.goal_marker_pub.publish(marker)
    
    def stop_robot(self):
        """Stop robot"""
        twist = Twist()
        self.cmd_vel_pub.publish(twist)
    
    def get_yaw(self, quat):
        """Extract yaw from quaternion"""
        x, y, z, w = quat.x, quat.y, quat.z, quat.w
        yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y**2 + z**2))
        return yaw
    
    def save_map(self):
        """Save map to package config/maps directory"""
        self.get_logger().info('💾 Saving map to package directory...')
        try:
            from ament_index_python.packages import get_package_share_directory
            
            # Get package share directory
            pkg_share_dir = get_package_share_directory('sweepi_exploration')
            
            # Create maps directory inside package
            maps_dir = os.path.join(pkg_share_dir, 'maps')
            os.makedirs(maps_dir, exist_ok=True)
            
            self.get_logger().info(f'📁 Saving to: {maps_dir}')
            
            # Run map saver
            cmd = f'ros2 run nav2_map_server map_saver_cli -f {maps_dir}/sweepi_map'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.get_logger().info(f'✅ Map saved successfully!')
                self.get_logger().info(f'📍 YAML: {maps_dir}/sweepi_map.yaml')
                self.get_logger().info(f'📍 PGM:  {maps_dir}/sweepi_map.pgm')
            else:
                self.get_logger().warn(f'⚠️  Map save failed: {result.stderr}')
        
        except Exception as e:
            self.get_logger().error(f'❌ Error saving map: {e}')

def main(args=None):
    rclpy.init(args=args)
    manager = SimpleExplorationManager()
    try:
        rclpy.spin(manager)
    except KeyboardInterrupt:
        manager.stop_robot()
        manager.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
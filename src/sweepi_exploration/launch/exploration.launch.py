"""
exploration.launch.py - SweePi Wavefront Frontier Exploration

Usage:
  ros2 launch sweepi_exploration exploration.launch.py
  ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=5
  ros2 launch sweepi_exploration exploration.launch.py \
    frontier_min_size:=5 cluster_distance:=2.0 exploration_frequency:=2.0
  ros2 launch sweepi_exploration exploration.launch.py max_velocity:=0.2
  ros2 launch sweepi_exploration exploration.launch.py \
    frontier_min_size:=5 max_velocity:=0.3 max_angular_velocity:=0.5
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Package directories
    sweepi_slam_dir = get_package_share_directory('sweepi_slam')

    # ============================================================
    # Frontier Detection Parameters
    # ============================================================
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time')

    declare_frontier_min_size = DeclareLaunchArgument(
        'frontier_min_size',
        default_value='6',
        description='Minimum cells per frontier cluster')

    declare_cluster_distance = DeclareLaunchArgument(
        'cluster_distance',
        default_value='2.0',
        description='Distance to cluster frontier cells (meters)')

    declare_exploration_frequency = DeclareLaunchArgument(
        'exploration_frequency',
        default_value='2.0',
        description='Exploration loop frequency (Hz)')

    declare_nav_timeout = DeclareLaunchArgument(
        'nav_timeout',
        default_value='30.0',
        description='Navigation timeout (seconds)')

    # ============================================================
    # Speed Control Parameters
    # ============================================================
    declare_max_velocity = DeclareLaunchArgument(
        'max_velocity',
        default_value='0.05',
        description='Maximum linear velocity (m/s). Safe: 0.1-0.5, Sim: 0.5-1.0')

    declare_max_angular_velocity = DeclareLaunchArgument(
        'max_angular_velocity',
        default_value='0.5',
        description='Maximum angular velocity (rad/s). Safe: 0.2-0.8, Sim: 0.8-2.0')

    declare_acceleration_limit = DeclareLaunchArgument(
        'acceleration_limit',
        default_value='0.3',
        description='Maximum acceleration (m/s²). Range: 0.1-0.5')

    # SLAM Toolbox
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(sweepi_slam_dir, 'launch', 'slam_toolbox.launch.py')
        ),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'autostart': 'true',
        }.items(),
    )

    # Wavefront Exploration Manager
    explorer = Node(
        package='sweepi_exploration',
        executable='wavefront_explorer.py',
        name='wavefront_explorer',
        output='screen',
        parameters=[
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'frontier_min_size': LaunchConfiguration('frontier_min_size'),
                'cluster_distance': LaunchConfiguration('cluster_distance'),
                'exploration_frequency': LaunchConfiguration('exploration_frequency'),
                'nav_timeout': LaunchConfiguration('nav_timeout'),
                'max_velocity': LaunchConfiguration('max_velocity'),
                'max_angular_velocity': LaunchConfiguration('max_angular_velocity'),
                'acceleration_limit': LaunchConfiguration('acceleration_limit'),
            }
        ],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_frontier_min_size,
        declare_cluster_distance,
        declare_exploration_frequency,
        declare_nav_timeout,
        declare_max_velocity,
        declare_max_angular_velocity,
        declare_acceleration_limit,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting SLAM...'),
        slam_launch,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting Wavefront Explorer...'),
        explorer,
    ])
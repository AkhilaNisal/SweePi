"""
exploration.launch.py - SweePi Wavefront Frontier Exploration

Usage:
  ros2 launch sweepi_exploration exploration.launch.py
  ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=5
  ros2 launch sweepi_exploration exploration.launch.py \
    frontier_min_size:=5 cluster_distance:=2.0 exploration_frequency:=2.0
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

    # Launch arguments with CORRECT types
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time')

    declare_frontier_min_size = DeclareLaunchArgument(
        'frontier_min_size',
        default_value='5',
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
            }
        ],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_frontier_min_size,
        declare_cluster_distance,
        declare_exploration_frequency,
        declare_nav_timeout,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting SLAM...'),
        slam_launch,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting Wavefront Explorer...'),
        explorer,
    ])

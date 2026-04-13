"""
exploration.launch.py - SweePi Wavefront Frontier Exploration
==============================================================
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

    # Launch arguments
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time')

    declare_frontier_min_size = DeclareLaunchArgument(
        'frontier_min_size',
        default_value='15',
        description='Minimum cells per frontier cluster')

    declare_cluster_distance = DeclareLaunchArgument(
        'cluster_distance',
        default_value='1.5',
        description='Distance to cluster frontier cells (meters)')

    declare_exploration_frequency = DeclareLaunchArgument(
        'exploration_frequency',
        default_value='3.0',
        description='Exploration loop frequency (Hz)')

    use_sim_time = LaunchConfiguration('use_sim_time')
    frontier_min_size = LaunchConfiguration('frontier_min_size')
    cluster_distance = LaunchConfiguration('cluster_distance')
    exploration_frequency = LaunchConfiguration('exploration_frequency')

    # SLAM Toolbox
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(sweepi_slam_dir, 'launch', 'slam_toolbox.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
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
                'use_sim_time': use_sim_time,
                'exploration_frequency': exploration_frequency,
                'frontier_min_size': frontier_min_size,
                'cluster_distance': cluster_distance,
                'nav_timeout': 30.0,
            }
        ],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_frontier_min_size,
        declare_cluster_distance,
        declare_exploration_frequency,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting SLAM...'),
        slam_launch,
        LogInfo(msg='[sweepi_exploration] 🚀 Starting Wavefront Explorer...'),
        explorer,
    ])

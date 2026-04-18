"""localization.launch.py - AMCL localization on pre-saved map"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )
    
    # Nav2 Map Server - proper RViz2 compatible map publishing
    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[
            {
                'yaml_filename': '/home/akhila-wedamestrige/SweePi/maps/swepi_exploration_map_20260418_021201.yaml',
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }
        ],
    )
    
    # AMCL node - provides map->base_link transform
    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'initial_pose.x': 0.0,
                'initial_pose.y': 0.0,
                'initial_pose.z': 0.0,
                'initial_pose.yaw': 0.0,
                'min_particles': 500,
                'max_particles': 2000,
                'pf_err': 0.05,
                'pf_z': 0.99,
                'laser_min_range': 0.12,
                'laser_max_range': 12.0,
                'scan_topic': '/scan',
                'map_topic': '/map',
                'odom_frame_id': 'odom',
                'base_frame_id': 'base_footprint',
                'global_frame_id': 'map',
                'transform_tolerance': 1.0,
            }
        ],
    )
    
    # Lifecycle manager - activates nodes
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'autostart': True,
                'node_names': ['map_server', 'amcl'],
            }
        ],
    )
    
    return LaunchDescription([
        declare_use_sim_time,
        
        LogInfo(msg='Starting Map Server and AMCL Localization'),
        LogInfo(msg='Map: swepi_exploration_map_20260418_021201'),
        
        map_server,
        amcl,
        
        # Delay lifecycle manager to allow nodes to initialize first
        TimerAction(
            period=2.0,
            actions=[lifecycle_manager],
        ),
    ])
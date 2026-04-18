"""navigation.launch.py - Simple navigation with pre-saved map"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    declare_map_name = DeclareLaunchArgument(
        'map_name',
        default_value='swepi_exploration_map_20260418_021201',
        description='Map name to load'
    )
    
    declare_nav_timeout = DeclareLaunchArgument(
        'nav_timeout',
        default_value='30.0',
        description='Navigation timeout in seconds'
    )
    
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )
    
    nav_goal_publisher = Node(
        package='sweepi_coverage',
        executable='nav_goal_publisher.py',
        name='nav_goal_publisher',
        output='screen',
        parameters=[
            {
                'map_name': LaunchConfiguration('map_name'),
                'nav_timeout': LaunchConfiguration('nav_timeout'),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }
        ],
    )
    
    return LaunchDescription([
        declare_map_name,
        declare_nav_timeout,
        declare_use_sim_time,
        
        LogInfo(msg='Starting SweePi Navigation with Pre-saved Map'),
        LogInfo(msg='Map: swepi_exploration_map_20260418_021201'),
        
        nav_goal_publisher,
    ])
"""
exploration.launch.py – SweePi autonomous exploration launcher
==============================================================

Launch order
------------
1. sweepi_slam  – SLAM Toolbox (map + TF tree)
2. Nav2 stack   – path planning + obstacle avoidance
3. Exploration manager – frontier detection + goal publishing

Usage
-----
  ros2 launch sweepi_exploration exploration.launch.py

Optional arguments
------------------
  use_sim_time:=true|false    (default: true)
  slam_params_file:=<path>    override SLAM params
  nav2_params_file:=<path>    override Nav2 params
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    # ------------------------------------------------------------------ #
    # Package directories                                                  #
    # ------------------------------------------------------------------ #
    exploration_dir = get_package_share_directory('sweepi_exploration')
    sweepi_slam_dir = get_package_share_directory('sweepi_slam')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    # ------------------------------------------------------------------ #
    # Default config paths                                                 #
    # ------------------------------------------------------------------ #
    default_nav2_params = os.path.join(
        exploration_dir, 'config', 'nav2_params.yaml')

    # ------------------------------------------------------------------ #
    # Launch arguments                                                     #
    # ------------------------------------------------------------------ #
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock')

    declare_slam_params = DeclareLaunchArgument(
        'slam_params_file',
        default_value='',
        description='Full path to SLAM Toolbox params (empty = sweepi_slam default)')

    declare_nav2_params = DeclareLaunchArgument(
        'nav2_params_file',
        default_value=default_nav2_params,
        description='Full path to Nav2 parameters file')

    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_params_file = LaunchConfiguration('slam_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')

    # ------------------------------------------------------------------ #
    # 1. SLAM – reuse sweepi_slam launch                                  #
    # ------------------------------------------------------------------ #
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(sweepi_slam_dir, 'launch', 'slam_toolbox.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
        }.items(),
    )

    # ------------------------------------------------------------------ #
    # 2. Nav2 – navigation stack                                           #
    # ------------------------------------------------------------------ #
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
            # map_subscribe_transient_local: needed when SLAM publishes map
            # via a transient-local publisher
            'use_lifecycle_mgr': 'true',
            'map_subscribe_transient_local': 'true',
        }.items(),
    )

    # ------------------------------------------------------------------ #
    # 3. Exploration manager                                               #
    # ------------------------------------------------------------------ #
    exploration_manager = Node(
        package='sweepi_exploration',
        executable='exploration_manager.py',
        name='exploration_manager',
        output='screen',
        parameters=[
            {
                'use_sim_time': use_sim_time,
                'frontier_min_size': 5,
                'cluster_distance': 0.5,
                'goal_tolerance': 0.3,
                'exploration_frequency': 3.0,
                'nav_timeout': 30.0,
            }
        ],
    )

    # ------------------------------------------------------------------ #
    # Launch description                                                   #
    # ------------------------------------------------------------------ #
    return LaunchDescription([
        declare_use_sim_time,
        declare_slam_params,
        declare_nav2_params,
        LogInfo(msg='[sweepi_exploration] Starting SLAM...'),
        slam_launch,
        LogInfo(msg='[sweepi_exploration] Starting Nav2...'),
        nav2_launch,
        LogInfo(msg='[sweepi_exploration] Starting Exploration Manager...'),
        exploration_manager,
    ])

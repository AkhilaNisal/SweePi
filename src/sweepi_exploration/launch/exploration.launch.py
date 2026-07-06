"""exploration.launch.py with proximity-based blocking"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    sweepi_slam_dir = get_package_share_directory('sweepi_slam')

    declare_map_name = DeclareLaunchArgument(
        'map_name',
        description='Required output map name. Used for automatic and manual map saves.')
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true')
    declare_frontier_min_size = DeclareLaunchArgument(
        'frontier_min_size', default_value='3')
    declare_cluster_distance = DeclareLaunchArgument(
        'cluster_distance', default_value='1.2') # 1.2
    declare_min_unknown_region_area_m2 = DeclareLaunchArgument(
        'min_unknown_region_area_m2', default_value='0.25',
        description='Ignore frontier regions exposing less unknown area than this')
    declare_exploration_frequency = DeclareLaunchArgument(
        'exploration_frequency', default_value='3.0')
    declare_nav_timeout = DeclareLaunchArgument(
        'nav_timeout', default_value='15.0')
    declare_max_velocity = DeclareLaunchArgument(
        'max_velocity', default_value='0.1')
    declare_max_angular_velocity = DeclareLaunchArgument(
        'max_angular_velocity', default_value='0.5')
    declare_acceleration_limit = DeclareLaunchArgument(
        'acceleration_limit', default_value='0.1')
    declare_max_attempts_per_frontier = DeclareLaunchArgument(
        'max_attempts_per_frontier', default_value='2')
    declare_max_consecutive_timeouts = DeclareLaunchArgument(
        'max_consecutive_timeouts', default_value='4')
    declare_max_total_timeouts = DeclareLaunchArgument(
        'max_total_timeouts', default_value='35')
    declare_max_exploration_time = DeclareLaunchArgument(
        'max_exploration_time', default_value='600')
    declare_goal_offset_distance = DeclareLaunchArgument(
        'goal_offset_distance', default_value='0.6',
        description='Offset goal from frontier')
    declare_robot_radius = DeclareLaunchArgument(
        'robot_radius', default_value='0.3')
    declare_safety_margin = DeclareLaunchArgument(
        'safety_margin', default_value='0.15')
    
    # NEW: Proximity-based blocking parameter
    declare_unreachable_region_radius = DeclareLaunchArgument(
        'unreachable_region_radius', default_value='0.6',
        description='Block all frontiers within this distance of failed frontier')
    declare_failed_frontier_retry_sec = DeclareLaunchArgument(
        'failed_frontier_retry_sec', default_value='30.0',
        description='Retry failed frontier regions after this cooldown')
    declare_completion_retry_cycles = DeclareLaunchArgument(
        'completion_retry_cycles', default_value='3',
        description='Final retry sweeps before accepting remaining blocked frontiers')
    declare_frontier_goal_search_radius = DeclareLaunchArgument(
        'frontier_goal_search_radius', default_value='1.4',
        description='Search radius for obstacle-aware frontier viewpoints')
    declare_frontier_goal_unknown_radius = DeclareLaunchArgument(
        'frontier_goal_unknown_radius', default_value='0.8',
        description='Unknown-cell radius used to score frontier viewpoints')
    declare_start_mode = DeclareLaunchArgument(
        'start_mode', default_value='auto',
        description='Initial exploration mode: auto, manual, or stopped')
    declare_cmd_vel_topic = DeclareLaunchArgument(
        'cmd_vel_topic', default_value='/cmd_vel',
        description='Velocity topic used by manual teleop and stop commands')

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(sweepi_slam_dir, 'launch', 'slam_toolbox.launch.py')
        ),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'autostart': 'true',
        }.items(),
    )

    explorer = Node(
        package='sweepi_exploration',
        executable='wavefront_explorer.py',
        name='wavefront_explorer',
        output='screen',
        parameters=[
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'map_name': LaunchConfiguration('map_name'),
                'frontier_min_size': LaunchConfiguration('frontier_min_size'),
                'cluster_distance': LaunchConfiguration('cluster_distance'),
                'min_unknown_region_area_m2': LaunchConfiguration('min_unknown_region_area_m2'),
                'exploration_frequency': LaunchConfiguration('exploration_frequency'),
                'nav_timeout': LaunchConfiguration('nav_timeout'),
                'max_velocity': LaunchConfiguration('max_velocity'),
                'max_angular_velocity': LaunchConfiguration('max_angular_velocity'),
                'acceleration_limit': LaunchConfiguration('acceleration_limit'),
                'max_attempts_per_frontier': LaunchConfiguration('max_attempts_per_frontier'),
                'max_consecutive_timeouts': LaunchConfiguration('max_consecutive_timeouts'),
                'max_total_timeouts': LaunchConfiguration('max_total_timeouts'),
                'max_exploration_time': LaunchConfiguration('max_exploration_time'),
                'goal_offset_distance': LaunchConfiguration('goal_offset_distance'),
                'robot_radius': LaunchConfiguration('robot_radius'),
                'safety_margin': LaunchConfiguration('safety_margin'),
                'unreachable_region_radius': LaunchConfiguration('unreachable_region_radius'),
                'failed_frontier_retry_sec': LaunchConfiguration('failed_frontier_retry_sec'),
                'completion_retry_cycles': LaunchConfiguration('completion_retry_cycles'),
                'frontier_goal_search_radius': LaunchConfiguration('frontier_goal_search_radius'),
                'frontier_goal_unknown_radius': LaunchConfiguration('frontier_goal_unknown_radius'),
                'start_mode': LaunchConfiguration('start_mode'),
                'cmd_vel_topic': LaunchConfiguration('cmd_vel_topic'),
            }
        ],
    )

    return LaunchDescription([
        declare_map_name,
        declare_use_sim_time,
        declare_frontier_min_size,
        declare_cluster_distance,
        declare_min_unknown_region_area_m2,
        declare_exploration_frequency,
        declare_nav_timeout,
        declare_max_velocity,
        declare_max_angular_velocity,
        declare_acceleration_limit,
        declare_max_attempts_per_frontier,
        declare_max_consecutive_timeouts,
        declare_max_total_timeouts,
        declare_max_exploration_time,
        declare_goal_offset_distance,
        declare_robot_radius,
        declare_safety_margin,
        declare_unreachable_region_radius,
        declare_failed_frontier_retry_sec,
        declare_completion_retry_cycles,
        declare_frontier_goal_search_radius,
        declare_frontier_goal_unknown_radius,
        declare_start_mode,
        declare_cmd_vel_topic,
        
        LogInfo(msg='🚀 STARTING SWEEPI AUTONOMOUS EXPLORATION'),
        LogInfo(msg='💾 Map name: ${map_name}'),
        LogInfo(msg='📏 Proximity-based blocking: ${unreachable_region_radius}m'),
        LogInfo(msg='🔁 Completion retry sweeps: ${completion_retry_cycles}'),
        LogInfo(msg='🎮 Exploration mode: ${start_mode}'),
        
        slam_launch,
        explorer,
    ])

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
        'frontier_min_size', default_value='8')
    declare_cluster_distance = DeclareLaunchArgument(
        'cluster_distance', default_value='1.2') # 1.2
    declare_exploration_frequency = DeclareLaunchArgument(
        'exploration_frequency', default_value='1.0')
    declare_nav_timeout = DeclareLaunchArgument(
        'nav_timeout', default_value='15.0')
    declare_max_frontier_candidates = DeclareLaunchArgument(
        'max_frontier_candidates', default_value='0')
    declare_no_frontier_finish_count = DeclareLaunchArgument(
        'no_frontier_finish_count', default_value='10')
    declare_robot_base_frame = DeclareLaunchArgument(
        'robot_base_frame', default_value='base_footprint')
    declare_far_exploration_goal_count = DeclareLaunchArgument(
        'far_exploration_goal_count', default_value='8')
    declare_far_min_distance = DeclareLaunchArgument(
        'far_min_distance', default_value='1.0')
    declare_far_distance_weight = DeclareLaunchArgument(
        'far_distance_weight', default_value='80.0')
    declare_frontier_size_weight = DeclareLaunchArgument(
        'frontier_size_weight', default_value='2.0')
    declare_safe_goal_clearance_weight = DeclareLaunchArgument(
        'safe_goal_clearance_weight', default_value='250.0')
    declare_cleanup_size_weight = DeclareLaunchArgument(
        'cleanup_size_weight', default_value='5.0')
    declare_cleanup_distance_weight = DeclareLaunchArgument(
        'cleanup_distance_weight', default_value='20.0')
    declare_max_velocity = DeclareLaunchArgument(
        'max_velocity', default_value='0.1')
    declare_max_angular_velocity = DeclareLaunchArgument(
        'max_angular_velocity', default_value='0.5')
    declare_acceleration_limit = DeclareLaunchArgument(
        'acceleration_limit', default_value='0.1')
    declare_max_attempts_per_frontier = DeclareLaunchArgument(
        'max_attempts_per_frontier', default_value='3')
    declare_max_consecutive_timeouts = DeclareLaunchArgument(
        'max_consecutive_timeouts', default_value='2')
    declare_max_total_timeouts = DeclareLaunchArgument(
        'max_total_timeouts', default_value='10')
    declare_max_exploration_time = DeclareLaunchArgument(
        'max_exploration_time', default_value='600')
    declare_goal_offset_distance = DeclareLaunchArgument(
        'goal_offset_distance', default_value='0.45',
        description='Offset goal from frontier')
    declare_robot_radius = DeclareLaunchArgument(
        'robot_radius', default_value='0.3')
    declare_safety_margin = DeclareLaunchArgument(
        'safety_margin', default_value='0.15')
    
    # NEW: Proximity-based blocking parameter
    declare_unreachable_region_radius = DeclareLaunchArgument(
        'unreachable_region_radius', default_value='0.4',
        description='Block all frontiers within this distance of failed frontier')
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
                'exploration_frequency': LaunchConfiguration('exploration_frequency'),
                'nav_timeout': LaunchConfiguration('nav_timeout'),
                'max_frontier_candidates': LaunchConfiguration('max_frontier_candidates'),
                'no_frontier_finish_count': LaunchConfiguration('no_frontier_finish_count'),
                'robot_base_frame': LaunchConfiguration('robot_base_frame'),
                'far_exploration_goal_count': LaunchConfiguration('far_exploration_goal_count'),
                'far_min_distance': LaunchConfiguration('far_min_distance'),
                'far_distance_weight': LaunchConfiguration('far_distance_weight'),
                'frontier_size_weight': LaunchConfiguration('frontier_size_weight'),
                'safe_goal_clearance_weight': LaunchConfiguration('safe_goal_clearance_weight'),
                'cleanup_size_weight': LaunchConfiguration('cleanup_size_weight'),
                'cleanup_distance_weight': LaunchConfiguration('cleanup_distance_weight'),
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
        declare_exploration_frequency,
        declare_nav_timeout,
        declare_max_frontier_candidates,
        declare_no_frontier_finish_count,
        declare_robot_base_frame,
        declare_far_exploration_goal_count,
        declare_far_min_distance,
        declare_far_distance_weight,
        declare_frontier_size_weight,
        declare_safe_goal_clearance_weight,
        declare_cleanup_size_weight,
        declare_cleanup_distance_weight,
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
        declare_start_mode,
        declare_cmd_vel_topic,
        
        LogInfo(msg='🚀 STARTING SWEEPI AUTONOMOUS EXPLORATION'),
        LogInfo(msg='💾 Map name: ${map_name}'),
        LogInfo(msg='📏 Proximity-based blocking: ${unreachable_region_radius}m'),
        LogInfo(msg='🎮 Exploration mode: ${start_mode}'),
        
        slam_launch,
        explorer,
    ])

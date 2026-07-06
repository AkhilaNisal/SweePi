"""Launch the SweePi exploration task stack."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    exploration_dir = get_package_share_directory('sweepi_exploration')
    default_nav2_params_file = os.path.join(
        exploration_dir,
        'config',
        'nav2_exploration_rpi_params.yaml',
    )

    map_name = LaunchConfiguration('map_name')
    use_sim_time = LaunchConfiguration('use_sim_time')
    start_mode = LaunchConfiguration('start_mode')
    nav2_params_file = LaunchConfiguration('nav2_params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'map_name',
            description='Required output map name for exploration saves',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'start_mode',
            default_value='auto',
            description='Initial exploration mode: auto, manual, or stopped',
        ),
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=default_nav2_params_file,
            description='Nav2 params file tuned for exploration on the real robot',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
            ),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'params_file': nav2_params_file,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(exploration_dir, 'launch', 'exploration.launch.py')
            ),
            launch_arguments={
                'map_name': map_name,
                'use_sim_time': use_sim_time,
                'start_mode': start_mode,
            }.items(),
        ),
    ])

"""Launch the SweePi coverage task stack."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    coverage_dir = get_package_share_directory('sweepi_coverage')
    default_coverage_params_file = os.path.join(
        coverage_dir,
        'config',
        'coverage_follow_path_params.yaml',
    )

    map_name = LaunchConfiguration('map_name')
    use_sim_time = LaunchConfiguration('use_sim_time')
    auto_start = LaunchConfiguration('auto_start')
    coverage_params_file = LaunchConfiguration('coverage_params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'map_name',
            description='Required map name to load from ~/SweePi/maps/<map_name>.yaml',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'auto_start',
            default_value='false',
            description='Start coverage automatically when path is ready',
        ),
        DeclareLaunchArgument(
            'coverage_params_file',
            default_value=default_coverage_params_file,
            description='Coverage tracker/planner/FollowPath executor params file',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(coverage_dir, 'launch', 'nav2_bringup.launch.py')
            ),
            launch_arguments={
                'map_name': map_name,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(coverage_dir, 'launch', 'coverage_follow_path.launch.py')
            ),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'auto_start': auto_start,
                'params_file': coverage_params_file,
            }.items(),
        ),
    ])

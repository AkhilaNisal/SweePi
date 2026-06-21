import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup_share = get_package_share_directory('sweepi_bringup')
    coverage_share = get_package_share_directory('sweepi_coverage')

    robot_bringup_launch = os.path.join(
        bringup_share,
        'launch',
        'robot_bringup.launch.py',
    )
    nav2_launch = os.path.join(coverage_share, 'launch', 'nav2_bringup.launch.py')
    coverage_launch = os.path.join(
        coverage_share,
        'launch',
        'coverage_follow_path.launch.py',
    )

    map_yaml = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    auto_start = LaunchConfiguration('auto_start')

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value='',
            description='Full path to the map yaml used by Nav2',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'auto_start',
            default_value='false',
            description='Start coverage automatically when a valid path is received',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(robot_bringup_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_launch),
            launch_arguments={
                'map': map_yaml,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(coverage_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'auto_start': auto_start,
            }.items(),
        ),
    ])

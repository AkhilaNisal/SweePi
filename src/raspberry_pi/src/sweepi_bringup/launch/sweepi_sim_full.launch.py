import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)


def generate_launch_description():
    bringup_share = get_package_share_directory('sweepi_bringup')
    coverage_share = get_package_share_directory('sweepi_coverage')

    gazebo_launch = os.path.join(bringup_share, 'launch', 'gazebo.launch.xml')
    nav2_launch = os.path.join(coverage_share, 'launch', 'nav2_bringup.launch.py')
    coverage_launch = os.path.join(
        coverage_share,
        'launch',
        'coverage_follow_path.launch.py',
    )

    return LaunchDescription([
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(gazebo_launch),
            launch_arguments={
                'use_sim_time': 'true',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_launch),
            launch_arguments={
                'use_sim_time': 'true',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(coverage_launch),
            launch_arguments={
                'use_sim_time': 'true',
                'auto_start': 'false',
            }.items(),
        ),
    ])

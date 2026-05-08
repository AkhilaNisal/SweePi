import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('sweepi_coverage')
    default_params_file = os.path.join(
        pkg_share,
        'config',
        'coverage_params.yaml',
    )

    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='Path to coverage-system parameter file',
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_tracker_node.py',
            name='coverage_tracker_node',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_planner_node.py',
            name='coverage_planner_node',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_executor_node.py',
            name='coverage_executor_node',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_manager_node.py',
            name='coverage_manager_node',
            output='screen',
            parameters=[params_file],
        ),
    ])

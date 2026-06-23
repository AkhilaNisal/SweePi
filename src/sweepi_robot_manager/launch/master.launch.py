"""Top-level launch for the SweePi robot manager."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    bringup_dir = get_package_share_directory('sweepi_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_sim = LaunchConfiguration('launch_sim')
    headless = LaunchConfiguration('headless')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'launch_sim',
            default_value='true',
            description='Launch Gazebo/robot bringup from sweepi_bringup',
        ),
        DeclareLaunchArgument(
            'headless',
            default_value='false',
            description='Run Gazebo without GUI when launch_sim is true',
        ),
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(bringup_dir, 'launch', 'gazebo.launch.xml')
            ),
            condition=IfCondition(launch_sim),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'headless': headless,
            }.items(),
        ),
        Node(
            package='sweepi_robot_manager',
            executable='sweepi_robot_manager_node.py',
            name='sweepi_robot_manager',
            output='screen',
            parameters=[
                {
                    'use_sim_time': PythonExpression([
                        "'",
                        use_sim_time,
                        "' == 'true'",
                    ]),
                }
            ],
        ),
    ])

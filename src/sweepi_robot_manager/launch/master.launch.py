"""Top-level launch for the SweePi robot manager."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    bringup_dir = get_package_share_directory('sweepi_bringup')
    api_bridge_dir = get_package_share_directory('sweepi_api_bridge')

    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_sim = LaunchConfiguration('launch_sim')
    headless = LaunchConfiguration('headless')
    launch_api_bridge = LaunchConfiguration('launch_api_bridge')
    api_host = LaunchConfiguration('api_host')
    api_port = LaunchConfiguration('api_port')

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
        DeclareLaunchArgument(
            'launch_api_bridge',
            default_value='false',
            description='Launch sweepi_api_bridge HTTP server',
        ),
        DeclareLaunchArgument(
            'api_host',
            default_value='0.0.0.0',
            description='HTTP API bind host when launch_api_bridge is true',
        ),
        DeclareLaunchArgument(
            'api_port',
            default_value='8080',
            description='HTTP API bind port when launch_api_bridge is true',
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(api_bridge_dir, 'launch', 'api_bridge.launch.py')
            ),
            condition=IfCondition(launch_api_bridge),
            launch_arguments={
                'api_host': api_host,
                'api_port': api_port,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
    ])

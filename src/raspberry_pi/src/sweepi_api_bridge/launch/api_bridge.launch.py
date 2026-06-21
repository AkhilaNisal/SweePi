from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'api_host',
            default_value='0.0.0.0',
            description='LAN API bind host',
        ),
        DeclareLaunchArgument(
            'api_port',
            default_value='8080',
            description='LAN API HTTP port',
        ),
        DeclareLaunchArgument(
            'ws_port',
            default_value='8765',
            description='LAN API websocket port',
        ),
        Node(
            package='sweepi_api_bridge',
            executable='api_bridge_node',
            name='api_bridge_node',
            output='screen',
            parameters=[
                {
                    'api_host': LaunchConfiguration('api_host'),
                    'api_port': LaunchConfiguration('api_port'),
                    'ws_port': LaunchConfiguration('ws_port'),
                }
            ],
        ),
    ])

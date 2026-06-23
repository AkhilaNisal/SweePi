"""Launch the SweePi HTTP API bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    api_host = LaunchConfiguration('api_host')
    api_port = LaunchConfiguration('api_port')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument(
            'api_host',
            default_value='0.0.0.0',
            description='HTTP API bind host',
        ),
        DeclareLaunchArgument(
            'api_port',
            default_value='8080',
            description='HTTP API bind port',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock',
        ),
        Node(
            package='sweepi_api_bridge',
            executable='api_bridge_node',
            name='sweepi_api_bridge',
            output='screen',
            parameters=[
                {
                    'api_host': api_host,
                    'api_port': api_port,
                    'use_sim_time': PythonExpression([
                        "'",
                        use_sim_time,
                        "' == 'true'",
                    ]),
                }
            ],
        ),
    ])

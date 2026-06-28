import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_dir = get_package_share_directory('sweepi_base_driver')
    default_params = os.path.join(package_dir, 'config', 'base_driver_params.yaml')

    params_file = LaunchConfiguration('params_file')
    serial_port = LaunchConfiguration('serial_port')
    baud_rate = LaunchConfiguration('baud_rate')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params,
            description='Base driver parameter file',
        ),
        DeclareLaunchArgument(
            'serial_port',
            default_value='/dev/ttyACM0',
            description='STM32 serial device',
        ),
        DeclareLaunchArgument(
            'baud_rate',
            default_value='115200',
            description='STM32 serial baud rate',
        ),
        Node(
            package='sweepi_base_driver',
            executable='base_driver_node',
            name='base_driver_node',
            output='screen',
            parameters=[
                params_file,
                {
                    'serial_port': serial_port,
                    'baud_rate': baud_rate,
                },
            ],
        ),
    ])

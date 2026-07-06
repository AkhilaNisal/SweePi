"""Top-level launch for the SweePi robot manager."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def as_bool(value):
    return PythonExpression(["'", value, "' == 'true'"])


def generate_launch_description():
    bringup_dir = get_package_share_directory('sweepi_bringup')
    real_bringup_dir = get_package_share_directory('sweepi_real_bringup')
    api_bridge_dir = get_package_share_directory('sweepi_api_bridge')

    sim_launch = os.path.join(bringup_dir, 'launch', 'gazebo.launch.xml')
    hardware_launch = os.path.join(
        real_bringup_dir,
        'launch',
        'hardware_debug.launch.py',
    )
    api_bridge_launch = os.path.join(api_bridge_dir, 'launch', 'api_bridge.launch.py')
    rviz_config_path = os.path.join(bringup_dir, 'rviz', 'urdf_config.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_sim = LaunchConfiguration('launch_sim')
    launch_hardware = LaunchConfiguration('launch_hardware')
    launch_temp_hardware = LaunchConfiguration('launch_temp_hardware')
    launch_base = LaunchConfiguration('launch_base')
    launch_ekf = LaunchConfiguration('launch_ekf')
    launch_robot_description = LaunchConfiguration('launch_robot_description')
    launch_lidar = LaunchConfiguration('launch_lidar')
    headless = LaunchConfiguration('headless')
    launch_rviz = LaunchConfiguration('launch_rviz')
    launch_api_bridge = LaunchConfiguration('launch_api_bridge')
    api_host = LaunchConfiguration('api_host')
    api_port = LaunchConfiguration('api_port')
    base_serial_port = LaunchConfiguration('base_serial_port')
    base_baud_rate = LaunchConfiguration('base_baud_rate')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_baud_rate = LaunchConfiguration('lidar_baud_rate')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')
    hardware_enabled = PythonExpression([
        "'",
        launch_hardware,
        "' == 'true' or '",
        launch_temp_hardware,
        "' == 'true'",
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'launch_sim',
            default_value='false',
            description='Launch Gazebo/robot bringup from sweepi_bringup',
        ),
        DeclareLaunchArgument(
            'launch_hardware',
            default_value='true',
            description='Launch real STM32 base driver, EKF, robot description, and optional lidar',
        ),
        DeclareLaunchArgument(
            'launch_temp_hardware',
            default_value='false',
            description='Deprecated compatibility alias for launch_hardware',
        ),
        DeclareLaunchArgument(
            'launch_base',
            default_value='true',
            description='Launch STM32 base driver when launch_hardware is true',
        ),
        DeclareLaunchArgument(
            'launch_ekf',
            default_value='true',
            description='Launch robot_localization EKF when launch_hardware is true',
        ),
        DeclareLaunchArgument(
            'launch_robot_description',
            default_value='true',
            description='Launch robot_state_publisher when launch_hardware is true',
        ),
        DeclareLaunchArgument(
            'launch_lidar',
            default_value='true',
            description='Launch real RPLIDAR when launch_hardware is true',
        ),
        DeclareLaunchArgument(
            'base_serial_port',
            default_value='/dev/ttyAMA0',
            description='STM32 serial device',
        ),
        DeclareLaunchArgument(
            'base_baud_rate',
            default_value='115200',
            description='STM32 serial baud rate',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/ttyUSB0',
            description='RPLIDAR serial device',
        ),
        DeclareLaunchArgument(
            'lidar_baud_rate',
            default_value='460800',
            description='SLLidar serial baud rate',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='lidar_link',
            description='LaserScan frame id',
        ),
        DeclareLaunchArgument(
            'launch_rviz',
            default_value='true',
            description='Launch RViz when launch_hardware is true',
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
            AnyLaunchDescriptionSource(sim_launch),
            condition=IfCondition(launch_sim),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'headless': headless,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(hardware_launch),
            condition=IfCondition(hardware_enabled),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'launch_base': launch_base,
                'launch_ekf': launch_ekf,
                'publish_robot_description': launch_robot_description,
                'launch_lidar': launch_lidar,
                'base_serial_port': base_serial_port,
                'base_baud_rate': base_baud_rate,
                'lidar_serial_port': lidar_serial_port,
                'lidar_baud_rate': lidar_baud_rate,
                'lidar_frame_id': lidar_frame_id,
            }.items(),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            condition=IfCondition(PythonExpression([
                "(",
                hardware_enabled,
                ") and '",
                launch_rviz,
                "' == 'true'",
            ])),
            arguments=['-d', rviz_config_path],
            parameters=[
                {
                    'use_sim_time': as_bool(use_sim_time),
                }
            ],
        ),
        Node(
            package='sweepi_robot_manager',
            executable='sweepi_robot_manager_node.py',
            name='sweepi_robot_manager',
            output='screen',
            parameters=[
                {
                    'use_sim_time': as_bool(use_sim_time),
                }
            ],
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(api_bridge_launch),
            condition=IfCondition(launch_api_bridge),
            launch_arguments={
                'api_host': api_host,
                'api_port': api_port,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
    ])

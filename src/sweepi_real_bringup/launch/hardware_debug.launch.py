import os

from ament_index_python.packages import get_package_share_directory
from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    base_driver_dir = get_package_share_directory('sweepi_base_driver')
    state_estimation_dir = get_package_share_directory('sweepi_state_estimation')
    lidar_dir = get_package_share_directory('sllidar_ros2')
    description_dir = get_package_share_path('sweepi_description')

    base_launch = os.path.join(base_driver_dir, 'launch', 'base_driver.launch.py')
    ekf_launch = os.path.join(state_estimation_dir, 'launch', 'ekf.launch.py')
    default_ekf_params = os.path.join(state_estimation_dir, 'config', 'ekf.yaml')
    lidar_launch = os.path.join(lidar_dir, 'launch', 'sllidar_c1_launch.py')
    urdf_path = os.path.join(description_dir, 'urdf', 'sweepi.urdf.xacro')

    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_base = LaunchConfiguration('launch_base')
    launch_ekf = LaunchConfiguration('launch_ekf')
    launch_lidar = LaunchConfiguration('launch_lidar')
    publish_robot_description = LaunchConfiguration('publish_robot_description')
    base_serial_port = LaunchConfiguration('base_serial_port')
    ekf_params_file = LaunchConfiguration('ekf_params_file')
    base_baud_rate = LaunchConfiguration('base_baud_rate')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_baud_rate = LaunchConfiguration('lidar_baud_rate')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')

    robot_description = ParameterValue(Command(['xacro ', str(urdf_path)]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'launch_base',
            default_value='true',
            description='Launch STM32 base driver',
        ),
        DeclareLaunchArgument(
            'launch_ekf',
            default_value='true',
            description='Launch robot_localization EKF',
        ),
        DeclareLaunchArgument(
            'launch_lidar',
            default_value='true',
            description='Launch the real RPLIDAR driver',
        ),
        DeclareLaunchArgument(
            'publish_robot_description',
            default_value='true',
            description='Launch robot_state_publisher for fixed hardware frames',
        ),
        DeclareLaunchArgument(
            'ekf_params_file',
            default_value=default_ekf_params,
            description='robot_localization EKF parameter file',
        ),
        DeclareLaunchArgument(
            'base_serial_port',
            default_value='/dev/ttyACM0',
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(base_launch),
            condition=IfCondition(launch_base),
            launch_arguments={
                'serial_port': base_serial_port,
                'baud_rate': base_baud_rate,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(ekf_launch),
            condition=IfCondition(launch_ekf),
            launch_arguments={
                'params_file': ekf_params_file,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(lidar_launch),
            condition=IfCondition(launch_lidar),
            launch_arguments={
                'serial_port': lidar_serial_port,
                'serial_baudrate': lidar_baud_rate,
                'frame_id': lidar_frame_id,
            }.items(),
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            condition=IfCondition(publish_robot_description),
            parameters=[
                {
                    'robot_description': robot_description,
                    'use_sim_time': PythonExpression([
                        "'",
                        use_sim_time,
                        "' == 'true'",
                    ]),
                },
            ],
        ),
    ])

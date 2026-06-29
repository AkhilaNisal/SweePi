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
from launch_ros.substitutions import FindPackageShare


def as_bool(value):
    return PythonExpression(["'", value, "' == 'true'"])


def generate_launch_description():
    temp_hardware_dir = get_package_share_directory('sweepi_temp_rpi_hardware')
    state_estimation_dir = get_package_share_directory('sweepi_state_estimation')
    description_dir = get_package_share_path('sweepi_description')

    temp_launch = os.path.join(temp_hardware_dir, 'launch', 'temp_rpi_hardware.launch.py')
    ekf_launch = os.path.join(state_estimation_dir, 'launch', 'ekf.launch.py')
    urdf_path = os.path.join(description_dir, 'urdf', 'sweepi.urdf.xacro')

    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_temp_hardware = LaunchConfiguration('launch_temp_hardware')
    launch_ekf = LaunchConfiguration('launch_ekf')
    launch_robot_description = LaunchConfiguration('launch_robot_description')
    launch_lidar = LaunchConfiguration('launch_lidar')
    temp_params_file = LaunchConfiguration('temp_params_file')
    dry_run_gpio = LaunchConfiguration('dry_run_gpio')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_baud_rate = LaunchConfiguration('lidar_baud_rate')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')

    robot_description = ParameterValue(Command(['xacro ', str(urdf_path)]), value_type=str)
    lidar_launch = [
        FindPackageShare('sllidar_ros2'),
        '/launch/sllidar_a1_launch.py',
    ]

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'launch_temp_hardware',
            default_value='true',
            description='Launch the temporary Raspberry Pi hardware layer',
        ),
        DeclareLaunchArgument(
            'launch_ekf',
            default_value='true',
            description='Launch robot_localization EKF',
        ),
        DeclareLaunchArgument(
            'launch_robot_description',
            default_value='true',
            description='Launch robot_state_publisher for fixed hardware frames',
        ),
        DeclareLaunchArgument(
            'launch_lidar',
            default_value='false',
            description='Launch the real RPLIDAR driver',
        ),
        DeclareLaunchArgument(
            'temp_params_file',
            default_value=os.path.join(temp_hardware_dir, 'config', 'temp_rpi_hardware.yaml'),
            description='Temporary RPi hardware parameter file',
        ),
        DeclareLaunchArgument(
            'dry_run_gpio',
            default_value='false',
            description='Simulate step counts without accessing GPIO',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/ttyUSB0',
            description='RPLIDAR serial device',
        ),
        DeclareLaunchArgument(
            'lidar_baud_rate',
            default_value='115200',
            description='RPLIDAR serial baud rate',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='lidar_link',
            description='LaserScan frame id',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(temp_launch),
            condition=IfCondition(launch_temp_hardware),
            launch_arguments={
                'params_file': temp_params_file,
                'use_sim_time': use_sim_time,
                'dry_run_gpio': dry_run_gpio,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(ekf_launch),
            condition=IfCondition(launch_ekf),
            launch_arguments={
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
            condition=IfCondition(launch_robot_description),
            parameters=[
                {
                    'robot_description': robot_description,
                    'use_sim_time': as_bool(use_sim_time),
                },
            ],
        ),
    ])

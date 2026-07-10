import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def as_bool(value):
    return PythonExpression(["'", value, "' == 'true'"])


def generate_launch_description():
    package_dir = get_package_share_directory('sweepi_temp_rpi_hardware')
    default_params = os.path.join(package_dir, 'config', 'temp_rpi_hardware.yaml')

    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    launch_steppers = LaunchConfiguration('launch_steppers')
    launch_wheel_odom = LaunchConfiguration('launch_wheel_odom')
    launch_imu = LaunchConfiguration('launch_imu')
    launch_cleaning_motors = LaunchConfiguration('launch_cleaning_motors')
    dry_run_gpio = LaunchConfiguration('dry_run_gpio')

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='RPi hardware parameter file'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('launch_steppers', default_value='true'),
        DeclareLaunchArgument('launch_wheel_odom', default_value='true'),
        DeclareLaunchArgument('launch_imu', default_value='true'),
        DeclareLaunchArgument('launch_cleaning_motors', default_value='false',
                              description='Launch vacuum and brush GPIO controller'),
        DeclareLaunchArgument('dry_run_gpio', default_value='false'),
        Node(
            package='sweepi_temp_rpi_hardware', executable='stepper_driver_node',
            name='sweepi_temp_stepper_driver', output='screen',
            condition=IfCondition(launch_steppers),
            parameters=[params_file, {'use_sim_time': as_bool(use_sim_time),
                                      'dry_run_gpio': as_bool(dry_run_gpio)}],
        ),
        Node(
            package='sweepi_temp_rpi_hardware', executable='stepper_ticks_to_odom_node',
            name='sweepi_temp_stepper_odom', output='screen',
            condition=IfCondition(launch_wheel_odom),
            parameters=[params_file, {'use_sim_time': as_bool(use_sim_time)}],
        ),
        Node(
            package='sweepi_temp_rpi_hardware', executable='mpu6050_imu_node',
            name='sweepi_temp_mpu6050', output='screen', condition=IfCondition(launch_imu),
            parameters=[params_file, {'use_sim_time': as_bool(use_sim_time)}],
        ),
        Node(
            package='sweepi_temp_rpi_hardware', executable='cleaning_motor_controller_node',
            name='cleaning_motor_controller', output='screen',
            condition=IfCondition(launch_cleaning_motors),
            parameters=[params_file, {'use_sim_time': as_bool(use_sim_time),
                                      'dry_run_gpio': as_bool(dry_run_gpio)}],
        ),
    ])

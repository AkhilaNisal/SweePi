import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def validate_params_file(context):
    params_path = LaunchConfiguration('params_file').perform(context)
    if not os.path.isfile(params_path):
        raise RuntimeError(f'EKF parameter file does not exist: {params_path}')

    with open(params_path, 'r', encoding='utf-8') as stream:
        params_text = stream.read()

    required_entries = ('ekf_filter_node:', 'odom0:', 'imu0:')
    missing_entries = [entry for entry in required_entries if entry not in params_text]
    if missing_entries:
        missing_text = ', '.join(missing_entries)
        raise RuntimeError(
            f'EKF parameter file {params_path} is missing required entries: {missing_text}'
        )

    return []


def generate_launch_description():
    package_dir = get_package_share_directory('sweepi_state_estimation')
    default_params = os.path.join(package_dir, 'config', 'ekf.yaml')

    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params,
            description='robot_localization EKF parameter file',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock',
        ),
        OpaqueFunction(function=validate_params_file),
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[
                params_file,
                {
                    'use_sim_time': PythonExpression([
                        "'",
                        use_sim_time,
                        "' == 'true'",
                    ]),
                },
            ],
            remappings=[
                ('odometry/filtered', '/odom'),
            ],
        ),
    ])

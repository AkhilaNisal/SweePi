import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory('sweepi_coverage')
    default_params_file = os.path.join(
        pkg_share,
        'config',
        'coverage_follow_path_params.yaml',
    )

    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    auto_start = LaunchConfiguration('auto_start')
    require_robot_near_start = LaunchConfiguration('require_robot_near_start')
    max_start_distance_m = LaunchConfiguration('max_start_distance_m')
    use_robot_arm = LaunchConfiguration('use_robot_arm')

    use_sim_time_param = {
        'use_sim_time': ParameterValue(use_sim_time, value_type=bool),
    }

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_robot_arm',
            default_value='false',
            description='Enable rear robot-arm handling for eligible obstacles',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='Path to FollowPath coverage parameter file',
        ),
        DeclareLaunchArgument(
            'auto_start',
            default_value='false',
            description='Start FollowPath automatically when a valid path is received',
        ),
        DeclareLaunchArgument(
            'require_robot_near_start',
            default_value='false',
            description='Require robot to be near the first coverage path pose',
        ),
        DeclareLaunchArgument(
            'max_start_distance_m',
            default_value='0.75',
            description='Maximum allowed robot distance to first path pose',
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_tracker_node.py',
            name='coverage_tracker_node',
            output='screen',
            parameters=[params_file, use_sim_time_param],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_planner_node.py',
            name='coverage_planner_node',
            output='screen',
            parameters=[params_file, use_sim_time_param],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_arm_follow_path_executor_node.py',
            name='coverage_follow_path_executor_node',
            output='screen',
            parameters=[
                params_file,
                use_sim_time_param,
                {
                    'auto_start': ParameterValue(auto_start, value_type=bool),
                    'use_robot_arm': ParameterValue(use_robot_arm, value_type=bool),
                    'require_robot_near_start': ParameterValue(
                        require_robot_near_start,
                        value_type=bool,
                    ),
                    'max_start_distance_m': ParameterValue(
                        max_start_distance_m,
                        value_type=float,
                    ),
                },
            ],
        ),
        Node(
            package='sweepi_coverage',
            executable='coverage_manager_node.py',
            name='coverage_manager_node',
            output='screen',
            parameters=[params_file, use_sim_time_param],
        ),
    ])

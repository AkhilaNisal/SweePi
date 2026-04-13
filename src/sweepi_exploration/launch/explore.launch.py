import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    exploration_dir = get_package_share_directory('sweepi_exploration')
    slam_toolbox_dir = get_package_share_directory('slam_toolbox')
    
    slam_params = os.path.join(exploration_dir, 'config', 'slam_params.yaml')
    
    use_sim_time_arg = DeclareLaunchArgument('use_sim_time', default_value='true')
    use_sim_time = LaunchConfiguration('use_sim_time')
    
    # SLAM Toolbox
    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_toolbox_dir, 'launch', 'online_async_launch.py')
        ),
        launch_arguments={
            'slam_params_file': slam_params,
            'use_sim_time': use_sim_time,
        }.items(),
    )
    
    # Exploration Manager
    exploration_manager = Node(
        package='sweepi_exploration',
        executable='exploration_manager.py',
        name='exploration_manager',
        output='screen',
        parameters=[
            {'frontier_min_size': 0.5},
            {'exploration_mode': 'autonomous'},
        ],
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        slam_toolbox,
        exploration_manager,
    ])
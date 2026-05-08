import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    # === User-editable paths ===
    pkg_sweepi_coverage = get_package_share_directory('sweepi_coverage')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_nav2_params = os.path.join(
        pkg_sweepi_coverage,
        'config',
        'nav2_coverage_params.yaml',
    )
    default_map_path = '/home/akhila-wedamestrige/SweePi/maps/swepi_exploration_map_20260418_021201.yaml'
    rviz_config_path = os.path.join(pkg_nav2_bringup, 'rviz', 'nav2_default_view.rviz')  # Change as needed

    # === Launch configurations (for CLI override) ===
    map_yaml = LaunchConfiguration('map', default=default_map_path)
    params_file = LaunchConfiguration('params_file', default=pkg_nav2_params)
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    autostart = LaunchConfiguration('autostart', default='true')

    # === Main bringup file from nav2_bringup, includes everything needed ===
    nav2_bringup_launch = os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')

    return LaunchDescription([
        # -- Command-line args for flexibility --
        DeclareLaunchArgument('map', default_value=default_map_path, description='Full path to map yaml'),
        DeclareLaunchArgument('params_file', default_value=pkg_nav2_params, description='Full path to params.yaml'),
        DeclareLaunchArgument('use_sim_time', default_value='true', description='Use simulation (Gazebo) clock'),
        DeclareLaunchArgument('autostart', default_value='true', description='Autostart the nav2 stack'),

        # -- Include the Nav2 bringup stack --
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_bringup_launch),
            launch_arguments={
                'map': map_yaml,
                'params_file': params_file,
                'use_sim_time': use_sim_time,
                'autostart': autostart,
            }.items(),
        ),

        # -- Optionally bring up RViz2 automatically --
        # Remove/comment this section if you launch rviz2 separately!
        # Node(
        #     package='rviz2',
        #     executable='rviz2',
        #     name='rviz2',
        #     output='screen',
        #     arguments=['-d', rviz_config_path],
        #     parameters=[{'use_sim_time': use_sim_time}],
        # ),
    ])

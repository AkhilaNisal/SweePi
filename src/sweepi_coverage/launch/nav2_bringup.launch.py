import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _map_path_from_name(map_name):
    name = os.path.basename(str(map_name).strip())
    if name.endswith('.yaml'):
        name = name[:-5]
    return os.path.join(os.path.expanduser('~'), 'SweePi', 'maps', f'{name}.yaml')


def _include_nav2_bringup(context, nav2_bringup_launch, default_params_file):
    map_override = LaunchConfiguration('map').perform(context).strip()
    map_name = LaunchConfiguration('map_name').perform(context).strip()
    params_file = LaunchConfiguration('params_file').perform(context).strip()
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context).strip()
    autostart = LaunchConfiguration('autostart').perform(context).strip()

    map_yaml = map_override or _map_path_from_name(map_name)
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_bringup_launch),
            launch_arguments={
                'map': map_yaml,
                'params_file': params_file or default_params_file,
                'use_sim_time': use_sim_time,
                'autostart': autostart,
            }.items(),
        )
    ]


def generate_launch_description():
    # === User-editable paths ===
    pkg_sweepi_coverage = get_package_share_directory('sweepi_coverage')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_nav2_params = os.path.join(
        pkg_sweepi_coverage,
        'config',
        'nav2_coverage_params.yaml',
    )

    # === Main bringup file from nav2_bringup, includes everything needed ===
    nav2_bringup_launch = os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')

    return LaunchDescription([
        # -- Command-line args for flexibility --
        DeclareLaunchArgument(
            'map_name',
            description='Required saved map name in ~/SweePi/maps, without .yaml',
        ),
        DeclareLaunchArgument(
            'map',
            default_value='',
            description='Optional full path to map yaml. Overrides map_name when set.',
        ),
        DeclareLaunchArgument('params_file', default_value=pkg_nav2_params, description='Full path to params.yaml'),
        DeclareLaunchArgument('use_sim_time', default_value='true', description='Use simulation (Gazebo) clock'),
        DeclareLaunchArgument('autostart', default_value='true', description='Autostart the nav2 stack'),

        # -- Include the Nav2 bringup stack --
        OpaqueFunction(
            function=_include_nav2_bringup,
            args=[nav2_bringup_launch, pkg_nav2_params],
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

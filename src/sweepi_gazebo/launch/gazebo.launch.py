#!/usr/bin/env python3
"""
gazebo.launch.py — Launch Gazebo simulation for SweePi using the SDF model.

Separation of concerns (TurtleBot3 style):
  • URDF  (sweepi_description)  → robot_state_publisher / RViz (structure only)
  • SDF   (sweepi_gazebo)       → Gazebo simulation (sensors, physics, plugins)
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():
    pkg_sweepi_gazebo = get_package_share_directory('sweepi_gazebo')
    pkg_sweepi_description = get_package_share_directory('sweepi_description')
    pkg_sweepi_bringup = get_package_share_directory('sweepi_bringup')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # ── Paths ──────────────────────────────────────────────────────────────
    model_sdf_path = os.path.join(
        pkg_sweepi_gazebo, 'models', 'sweepi', 'model.sdf')
    urdf_path = os.path.join(
        pkg_sweepi_description, 'urdf', 'sweepi.urdf.xacro')
    world_path = os.path.join(
        pkg_sweepi_bringup, 'worlds', 'sweepi_world.world')
    bridge_config_path = os.path.join(
        pkg_sweepi_bringup, 'config', 'gazebo.bridge.yaml')
    rviz_config_path = os.path.join(
        pkg_sweepi_description, 'rviz', 'urdf_config.rviz')

    # ── Launch arguments ───────────────────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock')
    x_pose_arg = DeclareLaunchArgument(
        'x_pose', default_value='0.0',
        description='Initial X position of the robot')
    y_pose_arg = DeclareLaunchArgument(
        'y_pose', default_value='0.0',
        description='Initial Y position of the robot')

    use_sim_time = LaunchConfiguration('use_sim_time')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')

    # ── Gazebo Server ──────────────────────────────────────────────────────
    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': world_path + ' -r -s -v2',
            'on_exit_shutdown': 'true',
        }.items(),
    )

    # ── Gazebo Client (GUI) ────────────────────────────────────────────────
    gz_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': '-g -v2',
            'on_exit_shutdown': 'true',
        }.items(),
    )

    # ── Robot State Publisher (uses URDF for TF — no Gazebo tags) ─────────
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': Command(['xacro ', urdf_path]),
            'use_sim_time': use_sim_time,
        }],
    )

    # ── Spawn robot from SDF model ─────────────────────────────────────────
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-file', model_sdf_path,
            '-name', 'sweepi',
            '-x', x_pose,
            '-y', y_pose,
            '-z', '0.05',
        ],
        output='screen',
    )

    # ── ROS–Gazebo bridge ──────────────────────────────────────────────────
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': bridge_config_path,
            'use_sim_time': use_sim_time,
        }],
    )

    # ── RViz ──────────────────────────────────────────────────────────────
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_path],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
    )

    return LaunchDescription([
        use_sim_time_arg,
        x_pose_arg,
        y_pose_arg,
        gz_server,
        gz_client,
        robot_state_publisher,
        spawn_robot,
        ros_gz_bridge,
        rviz,
    ])

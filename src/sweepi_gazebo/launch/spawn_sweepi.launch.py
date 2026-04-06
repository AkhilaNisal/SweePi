#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    gazebo_pkg_dir = get_package_share_directory('sweepi_gazebo')

    # SDF model path
    sdf_model = os.path.join(gazebo_pkg_dir, 'models', 'sweepi', 'model.sdf')

    # Launch arguments
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    # Spawn robot in Gazebo
    spawn_robot_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'sweepi',
            '-file', sdf_model,
            '-x', x_pose,
            '-y', y_pose,
            '-z', '0.01'
        ],
        output='screen',
    )

    # ROS-Gazebo bridge
    bridge_params = os.path.join(gazebo_pkg_dir, 'params', 'sweepi_bridge.yaml')

    ros_gz_bridge_cmd = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '--ros-args',
            '-p',
            f'config_file:={bridge_params}',
        ],
        output='screen',
    )

    # Image bridge for camera
    image_bridge_cmd = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera/image_raw'],
        output='screen',
    )

    ld = LaunchDescription()

    ld.add_action(spawn_robot_cmd)
    ld.add_action(ros_gz_bridge_cmd)
    ld.add_action(image_bridge_cmd)

    return ld
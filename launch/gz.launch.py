#!/usr/bin/env python3
"""Gazebo launch — physics simulation only, no navigation code.

DDS interface (navigation systems connect via these topics):
  Publishes: /points_raw (PointCloud2), /odom, /clock, TF odom→base_footprint
  Subscribes: /cmd_vel
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

GZ_DIR = "/opt/gz"


def generate_launch_description():
    urdf_path = os.path.join(GZ_DIR, "urdf", "explore_bot.urdf.xacro")
    world_path = os.path.join(GZ_DIR, "worlds", "explore_room.world")
    gui = LaunchConfiguration("gui", default="true")

    robot_desc = ParameterValue(Command(["xacro ", urdf_path]), value_type=str)

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory("gazebo_ros"),
            "launch", "gazebo.launch.py")),
        launch_arguments={"world": world_path, "gui": gui}.items(),
    )

    robot_state_pub = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"robot_description": robot_desc, "use_sim_time": True}],
    )

    spawn = TimerAction(period=3.0, actions=[
        ExecuteProcess(
            cmd=["ros2", "run", "gazebo_ros", "spawn_entity.py",
                 "-entity", "explore_bot", "-topic", "robot_description",
                 "-x", "-12.0", "-y", "0.0", "-z", "0.05"],
            output="screen"),
    ])

    return LaunchDescription([
        DeclareLaunchArgument("gui", default_value="true"),
        gazebo, robot_state_pub, spawn,
    ])

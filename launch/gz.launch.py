#!/usr/bin/env python3
"""Gazebo launch — physics simulation only, no navigation code.

DDS interface (navigation systems connect via these topics):
  Publishes: /points_raw (PointCloud2), /odom, /clock, TF odom→base_footprint
  Subscribes: /cmd_vel

Launch arguments:
  world    — world file name placed under /opt/gz/worlds (default: explore_room.world)
  spawn_x  — robot spawn X coordinate (default: -12.0)
  spawn_y  — robot spawn Y coordinate (default: 0.0)
  gui      — start Gazebo GUI (default: true)
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

GZ_DIR = "/opt/gz"


def generate_launch_description():
    urdf_path = os.path.join(GZ_DIR, "urdf", "explore_bot.urdf.xacro")
    world = LaunchConfiguration("world")
    gui = LaunchConfiguration("gui")
    spawn_x = LaunchConfiguration("spawn_x")
    spawn_y = LaunchConfiguration("spawn_y")

    world_path = PathJoinSubstitution([GZ_DIR, "worlds", world])
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
                 "-x", spawn_x, "-y", spawn_y, "-z", "0.05"],
            output="screen"),
    ])

    return LaunchDescription([
        DeclareLaunchArgument("world", default_value="explore_room.world",
                              description="World file name under /opt/gz/worlds"),
        DeclareLaunchArgument("spawn_x", default_value="-12.0"),
        DeclareLaunchArgument("spawn_y", default_value="0.0"),
        DeclareLaunchArgument("gui", default_value="true"),
        gazebo, robot_state_pub, spawn,
    ])

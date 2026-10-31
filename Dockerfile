# nav4sim — standalone Gazebo Classic simulation for ROS 2 navigation testing.
#
# Publishes:  /points_raw (PointCloud2), /odom, /clock, TF odom→base_footprint
# Subscribes: /cmd_vel
#
# Build:  docker build -t nav4sim .
# Run:    docker run -d --name gz-sim --network host -e ROS_DOMAIN_ID=42 nav4sim

FROM ros:humble-ros-base

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
       ros-humble-gazebo-ros-pkgs \
       ros-humble-xacro \
       ros-humble-robot-state-publisher \
    && rm -rf /var/lib/apt/lists/*

COPY urdf/ /opt/gz/urdf/
COPY worlds/ /opt/gz/worlds/
COPY launch/ /opt/gz/launch/

ENV ROS_DOMAIN_ID=42

CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && ros2 launch /opt/gz/launch/gz.launch.py"]

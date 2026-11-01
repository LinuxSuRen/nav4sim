# nav4sim — standalone Gazebo Classic simulation for ROS 2 navigation testing.
#
# Publishes:  /points_raw (PointCloud2), /odom, /clock, TF odom→base_footprint
# Subscribes: /cmd_vel
#
# Build:  docker build -t nav4sim .
# Run:    docker run -d --name gz-sim --network host -e ROS_DOMAIN_ID=42 nav4sim

FROM golang:1.23 AS web
WORKDIR /src
COPY web/go.mod web/main.go ./
RUN CGO_ENABLED=0 go build -o /nav4sim-web .

FROM ros:humble-ros-base

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
       ros-humble-gazebo-ros-pkgs \
       ros-humble-xacro \
       ros-humble-robot-state-publisher \
    && rm -rf /var/lib/apt/lists/*

COPY --from=web /nav4sim-web /usr/local/bin/nav4sim-web
COPY urdf/ /opt/gz/urdf/
COPY worlds/ /opt/gz/worlds/
COPY launch/ /opt/gz/launch/

ENV ROS_DOMAIN_ID=42
ENV NAV4SIM_WEB_PORT=8080

# Web UI on $NAV4SIM_WEB_PORT (default 8080): pick a world from a dropdown
# and (re)start the simulation. The default world starts automatically on boot.
EXPOSE 8080

CMD ["nav4sim-web"]

# nav4sim

ROS 2 navigation simulation environment — a standalone [Gazebo Classic](https://classic.gazebosim.org/) simulation that provides sensor and chassis DDS interfaces for testing autonomous navigation systems **without real hardware**.

## What it does

This simulation publishes the exact same DDS topics that a real robot would:

| DDS Topic | Type | Description |
|---|---|---|
| `/points_raw` | `sensor_msgs/PointCloud2` | 3D LiDAR point cloud (720×16, 10 Hz, 15 m range) |
| `/odom` | `nav_msgs/Odometry` | Wheel odometry (ground truth from physics engine) |
| `/clock` | `rosgraph_msgs/Clock` | Simulation clock (for `use_sim_time`) |
| TF `odom→base_footprint` | — | Chassis TF |
| `/cmd_vel` (subscribe) | `geometry_msgs/Twist` | Velocity commands |

Any ROS 2 navigation stack that subscribes to these topics will work with this simulation out of the box — no code changes needed.

## Quick start

### Prerequisites

- Docker (with `--network host` support)
- A DDS-compatible ROS 2 navigation system

### 1. Build the image

```bash
git clone https://github.com/LinuxSuRen/nav4sim.git
cd nav4sim
docker build -t nav4sim .
```

Or pull the prebuilt image (published to GHCR from `master` on every merge):

```bash
docker pull ghcr.io/linuxsuren/nav4sim:latest
```

### 2. Start the simulation

```bash
# Headless (no GUI, recommended for CI/automated testing)
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  nav4sim

# With Gazebo GUI (requires X11 forwarding)
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  -e DISPLAY=host.docker.internal:0.0 \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  nav4sim
```

### 3. Connect your navigation system

Start your navigation stack in another container with the same `ROS_DOMAIN_ID`:

```bash
docker run -d --name nav --network host \
  -e ROS_DOMAIN_ID=42 \
  <your-navigation-image>
```

DDS discovery is automatic — no configuration needed.

## Simulation world

Default world: 30 m × 20 m closed room with:

- Central wall block (creates occlusion zones for frontier detection)
- East wing walls (occludes corridors)
- West partition (creates sub-rooms)
- Dead-end pocket (tests goal blacklisting)
- Box clusters and low bar (obstacle avoidance testing)

Custom worlds can be placed in `worlds/` and referenced in the launch file.

## Robot model

Simple box robot (`urdf/explore_bot.urdf.xacro`):

- **Body**: 0.8 × 0.45 × 0.25 m box
- **LiDAR**: 720 horizontal × 16 vertical rays, 10 Hz, 15 m range
- **Chassis**: `gazebo_ros_planar_move` plugin (velocity-commanded, publishes odometry)

## Files

```
nav4sim/
├── Dockerfile              # ros:humble-ros-base + gazebo-ros-pkgs
├── launch/
│   └── gz.launch.py       # Gazebo launch (headless/GUI, robot spawn)
├── urdf/
│   └── explore_bot.urdf.xacro  # Robot model (sensors + planar_move)
├── worlds/
│   └── explore_room.world      # 30×20m test environment
└── README.md
```

## License

[MIT](LICENSE)

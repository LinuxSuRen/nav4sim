# nav4sim

ROS 2 navigation simulation environment — a standalone [Gazebo Classic](https://classic.gazebosim.org/) simulation that provides sensor and chassis DDS interfaces for testing autonomous navigation systems **without real hardware**.

## What it does

This simulation publishes the exact same DDS topics that a real robot would:

| DDS Topic | Type | Description |
|---|---|---|
| `/points_raw` | `sensor_msgs/PointCloud2` | 3D LiDAR point cloud, front slot (720×16, 10 Hz, 15 m range) |
| `/points_raw/rear` | `sensor_msgs/PointCloud2` | 3D LiDAR point cloud, rear slot `lidar_rear_link` (omit with `rear_lidar:=false`) |
| `/odom` | `nav_msgs/Odometry` | Wheel odometry (ground truth from physics engine) |
| `/clock` | `rosgraph_msgs/Clock` | Simulation clock (for `use_sim_time`) |
| TF `odom→base_footprint` | — | Chassis TF |
| TF `base_link→{lidar_link,lidar_rear_link}` | — | Sensor TF |
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

The image starts a small web service (default port `8080`) where you can pick
the simulation world from a dropdown and (re)start it — no container restart
or `docker exec` needed.

```bash
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  -p 8080:8080 \
  nav4sim
```

Open <http://localhost:8080>, choose a world (plus optional spawn point and
GUI switch) and click **Start / Switch**. The default world starts
automatically on boot. The port can be changed with `NAV4SIM_WEB_PORT`; the
web service can be bypassed by overriding the image CMD as shown below.

```bash
# With Gazebo GUI (requires X11 forwarding; on Windows see
# "Visualization (RViz2) → Windows" below)
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  -e DISPLAY=host.docker.internal:0.0 \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  nav4sim

# Select a world and/or spawn point (overrides the image CMD)
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  nav4sim ros2 launch /opt/gz/launch/gz.launch.py \
    world:=<world-file> spawn_x:=0.0 spawn_y:=0.0

# Launch a specific world directly, bypassing the web service
docker run -d --name gz-sim --network host \
  -e ROS_DOMAIN_ID=42 \
  nav4sim bash -c "source /opt/ros/humble/setup.bash && ros2 launch /opt/gz/launch/gz.launch.py \
    world:=maze.world spawn_x:=-17.0 spawn_y:=-17.0"
```

### 3. Connect your navigation system

Start your navigation stack in another container with the same `ROS_DOMAIN_ID`:

```bash
docker run -d --name nav --network host \
  -e ROS_DOMAIN_ID=42 \
  <your-navigation-image>
```

DDS discovery is automatic — no configuration needed.

## Visualization (RViz2)

The image bundles RViz2 and a preset config (`config/nav4sim.rviz`) that
shows the grid, robot model, TF, the LiDAR point cloud (`/points_raw`) and
odometry arrows (`/odom`). Run it as a **sidecar container** with the same
`ROS_DOMAIN_ID` — the simulation itself stays headless.

On **Linux** (X11 forwarding to a local display):

```bash
docker run --rm -it --network host \
  -e ROS_DOMAIN_ID=42 \
  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  nav4sim rviz2 -d /opt/gz/config/nav4sim.rviz
```

### Windows (Docker Desktop): run in containers and see the GUI

Requirements: Docker Desktop with the **WSL 2** backend, 4.34+ (for
`--network host`). Windows itself provides the display via **WSLg**
(built into Windows 10 build 19044+ / Windows 11) — no extra software.

From PowerShell:

```powershell
# 1. Simulation — the DISPLAY flags also enable the "Gazebo GUI" checkbox in the web UI
docker run -d --name gz-sim --network host `
  -e ROS_DOMAIN_ID=42 `
  -e DISPLAY=:0 -e QT_X11_NO_MITSHM=1 -e LIBGL_ALWAYS_SOFTWARE=1 `
  -v /mnt/wslg:/mnt/wslg `
  nav4sim

# 2. RViz2 sidecar — its window opens on the Windows desktop
docker run --rm -it --name rviz --network host `
  -e ROS_DOMAIN_ID=42 `
  -e DISPLAY=:0 -e QT_X11_NO_MITSHM=1 -e LIBGL_ALWAYS_SOFTWARE=1 `
  -v /mnt/wslg:/mnt/wslg `
  nav4sim rviz2 -d /opt/gz/config/nav4sim.rviz
```

Then:

- Open <http://localhost:8080> to pick a world; tick **Gazebo GUI** there to
  also see the Gazebo client window (it uses the same `DISPLAY`).
- Drive the robot and watch it move in RViz2 (Ctrl+C to stop):

```powershell
docker exec gz-sim bash -c "source /opt/ros/humble/setup.bash && \
  ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.5}}'"
```

What the display flags do:

| Flag | Why |
|---|---|
| `-v /mnt/wslg:/mnt/wslg` + `DISPLAY=:0` | routes X11 to WSLg, the X server built into WSL |
| `QT_X11_NO_MITSHM=1` | avoids Qt shared-memory errors inside containers |
| `LIBGL_ALWAYS_SOFTWARE=1` | forces software OpenGL (reliable everywhere) |

For GPU acceleration, drop `LIBGL_ALWAYS_SOFTWARE` and add
`-v /usr/lib/wsl:/usr/lib/wsl` (needs WSLg GPU paravirtualization).

**Alternative — X server on Windows (VcXsrv/X410):** install
[VcXsrv](https://sourceforge.net/projects/vcxsrv/) and start it via
**XLaunch** (Multiple windows → Display number `0` → Start no client → tick
**Disable access control**), allow it through the Windows firewall, then use
the same commands with the display flags replaced by
`-e DISPLAY=host.docker.internal:0.0` and without the `/mnt/wslg` mount.

If <http://localhost:8080> does not respond, your Docker Desktop predates
host-networking support — upgrade to 4.34+.

## Simulation worlds

Pick a world with the `world` launch argument (file name under `worlds/`);
set the robot start pose with `spawn_x` / `spawn_y`; drop the rear LiDAR
with `rear_lidar:=false` (saves sensor CPU when your stack only consumes
the front cloud).

| World | Size | Test focus |
|---|---|---|
| `explore_room.world` (default) | 30×20 m | Frontier exploration: occlusion zones, sub-rooms, dead-end pocket |
| `maze.world` | 36×36 m | Perfect maze, 1.8 m corridors: narrow-passage planning, forced backtracking |
| `warehouse.world` | 50×30 m | Aisles beyond LiDAR range, repeated shelving (landmark aliasing), pillars/pallets |
| `dynamic_room.world` | 30×20 m | Wandering frictionless movers (LiDAR-visible): dynamic obstacle avoidance |
| `loop_corridor.world` | 30×30 m | Ring corridor + central room + dead-end pockets: loop closure, relocalization |

Default world (`explore_room.world`) details:

- Central wall block (creates occlusion zones for frontier detection)
- East wing walls (occludes corridors)
- West partition (creates sub-rooms)
- Dead-end pocket (tests goal blacklisting)
- Box clusters and low bar (obstacle avoidance testing)

Custom worlds can be placed in `worlds/` and selected with the `world`
launch argument.

## Robot model

Simple box robot (`urdf/explore_bot.urdf.xacro`):

- **Body**: 0.8 × 0.45 × 0.25 m box
- **LiDAR**: 720 horizontal × 16 vertical rays, 10 Hz, 15 m range
- **Chassis**: `gazebo_ros_planar_move` plugin (velocity-commanded, publishes odometry)

No ROS at hand? Preview this URDF/Xacro in a browser with
[robot-viewer](https://github.com/LinuxSuRen/robot-viewer) — load the
`urdf/` directory (or drag & drop the file) to render the model in 3D
without installing anything.

## Files

```
nav4sim/
├── Dockerfile              # ros:humble-ros-base + gazebo-ros-pkgs + rviz2
├── config/
│   └── nav4sim.rviz        # RViz2 preset: grid, robot, TF, /points_raw, /odom
├── launch/
│   └── gz.launch.py       # Gazebo launch (world/spawn args, headless/GUI, robot spawn)
├── urdf/
│   └── explore_bot.urdf.xacro  # Robot model (sensors + planar_move)
├── web/
│   └── main.go            # web control service (Go): world dropdown, start/stop/switch (port 8080)
├── tools/                # world generator scripts (deterministic regeneration)
├── worlds/                 # simulation worlds (see table above)
└── README.md
```

## License

[MIT](LICENSE)

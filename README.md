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
# With Gazebo GUI (requires X11 forwarding)
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

## Simulation worlds

Pick a world with the `world` launch argument (file name under `worlds/`);
set the robot start pose with `spawn_x` / `spawn_y`.

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

## Files

```
nav4sim/
├── Dockerfile              # ros:humble-ros-base + gazebo-ros-pkgs
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

## Troubleshooting

### `ros2 launch` reports "does not contain the required function 'generate_launch_description()'"

The image is built and published only after a runtime smoke test, so a
published image always contains a working launch file. If you still see this
error (or `error while loading shared libraries: ... file too short`), the
image files were **truncated on your machine during pull** — a known Docker
Desktop bug (typically on macOS with the VirtioFS file-sharing
implementation). ROS 2 loads the truncated launch file as a valid but empty
Python module, hence the misleading message.

Verify and recover:

```bash
# 1. Check for truncated (0-byte) files inside the image — prints 0 when healthy
docker run --rm --entrypoint find ghcr.io/linuxsuren/nav4sim:latest \
  /opt/gz /usr/lib/x86_64-linux-gnu -type f -size 0 | wc -l

# 2. If any file is 0 bytes: delete the local copy and pull again
docker image rm ghcr.io/linuxsuren/nav4sim:latest
docker pull ghcr.io/linuxsuren/nav4sim:latest

# 3. If it recurs: Settings → General → switch the file-sharing
#    implementation (VirtioFS → gRPC FUSE), then repeat step 2
```

### Other issues

- No LiDAR data: make sure both containers use the same `ROS_DOMAIN_ID` and
  `--network host`.
- GUI does not appear: X11 forwarding is required (`DISPLAY` +
  `host.docker.internal:0.0`), see the example above.

## License

[MIT](LICENSE)

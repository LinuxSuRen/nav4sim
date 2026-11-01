#!/usr/bin/env python3
"""Generate maze.world (SDF) for nav4sim.

Recursive-backtracker perfect maze on a cell grid, emitted as static box walls.
Grid: 18x18 cells, cell pitch 2.0 m, wall thickness 0.2 m, wall height 1.0 m.
Outer shell: 36m x 36m. Corridor width = 2.0 - 0.2 = 1.8 m (robot is 0.8x0.45).
Perfect maze => single path between any two cells: tests full-coverage exploration.
Spawn: cell (0,0) center => (-17.0, -17.0); exit goal suggestion: opposite corner.
"""
import random
import sys

random.seed(42)

CELLS = 18          # cells per side
PITCH = 2.0         # m per cell
WALL_T = 0.2        # wall thickness
WALL_H = 1.0        # wall height
SIZE = CELLS * PITCH  # 36.0
HALF = SIZE / 2.0

# Grid of walls: vertical walls between (cx,cy)-(cx+1,cy) => v[cx][cy], cx in 0..CELLS-2
# horizontal walls between (cx,cy)-(cx,cy+1) => h[cx][cy], cy in 0..CELLS-2
v = [[True] * CELLS for _ in range(CELLS - 1)]   # v[cx][cy]
h = [[True] * (CELLS - 1) for _ in range(CELLS)] # h[cx][cy]

visited = [[False] * CELLS for _ in range(CELLS)]
stack = [(0, 0)]
visited[0][0] = True
while stack:
    cx, cy = stack[-1]
    nbrs = []
    if cx > 0 and not visited[cx - 1][cy]: nbrs.append(("W", cx - 1, cy))
    if cx < CELLS - 1 and not visited[cx + 1][cy]: nbrs.append(("E", cx + 1, cy))
    if cy > 0 and not visited[cx][cy - 1]: nbrs.append(("S", cx, cy - 1))
    if cy < CELLS - 1 and not visited[cx][cy + 1]: nbrs.append(("N", cx, cy + 1))
    if not nbrs:
        stack.pop()
        continue
    d, nx, ny = random.choice(nbrs)
    if d == "W": v[cx - 1][cy] = False
    elif d == "E": v[cx][ny] = False
    elif d == "S": h[cx][cy - 1] = False
    elif d == "N": h[cx][cy] = False
    visited[nx][ny] = True
    stack.append((nx, ny))

def cell_center(cx, cy):
    return (-HALF + (cx + 0.5) * PITCH, -HALF + (cy + 0.5) * PITCH)

# Deduplicate walls: merge collinear contiguous wall segments into single boxes
# Vertical walls (running along Y) at grid line x = -HALF + (k+1)*PITCH for k in 0..CELLS-2,
# plus outer lines k=-1 and k=CELLS-1 handled as outer shell separately.
# For interior vertical line k: segments over cy where v[k][cy] is True -> merge consecutive.
vsegs = []
for k in range(CELLS - 1):
    x = -HALF + (k + 1) * PITCH
    cy = 0
    while cy < CELLS:
        if v[k][cy]:
            start = cy
            while cy < CELLS and v[k][cy]:
                cy += 1
            vsegs.append((x, start, cy - 1))  # y-line index range inclusive
        else:
            cy += 1

hsegs = []
for k in range(CELLS - 1):
    y = -HALF + (k + 1) * PITCH
    cx = 0
    while cx < CELLS:
        if h[cx][k]:
            start = cx
            while cx < CELLS and h[cx][k]:
                cx += 1
            hsegs.append((y, start, cx - 1))
        else:
            cx += 1

def box(name, x, y, sx, sy, mat):
    return f'''    <model name="{name}">
      <pose>{x:.3f} {y:.3f} {WALL_H/2:.3f} 0 0 0</pose>
      <static>true</static>
      <link name="link">
        <collision name="collision"><geometry><box><size>{sx:.3f} {sy:.3f} {WALL_H:.3f}</size></box></geometry></collision>
        <visual name="visual"><geometry><box><size>{sx:.3f} {sy:.3f} {WALL_H:.3f}</size></box></geometry>
          <material><ambient>{mat}</ambient><diffuse>{mat}</diffuse></material>
        </visual>
      </link>
    </model>
'''

out = []
out.append('''<?xml version="1.0"?>
<!-- 36m x 36m perfect maze (single solution path between any two cells).

Test focus:
  - narrow-corridor path planning (1.8m corridors, robot footprint 0.8 x 0.45m)
  - full-coverage exploration (a perfect maze forces backtracking)
  - LiDAR (15m) cannot see across the maze: local decision-making under uncertainty

Spawn point: cell (0,0) center  =>  spawn_x:=-17.0  spawn_y:=-17.0
Suggested goal: cell (17,17)    =>  x=17.0, y=17.0 (opposite corner)

Generated with a seeded recursive-backtracker (see PR description); regenerate
deterministically with seed 42.
-->
<sdf version="1.6">
  <world name="maze">

    <include><uri>model://sun</uri></include>
    <include><uri>model://ground_plane</uri></include>

    <physics name="default_physics" type="ode">
      <max_step_size>0.005</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
''')

MAT_WALL = "0.7 0.7 0.75 1"
MAT_SHELL = "0.55 0.6 0.65 1"

# Outer shell (4 walls), 0.2 thick, length 36.4 to overlap corners
out.append(box("shell_n", 0.0, HALF, SIZE + WALL_T, WALL_T, MAT_SHELL))
out.append(box("shell_s", 0.0, -HALF, SIZE + WALL_T, WALL_T, MAT_SHELL))
out.append(box("shell_e", HALF, 0.0, WALL_T, SIZE + WALL_T, MAT_SHELL))
out.append(box("shell_w", -HALF, 0.0, WALL_T, SIZE + WALL_T, MAT_SHELL))

# Interior vertical wall segments: length = (n_cells)*PITCH - PITCH + WALL_T over cell range
for i, (x, c0, c1) in enumerate(vsegs):
    n = c1 - c0 + 1
    y_center = (-HALF + (c0 + 0.5) * PITCH + -HALF + (c1 + 0.5) * PITCH) / 2.0
    sy = (n - 1) * PITCH + WALL_T
    out.append(box(f"mv{i:03d}", x, y_center, WALL_T, sy, MAT_WALL))

for i, (y, c0, c1) in enumerate(hsegs):
    n = c1 - c0 + 1
    x_center = (-HALF + (c0 + 0.5) * PITCH + -HALF + (c1 + 0.5) * PITCH) / 2.0
    sx = (n - 1) * PITCH + WALL_T
    out.append(box(f"mh{i:03d}", x_center, y, sx, WALL_T, MAT_WALL))

out.append('''
  </world>
</sdf>
''')

with open(sys.argv[1] if len(sys.argv) > 1 else "maze.world", "w", encoding="utf-8") as f:
    f.write("".join(out))

# Connectivity sanity: BFS over maze graph
from collections import deque
adj = {(cx, cy): [] for cx in range(CELLS) for cy in range(CELLS)}
for k in range(CELLS - 1):
    for cy in range(CELLS):
        if not v[k][cy]:
            adj[(k, cy)].append((k + 1, cy)); adj[(k + 1, cy)].append((k, cy))
for k in range(CELLS - 1):
    for cx in range(CELLS):
        if not h[cx][k]:
            adj[(cx, k)].append((cx, k + 1)); adj[(cx, k + 1)].append((cx, k))
seen = {(0, 0)}
q = deque([(0, 0)])
while q:
    c = q.popleft()
    for n2 in adj[c]:
        if n2 not in seen:
            seen.add(n2); q.append(n2)
print(f"cells reachable from (0,0): {len(seen)}/{CELLS*CELLS}")
print(f"interior v-segments: {len(vsegs)}, h-segments: {len(hsegs)} (models total: {len(vsegs)+len(hsegs)+4})")
print(f"spawn cell (0,0) center: ({-HALF + 0.5*PITCH:.2f}, {-HALF + 0.5*PITCH:.2f})")
print(f"goal cell (17,17) center: ({-HALF + 17.5*PITCH:.2f}, {-HALF + 17.5*PITCH:.2f})")

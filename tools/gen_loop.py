#!/usr/bin/env python3
"""Generate loop_corridor.world (SDF) for nav4sim.

Ring corridor around a central block; two opposite doorways into the central
room; two dead-end pockets. All wall spans computed from a single spec so
segments butt exactly (no corner leaks, doorway widths are true clear widths).
"""
import sys

T_BLOCK = 0.3          # central block wall thickness
BLOCK_C = 11.6         # central block wall centerline (±)
BLOCK_OUT = BLOCK_C + T_BLOCK / 2   # 11.75 outer face
BLOCK_IN = BLOCK_C - T_BLOCK / 2    # 11.45 inner face
H = 1.0                # wall height
DOOR_HALF = 0.85       # N/S doorway half-width → 1.7m clear
POCKET_GAP = (3.15, 4.85)  # E entrance gap on block wall (1.7m clear)
POCKET_DEPTH_X = (6.9, 11.75)  # pocket x range (end wall centerline .. block face)
POCKET_SIDE = (3.0, 5.0)      # pocket side wall centerlines (y), → interior 1.7m


def box(name, x, y, sx, sy, mat):
    return f'''    <model name="{name}">
      <pose>{x:.3f} {y:.3f} {H/2:.3f} 0 0 0</pose>
      <static>true</static>
      <link name="link">
        <collision name="collision"><geometry><box><size>{sx:.3f} {sy:.3f} {H:.3f}</size></box></geometry></collision>
        <visual name="visual"><geometry><box><size>{sx:.3f} {sy:.3f} {H:.3f}</size></box></geometry>
          <material><ambient>{mat}</ambient><diffuse>{mat}</diffuse></material>
        </visual>
      </link>
    </model>
'''


def span_x(x0, x1, y, name, mat):
    """Wall running along X from x0 to x1 (inclusive), centered on y."""
    return box(name, (x0 + x1) / 2, y, x1 - x0, T_BLOCK, mat)


def span_y(y0, y1, x, name, mat):
    """Wall running along Y from y0 to y1 (inclusive), centered on x."""
    return box(name, x, (y0 + y1) / 2, T_BLOCK, y1 - y0, mat)


MAT_SHELL = "0.8 0.8 0.7 1"
MAT_BLOCK = "0.55 0.6 0.65 1"
MAT_ROOM = "0.5 0.5 0.6 1"
MAT_POCKET = "0.9 0.5 0.1 1"

o = []
o.append('''<?xml version="1.0"?>
<!-- 30m x 30m ring-corridor building: perimeter loop + central room + pockets.

Test focus:
  - loop closure: driving the ring corridor returns to previously seen
    geometry from a different viewpoint
  - relocalization under landmark aliasing (4 similar corners)
  - dead-end pockets branching off the ring (goal blacklisting)

Topology:
  - Ring corridor ~3.1m wide around the perimeter
  - Central room entered through two opposite 1.7m doorways (N/S)
  - Two dead-end pockets (E/W) with 1.7m entrances

Spawn point: (0, -13.2)  (south corridor)
Suggested goal: central pillar room (0, 0) or a pocket (±9.2, ±4.0).

Generated from a single geometry spec (see PR description); regenerate with:
  python3 gen_loop.py loop_corridor.world
-->
<sdf version="1.6">
  <world name="loop_corridor">

    <include><uri>model://sun</uri></include>
    <include><uri>model://ground_plane</uri></include>

    <physics name="default_physics" type="ode">
      <max_step_size>0.005</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- ═══════════ Outer shell 30m x 30m ═══════════ -->
''')
o.append(box("wall_n", 0, 15, 30.4, 0.2, MAT_SHELL))
o.append(box("wall_s", 0, -15, 30.4, 0.2, MAT_SHELL))
o.append(box("wall_e", 15, 0, 0.2, 30.4, MAT_SHELL))
o.append(box("wall_w", -15, 0, 0.2, 30.4, MAT_SHELL))

o.append('''
    <!-- ═══════════ Central block walls (23m x 23m, ring corridor ~3.1m wide) ═══════════ -->
''')
# N/S walls split by 1.7m doorway at |x| <= 0.85; segments span to block corners
o.append(span_x(-BLOCK_OUT, -DOOR_HALF, BLOCK_C, "cb_n_left", MAT_BLOCK))
o.append(span_x(DOOR_HALF, BLOCK_OUT, BLOCK_C, "cb_n_right", MAT_BLOCK))
o.append(span_x(-BLOCK_OUT, -DOOR_HALF, -BLOCK_C, "cb_s_left", MAT_BLOCK))
o.append(span_x(DOOR_HALF, BLOCK_OUT, -BLOCK_C, "cb_s_right", MAT_BLOCK))
# E wall split by pocket entrance gap; W wall mirrored
o.append(span_y(POCKET_GAP[1], BLOCK_OUT, BLOCK_C, "cb_e_top", MAT_BLOCK))
o.append(span_y(-BLOCK_OUT, POCKET_GAP[0], BLOCK_C, "cb_e_bottom", MAT_BLOCK))
o.append(span_y(-POCKET_GAP[1], BLOCK_OUT, -BLOCK_C, "cb_w_top", MAT_BLOCK))
o.append(span_y(-BLOCK_OUT, -POCKET_GAP[0], -BLOCK_C, "cb_w_bottom", MAT_BLOCK))

o.append('''
    <!-- ═══════════ Central room interior ═══════════ -->
''')
o.append(box("cr_pillar", 0, 0, 1.2, 1.2, "0.4 0.4 0.4 1"))
o.append(box("cr_wing_w", -4.0, -3.0, 0.3, 5.0, MAT_ROOM))
o.append(box("cr_wing_e", 4.0, 3.0, 0.3, 5.0, MAT_ROOM))

o.append('''
    <!-- ═══════════ Dead-end pockets (E/W), 1.7m entrances ═══════════ -->
''')
x0, x1 = POCKET_DEPTH_X
ys0, ys1 = POCKET_SIDE
# East pocket: side walls along X, end wall along Y; y center = (3.0+5.0)/2 = 4.0
o.append(span_x(x0, x1, ys1, "pocket_e_n", MAT_POCKET))
o.append(span_x(x0, x1, ys0, "pocket_e_s", MAT_POCKET))
o.append(span_y(ys0 - T_BLOCK / 2, ys1 + T_BLOCK / 2, x0, "pocket_e_end", MAT_POCKET))
# West pocket mirrored about y=0
o.append(span_x(x0, x1, -ys1, "pocket_w_n", MAT_POCKET))
o.append(span_x(x0, x1, -ys0, "pocket_w_s", MAT_POCKET))
o.append(span_y(-ys1 - T_BLOCK / 2, -ys0 + T_BLOCK / 2, x0, "pocket_w_end", MAT_POCKET))

o.append('''
  </world>
</sdf>
''')

with open(sys.argv[1] if len(sys.argv) > 1 else "loop_corridor.world", "w", encoding="utf-8") as f:
    f.write("".join(o))

# Sanity prints
print(f"ring corridor clear width: {14.9 - BLOCK_OUT:.2f} m")
print(f"N/S doorway clear width: {2*DOOR_HALF:.2f} m")
print(f"pocket entrance clear width: {POCKET_GAP[1]-POCKET_GAP[0]:.2f} m")
print(f"pocket interior depth: {BLOCK_IN - (x0 + T_BLOCK/2):.2f} m, "
      f"width: {ys1 - ys0 - T_BLOCK:.2f} m")

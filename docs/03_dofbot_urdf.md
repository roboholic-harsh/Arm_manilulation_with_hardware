# `dofbot_urdf` — Robot Model & Master Launch

> **Type:** ament_cmake resource package  
> **Role:** Contains the full URDF model (SolidWorks export), 14 STL mesh files, and the master `ai_bringup.launch.py` that starts the entire system.

---

## Purpose

This package provides:
1. The **complete URDF** of the Yahboom Dofbot arm — defines all links, joints, inertia properties, and visual/collision meshes
2. **14 STL mesh files** for 3D visualization in RViz
3. **Launch files** including the all-in-one `ai_bringup.launch.py`

---

## File Map

```
dofbot_urdf/
├── CMakeLists.txt           # Installs launch/, meshes/, urdf/ to share/
├── package.xml              # Minimal ament_cmake package
├── urdf/
│   ├── dofbot.urdf          # ⭐ Full robot URDF (791 lines, 18.5 KB)
│   └── dofbot-bk.urdf       # Backup/older URDF version
├── meshes/                  # 14 STL files from SolidWorks export
│   ├── base_link.STL        # 38 MB — base platform
│   ├── arm1_Link.STL        # 7.7 MB — turntable
│   ├── arm2_Link.STL        # 9.3 MB — shoulder
│   ├── arm3_Link.STL        # 9.3 MB — elbow
│   ├── arm4_Link.STL        # 12.3 MB — wrist pitch
│   ├── arm5_Link.STL        # 3.8 MB — wrist rotation
│   ├── Rlink1_Link.STL      # 1.3 MB — right gripper finger 1
│   ├── Rlink2_Link.STL      # 51 KB — right gripper finger 2
│   ├── Rlink3_Link.STL      # 888 KB — right gripper finger 3
│   ├── Llink1_Link.STL      # 1 MB — left gripper finger 1
│   ├── Llink2_Link.STL      # 51 KB — left gripper finger 2
│   ├── Llink3_Link.STL      # 888 KB — left gripper finger 3
│   ├── Camera_Link.STL      # 42 KB — camera mount
│   └── Gripping_Link.STL    # 34 KB — gripper tip
└── launch/
    ├── ai_bringup.launch.py    # ⭐ Master launch: hardware + MoveIt + AI + GUI
    ├── display.launch.py       # URDF viewer with joint_state_publisher_gui
    └── urdf_display.launch.py  # Alternative URDF viewer
```

---

## Kinematic Chain

```
world (fixed frame)
  └── base_link                              [base platform]
        └── arm1_Joint (revolute, Z-axis)    [turntable rotation]
              └── arm1_Link
                    └── arm2_Joint (revolute, -Y-axis)   [shoulder]
                          └── arm2_Link
                                └── arm3_Joint (revolute, -Y-axis)   [elbow]
                                      └── arm3_Link
                                            └── arm4_Joint (revolute, -Y-axis)   [wrist pitch]
                                                  └── arm4_Link
                                                  │     └── Camera_Joint (fixed)
                                                  │           └── Camera_Link
                                                  │
                                                  └── arm5_Joint (revolute, Z-axis)   [wrist rotation]
                                                        └── arm5_Link
                                                              ├── Rlink1_Joint → Rlink1 → Rlink2
                                                              ├── Llink1_Joint → Llink1 → Llink2
                                                              ├── Rlink3_Joint → Rlink3
                                                              ├── Llink3_Joint → Llink3
                                                              └── Gripping_Joint (fixed) → Gripping_point_Link
```

### Joint Details

| Joint | Type | Axis | Limits | Parent → Child |
|-------|------|------|--------|----------------|
| `arm1_Joint` | revolute | Z (yaw) | ±1.57 rad (±90°) | `base_link` → `arm1_Link` |
| `arm2_Joint` | revolute | -Y (pitch) | ±1.57 rad | `arm1_Link` → `arm2_Link` |
| `arm3_Joint` | revolute | -Y (pitch) | ±1.57 rad | `arm2_Link` → `arm3_Link` |
| `arm4_Joint` | revolute | -Y (pitch) | ±1.57 rad | `arm3_Link` → `arm4_Link` |
| `arm5_Joint` | revolute | Z (roll) | ±1.57 rad | `arm4_Link` → `arm5_Link` |
| `Camera_Joint` | **fixed** | — | — | `arm4_Link` → `Camera_Link` |
| `Gripping_Joint` | **fixed** | — | — | `arm5_Link` → `Gripping_point_Link` |

### Gripper Mimic Joints

The gripper is a **parallel linkage** driven by a single actuator (`Rlink1_Joint`). All other gripper joints mimic it:

| Joint | Type | Mimic Source | Multiplier |
|-------|------|-------------|------------|
| `Rlink1_Joint` | revolute | — (master) | — |
| `Rlink2_Joint` | continuous | `Rlink1_Joint` | -1 |
| `Llink1_Joint` | revolute | `Rlink1_Joint` | -1 |
| `Llink2_Joint` | continuous | `Rlink1_Joint` | +1 |
| `Rlink3_Joint` | continuous | `Rlink1_Joint` | +1 |
| `Llink3_Joint` | continuous | `Rlink1_Joint` | -1 |

> **Note:** In the 4-DOF configuration, `arm5_Joint` and the gripper are **not actuated** by the hardware. They exist in the URDF for complete kinematic modeling but are marked as passive in the SRDF.

---

## Link Dimensions & Origins

All link origins are relative to their parent joint. Key dimensions:

| Link | Z-offset from parent | Mass (kg) |
|------|---------------------|-----------|
| `base_link` | ground | 0.207 |
| `arm1_Link` | 92.5mm | 0.0255 |
| `arm2_Link` | 33mm | 0.0534 |
| `arm3_Link` | 82.85mm | 0.0534 |
| `arm4_Link` | 82.85mm | 0.0715 |
| `arm5_Link` | 78.15mm | 0.0533 |

**Total arm reach (approx):** 92.5 + 33 + 82.85 + 82.85 + 78.15 ≈ **369.35mm** from base to wrist

---

## `ai_bringup.launch.py` — Master Entry Point

This launch file starts the **entire system** with a single command:

```bash
ros2 launch dofbot_urdf ai_bringup.launch.py
```

### What it launches:

```python
def generate_launch_description():
    # 1. Include dofbot_moveit/robot_bringup.launch.py
    #    → Hardware driver, Controller Manager, controllers,
    #      MoveIt move_group, RViz
    robot_bringup = IncludeLaunchDescription(...)

    # 2. Launch dofbot_ai agent_node
    #    → ReAct agent with action server
    ai_agent_node = Node(package='dofbot_ai', executable='agent_node')

    # 3. Launch dofbot_ai_gui main
    #    → Streamlit subprocess (opens browser)
    gui_node = Node(package='dofbot_ai_gui', executable='main')
```

### Complete boot sequence:

```
t=0s   → dofbot_hardware plugin loaded (serial port opened)
t=0s   → Robot State Publisher (publishes /robot_description)
t=0s   → Static TF: world → base_link
t=2s   → JointStateBroadcaster (publishes /joint_states)
t=4s   → arm_controller (accepts trajectories)
t=6s   → MoveIt MoveGroup (motion planning services)
t=8s   → RViz (visualization)
t=10s  → GPIO controller (accepts /gpio_controller/commands)
t=~1s  → AI Agent node (waits for MoveIt services, registers tools)
t=~2s  → Streamlit GUI (opens browser at localhost:8501)
```

---

## URDF Source

The URDF was auto-generated by **SolidWorks to URDF Exporter** (version 1.6.0-4-g7f85cfe) and then manually modified to:
- Reduce from 6-DOF to 4-DOF active joints
- Add correct joint limits for the servo range
- Fix mesh file paths to use `package://dofbot_urdf/meshes/`

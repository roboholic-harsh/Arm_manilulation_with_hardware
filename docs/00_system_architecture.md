# Dofbot AI — Complete Technical Architecture

> This document provides a system-wide technical overview of how every component connects, how data flows from a natural language command to physical hardware, and how all packages interact.

---

## System Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: USER INTERFACE                                            │
│  dofbot_ai_gui (Streamlit)                                          │
│  Browser → st.chat_input → ArmTask Action Client                    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ ArmTask.Goal / Feedback / Result
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2: AI REASONING                                              │
│  dofbot_ai (ReAct Agent)                                            │
│  ActionServer → AgentCore → LLM Backend → ToolRegistry              │
└──────────────────┬──────────────────────────┬───────────────────────┘
                   │ MoveIt services          │ GPIO topic
                   ▼                          ▼
┌────────────────────────────┐  ┌────────────────────────────────────┐
│  LAYER 3A: MOTION PLANNING │  │  LAYER 3B: GPIO FORWARDING        │
│  MoveIt 2 MoveGroup        │  │  gpio_controller                  │
│  /plan_kinematic_path       │  │  /gpio_controller/commands        │
│  /execute_trajectory        │  │  → aux_hardware interfaces        │
└────────────┬───────────────┘  └──────────────┬─────────────────────┘
             │ FollowJointTrajectory            │ writes to hw vars
             ▼                                  │
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4: ros2_control                                              │
│  Controller Manager (20 Hz) + arm_controller + joint_state_bcaster  │
│  Calls DofbotSystemHardware::read() and write() every cycle         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ USB Serial (binary packets, 115200 baud)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 5: MICROCONTROLLER                                           │
│  ESP32 Firmware (halkubot_master.ino)                               │
│  Serial ↔ I²C bridge to Yahboom expansion board                    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ I²C (100 kHz, address 0x15)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 6: PHYSICAL HARDWARE                                        │
│  4 Servo Motors + RGB LED + Buzzer + Encoders                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Trace: "Move joint 1 to 45 degrees and turn the LED green"

### Step 1: User Input → GUI
**File:** `dofbot_ai_gui/app.py`
```
User types "Move joint 1 to 45 degrees and turn the LED green"
→ st.session_state.messages.append({"role": "user", "content": "..."})
→ st.rerun()
→ send_command(node, prompt, ...)
→ node.action_client.send_goal_async(ArmTask.Goal(json_command="..."))
```

### Step 2: Action Server → ReAct Agent
**File:** `dofbot_ai/agent_node.py`
```
_execute_callback(goal_handle):
    user_message = "Move joint 1 to 45 degrees and turn the LED green"
    publish_feedback("Processing...")
    agent._feedback_cb = goal_handle.publish_feedback
    result_text = agent.run(user_message)
```

### Step 3: ReAct Loop — Step 1 (Move)
**File:** `dofbot_ai/agent_core.py`
```
messages = [system_prompt, "Move joint 1 to 45 degrees and turn the LED green"]
response = llm.chat(messages, tools=[10 tool schemas])
→ LLM returns: tool_call("move_joints", {"joint_angles": [45, -402, -402, -402]})
→ feedback("🔧 Calling tool: move_joints(...)")
→ registry.execute("move_joints", joint_angles=[45, -402, -402, -402])
```

### Step 4: MoveJointsTool Execution
**File:** `dofbot_ai/tools/move_joints.py`
```
1. Read current_joint_state from /joint_states subscription
2. Joint 1: 45° → 0.785 rad
3. Joints 2-4: -402 → keep current values from joint state
4. Build MotionPlanRequest with JointConstraints
5. Call /plan_kinematic_path → get trajectory
6. Send trajectory to /execute_trajectory
7. Wait for execution complete
```

### Step 5: Trajectory Through ros2_control
**Files:** `dofbot_moveit/config/`, `dofbot_hardware/src/dofbot_system.cpp`
```
MoveIt MoveGroup → FollowJointTrajectory action → arm_controller
→ arm_controller interpolates trajectory points at 20 Hz
→ Each cycle: writes to hw_commands_[0..3]
→ DofbotSystemHardware::write():
    - Converts hw_commands_ radians → degrees
    - Packs CommandPacket(cmd_type=1, params=[135, 90, 90, 90, 1000])
      (45° in ROS = 135° in servo space because rad_to_deg adds 90° offset)
    - Sends 13 bytes over USB serial
```

### Step 6: ESP32 → Physical Servo
**File:** `useful_scripts/ESP_codes/halkubot_master/halkubot_master.ino`
```
1. Receives 13-byte CommandPacket on Serial
2. Validates checksum
3. cmd_type == 1 (MOVE):
   - Maps angles to pulse widths: map(135, 0, 180, 900, 3100) = 2550
   - Joints 2-4: inverts (180 - angle)
   - Injects dummy J5 and J6 values
   - Writes transit time to I²C register 0x1E
   - Writes 6 servo positions to I²C register 0x1D
   → Physical servo 1 rotates to 135° (= 45° in ROS space)
```

### Step 7: ReAct Loop — Step 2 (RGB)
**File:** `dofbot_ai/agent_core.py`
```
messages now include: [system, user, assistant_tool_call, tool_result_success]
response = llm.chat(messages, tools=[...])
→ LLM returns: tool_call("rgb_control", {"r": 0, "g": 255, "b": 0})
→ feedback("🔧 Calling tool: rgb_control(...)")
→ registry.execute("rgb_control", r=0, g=255, b=0)
```

### Step 8: RGB Through GPIO Pipeline
**Files:** `dofbot_ai/tools/rgb_control.py` → `agent_node.py` → hardware
```
1. Tool sets node.led_r=0, node.led_g=255, node.led_b=0
2. node.publish_gpio_command():
   → Float64MultiArray([0, 255, 0, 1.0, 0]) → /gpio_controller/commands
3. gpio_controller receives → writes to aux_hardware interfaces:
   - led_r = 0.0, led_g = 255.0, led_b = 0.0
4. DofbotSystemHardware::write() detects change:
   - hw_led_g_ (255) != prev_led_g_ (-1) → dirty!
   - Packs CommandPacket(cmd_type=2, params=[0, 255, 0, 0, 0])
   - Sends over serial
5. ESP32: calls setRGB(0, 255, 0)
   → I²C write to register 0x02: [0, 255, 0]
   → LED turns green
```

### Step 9: ReAct Loop — Step 3 (Final Response)
```
messages now include all tool calls and results
response = llm.chat(messages, tools=[...])
→ LLM returns: text = "Done! I moved joint 1 to 45° and turned the LED green."
→ return "Done! I moved joint 1 to 45° and turned the LED green."
```

### Step 10: Result → GUI
```
agent_node: goal_handle.succeed()
    result.success = True
    result.message = "Done! I moved joint 1 to 45° and turned the LED green."
→ GUI receives result
→ st.session_state.messages.append({"role": "assistant", "content": "✅ Done! ..."})
→ st.rerun() → renders green-checkmark AI bubble
```

---

## ROS 2 Communication Map

### Topics

| Topic | Type | Publisher | Subscriber | Rate |
|-------|------|----------|------------|------|
| `/joint_states` | `JointState` | `joint_state_broadcaster` | AI agent, MoveIt, RViz | 20 Hz |
| `/gpio_controller/commands` | `Float64MultiArray` | AI agent (tools) | `gpio_controller` | On-demand |
| `/robot_description` | `String` | `robot_state_publisher` | MoveIt, RViz | Latched |

### Services

| Service | Type | Server | Client |
|---------|------|--------|--------|
| `/plan_kinematic_path` | `GetMotionPlan` | MoveIt MoveGroup | AI agent (`move_joints`) |

### Actions

| Action | Type | Server | Client |
|--------|------|--------|--------|
| `/dofbot_command` | `ArmTask` | AI agent | Streamlit GUI |
| `/execute_trajectory` | `ExecuteTrajectory` | MoveIt MoveGroup | AI agent (`move_joints`) |
| `/arm_controller/follow_joint_trajectory` | `FollowJointTrajectory` | `arm_controller` | MoveIt |

---

## Active ROS 2 Nodes

| Node | Package | Purpose |
|------|---------|---------|
| `robot_state_publisher` | `robot_state_publisher` | Publishes URDF → TF tree |
| `ros2_control_node` | `controller_manager` | Loads hardware plugin, runs control loop |
| `joint_state_broadcaster` | `ros2_controllers` | Publishes /joint_states |
| `arm_controller` | `ros2_controllers` | Trajectory execution |
| `gpio_controller` | `ros2_controllers` | GPIO forwarding |
| `move_group` | `moveit_ros_move_group` | Motion planning |
| `rviz2` | `rviz2` | Visualization |
| `static_transform_publisher` | `tf2_ros` | world → base_link TF |
| `dofbot_agent_node` | `dofbot_ai` | AI ReAct agent |
| `dofbot_ai_gui_node` | `dofbot_ai_gui` | Streamlit ROS bridge |

---

## Angle Conventions

The system has **three different angle representations** that are converted at different layers:

| Layer | Range | Center | Example "45° ROS" |
|-------|-------|--------|-------------------|
| **ROS 2 / MoveIt** | -π/2 to +π/2 rad | 0 rad | +0.785 rad |
| **dofbot_hardware** | 0° to 180° | 90° | 135° |
| **ESP32 / Servo** | Pulse 900-3100 | Pulse 2000 | Pulse 2550 |

### Conversion Functions

```
ROS → Hardware:  deg = max(0, min(rad × 180/π + 90, 180))
Hardware → ROS:  rad = (deg - 90) × π/180
Hardware → Servo: pulse = map(deg, 0, 180, 900, 3100)
```

Joints 2-4 are additionally **inverted** on the ESP32: `angle = 180 - angle` before pulse conversion, because the physical motor is mounted in reverse.

---

## Build Order

```bash
# 1. Interfaces first (generates Python/C++ types)
colcon build --packages-select dofbot_custom_interfaces

# 2. URDF package (provides meshes and URDF)
colcon build --packages-select dofbot_urdf

# 3. Hardware driver (C++ shared library)
colcon build --packages-select dofbot_hardware

# 4. MoveIt config (depends on dofbot_urdf, dofbot_hardware)
colcon build --packages-select dofbot_moveit

# 5. AI packages (depends on interfaces)
colcon build --packages-select dofbot_ai dofbot_ai_gui

# Or build everything:
colcon build --symlink-install
```

---

## Package Dependency Graph

```
dofbot_custom_interfaces  ←── dofbot_ai
                          ←── dofbot_ai_gui

dofbot_urdf  ←── dofbot_moveit  ←── dofbot_ai (uses MoveIt services)

dofbot_hardware  ←── dofbot_moveit (loads as ros2_control plugin)

useful_scripts  (standalone, no ROS dependencies)
```

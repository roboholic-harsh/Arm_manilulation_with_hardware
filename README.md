<p align="center">
  <img src="https://img.shields.io/badge/ROS_2-Humble-blue?logo=ros&logoColor=white" alt="ROS 2 Humble" />
  <img src="https://img.shields.io/badge/MoveIt_2-Motion_Planning-blueviolet" alt="MoveIt 2" />
  <img src="https://img.shields.io/badge/LLM-ReAct_Agent-orange?logo=openai" alt="LLM Agent" />
  <img src="https://img.shields.io/badge/ESP32-Firmware-green?logo=espressif" alt="ESP32" />
  <img src="https://img.shields.io/badge/Streamlit-GUI-red?logo=streamlit" alt="Streamlit" />
  <img src="https://img.shields.io/badge/C++-Hardware_Interface-00599C?logo=cplusplus" alt="C++" />
  <img src="https://img.shields.io/badge/Python-3.10+-yellow?logo=python" alt="Python" />
</p>

<h1 align="center">🤖 Dofbot AI — LLM-Powered Robotic Arm</h1>

<p align="center">
  <strong>A natural-language-controlled 4-DOF robotic arm powered by ROS 2, MoveIt 2, and an LLM ReAct agent.</strong><br/>
  Talk to your robot in plain English — the AI plans and executes real-world motions, GPIO peripherals, and multi-step tasks autonomously.
</p>

---

## 🎬 How It Works

```
User: "Move joint 1 to 45 degrees and turn the LED green"
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  Streamlit Chat UI  →  ROS 2 Action  →  ReAct Agent Loop    │
│                                                              │
│  LLM reasons:  "I need to call move_joints then rgb_control" │
│    Step 1: move_joints([45, -402, -402, -402])  ──→ MoveIt   │
│    Step 2: rgb_control(r=0, g=255, b=0)         ──→ GPIO     │
│    Step 3: "Done! Joint 1 at 45° and LED is green."          │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
Physical arm moves + LED turns green 🟢
```

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                              │
│                    Streamlit Chat Interface                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ ArmTask Action (Goal/Feedback/Result)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    dofbot_ai  (Agent Backend)                        │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────────┐      │
│  │ AgentCore│◄──│  LLM Backend │   │     Tool Registry      │      │
│  │ (ReAct)  │──►│ Gemini/Groq/ │   │  10 Robot Tools        │      │
│  │          │   │ Ollama       │   │  (move, GPIO, sensor)  │      │
│  └──────────┘   └──────────────┘   └───────────┬────────────┘      │
└────────────────────────────────────────────────┬────────────────────┘
                                                 │
                    ┌────────────────────────────┬┘
                    ▼                            ▼
         ┌──────────────────┐         ┌──────────────────────┐
         │    MoveIt 2      │         │   GPIO Controller    │
         │ Plan + Execute   │         │ RGB / Torque / Buzz  │
         └────────┬─────────┘         └──────────┬───────────┘
                  │                              │
                  └──────────────┬───────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              dofbot_hardware  (ros2_control Plugin)                  │
│         C++ SystemInterface  ──  Serial @ 115200 baud               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ USB Serial (Binary Protocol)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│            ESP32 Firmware  (I²C Master → Servo Board)               │
│         4 Servo Motors  •  RGB LED  •  Buzzer  •  Encoders          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Package Overview

| Package | Language | Purpose |
|---------|----------|---------|
| [`dofbot_ai`](#-dofbot_ai--ai-agent-backend) | Python | LLM ReAct agent with 10 robot tools & action server |
| [`dofbot_ai_gui`](#-dofbot_ai_gui--streamlit-chat-ui) | Python | Premium dark-mode Streamlit chat interface |
| [`dofbot_hardware`](#-dofbot_hardware--ros2_control-driver) | C++ | `ros2_control` hardware plugin — serial I/O to ESP32 |
| [`dofbot_moveit`](#-dofbot_moveit--motion-planning) | Config | MoveIt 2 configuration for the 4-DOF arm + GPIO |
| [`dofbot_urdf`](#-dofbot_urdf--robot-model) | URDF | Full URDF model with 14 STL meshes (SolidWorks export) |
| [`dofbot_custom_interfaces`](#-dofbot_custom_interfaces) | C++ | ROS 2 `ArmTask.action` definition |
| [`useful_scripts`](#-useful_scripts) | Python/C++ | ESP32 Arduino firmware + standalone Tkinter commander |

> 📖 **Deep technical documentation** for each package is available in the [`docs/`](docs/) directory.

---

## 🧠 `dofbot_ai` — AI Agent Backend

The brain of the system. Implements a **ReAct (Reasoning + Acting) agent** that interprets natural language and calls robot tools iteratively.

### Key Files

| File | Purpose |
|------|---------|
| `agent_node.py` | ROS 2 node — Action Server, MoveIt clients, GPIO publisher, tool wiring |
| `agent_core.py` | ReAct loop engine — LLM ↔ Tool execution cycle (max 15 steps) |
| `llm_backends/` | Pluggable LLM backends: **Gemini**, **Groq**, **Ollama** |
| `tools/` | 10 robot tool implementations |

### LLM Backends

| Backend | SDK | API Key |
|---------|-----|---------|
| **Google Gemini** | `google-generativeai` | `GEMINI_API_KEY` |
| **Groq** (default) | `groq` Python SDK | `GROQ_API_KEY` |
| **Ollama** (local) | HTTP `/api/chat` | None |

> Default: **Groq** with `qwen/qwen3-32b` model

### Robot Tools

| Category | Tool | Description |
|----------|------|-------------|
| **Motion** | `move_joints` | Plan + execute via MoveIt 2. Use `-402` to keep a joint unchanged |
| **Motion** | `move_to_home` | Preset: `[0°, 90°, -90°, -90°]` |
| **Motion** | `move_to_zero` | Preset: `[0°, 0°, 0°, 0°]` |
| **Motion** | `move_to_ready_pose` | Preset: `[0°, 45°, -90°, -45°]` |
| **GPIO** | `rgb_control` | Set RGB LED color (0-255 per channel) |
| **GPIO** | `torque_control` | Enable/disable motor torque |
| **GPIO** | `buzzer_control` | Toggle piezo buzzer |
| **Sensor** | `get_encoder_values` | Read live joint positions from `/joint_states` |
| **Utility** | `wait` | Sleep 0–300 seconds |
| **Utility** | `print_message` | Send live text updates to the GUI |

---

## 💬 `dofbot_ai_gui` — Streamlit Chat UI

A premium **dark-mode glassmorphism** chat interface built with Streamlit.

### Features
- 🎨 Custom CSS with `Outfit` font, purple/indigo radial gradients on `#0a0a0f` background
- 💬 Custom HTML chat bubbles with `fadeIn` animations
- 🔄 Live tool-call feedback during agent execution
- 📡 ROS 2 connection status indicator in sidebar
- 🔧 Active tool badge grid
- 💡 Suggestion prompts for quick commands

### Feedback Pipeline
The GUI receives real-time feedback via the `ArmTask` action's `Feedback.state` field:
- **Tool calls** → gray italic status text
- **`[USER_MSG]` prefix** → rendered as distinct blue-bordered chat bubbles

---

## ⚙️ `dofbot_hardware` — ros2_control Driver

A **C++ `SystemInterface` plugin** for `ros2_control` that communicates with the physical robot via USB serial.

### Binary Protocol

| Packet | Header | Direction | Purpose |
|--------|--------|-----------|---------|
| `CommandPacket` | `0xA6` | PC → ESP32 | Move, RGB, Torque, Buzz, Get Encoders |
| `StatePacket` | `0xA5` | ESP32 → PC | 4× encoder angles + checksum |

### Command Types

| `cmd_type` | Command | Params |
|------------|---------|--------|
| `1` | MOVE | `[angle1, angle2, angle3, angle4, transit_time]` |
| `2` | RGB | `[R, G, B, 0, 0]` |
| `3` | TORQUE | `[enable, 0, 0, 0, 0]` |
| `4` | BUZZER | `[state, 0, 0, 0, 0]` |
| `5` | GET_ENCODERS | Request encoder readback |

### GPIO Interfaces
Exposed as `ros2_control` command interfaces under the `aux_hardware` GPIO group:
- `led_r`, `led_g`, `led_b` — RGB LED channels
- `torque_enable` — Motor torque on/off
- `buzzer_trigger` — Buzzer on/off

---

## 🦾 `dofbot_moveit` — Motion Planning

MoveIt 2 configuration for the **`dofbot_arm`** planning group (4 revolute joints).

### Configuration

| File | Purpose |
|------|---------|
| `dofbot_urdf.ros2_control.xacro` | Hardware plugin binding (`dofbot_hardware/DofbotSystemHardware`) |
| `dofbot_urdf.srdf` | Semantic robot description — planning groups, pose presets |
| `ros2_controllers.yaml` | Controller definitions — `arm_controller` + `gpio_controller` |
| `kinematics.yaml` | KDL kinematics solver config |
| `joint_limits.yaml` | Joint velocity/acceleration limits |

### Controllers

| Controller | Type | Interfaces |
|------------|------|------------|
| `arm_controller` | `JointTrajectoryController` | 4 position joints |
| `gpio_controller` | `MultiInterfaceForwardCommandController` | 5 GPIO interfaces |
| `joint_state_broadcaster` | `JointStateBroadcaster` | Position feedback |

### Launch Sequence (`robot_bringup.launch.py`)
```
t=0s   → Hardware driver + Robot State Publisher
t=0s   → Static virtual joint TFs
t=2s   → Joint State Broadcaster
t=4s   → Arm Controller
t=6s   → MoveIt Move Group
t=8s   → RViz
t=10s  → GPIO Controller
```

---

## 🏗️ `dofbot_urdf` — Robot Model

Full **URDF model** of the Yahboom Dofbot arm exported from SolidWorks.

### Kinematic Chain
```
base_link → arm1_Link (Z-axis) → arm2_Link (Y-axis) → arm3_Link (Y-axis)
  → arm4_Link (Y-axis) → arm5_Link (Z-axis) → Gripper linkage + Camera
```

### Links & Meshes (14 STL files)
- `base_link` — Base platform (~38 MB mesh)
- `arm1-4_Link` — Main arm segments (4 actuated joints)
- `arm5_Link` — Wrist rotation (passive in 4-DOF config)
- `Rlink1-3`, `Llink1-3` — Parallel gripper linkage (mimic joints)
- `Camera_Link` — Camera mount (fixed joint)
- `Gripping_point_Link` — Gripper tip (fixed joint)

---

## 📡 `dofbot_custom_interfaces`

Defines the `ArmTask.action` used for GUI ↔ Agent communication:

```
# Goal
string json_command        ← Natural language command

---
# Result  
bool success               ← Completion status
string message             ← Final LLM response text

---
# Feedback
string state               ← Live tool execution updates
```

---

## 🛠️ `useful_scripts`

### ESP32 Firmware (`halkubot_master.ino`)
Arduino firmware for the ESP32 that acts as an **I²C master** to the Yahboom servo expansion board:
- Receives binary commands via USB Serial at 115200 baud
- Translates commands to I²C writes (address `0x15`)
- Reads encoder positions and transmits back with checksums
- Handles: Move (4 motors), RGB LED, Torque, Buzzer, Encoder polling
- I²C pins: **SDA=21, SCL=22**

### Tkinter Robot Commander (`tkinter_robot_commander.py`)
Standalone Python GUI for direct serial control (no ROS required):
- 4 joint sliders with real-time telemetry
- RGB, Torque, and Buzzer controls
- Master polling loop at ~20 Hz
- Useful for hardware debugging and testing

---

## 🚀 Quick Start

### Prerequisites
- **Ubuntu 22.04** with **ROS 2 Humble**
- **MoveIt 2** (`sudo apt install ros-humble-moveit`)
- **ros2_control** (`sudo apt install ros-humble-ros2-control ros-humble-ros2-controllers`)
- **LibSerial** (`sudo apt install libserial-dev`)
- **Python 3.10+** with `pip install streamlit groq google-generativeai`
- **ESP32** flashed with `halkubot_master.ino`

### 1. Clone & Build

```bash
cd ~/dofbotarm/harsh_ws
colcon build --symlink-install
source install/setup.bash
```

### 2. Set API Key

```bash
# For Groq (default)
export GROQ_API_KEY="your-key-here"

# OR for Gemini
export GEMINI_API_KEY="your-key-here"
```

### 3. Launch Everything

```bash
# One command to launch Hardware + MoveIt + AI Agent + GUI
ros2 launch dofbot_urdf ai_bringup.launch.py
```

This launches:
1. **Hardware drivers** — serial connection to ESP32
2. **ros2_control controllers** — joint trajectory + GPIO
3. **MoveIt 2** — motion planning + RViz
4. **AI Agent** — ReAct action server
5. **Streamlit GUI** — opens in your browser

### 4. Start Talking to Your Robot! 🎉

Open the Streamlit interface and try:
- *"Move the first joint to 45 degrees"*
- *"Go to home position and turn the LED red"*
- *"Where are your joints right now?"*
- *"Wave the arm: go to zero, wait 2 seconds, go to ready pose"*

---

## 🔧 Configuration

### Agent Config (`dofbot_ai/config/agent_config.yaml`)

```yaml
agent:
  system_prompt: |
    You are Dofbot AI Assistant, a helpful 4-DOF robot arm assistant...
  max_steps: 15
  default_provider: "groq"        # groq | gemini | ollama
  default_model: "qwen/qwen3-32b"

robot:
  arm_group: "dofbot_arm"
  joint_names: [arm1_Joint, arm2_Joint, arm3_Joint, arm4_Joint]
  dof: 4
  home_position: [0.0, 90.0, -90.0, -90.0]
```

### ROS Parameter Overrides

```bash
ros2 run dofbot_ai agent_node --ros-args \
  -p provider:=gemini \
  -p model:=gemini-2.0-flash \
  -p api_key:=YOUR_KEY
```

---

## 🗺️ ROS 2 Interface Map

| Interface | Type | Direction | Used By |
|-----------|------|-----------|---------|
| `/dofbot_command` | `ArmTask` Action | GUI → Agent | Communication bridge |
| `/joint_states` | `JointState` Topic | Hardware → Agent | Encoder feedback |
| `/gpio_controller/commands` | `Float64MultiArray` Topic | Agent → Hardware | RGB, Torque, Buzzer |
| `/plan_kinematic_path` | `GetMotionPlan` Service | Agent → MoveIt | Motion planning |
| `/execute_trajectory` | `ExecuteTrajectory` Action | Agent → MoveIt | Trajectory execution |

---

## 🧱 Hardware Stack

| Component | Details |
|-----------|---------|
| **Robot** | Yahboom Dofbot (modified 4-DOF) |
| **MCU** | ESP32 (I²C master, USB serial bridge) |
| **Servo Board** | Yahboom expansion board @ `0x15` |
| **Motors** | 4× servo motors (0-180° range) |
| **Peripherals** | RGB LED, Piezo Buzzer, Torque control |
| **Camera** | Fixed-mount camera on arm4 |
| **Connection** | USB Serial @ 115200 baud (`/dev/ttyUSB0`) |
| **I²C** | SDA=GPIO21, SCL=GPIO22, 100kHz |

---

## 📂 Repository Structure

```
src/
├── docs/                     # 📖 Deep technical documentation
│   ├── 00_system_architecture.md   # End-to-end data flow & system overview
│   ├── 01_dofbot_hardware.md       # C++ ros2_control driver deep dive
│   ├── 02_dofbot_moveit.md         # MoveIt 2 configuration details
│   ├── 03_dofbot_urdf.md           # URDF model & kinematic chain
│   ├── 04_dofbot_ai.md             # AI ReAct agent architecture
│   ├── 05_dofbot_ai_gui.md         # Streamlit GUI internals
│   ├── 06_dofbot_custom_interfaces.md  # Action definition & usage
│   └── 07_useful_scripts.md        # ESP32 firmware & Tkinter commander
├── dofbot_ai/                # 🧠 LLM ReAct Agent
│   ├── config/agent_config.yaml
│   └── dofbot_ai/
│       ├── agent_node.py     # ROS 2 Action Server
│       ├── agent_core.py     # ReAct loop engine
│       ├── llm_backends/     # gemini, groq, ollama
│       └── tools/            # 10 robot tools
├── dofbot_ai_gui/            # 💬 Streamlit Chat UI
│   └── dofbot_ai_gui/
│       ├── app.py            # Full Streamlit application
│       └── main.py           # ROS 2 entry point
├── dofbot_custom_interfaces/ # 📡 ArmTask.action definition
│   └── action/ArmTask.action
├── dofbot_hardware/          # ⚙️ C++ ros2_control driver
│   ├── include/dofbot_hardware/dofbot_system.hpp
│   └── src/dofbot_system.cpp
├── dofbot_moveit/            # 🦾 MoveIt 2 config (URDF-based)
│   ├── config/               # controllers, kinematics, SRDF
│   └── launch/               # bringup, move_group, rviz
├── dofbot_urdf/              # 🏗️ Robot URDF + meshes
│   ├── launch/ai_bringup.launch.py  # ⭐ Main entry point
│   ├── meshes/               # 14 STL files
│   └── urdf/dofbot.urdf
└── useful_scripts/           # 🛠️ Standalone tools
    ├── ESP_codes/halkubot_master/halkubot_master.ino
    └── tkinter_robot_commander.py
```

---

## 🎨 Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **ReAct Agent** | `AgentCore` | LLM reasons step-by-step, calling tools iteratively until done |
| **Strategy** | LLM Backends | All 3 providers implement `BaseLLMBackend.chat()` — hot-swappable |
| **Delegate** | Preset Poses | Home/Zero/Ready tools delegate to `MoveJointsTool.execute()` |
| **GPIO Multiplexing** | Hardware driver | All peripherals share a single `Float64MultiArray` publisher |
| **Action Feedback** | Streamlit GUI | Live tool updates streamed via ROS 2 action protocol |

---

## 👤 Author

**Harsh Jadav** ([@roboholic_harsh](https://github.com/roboholic-harsh))  
📧 harshpjadav165@gmail.com


**Kathan Shah** ([@kathanshah28](https://github.com/kathanshah28))  
📧 kathanshah2004@gmail.com

---

## 📄 License

This project is currently unlicensed. License declaration pending.

---

<p align="center">
  <i>Built with ❤️ using ROS 2, MoveIt 2, and the power of LLMs</i>
</p>

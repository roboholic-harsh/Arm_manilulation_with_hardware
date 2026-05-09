# `dofbot_custom_interfaces` — ROS 2 Action Definition

> **Type:** C++ (ament_cmake) with `rosidl_default_generators`  
> **Role:** Defines the `ArmTask.action` interface used for GUI ↔ Agent communication.

---

## Purpose

This is a **pure interface package** — it contains no executable code. It defines the `ArmTask` action message type that is the sole communication contract between the Streamlit GUI (action client) and the AI agent (action server).

---

## File Map

```
dofbot_custom_interfaces/
├── CMakeLists.txt     # Uses rosidl_generate_interfaces to build the action
├── package.xml        # Depends on action_msgs, rosidl_default_generators
├── action/
│   └── ArmTask.action # ⭐ The action definition
├── include/           # Auto-generated C++ headers (after build)
└── src/               # Empty
```

---

## `ArmTask.action` Definition

```
# Goal
string json_command        ← Natural language command from user

---
# Result
bool success               ← True if agent completed successfully
string message             ← Final LLM text response

---
# Feedback
string state               ← Live tool call updates / [USER_MSG] bubbles
```

### Field Details

#### Goal: `json_command`
Despite the name, this is a **plain English string**, not JSON. Examples:
- `"Move joint 1 to 45 degrees"`
- `"Go home and turn the LED red"`
- `"Where are your joints right now?"`

The name `json_command` is a legacy artifact from an earlier design where structured JSON commands were planned.

#### Result: `success` + `message`
- `success=True, message="Done! I moved joint 1 to 45° and set the LED to red."` — agent completed
- `success=False, message="Motion planning failed. Target may be unreachable."` — agent error
- `success=False, message="Agent error: Groq API returned 503"` — backend error

#### Feedback: `state`
Published multiple times during execution. The GUI interprets the `state` string differently based on prefix:

| Prefix | Rendering | Example |
|--------|-----------|---------|
| `[USER_MSG]` | Blue-bordered chat bubble | `[USER_MSG]Current positions: {arm1: 0.5, ...}` |
| `🔧 Calling tool:` | Gray italic status text | `🔧 Calling tool: move_joints({'joint_angles': [45, -402, -402, -402]})` |
| `📋 Result:` | Gray italic status text | `📋 Result: ✅ Successfully moved joints to [45, ...]` |
| Other | Gray italic status text | `Processing...` |

---

## Build System

```cmake
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/ArmTask.action"
  DEPENDENCIES action_msgs
)
```

This generates:
- **Python:** `dofbot_custom_interfaces.action.ArmTask` (Goal, Result, Feedback classes)
- **C++:** `dofbot_custom_interfaces/action/arm_task.hpp`
- **IDL/typesupport** libraries for serialization

---

## Usage in Code

### Python (Agent Node — Action Server)
```python
from dofbot_custom_interfaces.action import ArmTask

# Action server
self._action_server = ActionServer(self, ArmTask, 'dofbot_command', self._execute_callback)

# In callback:
goal_handle.request.json_command  # → "Move joint 1 to 45 degrees"
feedback = ArmTask.Feedback()
feedback.state = "🔧 Calling tool: move_joints(...)"
goal_handle.publish_feedback(feedback)

result = ArmTask.Result()
result.success = True
result.message = "Done!"
```

### Python (GUI — Action Client)
```python
from dofbot_custom_interfaces.action import ArmTask

self.action_client = ActionClient(self, ArmTask, '/dofbot_command')
goal_msg = ArmTask.Goal()
goal_msg.json_command = "Move joint 1 to 45 degrees"
send_future = self.action_client.send_goal_async(goal_msg, feedback_callback=cb)
```

---

## Data Flow Through the Action

```
Streamlit GUI                            AI Agent Node
    │                                        │
    ├── ArmTask.Goal ──────────────────────► │ _execute_callback()
    │   json_command = "Move j1 to 45°"      │
    │                                        │ agent.run("Move j1 to 45°")
    │                                        │   ├── LLM → tool_call
    │ ◄──────────── ArmTask.Feedback ───────┤   ├── feedback("🔧 Calling move_joints")
    │               state = "🔧 Calling..."  │   ├── execute tool
    │ ◄──────────── ArmTask.Feedback ───────┤   ├── feedback("📋 Result: ✅ ...")
    │               state = "📋 Result..."   │   ├── LLM → text
    │                                        │   └── return "Done!"
    │ ◄──────────── ArmTask.Result ─────────┤
    │   success=True                         │
    │   message="Done! Moved j1 to 45°"     │
    ▼                                        ▼
```

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `ament_cmake` | Build system |
| `rosidl_default_generators` | Generates Python/C++ from .action file |
| `action_msgs` | Base action message types |

### Build Command
```bash
colcon build --packages-select dofbot_custom_interfaces
```

> **Important:** This package must be built **before** `dofbot_ai` and `dofbot_ai_gui` since they import from it.

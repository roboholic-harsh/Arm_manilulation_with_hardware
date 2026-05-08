# Dofbot AI System — Complete Architectural Analysis

## System Overview

The Dofbot AI system is a **natural-language-controlled robotic arm** built on two ROS 2 packages that together form an **LLM-powered ReAct (Reasoning + Acting) agent**. A user types a command in a chat UI → an LLM decides which robot tools to call → tools execute real MoveIt motions and GPIO commands on the physical 4-DOF Yahboom Dofbot arm.

```mermaid
graph LR
    subgraph "dofbot_ai_gui (Frontend)"
        A["Streamlit Chat UI<br/>app.py"] --> B["GUIRosNode<br/>(ROS 2 Action Client)"]
    end

    subgraph "dofbot_ai (Backend)"
        C["DofbotAgentNode<br/>(ROS 2 Action Server)"] --> D["AgentCore<br/>(ReAct Loop)"]
        D --> E["LLM Backend<br/>(Gemini / Groq / Ollama)"]
        D --> F["ToolRegistry<br/>(10 Robot Tools)"]
    end

    subgraph "Hardware Layer"
        G["MoveIt 2<br/>(Plan + Execute)"]
        H["GPIO Controller<br/>(RGB, Buzzer, Torque)"]
        I["/joint_states Topic"]
    end

    B -- "ArmTask Action<br/>(Goal: json_command)" --> C
    C -- "Feedback: state" --> B
    F --> G
    F --> H
    F --> I
```

---

## Package 1: `dofbot_ai` — The Agent Backend

### File Structure

| File | Purpose |
|------|---------|
| [agent_node.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/agent_node.py) | ROS 2 node: Action Server + wiring everything together |
| [agent_core.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/agent_core.py) | ReAct loop engine (LLM ↔ Tool execution cycle) |
| [agent_config.yaml](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/config/agent_config.yaml) | System prompt, provider, model, joint names |
| [base_backend.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/llm_backends/base_backend.py) | Abstract LLM interface (`BaseLLMBackend`, `LLMResponse`, `ToolCall`) |
| [gemini_backend.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/llm_backends/gemini_backend.py) | Google Gemini backend (native function calling) |
| [groq_backend.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/llm_backends/groq_backend.py) | Groq backend (OpenAI-compatible API) |
| [ollama_backend.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/llm_backends/ollama_backend.py) | Ollama local backend (HTTP `/api/chat`) |
| [base_tool.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/base_tool.py) | Abstract tool class + `ToolResult` dataclass |
| [registry.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/registry.py) | Central tool registration + execution + schema generation |
| [move_joints.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/move_joints.py) | **Core motion tool** — MoveIt plan + execute |
| [move_to_home.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/move_to_home.py) | Preset: `[0, 90, -90, -90]` degrees |
| [move_to_zero.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/move_to_zero.py) | Preset: `[0, 0, 0, 0]` degrees |
| [move_to_ready_pose.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/move_to_ready_pose.py) | Preset: `[0, 45, -90, -45]` degrees |
| [torque_control.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/torque_control.py) | Enable/disable motor torque via GPIO |
| [rgb_control.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/rgb_control.py) | Set RGB LED color via GPIO |
| [buzzer_control.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/buzzer_control.py) | Toggle buzzer via GPIO |
| [get_encoder_values.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/get_encoder_values.py) | Read current joint positions from `/joint_states` |
| [wait.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/wait.py) | `time.sleep()` with 0–300s safety cap |
| [print_message.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai/dofbot_ai/tools/print_message.py) | Send a `[USER_MSG]` to the GUI via feedback callback |

---

### 1. Node Initialization Flow (`DofbotAgentNode.__init__`)

```mermaid
sequenceDiagram
    participant Main as main()
    participant Node as DofbotAgentNode
    participant Config as agent_config.yaml
    participant MoveIt as MoveIt 2 Services
    participant Registry as ToolRegistry
    participant LLM as LLM Backend
    participant Core as AgentCore
    participant ActionSrv as ActionServer

    Main->>Node: __init__()
    Node->>Config: Load YAML (param or share dir)
    Config-->>Node: system_prompt, provider, model,<br/>arm_group, joint_names
    Node->>Node: Subscribe to /joint_states
    Node->>Node: Create /gpio_controller/commands publisher
    Node->>MoveIt: Wait for /plan_kinematic_path (30s)
    Node->>MoveIt: Wait for /execute_trajectory (30s)
    Node->>Registry: Register 10 tools
    Node->>LLM: Create backend (gemini/groq/ollama)
    Node->>Core: Create AgentCore(llm, registry, prompt, max_steps=15)
    Node->>ActionSrv: Create ActionServer('dofbot_command')
    Note right of Node: 🤖 Ready!
```

**Key details:**
- Config is loaded from a ROS param `config_file` or falls back to the installed share directory
- ROS params `provider`, `model`, `api_key` can override YAML defaults
- Defaults: **Groq** provider with `qwen/qwen3-32b` model, **15 max ReAct steps**
- Robot config: `dofbot_arm` planning group, 4 joints (`arm1_Joint` through `arm4_Joint`)

---

### 2. The ReAct Loop (`AgentCore.run`)

This is the **brain** of the system. It implements a classic ReAct (Reason + Act) pattern:

```mermaid
flowchart TD
    A["User message arrives"] --> B["Build messages:<br/>system_prompt + user_message"]
    B --> C["Get tool definitions<br/>from ToolRegistry"]
    C --> D{"Step ≤ max_steps?"}
    D -- Yes --> E["Call LLM.chat(messages, tools)"]
    E --> F{"Response type?"}
    F -- "tool_calls" --> G["For each tool_call:<br/>registry.execute(name, args)"]
    G --> H["Append assistant + tool_result<br/>messages to history"]
    H --> I["Send feedback to GUI<br/>(🔧 / 📋 updates)"]
    I --> D
    F -- "text" --> J["Return final text<br/>to the user ✅"]
    D -- "No (max steps)" --> K["Return: 'Completed<br/>available steps'"]

    style A fill:#4f46e5,color:#fff
    style J fill:#10b981,color:#fff
    style K fill:#f59e0b,color:#fff
    style G fill:#8b5cf6,color:#fff
```

**Step-by-step:**
1. Build the message array: `[system_prompt, user_message]`
2. Collect JSON schemas of all 10 tools from `ToolRegistry.get_tool_definitions()`
3. Loop (up to 15 iterations):
   - Send messages + tool schemas to LLM → get `LLMResponse`
   - If response contains `tool_calls` → execute each tool → append results to message history → loop back
   - If response contains `text` → done, return text to user
4. If 15 steps exhausted → return a fallback message

---

### 3. LLM Backend Abstraction

All three backends implement the same interface:

```mermaid
classDiagram
    class BaseLLMBackend {
        <<abstract>>
        +chat(messages, tools) LLMResponse
    }
    class LLMResponse {
        +text: str?
        +tool_calls: List~ToolCall~
        +has_tool_calls() bool
    }
    class ToolCall {
        +name: str
        +args: dict
        +id: str
    }
    class GeminiBackend {
        -_genai: genai module
        -_model_name: str
        +chat() LLMResponse
        -_json_schema_to_proto_schema()
        -_convert_tools()
        -_convert_proto_value()
    }
    class GroqBackend {
        -_client: Groq
        -_model_name: str
        +chat() LLMResponse
        -_convert_tools()
    }
    class OllamaBackend {
        -_model_name: str
        -_base_url: str
        +chat() LLMResponse
        -_convert_tools()
    }

    BaseLLMBackend <|-- GeminiBackend
    BaseLLMBackend <|-- GroqBackend
    BaseLLMBackend <|-- OllamaBackend
    BaseLLMBackend ..> LLMResponse
    LLMResponse *-- ToolCall
```

| Backend | SDK/Protocol | Tool Schema Format | API Key Env Var |
|---------|-------------|-------------------|-----------------|
| **Gemini** | `google-generativeai` | Protobuf `FunctionDeclaration` | `GEMINI_API_KEY` |
| **Groq** | `groq` Python SDK | OpenAI-compatible `tools[]` | `GROQ_API_KEY` |
| **Ollama** | HTTP `requests` to `/api/chat` | OpenAI-compatible `tools[]` | None (local) |

> [!NOTE]
> Each backend handles its own message format conversion internally (e.g., Gemini uses `role: "model"` and `role: "function"`, Groq uses `role: "tool"` with `tool_call_id`).

---

### 4. Tool System Architecture

```mermaid
classDiagram
    class BaseTool {
        <<abstract>>
        +name: str
        +description: str
        +parameters: dict
        +execute(**kwargs) ToolResult
        +to_function_declaration() dict
    }
    class ToolResult {
        +success: bool
        +message: str
        +data: dict
    }
    class ToolRegistry {
        -_tools: Dict~str, BaseTool~
        +register(tool)
        +execute(name, **kwargs) ToolResult
        +get_tool_definitions() list
    }

    BaseTool <|-- MoveJointsTool
    BaseTool <|-- MoveToHomeTool
    BaseTool <|-- MoveToZeroTool
    BaseTool <|-- MoveToReadyPoseTool
    BaseTool <|-- TorqueControlTool
    BaseTool <|-- RGBControlTool
    BaseTool <|-- BuzzerControlTool
    BaseTool <|-- GetEncoderValuesTool
    BaseTool <|-- WaitTool
    BaseTool <|-- PrintMessageTool
    ToolRegistry o-- BaseTool
    BaseTool ..> ToolResult
```

#### Tool Categories

**Motion Tools** (use MoveIt 2):
| Tool | Parameters | What It Does |
|------|-----------|--------------|
| `move_joints` | `joint_angles: [4 floats]` | Plans via `/plan_kinematic_path` → executes via `/execute_trajectory`. `-402` = keep joint unchanged |
| `move_to_home` | None | Delegates to `move_joints([0, 90, -90, -90])` |
| `move_to_zero` | None | Delegates to `move_joints([0, 0, 0, 0])` |
| `move_to_ready_pose` | None | Delegates to `move_joints([0, 45, -90, -45])` |

**GPIO Tools** (publish to `/gpio_controller/commands`):
| Tool | Parameters | GPIO Array Position |
|------|-----------|-------------------|
| `rgb_control` | `r, g, b: int (0-255)` | `[R, G, B, -, -]` |
| `torque_control` | `enable: bool` | `[-, -, -, torque, -]` |
| `buzzer_control` | `state: bool` | `[-, -, -, -, buzzer]` |

The GPIO command is a `Float64MultiArray` with layout: `[led_r, led_g, led_b, torque_enable, buzzer_trigger]`

**Sensor/Utility Tools:**
| Tool | What It Does |
|------|-------------|
| `get_encoder_values` | Reads `/joint_states` subscription, returns current positions as a dict |
| `wait` | `time.sleep(seconds)`, capped at 300s |
| `print_message` | Sends `[USER_MSG]<text>` via the feedback callback to the GUI |

#### MoveJoints Deep Dive (the core motion tool)

```mermaid
flowchart TD
    A["execute(joint_angles)"] --> B{"Validate:<br/>len == 4?"}
    B -- No --> ERR1["❌ Expected 4 angles"]
    B -- Yes --> C["Read current_joint_state"]
    C --> D["For each joint:<br/>-402? → keep current<br/>else → deg→rad"]
    D --> E["Build MoveIt MotionPlanRequest<br/>with JointConstraints"]
    E --> F["Call /plan_kinematic_path<br/>(async, 10s timeout)"]
    F --> G{"Plan succeeded?<br/>error_code == 1"}
    G -- No --> ERR2["❌ Planning failed"]
    G -- Yes --> H["Send trajectory to<br/>/execute_trajectory action"]
    H --> I{"Execution accepted?"}
    I -- No --> ERR3["❌ Rejected"]
    I -- Yes --> J["Wait for result<br/>(30s timeout)"]
    J --> K{"error_code == 1?"}
    K -- No --> ERR4["❌ Execution failed"]
    K -- Yes --> SUCCESS["✅ Moved to target"]

    style SUCCESS fill:#10b981,color:#fff
```

---

## Package 2: `dofbot_ai_gui` — The Streamlit Frontend

### File Structure

| File | Purpose |
|------|---------|
| [main.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai_gui/dofbot_ai_gui/main.py) | ROS 2 entry point: finds `app.py` in share dir, runs `streamlit run` |
| [app.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_ai_gui/dofbot_ai_gui/app.py) | Full Streamlit application (UI + ROS 2 action client) |

### GUI Architecture

```mermaid
flowchart TD
    subgraph "Streamlit Process"
        A["main.py<br/>ros2 run entry"] --> B["subprocess.run<br/>streamlit run app.py"]
        B --> C["app.py starts"]
        C --> D["setup_ros()<br/>(cached, runs once)"]
        D --> E["GUIRosNode<br/>(ActionClient on /dofbot_command)"]
        D --> F["Spin thread<br/>(daemon, background)"]
        C --> G["Render sidebar:<br/>Status, Tools, Clear btn"]
        C --> H["Render chat history<br/>(custom HTML bubbles)"]
        C --> I["st.chat_input<br/>('Command the robot...')"]
    end

    subgraph "On User Message"
        I --> J["Append to st.session_state.messages"]
        J --> K["Set processing_prompt flag"]
        K --> L["st.rerun() → Process pending"]
        L --> M["send_command(node, prompt)"]
        M --> N["ActionClient.send_goal_async<br/>(ArmTask.Goal)"]
        N --> O["Poll for feedback<br/>in 0.1s loop"]
        O --> P{"Feedback type?"}
        P -- "[USER_MSG]..." --> Q["Render live chat bubble<br/>in updates container"]
        P -- "Tool status" --> R["Update gray status text"]
        O --> S["Wait for result<br/>(600s timeout)"]
        S --> T["Append AI response<br/>to messages → rerun"]
    end

    style E fill:#3b82f6,color:#fff
    style N fill:#4f46e5,color:#fff
```

### UI Design

The GUI uses a **premium dark-mode glassmorphism design** with:
- **Custom CSS**: Dark `#0a0a0f` background with purple/indigo radial gradients
- **Outfit font** from Google Fonts
- **Custom chat bubbles**: User messages in purple gradient (right-aligned), AI messages in frosted glass (left-aligned)
- **Animated entry**: `fadeIn` CSS animation on new messages
- **Sidebar**: ROS 2 connection status indicator, tool badge grid, suggestion prompts
- **Live feedback**: Tool calls shown as gray italic text during execution; `[USER_MSG]` feedback rendered as distinct blue-bordered bubbles

### Feedback Pipeline

```mermaid
sequenceDiagram
    participant GUI as Streamlit (app.py)
    participant Action as ArmTask Action
    participant Agent as AgentCore
    participant Tool as Tool.execute()

    GUI->>Action: send_goal_async(prompt)
    Action->>Agent: _execute_callback()
    Agent->>Agent: Set live_feedback_cb
    
    loop ReAct Steps
        Agent->>Tool: Execute tool
        Tool-->>Agent: ToolResult
        Agent->>Action: publish_feedback("🔧 Calling tool: X")
        Action-->>GUI: feedback_callback → shared_queue
        GUI->>GUI: Pop queue → render status text
        Agent->>Action: publish_feedback("📋 Result: ...")
    end

    Agent->>Action: Final text response
    Action-->>GUI: result.message
    GUI->>GUI: Append to chat, rerun
```

---

## Custom Interface: `ArmTask.action`

Defined in [ArmTask.action](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_custom_interfaces/action/ArmTask.action):

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

---

## End-to-End Flow: "Move joint 1 to 45 degrees and turn the LED green"

```mermaid
sequenceDiagram
    participant User as User (Browser)
    participant GUI as Streamlit GUI
    participant ROS as ROS 2 Action
    participant Agent as AgentCore
    participant LLM as Groq/Gemini
    participant MJ as move_joints Tool
    participant RGB as rgb_control Tool
    participant MoveIt as MoveIt 2
    participant GPIO as /gpio_controller

    User->>GUI: Types message in chat
    GUI->>ROS: ArmTask.Goal(json_command="Move joint 1...")
    ROS->>Agent: _execute_callback()
    
    Agent->>LLM: messages + 10 tool schemas
    LLM-->>Agent: tool_call: move_joints([45, -402, -402, -402])
    Agent->>ROS: feedback("🔧 Calling move_joints")
    ROS-->>GUI: Render gray status
    
    Agent->>MJ: execute(joint_angles=[45, -402, -402, -402])
    MJ->>MoveIt: GetMotionPlan (45° for joint1, keep others)
    MoveIt-->>MJ: Trajectory
    MJ->>MoveIt: ExecuteTrajectory
    MoveIt-->>MJ: Success
    MJ-->>Agent: ToolResult(✅ "Moved to [45, -402, -402, -402]")
    
    Agent->>LLM: messages + tool_result
    LLM-->>Agent: tool_call: rgb_control(r=0, g=255, b=0)
    Agent->>ROS: feedback("🔧 Calling rgb_control")
    
    Agent->>RGB: execute(r=0, g=255, b=0)
    RGB->>GPIO: Float64MultiArray [0, 255, 0, 1.0, 0]
    RGB-->>Agent: ToolResult(✅ "Set RGB to 0,255,0")
    
    Agent->>LLM: messages + tool_result
    LLM-->>Agent: text: "Done! Moved joint 1 to 45° and LED is green."
    
    Agent-->>ROS: Result(success=True, message="Done!...")
    ROS-->>GUI: Display ✅ response bubble
    GUI-->>User: Sees result in chat
```

---

## Launch System

[ai_bringup.launch.py](file:///home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/dofbot_urdf/launch/ai_bringup.launch.py) orchestrates everything:

```
ros2 launch dofbot_urdf ai_bringup.launch.py
```

1. **Includes** `dofbot_moveit/robot_bringup.launch.py` — starts hardware drivers, controllers, MoveIt
2. **Launches** `dofbot_ai/agent_node` — the ReAct agent with action server
3. **Launches** `dofbot_ai_gui/main` — Streamlit subprocess on browser

---

## ROS 2 Topic/Service/Action Map

| Interface | Type | Direction | Used By |
|-----------|------|-----------|---------|
| `/dofbot_command` | ArmTask Action | GUI → Agent | Communication bridge |
| `/joint_states` | JointState Topic | Hardware → Agent | `get_encoder_values`, `move_joints` |
| `/gpio_controller/commands` | Float64MultiArray Topic | Agent → Hardware | `rgb_control`, `buzzer_control`, `torque_control` |
| `/plan_kinematic_path` | GetMotionPlan Service | Agent → MoveIt | `move_joints` |
| `/execute_trajectory` | ExecuteTrajectory Action | Agent → MoveIt | `move_joints` |

---

## Key Design Patterns

1. **ReAct Agent Pattern**: The LLM reasons step-by-step, calling tools iteratively until it has enough information to produce a final answer. This allows multi-step task execution from a single natural language command.

2. **Strategy Pattern for LLM Backends**: All three providers (Gemini, Groq, Ollama) implement `BaseLLMBackend.chat()`, making the provider hot-swappable via a single config param.

3. **Decorator/Delegate Pattern for Preset Poses**: `MoveToHomeTool`, `MoveToZeroTool`, `MoveToReadyPoseTool` all delegate to `MoveJointsTool.execute()` — they're thin wrappers with hardcoded angles.

4. **GPIO Multiplexing**: All GPIO peripherals (RGB, torque, buzzer) share a single `Float64MultiArray` publisher. Each tool modifies its own fields on the node and calls `publish_gpio_command()`.

5. **Live Feedback via Action Protocol**: The `ArmTask` action's `Feedback.state` field carries real-time tool execution updates from the agent to the GUI, enabling a responsive chat experience.

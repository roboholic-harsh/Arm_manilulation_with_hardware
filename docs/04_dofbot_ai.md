# `dofbot_ai` — LLM ReAct Agent Backend

> **Type:** Python (ament_python)  
> **Role:** The AI brain — a ROS 2 action server that receives natural language commands and executes them using a ReAct (Reasoning + Acting) loop with pluggable LLM backends and 10 robot tools.

---

## Purpose

This package implements an **autonomous AI agent** that:
1. Receives a natural language command via the `ArmTask` action interface
2. Sends the command + 10 tool schemas to an LLM
3. The LLM reasons and returns tool calls (or a final text response)
4. The agent executes each tool call (MoveIt planning, GPIO control, etc.)
5. Feeds results back to the LLM for further reasoning
6. Loops until the LLM produces a final text answer (max 15 steps)

---

## File Map

```
dofbot_ai/
├── package.xml                         # Depends on rclpy, action_msgs, dofbot_custom_interfaces
├── setup.py                            # Entry point: agent_node = dofbot_ai.agent_node:main
├── setup.cfg
├── config/
│   └── agent_config.yaml               # System prompt, provider, model, joint names
├── dofbot_ai/
│   ├── __init__.py
│   ├── agent_node.py                   # ⭐ ROS 2 node — Action Server + tool wiring
│   ├── agent_core.py                   # ⭐ ReAct loop engine
│   ├── llm_backends/
│   │   ├── __init__.py                 # Exports: BaseLLMBackend, LLMResponse, ToolCall
│   │   ├── base_backend.py            # Abstract base: BaseLLMBackend, LLMResponse, ToolCall dataclasses
│   │   ├── gemini_backend.py          # Google Gemini (native function calling via protobuf)
│   │   ├── groq_backend.py            # Groq (OpenAI-compatible SDK)
│   │   └── ollama_backend.py          # Ollama local (HTTP /api/chat)
│   └── tools/
│       ├── __init__.py                 # Exports all 10 tools + ToolRegistry
│       ├── base_tool.py               # Abstract BaseTool + ToolResult dataclass
│       ├── registry.py                # ToolRegistry — central register/execute/schema hub
│       ├── move_joints.py             # ⭐ Core motion tool (MoveIt plan + execute)
│       ├── move_to_home.py            # Preset: [0, 90, -90, -90]°
│       ├── move_to_zero.py            # Preset: [0, 0, 0, 0]°
│       ├── move_to_ready_pose.py      # Preset: [0, 45, -90, -45]°
│       ├── rgb_control.py             # GPIO: set RGB LED
│       ├── torque_control.py          # GPIO: enable/disable torque
│       ├── buzzer_control.py          # GPIO: toggle buzzer
│       ├── get_encoder_values.py      # Read /joint_states
│       ├── wait.py                    # time.sleep() with 300s cap
│       └── print_message.py           # Send [USER_MSG] feedback to GUI
└── test/
```

---

## Node: `DofbotAgentNode`

**Executable:** `agent_node`  
**Entry point:** `dofbot_ai.agent_node:main`

### ROS 2 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `config_file` | `""` (auto-detect from share/) | Path to `agent_config.yaml` |
| `provider` | `""` (from YAML: `groq`) | LLM provider: `gemini`, `groq`, `ollama` |
| `model` | `""` (from YAML: `qwen/qwen3-32b`) | Model name |
| `api_key` | `""` (from env var) | API key override |

### Subscriptions

| Topic | Type | Purpose |
|-------|------|---------|
| `/joint_states` | `sensor_msgs/JointState` | Live encoder feedback — stored in `self.current_joint_state` |

### Publishers

| Topic | Type | Purpose |
|-------|------|---------|
| `/gpio_controller/commands` | `std_msgs/Float64MultiArray` | GPIO commands: `[led_r, led_g, led_b, torque_enable, buzzer_trigger]` |

### Action Server

| Action | Type | Purpose |
|--------|------|---------|
| `/dofbot_command` | `dofbot_custom_interfaces/ArmTask` | Receives NL commands, returns AI response + live feedback |

### Service Clients

| Service | Type | Purpose |
|---------|------|---------|
| `/plan_kinematic_path` | `moveit_msgs/GetMotionPlan` | Request motion plans from MoveIt |

### Action Clients

| Action | Type | Purpose |
|--------|------|---------|
| `/execute_trajectory` | `moveit_msgs/ExecuteTrajectory` | Execute planned trajectories |

---

## Initialization Sequence (`__init__`)

```
1. Load config from YAML (param or share directory)
2. Extract: system_prompt, max_steps, provider, model, joint_names, arm_group
3. Subscribe to /joint_states
4. Create /gpio_controller/commands publisher
5. Wait for /plan_kinematic_path service (30s timeout)
6. Wait for /execute_trajectory action server (30s timeout)
7. Create ToolRegistry → register 10 tools
8. Create LLM backend (gemini/groq/ollama based on provider)
9. Create AgentCore(llm, registry, system_prompt, max_steps=15)
10. Create ActionServer('dofbot_command')
11. Log "🤖 Dofbot AI Agent is ready!"
```

### Tool Registration Order

```python
move_joints = MoveJointsTool(node, plan_client, execute_client, joint_names, arm_group)
registry.register(move_joints)
registry.register(MoveToHomeTool(move_joints))      # delegates to move_joints
registry.register(MoveToZeroTool(move_joints))      # delegates to move_joints
registry.register(MoveToReadyPoseTool(move_joints)) # delegates to move_joints
registry.register(TorqueControlTool(node))
registry.register(RGBControlTool(node))
registry.register(BuzzerControlTool(node))
registry.register(GetEncoderValuesTool(node, joint_names))
registry.register(WaitTool())
registry.register(PrintMessageTool(node))
```

---

## `AgentCore` — ReAct Loop Engine

### Algorithm

```
INPUT: user_message (string)
OUTPUT: final_text (string)

messages = [system_prompt, user_message]
tool_definitions = registry.get_tool_definitions()  # JSON schemas for all 10 tools

FOR step = 1 TO max_steps (15):
    response = llm.chat(messages, tools=tool_definitions)

    IF response has tool_calls:
        FOR EACH tool_call in response.tool_calls:
            result = registry.execute(tool_call.name, **tool_call.args)
            messages.append(assistant: "I'll call {name}")
            messages.append(tool_result: str(result))
            feedback_cb("🔧 Calling tool: {name}({args})")
            feedback_cb("📋 Result: {result}")

    ELSE (response has text):
        RETURN response.text  ← DONE

RETURN "I completed the available steps."  ← safety fallback
```

### Feedback Mechanism

During execution, `AgentCore._feedback_cb` is set by the action server to `goal_handle.publish_feedback()`. This allows the GUI to show live tool execution status:
- `"🔧 Calling tool: move_joints({'joint_angles': [45, -402, -402, -402]})"` → gray status text
- `"📋 Result: ✅ Successfully moved joints to [45, -402, -402, -402]"` → gray status text
- `"[USER_MSG]The current positions are: ..."` → rendered as a chat bubble in the GUI

---

## LLM Backend System

### Abstract Interface

```python
class BaseLLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list, tools: list) -> LLMResponse:
        """Returns LLMResponse with either .text or .tool_calls"""

@dataclass
class LLMResponse:
    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    def has_tool_calls(self) -> bool: ...

@dataclass
class ToolCall:
    name: str          # e.g., "move_joints"
    args: Dict[str, Any]  # e.g., {"joint_angles": [45, -402, -402, -402]}
    id: str = ""       # Groq/OpenAI provide tracking IDs
```

### Backend Implementations

#### `GeminiBackend`
- **SDK:** `google-generativeai`
- **Key env var:** `GEMINI_API_KEY`
- **Default model:** `gemini-2.0-flash`
- **Tool format:** Protobuf `FunctionDeclaration` objects
- **Special handling:**
  - Converts JSON Schema → `genai.protos.Schema` recursively (`_json_schema_to_proto_schema`)
  - Uses `role: "model"` for assistant messages, `role: "function"` for tool results
  - Parses protobuf `FunctionCall` responses, converting `MapComposite` to Python dicts
  - System prompt passed as `system_instruction` parameter to `GenerativeModel`

#### `GroqBackend`
- **SDK:** `groq` Python SDK
- **Key env var:** `GROQ_API_KEY`
- **Default model:** `llama-3.1-70b-versatile`
- **Tool format:** OpenAI-compatible `{"type": "function", "function": {...}}`
- **Temperature:** 0.1 (near-deterministic for tool calling reliability)
- **Special handling:**
  - Uses `role: "tool"` with `tool_call_id` for tool results
  - `tool_choice: "auto"` lets the model decide when to call tools

#### `OllamaBackend`
- **Protocol:** HTTP POST to `http://localhost:11434/api/chat`
- **Default model:** `llama3.1:8b`
- **No API key required** (local inference)
- **Tool format:** OpenAI-compatible (Ollama 0.5+)
- **Timeout:** 60 seconds per request
- **Stream:** Disabled (`"stream": false`)

---

## Tool System

### `BaseTool` Abstract Class

```python
class BaseTool(ABC):
    name: str            # Unique identifier
    description: str     # LLM-readable description
    parameters: dict     # JSON Schema for arguments

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult: ...

    def to_function_declaration(self) -> dict:
        """Returns {name, description, parameters} for LLM function calling"""
```

### `ToolResult` Dataclass

```python
@dataclass
class ToolResult:
    success: bool
    message: str
    data: Optional[Dict] = field(default_factory=dict)

    def __str__(self):
        return f"{'✅' if self.success else '❌'} {self.message}"
```

### `ToolRegistry`

```python
class ToolRegistry:
    def register(self, tool: BaseTool)           # Add tool
    def execute(self, name, **kwargs) -> ToolResult  # Run tool by name
    def get_tool_definitions(self) -> list       # Get all schemas for LLM
    def list_tools(self) -> str                  # Pretty-print
```

If a tool name is not found, returns `ToolResult(False, "Unknown tool: ...")`.
If a tool raises an exception, returns `ToolResult(False, "Tool crashed: ...")`.

---

## Tool Deep Dives

### `MoveJointsTool` — Core Motion Tool

The most complex tool. Uses MoveIt 2 for motion planning and execution.

**Parameters:** `{"joint_angles": [4 floats]}` — angles in degrees, `-402` = keep unchanged

**Execution flow:**
```
1. Validate: len(joint_angles) == 4
2. Read current joint state from self._node.current_joint_state
3. For each joint:
   - If angle == -402: use current position (from /joint_states)
   - Else: convert degrees → radians
4. Build MoveIt MotionPlanRequest:
   - group_name = "dofbot_arm"
   - JointConstraints with tolerance ±0.01 rad, weight 1.0
   - allowed_planning_time = 5.0 seconds
5. Call /plan_kinematic_path (async, 10s timeout)
6. Check error_code == 1 (SUCCESS)
7. Send trajectory to /execute_trajectory (async)
8. Wait for acceptance (10s timeout)
9. Wait for result (30s timeout)
10. Check execution error_code == 1
11. Return ToolResult(True, "Successfully moved joints to [...]")
```

### Preset Pose Tools (Delegate Pattern)

All three preset tools store a reference to `MoveJointsTool` and delegate to it:

```python
# MoveToHomeTool
def execute(self, **kwargs):
    return self.move_joints_tool.execute([0.0, 90.0, -90.0, -90.0])

# MoveToZeroTool
def execute(self, **kwargs):
    return self.move_joints_tool.execute([0.0, 0.0, 0.0, 0.0])

# MoveToReadyPoseTool
def execute(self, **kwargs):
    return self.move_joints_tool.execute([0.0, 45.0, -90.0, -45.0])
```

### GPIO Tools

All GPIO tools follow the same pattern:
1. Update the node's state variable (`led_r`, `torque_enable`, etc.)
2. Call `node.publish_gpio_command()` which publishes a `Float64MultiArray`
3. Return success

```python
# node.publish_gpio_command():
msg.data = [self.led_r, self.led_g, self.led_b, self.torque_enable, self.buzzer_trigger]
# Published to /gpio_controller/commands
# → gpio_controller writes to aux_hardware interfaces
# → dofbot_hardware::write() sends binary serial packet to ESP32
```

### `GetEncoderValuesTool`

Reads the cached `/joint_states` message and returns a dict:
```python
# Returns: "Current encoder values: {'arm1_Joint': 0.0142, 'arm2_Joint': -0.5123, ...}"
```

### `WaitTool`

Simple `time.sleep()` with safety: must be >0 and ≤300 seconds.

### `PrintMessageTool`

Sends live text to the GUI by prefixing with `[USER_MSG]`:
```python
self._node._agent._feedback_cb(f"[USER_MSG]{message}")
```

The GUI detects the `[USER_MSG]` prefix and renders it as a distinct blue-bordered chat bubble instead of gray status text.

---

## Configuration (`agent_config.yaml`)

```yaml
agent:
  system_prompt: |
    You are Dofbot AI Assistant, a helpful 4-DOF robot arm assistant.
    You control a physical Yahboom DOF robot arm using the tools provided.
    Rules:
    - Always use tools to perform actions. Never make up results.
    - If the user asks about the robot's position, use get_encoder_values first.
    - Joint angles are in degrees. Index 0 = Base, 3 = Wrist.
    - Use -402 for joints that should remain unchanged.
  max_steps: 15
  default_provider: "groq"
  default_model: "qwen/qwen3-32b"

robot:
  arm_group: "dofbot_arm"
  joint_names: [arm1_Joint, arm2_Joint, arm3_Joint, arm4_Joint]
  dof: 4
  home_position: [0.0, 90.0, -90.0, -90.0]
```

---

## How to Add a New Tool

1. Create `dofbot_ai/tools/my_new_tool.py`:
```python
from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class MyNewTool(BaseTool):
    name = "my_new_tool"
    description = "Description for the LLM"
    parameters = {"type": "object", "properties": {...}, "required": [...]}

    def execute(self, **kwargs) -> ToolResult:
        # Your logic here
        return ToolResult(True, "Done!")
```

2. Add to `tools/__init__.py`:
```python
from dofbot_ai.tools.my_new_tool import MyNewTool
```

3. Register in `agent_node.py`:
```python
self._registry.register(MyNewTool(self))
```

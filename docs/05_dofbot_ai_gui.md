# `dofbot_ai_gui` — Streamlit Chat Interface

> **Type:** Python (ament_python)  
> **Role:** Premium dark-mode chat interface built with Streamlit that acts as a ROS 2 action client to the AI agent.

---

## Purpose

This package provides a **browser-based chat UI** where users type natural language commands. The GUI:
1. Sends commands to the AI agent via the `ArmTask` action
2. Displays live tool execution feedback in real-time
3. Renders the final AI response as a chat bubble

---

## File Map

```
dofbot_ai_gui/
├── package.xml                 # Depends on rclpy, action_msgs, dofbot_custom_interfaces
├── setup.py                    # Entry point: main = dofbot_ai_gui.main:main
│                               # Installs app.py to share/scripts/
├── setup.cfg
├── resource/dofbot_ai_gui
├── dofbot_ai_gui/
│   ├── __init__.py
│   ├── main.py                 # ⭐ ROS 2 entry point — launches Streamlit subprocess
│   └── app.py                  # ⭐ Full Streamlit application (469 lines)
└── test/
```

---

## Launch Mechanism

### `main.py` — ROS 2 → Streamlit Bridge

When launched via `ros2 run dofbot_ai_gui main`, this script:

```python
def main():
    share_dir = get_package_share_directory('dofbot_ai_gui')
    script_path = os.path.join(share_dir, 'scripts', 'app.py')
    cmd = [sys.executable, "-m", "streamlit", "run", script_path,
           "--server.headless", "true"]
    subprocess.run(cmd)
```

1. Finds `app.py` in the installed share directory
2. Runs `python -m streamlit run app.py --server.headless true`
3. Streamlit starts a web server on `http://localhost:8501`

> The `--server.headless true` flag prevents Streamlit from asking for email on first run.

---

## `app.py` — Full Streamlit Application

### Architecture

```
┌────────────────────────────────────────────────┐
│              Streamlit Process                  │
│                                                │
│  ┌─────────────────────────────────────┐       │
│  │  setup_ros() [cached, runs once]    │       │
│  │  ├── rclpy.init()                   │       │
│  │  ├── GUIRosNode (ActionClient)      │       │
│  │  └── spin_thread (daemon)           │       │
│  └─────────────────────────────────────┘       │
│                                                │
│  ┌─────────────────────────────────────┐       │
│  │  main() [runs on every interaction] │       │
│  │  ├── Render sidebar                 │       │
│  │  ├── Render chat history            │       │
│  │  ├── Handle st.chat_input()         │       │
│  │  └── Process pending AI response    │       │
│  └─────────────────────────────────────┘       │
└────────────────────────────────────────────────┘
```

### `GUIRosNode` — ROS 2 Node

```python
class GUIRosNode(Node):
    def __init__(self):
        super().__init__('dofbot_ai_gui_node')
        self.action_client = ActionClient(self, ArmTask, '/dofbot_command')
```

Initialized once via `@st.cache_resource`:
```python
@st.cache_resource
def setup_ros():
    rclpy.init()
    node = GUIRosNode()
    thread = threading.Thread(target=lambda: rclpy.spin(node), daemon=True)
    thread.start()
    return node
```

The daemon spin thread keeps the ROS node alive across Streamlit reruns.

---

### User Interaction Flow

```
1. User types in st.chat_input("Command the robot...")
2. Message appended to st.session_state.messages
3. st.session_state.processing_prompt = prompt
4. st.rerun() → input box clears, user message renders immediately
5. On rerun, detects processing_prompt is set:
   a. Creates live_updates_container (for [USER_MSG] bubbles)
   b. Creates feedback_placeholder (for tool status text)
   c. Calls send_command(node, prompt, feedback_placeholder, live_updates_container)
6. send_command():
   a. Waits for action server (5s timeout)
   b. Sends ArmTask.Goal(json_command=prompt)
   c. Polls for feedback every 0.1s:
      - [USER_MSG]... → renders as blue-bordered chat bubble
      - Other → renders as gray italic status text
   d. Waits for result (600s / 10 min timeout)
   e. Returns {success, message}
7. Response appended to messages → st.rerun() → renders AI bubble
```

### Feedback Pipeline (Thread Safety)

```python
# ROS spin thread calls this:
def feedback_callback(feedback_msg):
    shared_feedback_queue.append(feedback_msg.feedback.state)

# Streamlit main thread polls this:
while not result_future.done():
    while len(shared_feedback_queue) > 0:
        msg = shared_feedback_queue.pop(0)
        if msg.startswith("[USER_MSG]"):
            # Render as live chat bubble
        else:
            # Render as gray status text
    time.sleep(0.1)
```

Uses a **shared list queue** between the ROS spin thread (producer) and Streamlit main thread (consumer). This is thread-safe because Python's GIL protects list.append() and list.pop(0).

---

## UI Design System

### CSS Architecture

The app injects ~240 lines of custom CSS via `st.markdown(unsafe_allow_html=True)`:

| Element | Design |
|---------|--------|
| **Background** | `#0a0a0f` with purple/indigo radial gradients |
| **Font** | `Outfit` from Google Fonts (300-700 weights) |
| **Chat input** | Frosted glass pill with indigo border, purple glow on focus |
| **User bubbles** | Purple gradient (#4f46e5 → #7c3aed), right-aligned, rounded corners |
| **AI bubbles** | Frosted glass (rgba(30,30,40,0.85)), left-aligned, 12px blur backdrop |
| **Avatars** | 38px circles with gradient fills and shadow |
| **Animations** | `fadeIn` keyframe — 0.4s cubic-bezier slide-up |
| **Sidebar** | Dark glass background, green/red status dots with glow |
| **Tool badges** | Indigo border pills with 0.75rem text |
| **Buttons** | Transparent with white border, rose-red hover |

### Hidden Defaults
```css
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
```

### Chat Bubble Rendering

```python
def render_chat_message(role, content):
    if role == "user":
        # Right-aligned purple gradient bubble with 👤 avatar
    else:
        # Left-aligned frosted glass bubble with 🤖/⚡/⚠️ avatar
```

The avatar icon changes based on content: `🤖` for success (✅), `⚠️` for error (❌), `⚡` for everything else.

---

## Session State

| Key | Type | Purpose |
|-----|------|---------|
| `messages` | `list[dict]` | Chat history: `[{"role": "user"/"assistant", "content": "..."}]` |
| `processing_prompt` | `str` or `None` | Pending prompt to process (set before rerun) |

Initial state:
```python
st.session_state.messages = [
    {"role": "assistant", "content": "Hello! I am Dofbot AI, your agentic robot assistant. What would you like me to do today?"}
]
```

---

## Sidebar Components

1. **Title:** "Dofbot AI" (gradient text) + "Intelligent Robot Arm Controller" (subtitle)
2. **Status indicator:** Green dot + "ROS 2 Connected" or Red dot + "ROS 2 Disconnected"
3. **Active Tools grid:** 9 tool badges (all tools except `print_message`)
4. **Clear Conversation button:** Resets `st.session_state.messages`
5. **Suggestions:** Example prompts for first-time users

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `rclpy` | ROS 2 Python client |
| `dofbot_custom_interfaces` | `ArmTask` action type |

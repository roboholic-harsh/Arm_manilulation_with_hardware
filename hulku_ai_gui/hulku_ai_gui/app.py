"""
HulkuBot AI Agent — Streamlit Chat Interface

A modern chat UI that sends natural language commands to the 
hulku_ai_agent action server via ROS 2.
"""

import json
import os
import threading
import time

import streamlit as st

# ROS 2
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from custom_interfaces.action import ArmTask

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="HulkuBot AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.95);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }

    /* Chat messages */
    .stChatMessage {
        background: rgba(30, 30, 60, 0.6) !important;
        border: 1px solid rgba(99, 102, 241, 0.15) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(10px);
    }

    /* Input box */
    .stChatInput > div {
        background: rgba(30, 30, 60, 0.8) !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 12px !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4) !important;
    }

    /* Status indicators */
    .status-connected { color: #34d399; font-weight: 600; }
    .status-disconnected { color: #f87171; font-weight: 600; }

    /* Tool call indicator */
    .tool-call {
        background: rgba(99, 102, 241, 0.15);
        border-left: 3px solid #6366f1;
        padding: 8px 12px;
        border-radius: 0 8px 8px 0;
        margin: 4px 0;
        font-size: 0.85em;
    }

    /* Header gradient text */
    .gradient-text {
        background: linear-gradient(135deg, #6366f1, #a78bfa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2em;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# ROS 2 NODE
# ═══════════════════════════════════════════════════════════
class GUIRosNode(Node):
    def __init__(self):
        super().__init__('hulku_ai_gui_node')
        self.action_client = ActionClient(self, ArmTask, '/arm_command')
        self.get_logger().info('GUI ROS Node initialized')


@st.cache_resource
def setup_ros():
    """Initialize ROS 2 and create the action client node."""
    if not rclpy.ok():
        rclpy.init()
    node = GUIRosNode()

    def spin_thread():
        rclpy.spin(node)

    thread = threading.Thread(target=spin_thread, daemon=True)
    thread.start()
    return node


# ═══════════════════════════════════════════════════════════
# ACTION CLIENT LOGIC
# ═══════════════════════════════════════════════════════════
def send_command(node, user_message: str) -> dict:
    """
    Send a natural language command to the agent and wait for result.
    Returns dict with 'success' and 'message'.
    """
    if not node.action_client.wait_for_server(timeout_sec=5.0):
        return {"success": False, "message": "❌ Agent server '/arm_command' not available!"}

    goal_msg = ArmTask.Goal()
    goal_msg.json_command = user_message

    # Send goal
    send_future = node.action_client.send_goal_async(goal_msg)
    rclpy.spin_until_future_complete(node, send_future, timeout_sec=10.0)

    goal_handle = send_future.result()
    if not goal_handle or not goal_handle.accepted:
        return {"success": False, "message": "❌ Goal was rejected by the agent."}

    # Wait for result
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=60.0)

    if result_future.result() is None:
        return {"success": False, "message": "❌ Timed out waiting for agent response."}

    result = result_future.result().result
    return {"success": result.success, "message": result.message}


# ═══════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════
def main():
    # Initialize ROS
    try:
        ros_node = setup_ros()
        ros_connected = True
    except Exception as e:
        ros_connected = False
        ros_node = None

    # ─── SIDEBAR ──────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="gradient-text">HulkuBot</div>', unsafe_allow_html=True)
        st.caption("AI Agent Control Panel")
        st.markdown("---")

        # Connection status
        if ros_connected:
            st.markdown('🟢 <span class="status-connected">ROS 2 Connected</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown('🔴 <span class="status-disconnected">ROS 2 Disconnected</span>',
                        unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🛠️ Available Tools")
        st.markdown("""
        - **move_joints** — Move arm joints (degrees)
        - **move_gripper** — Open / Close gripper
        - **go_home** — Return to home position
        - **get_joint_states** — Read current position
        - **buzzer** — Toggle buzzer ON/OFF
        - **torque_mode** — Enable/Disable drag mode
        """)

        st.markdown("---")
        st.markdown("### 💡 Example Commands")
        st.markdown("""
        - *"Move joint 1 to 45 degrees"*
        - *"Go home and open the gripper"*
        - *"Where is the robot right now?"*
        - *"Turn on the buzzer"*
        - *"Enable drag mode"*
        """)

        st.markdown("---")
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    # ─── MAIN CHAT AREA ──────────────────────────────────
    st.markdown('<div class="gradient-text">🤖 HulkuBot AI Agent</div>',
                unsafe_allow_html=True)
    st.caption("Talk to your robot using natural language. The agent reasons and acts autonomously.")

    # Chat state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Tell your robot what to do..."):
        if not ros_connected:
            st.error("ROS 2 is not connected. Cannot send commands.")
            return

        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        # Send to agent
        with st.chat_message("assistant"):
            with st.spinner("🧠 Agent is thinking and acting..."):
                result = send_command(ros_node, prompt)

            if result["success"]:
                response_text = f"✅ {result['message']}"
            else:
                response_text = f"❌ {result['message']}"

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})


if __name__ == "__main__":
    main()

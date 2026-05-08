#!/usr/bin/env python3
"""
Dofbot AI Agent Node.

ROS 2 action server that receives natural language commands and 
executes them using a ReAct tool-calling loop with LLM backends.
"""

import os
import logging
import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient

from dofbot_custom_interfaces.action import ArmTask
from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.action import ExecuteTrajectory
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

from dofbot_ai.agent_core import AgentCore
from dofbot_ai.tools import (
    ToolRegistry,
    MoveJointsTool, MoveToHomeTool, MoveToZeroTool, MoveToReadyPoseTool,
    TorqueControlTool, RGBControlTool, BuzzerControlTool, GetEncoderValuesTool,
    WaitTool, PrintMessageTool
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger('dofbot_ai')


class DofbotAgentNode(Node):
    def __init__(self):
        super().__init__('dofbot_agent_node')

        # ==============================
        # PARAMETERS
        # ==============================
        self.declare_parameter('config_file', '')
        self.declare_parameter('provider', '')
        self.declare_parameter('model', '')
        self.declare_parameter('api_key', '')

        config_file = self.get_parameter('config_file').value

        # Load config
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self._config = yaml.safe_load(f)
        else:
            # Try loading from the installed share directory
            from ament_index_python.packages import get_package_share_directory
            share_dir = get_package_share_directory('dofbot_ai')
            default_config = os.path.join(share_dir, 'config', 'agent_config.yaml')
            if os.path.exists(default_config):
                with open(default_config, 'r') as f:
                    self._config = yaml.safe_load(f)
            else:
                self.get_logger().error("No config file found!")
                raise RuntimeError("Config file not found")

        agent_config = self._config.get('agent', {})
        robot_config = self._config.get('robot', {})

        # Allow ROS param overrides
        provider = self.get_parameter('provider').value or agent_config.get('default_provider', 'groq')
        model = self.get_parameter('model').value or agent_config.get('default_model', 'llama3-70b-8192')
        api_key = self.get_parameter('api_key').value or ''

        self._system_prompt = agent_config.get('system_prompt', 'You are a robot assistant.')
        self._max_steps = agent_config.get('max_steps', 5)

        # Robot config
        self._arm_group = robot_config.get('arm_group', 'arm')
        self._joint_names = robot_config.get('joint_names', [])

        self.get_logger().info(f"Provider: {provider} | Model: {model}")
        self.get_logger().info(f"Arm group: {self._arm_group} | Joints: {self._joint_names}")

        # ==============================
        # JOINT STATE SUBSCRIBER
        # ==============================
        self.current_joint_state = None
        self.create_subscription(JointState, '/joint_states', self._joint_state_cb, 10)

        # ==============================
        # HARDWARE PERIPHERALS (GPIO)
        # ==============================
        self.led_r = 0.0
        self.led_g = 0.0
        self.led_b = 0.0
        self.torque_enable = 1.0
        self.buzzer_trigger = 0.0
        self.gpio_publisher = self.create_publisher(Float64MultiArray, '/gpio_controller/commands', 10)

        # ==============================
        # MOVEIT INTERFACES
        # ==============================
        self.get_logger().info("Waiting for MoveIt services...")
        self._plan_client = self.create_client(GetMotionPlan, '/plan_kinematic_path')
        self._plan_client.wait_for_service(timeout_sec=30.0)

        self._execute_client = ActionClient(self, ExecuteTrajectory, '/execute_trajectory')
        self._execute_client.wait_for_server(timeout_sec=30.0)
        self.get_logger().info("MoveIt services connected!")

        # ==============================
        # TOOL REGISTRY
        # ==============================
        self._registry = ToolRegistry()

        move_joints = MoveJointsTool(
            self, self._plan_client, self._execute_client,
            self._joint_names, self._arm_group
        )
        self._registry.register(move_joints)
        self._registry.register(MoveToHomeTool(move_joints))
        self._registry.register(MoveToZeroTool(move_joints))
        self._registry.register(MoveToReadyPoseTool(move_joints))
        
        self._registry.register(TorqueControlTool(self))
        self._registry.register(RGBControlTool(self))
        self._registry.register(BuzzerControlTool(self))
        self._registry.register(GetEncoderValuesTool(self, self._joint_names))
        
        self._registry.register(WaitTool())
        self._registry.register(PrintMessageTool(self))

        self.get_logger().info(f"Registered tools:\n{self._registry.list_tools()}")

        # ==============================
        # LLM BACKEND
        # ==============================
        self._llm_backend = self._create_backend(provider, model, api_key)

        # ==============================
        # AGENT CORE
        # ==============================
        self._agent = AgentCore(
            llm_backend=self._llm_backend,
            tool_registry=self._registry,
            system_prompt=self._system_prompt,
            max_steps=self._max_steps,
        )

        # ==============================
        # ACTION SERVER
        # ==============================
        self._action_server = ActionServer(
            self, ArmTask, 'dofbot_command', self._execute_callback
        )

        self.get_logger().info("🤖 Dofbot AI Agent is ready!")

    def publish_gpio_command(self):
        msg = Float64MultiArray()
        msg.data = [self.led_r, self.led_g, self.led_b, self.torque_enable, self.buzzer_trigger]
        self.gpio_publisher.publish(msg)

    def _create_backend(self, provider: str, model: str, api_key: str):
        provider = provider.lower()

        if provider == "gemini":
            from dofbot_ai.llm_backends.gemini_backend import GeminiBackend
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            return GeminiBackend(model_name=model, api_key=key)

        elif provider == "groq":
            from dofbot_ai.llm_backends.groq_backend import GroqBackend
            key = api_key or os.environ.get("GROQ_API_KEY", "")
            return GroqBackend(model_name=model, api_key=key)

        elif provider == "ollama":
            from dofbot_ai.llm_backends.ollama_backend import OllamaBackend
            return OllamaBackend(model_name=model)
        else:
            raise ValueError(f"Unknown LLM provider: '{provider}'")

    def _joint_state_cb(self, msg):
        self.current_joint_state = msg

    def _execute_callback(self, goal_handle):
        user_message = goal_handle.request.json_command
        self.get_logger().info(f"📩 Received: {user_message}")

        try:
            feedback = ArmTask.Feedback()
            feedback.state = "Processing..."
            goal_handle.publish_feedback(feedback)

            def live_feedback_cb(state_str):
                feedback.state = state_str
                goal_handle.publish_feedback(feedback)

            self._agent._feedback_cb = live_feedback_cb
            result_text = self._agent.run(user_message)
            self._agent._feedback_cb = None

            self.get_logger().info(f"✅ Agent result: {result_text}")

            goal_handle.succeed()
            result = ArmTask.Result()
            result.success = True
            result.message = result_text
            return result

        except Exception as e:
            self.get_logger().error(f"❌ Agent error: {str(e)}")
            goal_handle.abort()
            result = ArmTask.Result()
            result.success = False
            result.message = f"Agent error: {str(e)}"
            return result


def main(args=None):
    rclpy.init(args=args)
    node = DofbotAgentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

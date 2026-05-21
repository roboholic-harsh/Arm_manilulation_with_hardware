#!/usr/bin/env python3
"""
HulkuBot AI Agent Node.

ROS 2 action server that receives natural language commands and 
executes them using a ReAct tool-calling loop with LLM backends.
"""

"""Standard python libraries"""
import os   # For file operations and interacting with the system (here for ex., fetching env etc.,)
import logging  # Debugging and tracking framework (here for System logger)
import yaml     # For parsing and writing YAML files (here for configuration files for llm params etc)

"""Core ros2 python libraries"""
import rclpy    #To access ros2 node and related functionalities
from rclpy.node import Node # Node - The fundamental class for creating, publish, subscribe, service client etc. for a node, 
from rclpy.action import ActionServer, ActionClient # A commnication type functionality which needs feeback and long run task
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

"""ROS2 message and action/service interfaces"""
from custom_interfaces.action import ArmTask # (Custom) action interface for commnicating to our main action server
from moveit_msgs.srv import GetMotionPlan # (Standard moveit2) service message interface to request collision free path planning from A -> B
from moveit_msgs.action import ExecuteTrajectory # (Standard moveit2) action interface for executing the pre computed joint trajectory command by trajectory controller
from sensor_msgs.msg import JointState # (Standard ROS) Recieving joint_state values including position, velocity and efforts
from std_msgs.msg import Float64MultiArray # (Standard ROS) To publish data in array format in our case for GPIO commands (Accepted by Forward command controller)

"""Local AI agent engine and tools"""
"""To be started from agent core after init"""
from hulku_ai_agent.agent_core import AgentCore # (Custom) AgentCore class - The main engine for the AI agent and LLM reasoning logic
from hulku_ai_agent.memory.memory_manager import MemoryManager # (Custom) MemoryManager class - For managing the memory of the AI agent (Short-term memory, Long-term, episodic etc.,)
from hulku_ai_agent.tools import (
    ToolRegistry, # (Custom) ToolRegistry class - For managing the tools that the AI agent can use
    MoveJointsTool, MoveGripperTool, BuzzerTool, # Custom tools
    TorqueModeTool, GetJointStatesTool, GoHomeTool, WaitTool, PrintMessageTool, RGBLightTool, ManageMemoryTool # Custom tools
)

"""There are two loggers oen from python as below and one of ROS itself described by self.get_logger()"""
# Configure logging (Creating a logger for this node or file)
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger('hulku_ai_agent')


class HulkuAgentNode(Node):
    def __init__(self):
        super().__init__('hulku_agent_node')

        # ================================================================
        # PARAMETERS To be Declared while launching the node using -p flag 
        # ================================================================
        self.declare_parameter('config_file', '') # A custom cofig file if provided
        self.declare_parameter('provider', '') # A custom provider name
        self.declare_parameter('model', '') # Model to use for inference
        self.declare_parameter('api_key', '') # custom Api key provided by the model provider

        config_file = self.get_parameter('config_file').value  #getting the config file path from the parameter

        # Load config from external config file if provider
        # otherwise to default provided in the package it self
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:  #opening and reading the config file
                self._config = yaml.safe_load(f)
        else:
            # Try loading from the installed share directory
            from ament_index_python.packages import get_package_share_directory
            share_dir = get_package_share_directory('hulku_ai_agent')
            default_config = os.path.join(share_dir, 'config', 'agent_config.yaml') # get default config file path

            # Checking if the default config file exists or not
            if os.path.exists(default_config):
                # if exist load and save in the _config variable of the class (HulkuAgentNode) 
                with open(default_config, 'r') as f:
                    self._config = yaml.safe_load(f)
            else:
                # else through debug erro
                self.get_logger().error("No config file found!")
                raise RuntimeError("Config file not found")

        # Loads the agent and robot config defined in the loaded config file and save in respective variables 
        agent_config = self._config.get('agent', {}) #Getting the 'agent' key's value from the loaded config 
        robot_config = self._config.get('robot', {}) #Getting the 'robot' key's value from the loaded config

        # Allow ROS param overrides - if any (More value to given params explicitly)
        provider = self.get_parameter('provider').value or agent_config.get('default_provider', 'gemini')
        model = self.get_parameter('model').value or agent_config.get('default_model', 'gemini-2.0-flash')
        api_key = self.get_parameter('api_key').value or '' # Not provided in config for privacy

        self._system_prompt = agent_config.get('system_prompt', 'You are a robot assistant.')
        self._max_steps = agent_config.get('max_steps', 5) # Max steps for the ReAct loop to get the task done

        # Robot config
        self._arm_group = robot_config.get('arm_group', 'arm')
        self._gripper_group = robot_config.get('gripper_group', 'gripper')
        self._joint_names = robot_config.get('joint_names', [])
        self._gripper_joint = robot_config.get('gripper_joint', 'Rlink1_Joint')

        self.get_logger().info(f"Provider: {provider} | Model: {model}")
        self.get_logger().info(f"Arm group: {self._arm_group} | Joints: {self._joint_names}")

        # ==============================
        # CALLBACK GROUP
        # ==============================
        self._cb_group = ReentrantCallbackGroup()

        # ==============================
        # JOINT STATE SUBSCRIBER
        # ==============================
        self.current_joint_state = None # Variable to store current joint states of the robot
        self.create_subscription(
            JointState, '/joint_states', self._joint_state_cb, 10,
            callback_group=self._cb_group
        )

        # =====================================
        # MOVEIT INTERFACES (For planning path)
        # =====================================
        self.get_logger().info("Waiting for MoveIt services...")
        self._plan_client = self.create_client(
            GetMotionPlan, '/plan_kinematic_path',
            callback_group=self._cb_group
        ) # Create a service client for topic /plan_kinematic_path and interface type GetMotionPlan
        self._plan_client.wait_for_service(timeout_sec=30.0) #

        # Creating action client for executing trajectory
        self._execute_client = ActionClient(
            self, ExecuteTrajectory, '/execute_trajectory',
            callback_group=self._cb_group
        )
        self._execute_client.wait_for_server(timeout_sec=30.0)
        self.get_logger().info("MoveIt services connected!")

        # =================================
        # TOOL REGISTRY (For managing tools)
        # =================================
        self._registry = ToolRegistry() # Create a tool registry instance

        # GPIO controller publisher (shared by buzzer, torque, RGB tools)
        self._gpio_pub = self.create_publisher(
            Float64MultiArray, '/gpio_controller/commands', 10)
        # GPIO state initialization
        self._gpio_state = [0.0, 1.0, 0.0, 0.0, 0.0]  # [buzzer, torque, r, g, b]

        move_joints = MoveJointsTool(
            self, self._plan_client, self._execute_client, # node:  self, client: _plan_client, execute_client: _execute_client
            self._joint_names, self._arm_group # joint names of robot, moveit group name to be used while planning
        )
        # register move_joints tool in the registry
        self._registry.register(move_joints)
        # register move_gripper tool in the registry (Comments not added because almost same as move_joints_tool)
        self._registry.register(MoveGripperTool(
            self, self._plan_client, self._execute_client, # same as move_joint
            self._gripper_joint, self._gripper_group # joint_names: gripper joint names, gripper group
        ))
        # register buzzer tool 
        self._registry.register(BuzzerTool(self, self._gpio_pub, self._gpio_state))
        # register Torque tool
        self._registry.register(TorqueModeTool(self, self._gpio_pub, self._gpio_state))
        # register current joint state requesting tool
        self._registry.register(GetJointStatesTool(self, self._joint_names))
        # register go home tool
        self._registry.register(GoHomeTool(move_joints))
        # resgister wait tool for inserting dealy in tasks if needed
        self._registry.register(WaitTool())
        # register print message tool (for getting inbetween feedback updates)
        self._registry.register(PrintMessageTool(self))
        # register LED light tools
        self._registry.register(RGBLightTool(self, self._gpio_pub, self._gpio_state))

        self.get_logger().info(f"Registered tools:\n{self._registry.list_tools()}")

        # ==============================
        # LLM BACKEND
        # ==============================
        # call the _create_backend method created backend object according to provider and assign to the _llm_backend variable
        self._llm_backend = self._create_backend(provider, model, api_key)

        # ==============================
        # MEMORY MANAGER
        # ==============================
        # create the memory manager objectwith the configs for the robot context memory
        self._memory_manager = MemoryManager(config=self._config)
        self._registry.register(ManageMemoryTool(self._memory_manager))

        # ==============================
        # AGENT CORE
        # ==============================
        # Initialize agent core with llm backend, tool registry, system prompt and memort manager, and a maximum reply steps
        self._agent = AgentCore(
            llm_backend=self._llm_backend,
            tool_registry=self._registry,
            system_prompt=self._system_prompt,
            memory_manager=self._memory_manager,
            max_steps=self._max_steps,
            # We don't pass feedback_cb here, we will inject it per-request
        )

        # ==============================
        # ACTION SERVER
        # ==============================
        # Creates action server for the arm tasks
        self._action_server = ActionServer(
            self, ArmTask, 'arm_command', self._execute_callback,
            callback_group=self._cb_group
        )

        self.get_logger().info("🤖 HulkuBot AI Agent is ready!")

    # create object of the llm_backend according to the provider selected 
    def _create_backend(self, provider: str, model: str, api_key: str):
        """Create the appropriate LLM backend based on provider string."""
        provider = provider.lower()

        if provider == "gemini":
            from hulku_ai_agent.llm_backends.gemini_backend import GeminiBackend
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            self.get_logger().info(f"Using Gemini backend: {model}")
            return GeminiBackend(model_name=model, api_key=key)

        elif provider == "groq":
            from hulku_ai_agent.llm_backends.groq_backend import GroqBackend
            key = api_key or os.environ.get("GROQ_API_KEY", "")
            self.get_logger().info(f"Using Groq backend: {model}")
            return GroqBackend(model_name=model, api_key=key)

        elif provider == "ollama":
            from hulku_ai_agent.llm_backends.ollama_backend import OllamaBackend
            self.get_logger().info(f"Using local Ollama backend: {model}")
            return OllamaBackend(model_name=model)
            
        elif provider == "ollama_cloud":
            from hulku_ai_agent.llm_backends.ollama_cloud_backend import OllamaCloudBackend
            key = api_key or os.environ.get("OLLAMA_CLOUD_API_KEY", "")
            self.get_logger().info(f"Using Ollama Cloud backend: {model}")
            return OllamaCloudBackend(model_name=model, api_key=key)

        elif provider == "openrouter":
            from hulku_ai_agent.llm_backends.openrouter_backend import OpenRouterBackend
            key = api_key or os.environ.get("OPEN_ROUTER_KEY", "")
            self.get_logger().info(f"Using OpenRouter backend: {model}")
            return OpenRouterBackend(model_name=model, api_key=key)

        elif provider == "nvidia":
            from hulku_ai_agent.llm_backends.nvidia_backend import NvidiaBackend
            key = api_key or os.environ.get("NVIDIA_API_KEY", "")
            self.get_logger().info(f"Using NVIDIA backend: {model}")
            return NvidiaBackend(model_name=model, api_key=key)

        elif provider == "mistral":
            from hulku_ai_agent.llm_backends.mistral_backend import MistralBackend
            key = api_key or os.environ.get("MISTRAL_API_KEY", "")
            self.get_logger().info(f"Using Mistral backend: {model}")
            return MistralBackend(model_name=model, api_key=key)

        else:
            raise ValueError(f"Unknown LLM provider: '{provider}'. Use 'gemini', 'groq', 'ollama', 'ollama_cloud', 'openrouter', 'nvidia', or 'mistral'.")

    # callback executed after each jointstate publish
    def _joint_state_cb(self, msg):
        self.current_joint_state = msg

    # callback function executed when action goal is received
    def _execute_callback(self, goal_handle):
        """Handle incoming ArmTask action goals."""
        user_message = goal_handle.request.json_command
        self.get_logger().info(f"📩 Received: {user_message}")

        try:
            # Publish initial feedback
            feedback = ArmTask.Feedback()
            feedback.state = "Processing..."
            goal_handle.publish_feedback(feedback)

            # Define a local callback to publish live feedback from the agent
            def live_feedback_cb(state_str):
                feedback.state = state_str
                goal_handle.publish_feedback(feedback)

            # Temporarily inject the callback for this run
            self._agent._feedback_cb = live_feedback_cb

            # Run the ReAct agent loop
            result_text = self._agent.run(
                user_message,
                current_joint_state=self.current_joint_state,
                gpio_state=self._gpio_state,
                joint_names=self._joint_names
            )

            # Clean up callback
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
    node = HulkuAgentNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        # Spin with a multi-threaded executor to run callbacks concurrently
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

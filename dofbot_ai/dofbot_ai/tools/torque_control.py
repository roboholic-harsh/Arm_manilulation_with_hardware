from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class TorqueControlTool(BaseTool):
    name = "torque_control"
    description = "Enables or disables torque for the Dofbot arm motors."
    parameters = {
        "type": "object",
        "properties": {
            "enable": {"type": "boolean", "description": "True to enable torque, False to disable"}
        },
        "required": ["enable"]
    }

    def __init__(self, node):
        self.node = node

    def execute(self, enable: bool, **kwargs) -> ToolResult:
        self.node.torque_enable = 1.0 if enable else 0.0
        self.node.publish_gpio_command()
        self.node.get_logger().info(f"Setting torque to {enable}")
        return ToolResult(True, f"Torque is now {'ENABLED' if enable else 'DISABLED'}.")

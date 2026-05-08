from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class BuzzerControlTool(BaseTool):
    name = "buzzer_control"
    description = "Turns the Dofbot buzzer on or off."
    parameters = {
        "type": "object",
        "properties": {
            "state": {"type": "boolean", "description": "True to turn on, False to turn off"}
        },
        "required": ["state"]
    }

    def __init__(self, node):
        self.node = node

    def execute(self, state: bool, **kwargs) -> ToolResult:
        self.node.buzzer_trigger = 1.0 if state else 0.0
        self.node.publish_gpio_command()
        self.node.get_logger().info(f"Setting buzzer to {state}")
        return ToolResult(True, f"Buzzer is now {'ON' if state else 'OFF'}.")

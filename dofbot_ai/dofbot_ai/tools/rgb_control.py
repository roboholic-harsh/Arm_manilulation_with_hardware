from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class RGBControlTool(BaseTool):
    name = "rgb_control"
    description = "Controls the RGB LED on the Dofbot expansion board."
    parameters = {
        "type": "object",
        "properties": {
            "r": {"type": "integer", "description": "Red value (0-255)"},
            "g": {"type": "integer", "description": "Green value (0-255)"},
            "b": {"type": "integer", "description": "Blue value (0-255)"}
        },
        "required": ["r", "g", "b"]
    }

    def __init__(self, node):
        self.node = node

    def execute(self, r: int, g: int, b: int, **kwargs) -> ToolResult:
        self.node.led_r = float(r)
        self.node.led_g = float(g)
        self.node.led_b = float(b)
        self.node.publish_gpio_command()
        self.node.get_logger().info(f"Setting RGB LED to ({r}, {g}, {b})")
        return ToolResult(True, f"Successfully set RGB to R={r}, G={g}, B={b}.")

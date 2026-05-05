"""Toggle the robot buzzer via ROS service on hulku_hardware."""

import rclpy
from std_srvs.srv import SetBool
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class BuzzerTool(BaseTool):
    name = "buzzer"
    description = "Turn the robot's buzzer ON or OFF."
    parameters = {
        "type": "object",
        "properties": {
            "state": {
                "type": "boolean",
                "description": "true to turn buzzer ON, false to turn OFF.",
            }
        },
        "required": ["state"],
    }

    def __init__(self, node):
        self._node = node
        self._client = node.create_client(SetBool, '/hulku_hardware/buzzer')

    def execute(self, state: bool = False, **kwargs) -> ToolResult:
        if not self._client.wait_for_service(timeout_sec=3.0):
            return ToolResult(False, "Buzzer service not available. Is hulku_hardware running?")

        req = SetBool.Request()
        req.data = bool(state)

        future = self._client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future, timeout_sec=5.0)

        res = future.result()
        if res is None:
            return ToolResult(False, "Buzzer service call timed out.")

        return ToolResult(res.success, res.message)

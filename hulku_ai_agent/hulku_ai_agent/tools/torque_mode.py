"""Toggle torque (Drag & Teach mode) via ROS service on hulku_hardware."""

import rclpy
from std_srvs.srv import SetBool
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class TorqueModeTool(BaseTool):
    name = "torque_mode"
    description = (
        "Enable or disable motor torque (Drag & Teach mode). "
        "When torque is OFF (enabled=false), the robot can be freely moved by hand. "
        "When torque is ON (enabled=true), the motors hold their position."
    )
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "true to enable torque (hold position), false to disable (allow free movement).",
            }
        },
        "required": ["enabled"],
    }

    def __init__(self, node):
        self._node = node
        self._client = node.create_client(SetBool, '/hulku_hardware/torque')

    def execute(self, enabled: bool = True, **kwargs) -> ToolResult:
        if not self._client.wait_for_service(timeout_sec=3.0):
            return ToolResult(False, "Torque service not available. Is hulku_hardware running?")

        req = SetBool.Request()
        req.data = bool(enabled)

        future = self._client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future, timeout_sec=5.0)

        res = future.result()
        if res is None:
            return ToolResult(False, "Torque service call timed out.")

        return ToolResult(res.success, res.message)

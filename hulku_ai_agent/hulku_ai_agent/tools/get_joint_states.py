"""Read current joint positions from the /joint_states topic."""

import math
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class GetJointStatesTool(BaseTool):
    name = "get_joint_states"
    description = (
        "Read the current position of all robot joints in degrees. "
        "Use this to check where the robot is before planning a move."
    )
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, node, joint_names):
        self._node = node # Node:  HulkuAgentNode
        self._joint_names = joint_names # List of currently available joints name 

    def execute(self, **kwargs) -> ToolResult:
        # get the current joint values from the hulkuagentnode current_joint_state variable
        state = self._node.current_joint_state
        if state is None:
            return ToolResult(False, "Joint state not received yet. Is the robot running?")

        # create a dictionary of joint names and their values in a single placeholder of dict object
        js_map = dict(zip(state.name, state.position))

        # initiate empty dictionary for storing current joints
        angles = {}
        # loop thorugh all in js_map and append in the new dict
        for name in self._joint_names:
            rad = js_map.get(name, 0.0)
            angles[name] = round(math.degrees(rad), 1)

        # return the result with joint states to the agent
        return ToolResult(
            True,
            f"Current joint positions (degrees): {angles}",
            data={"joint_angles": angles}
        )

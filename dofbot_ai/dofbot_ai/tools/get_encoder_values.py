from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class GetEncoderValuesTool(BaseTool):
    name = "get_encoder_values"
    description = "Reads the current encoder values (joint positions) of the Dofbot arm."
    parameters = {}

    def __init__(self, node, joint_names: list):
        self.node = node
        self.joint_names = joint_names

    def execute(self, **kwargs) -> ToolResult:
        if not self.node.current_joint_state:
            return ToolResult(False, "Error: No joint states received yet.")

        positions = []
        msg = self.node.current_joint_state
        for j_name in self.joint_names:
            try:
                idx = msg.name.index(j_name)
                positions.append(round(msg.position[idx], 4))
            except ValueError:
                positions.append(None)

        return ToolResult(True, f"Current encoder values: {dict(zip(self.joint_names, positions))}")

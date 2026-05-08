from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class MoveToZeroTool(BaseTool):
    name = "move_to_zero"
    description = "Moves the Dofbot arm to the zero pose (all joints straight up)."
    parameters = {}

    def __init__(self, move_joints_tool):
        self.move_joints_tool = move_joints_tool

    def execute(self, **kwargs) -> ToolResult:
        return self.move_joints_tool.execute([0.0, 0.0, 0.0, 0.0])

from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class MoveToReadyPoseTool(BaseTool):
    name = "move_to_ready_pose"
    description = "Moves the Dofbot arm to the ready pose."
    parameters = {}

    def __init__(self, move_joints_tool):
        self.move_joints_tool = move_joints_tool

    def execute(self, **kwargs) -> ToolResult:
        return self.move_joints_tool.execute([0.0, 45.0, -90.0, -45.0])

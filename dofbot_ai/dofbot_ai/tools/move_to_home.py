from dofbot_ai.tools.base_tool import BaseTool, ToolResult

class MoveToHomeTool(BaseTool):
    name = "move_to_home"
    description = "Moves the Dofbot arm to the home pose."
    parameters = {}

    def __init__(self, move_joints_tool):
        self.move_joints_tool = move_joints_tool

    def execute(self, **kwargs) -> ToolResult:
        return self.move_joints_tool.execute([0.0, 90.0, -90.0, -90.0])

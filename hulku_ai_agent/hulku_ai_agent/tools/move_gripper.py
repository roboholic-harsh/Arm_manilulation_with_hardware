"""Control the robot gripper via MoveIt planning + execution."""

import rclpy
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class MoveGripperTool(BaseTool):
    name = "move_gripper"
    description = (
        "Open or close the robot gripper. "
        "Use action='open' to open, action='close' to close."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Open or close the gripper.",
            }
        },
        "required": ["action"],
    }

    def __init__(self, node, plan_client, execute_client, gripper_joint, gripper_group):
        self._node = node
        self._plan_client = plan_client
        self._execute_client = execute_client
        self._gripper_joint = gripper_joint
        self._gripper_group = gripper_group

    def execute(self, action: str = "open", **kwargs) -> ToolResult:
        from moveit_msgs.srv import GetMotionPlan
        from moveit_msgs.action import ExecuteTrajectory
        from moveit_msgs.msg import MotionPlanRequest, Constraints, JointConstraint

        # Map open/close to joint position
        if action == "open":
            position = 0.0   # Open position
        elif action == "close":
            position = 1.0   # Closed position (adjust based on your gripper range)
        else:
            return ToolResult(False, f"Unknown gripper action: '{action}'. Use 'open' or 'close'.")

        constraints = Constraints()
        jc = JointConstraint()
        jc.joint_name = self._gripper_joint
        jc.position = position
        jc.tolerance_above = 0.01
        jc.tolerance_below = 0.01
        jc.weight = 1.0
        constraints.joint_constraints.append(jc)

        mpr = MotionPlanRequest()
        mpr.group_name = self._gripper_group
        mpr.goal_constraints.append(constraints)
        mpr.allowed_planning_time = 2.0

        req = GetMotionPlan.Request()
        req.motion_plan_request = mpr

        future = self._plan_client.call_async(req)
        
        # Wait for the future to complete thread-safely using a sleep loop
        import time
        start_time = time.time()
        while not future.done():
            time.sleep(0.05)
            if time.time() - start_time > 10.0:
                break

        res = future.result()
        if res is None or res.motion_plan_response.error_code.val != 1:
            return ToolResult(False, f"Gripper planning failed for action '{action}'.")

        goal = ExecuteTrajectory.Goal()
        goal.trajectory = res.motion_plan_response.trajectory

        send_future = self._execute_client.send_goal_async(goal)
        
        # Wait for goal acknowledgement thread-safely
        start_time = time.time()
        while not send_future.done():
            time.sleep(0.05)
            if time.time() - start_time > 10.0:
                break

        handle = send_future.result()
        if handle is None or not handle.accepted:
            return ToolResult(False, "Gripper execution rejected.")

        result_future = handle.get_result_async()
        
        # Wait for final result thread-safely
        start_time = time.time()
        while not result_future.done():
            time.sleep(0.05)
            if time.time() - start_time > 15.0:
                break

        execution_res = result_future.result()
        if execution_res is None or execution_res.result.error_code.val != 1:
            return ToolResult(False, "Gripper execution failed.")

        return ToolResult(True, f"Gripper {action}ed successfully.")

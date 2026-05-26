"""Move robot arm joints to target angles via MoveIt planning + execution."""

import math
import rclpy
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class MoveJointsTool(BaseTool):
    name = "move_joints"
    description = (
        "Move the robot arm joints to specific target angles in degrees. "
        "Provide a list of 5 joint angles. Use -402 for any joint you want to keep unchanged. "
        "Joint indices: 0=Base, 1-3=Intermediate, 4=Wrist."
    )
    parameters = {
        "type": "object",
        "properties": {
            "joint_angles": {
                "type": "array",
                "items": {"type": "number"},
                "description": "List of 5 target joint angles in degrees. Use -402 for unchanged joints.",
            }
        },
        "required": ["joint_angles"],
    }

    def __init__(self, node, plan_client, execute_client, joint_names, arm_group):
        self._node = node # node: The ROS node instance to which this tool belongs.
        self._plan_client = plan_client # plan_client: The MoveIt planner service client.
        self._execute_client = execute_client # execute_client: The MoveIt trajectory execution action client.
        self._joint_names = joint_names # joint_names: A list of joint names for the robot arm.
        self._arm_group = arm_group # arm_group: The name of the MoveIt planning group for the arm.

    # main execution of the tool
    def execute(self, joint_angles: list = None, **kwargs) -> ToolResult:
        ## angles provided at time of execution
        if joint_angles is None:
            return ToolResult(False, "Missing required parameter: joint_angles")

        ## message interface for motion plan store and execute trajectory
        from moveit_msgs.srv import GetMotionPlan
        from moveit_msgs.action import ExecuteTrajectory
        ## message interface for motion planning requests including constraints 
        # to be attached and also JointConstaint if any
        from moveit_msgs.msg import MotionPlanRequest, Constraints, JointConstraint
        # Interface to store the joint_state values recieve from the joint_state_publisher
        from sensor_msgs.msg import JointState

        # Checking if the number of joint angles provided is equal to the number of joints in the robot
        dof = len(self._joint_names)
        if len(joint_angles) != dof:
            return ToolResult(False, f"Expected {dof} joint angles, got {len(joint_angles)}")

        # Get current joint state for -402 handling
        current_state = self._node.current_joint_state
        if current_state is None:
            return ToolResult(False, "Joint state not received yet. Is the robot running?")

        # It parses two parallel list coming from current_state into one single and fast python dict for quick access
        # In this method order won't matter
        js_map = dict(zip(current_state.name, current_state.position)) # Zip pairs both as single iterator  dict takes it and converts into python dict object

        # Convert degrees to radians, preserving current for -402
        joint_rad = []
        for name, v in zip(self._joint_names, joint_angles):
            if v == -402:
                joint_rad.append(js_map.get(name, 0.0))
            else:
                joint_rad.append(math.radians(v))

        # Build MoveIt plan request
        constraints = Constraints()  # Constaints message object: - It includes joint, Position and orientation constraints
        for name, value in zip(self._joint_names, joint_rad): # Go through each joint and apply below constraint on each
            jc = JointConstraint() # Joint constraint message object
            jc.joint_name = name # Target joint
            jc.position = value # Target Position
            jc.tolerance_above = 0.01 # Sets the acceptable deviation in radians (need to set because physically exact precision is not hard)
            jc.tolerance_below = 0.01
            jc.weight = 1.0 # sets the priority of the joint constraint that this constraint is much mandatory
            constraints.joint_constraints.append(jc) # Append this joint constaint to the main constraints object

        mpr = MotionPlanRequest() # MotionPlanRequest object which contains all the information used by planning algorithm
        mpr.group_name = self._arm_group # Assigns for which joint group the planning is being done
        mpr.goal_constraints.append(constraints) # Appends the combined constraints to goal_constraints of MPR object
        mpr.allowed_planning_time = 5.0 # Add max planning time 

        req = GetMotionPlan.Request() # instantiate of standard service request object
        req.motion_plan_request = mpr # Assign motion plan request to service request object

        # Plan
        future = self._plan_client.call_async(req) # Call planning service asynchronously and return future object which satisfy when request complete
        
        # Wait for the future to complete thread-safely using a sleep loop
        import time
        start_time = time.time()
        while not future.done():
            time.sleep(0.05)
            if time.time() - start_time > 10.0:
                break

        res = future.result() # extracts the result object from the completed future object
        # checks the error code from result object which should be 1 if planning is successful other means planning failed/ collision detected/ out_of_bounds
        if res is None or res.motion_plan_response.error_code.val != 1:
            return ToolResult(False, "Motion planning failed. Target may be unreachable.")

        # Execute
        goal = ExecuteTrajectory.Goal() #Instantiate ExecuteTrajectory.goal object
        goal.trajectory = res.motion_plan_response.trajectory # Copies the trajectory data to the goal.trajectory object

        send_future = self._execute_client.send_goal_async(goal) # submits goal to the MoveIt action server and returns a future object 
        # This is goal handshake acknowledgement 
        
        # Wait for goal acknowledgement thread-safely
        start_time = time.time()
        while not send_future.done():
            time.sleep(0.05)
            if time.time() - start_time > 10.0:
                break

        handle = send_future.result() # stores result in handle object 
        if handle is None or not handle.accepted:
            return ToolResult(False, "Trajectory execution was rejected by the controller.")

        result_future = handle.get_result_async() # request final execution result if completed or not 
        
        # Wait for final result thread-safely
        start_time = time.time()
        while not result_future.done():
            time.sleep(0.05)
            if time.time() - start_time > 30.0:
                break

        # queries final result if not success (which is 1) then return failure
        execution_res = result_future.result()
        if execution_res is None or execution_res.result.error_code.val != 1:
            return ToolResult(False, "Trajectory execution failed.")

        return ToolResult(True, f"Successfully moved joints to {joint_angles} degrees.")

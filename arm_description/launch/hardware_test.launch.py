import os
from launch import LaunchDescription
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    # 1. Parse the URDF
    urdf_path = "src/arm_description/description/bot.urdf.xacro"
    # /home/roboholic_harsh/Desktop/dofbotarm/harsh_ws/src/arm_moveit_config/config/robot.urdf.xacro
    doc = xacro.process_file(urdf_path)
    robot_description = {"robot_description": doc.toxml()}

    # 2. Start the Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description]
    )

    # 3. Start the Controller Manager
    # Notice it doesn't need the URDF parameter, it pulls it from RSP!
    node_controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=['src/arm_description/config/controllers.yaml'],
        remappings=[
            ('~/robot_description', '/robot_description'), # <--- THIS IS THE FIX
        ],
        output='screen'
    )

    return LaunchDescription([
        node_robot_state_publisher,
        node_controller_manager
    ])
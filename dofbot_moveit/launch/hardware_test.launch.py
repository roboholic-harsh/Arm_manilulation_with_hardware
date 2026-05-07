import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder

def generate_launch_description():
    # 1. Parse the URDF via MoveItConfigsBuilder
    moveit_config = MoveItConfigsBuilder("dofbot_urdf", package_name="dofbot_moveit").to_moveit_configs()

    # 2. Start the Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[moveit_config.robot_description]
    )

    # 3. Start the Controller Manager
    node_controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[
            moveit_config.robot_description,
            os.path.join(get_package_share_directory('dofbot_moveit'), 'config', 'ros2_controllers.yaml')
        ],
        output='screen'
    )

    return LaunchDescription([
        node_robot_state_publisher,
        node_controller_manager
    ])

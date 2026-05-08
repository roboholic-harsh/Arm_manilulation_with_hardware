from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    # 1. Include the main robot bringup from dofbot_moveit
    robot_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('dofbot_moveit'),
                'launch',
                'robot_bringup.launch.py'
            ])
        ])
    )

    # 2. Launch the dofbot AI agent node
    ai_agent_node = Node(
        package='dofbot_ai',
        executable='agent_node',
        name='dofbot_agent_node',
        output='screen'
    )

    # 3. Launch the Streamlit GUI
    gui_node = Node(
        package='dofbot_ai_gui',
        executable='main',
        name='dofbot_ai_gui',
        output='screen'
    )

    return LaunchDescription([
        LogInfo(msg="Launching Dofbot Hardware, MoveIt, AI Agent, and GUI..."),
        robot_bringup,
        ai_agent_node,
        gui_node
    ])

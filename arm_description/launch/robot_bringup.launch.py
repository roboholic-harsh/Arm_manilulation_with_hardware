import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    # 1. Hardware Base (Controller Manager + Robot State Publisher)
    # Assumes hardware_test.launch.py is inside arm_description/launch/
    hardware_test_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('arm_description'), 'launch', 'hardware_test.launch.py')
        ])
    )

    # 2. Spawn Joint State Broadcaster
    jsb_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],
    )

    # 3. Spawn Arm Controller
    arm_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["arm_controller"],
    )

    load_gpio_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gpio_controller"],
    )

    # 4. MoveIt MoveGroup
    move_group_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('arm_moveit_config'), 'launch', 'move_group.launch.py')
        ])
    )

    # 5. MoveIt RViz
    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('arm_moveit_config'), 'launch', 'moveit_rviz.launch.py')
        ])
    )

    # Compile the Launch Description with Timers to stagger the boot sequence
    return LaunchDescription([
        hardware_test_launch,
        TimerAction(period=2.0, actions=[jsb_spawner]),
        TimerAction(period=4.0, actions=[arm_controller_spawner]),
        TimerAction(period=6.0, actions=[move_group_launch]),
        TimerAction(period=8.0, actions=[rviz_launch]),
        TimerAction(period=10.0, actions=[load_gpio_controller]),
    ])
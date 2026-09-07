import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    is_sim = LaunchConfiguration("is_sim")
    
    is_sim_arg = DeclareLaunchArgument(
        "is_sim",
        default_value="True"
    )

    # NOTE: Do NOT start ros2_control_node here.
    # When using ign_ros2_control, the Gazebo plugin creates the controller_manager
    # inside the Gazebo process. We only need to spawn controllers into it.

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            "/controller_manager",
        ],
    )

    arm_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["arm_controller", "--controller-manager", "/controller_manager"],
    )

    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gripper_controller", "--controller-manager", "/controller_manager"],
    )

    return LaunchDescription(
        [
            is_sim_arg,
            joint_state_broadcaster_spawner,
            arm_controller_spawner,
            gripper_controller_spawner,
        ]
    )

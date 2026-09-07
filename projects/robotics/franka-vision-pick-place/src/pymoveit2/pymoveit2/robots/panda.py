from typing import List

MOVE_GROUP_ARM: str = "arm"
MOVE_GROUP_GRIPPER: str = "gripper"

# Allegro Hand: open = fingers extended, close = fingers curled
OPEN_GRIPPER_JOINT_POSITIONS: List[float] = [
    # thumb: rotatory, flexor1, flexor2, flexor3
    0.463, 0.0, 0.0, 0.0,
    # finger1: rotatory, flexor1, flexor2, flexor3
    0.0, 0.0, 0.0, 0.0,
    # finger2
    0.0, 0.0, 0.0, 0.0,
    # finger3
    0.0, 0.0, 0.0, 0.0,
]

CLOSED_GRIPPER_JOINT_POSITIONS: List[float] = [
    # thumb: rotatory, flexor1, flexor2, flexor3
    1.3, 1.1, 1.3, 1.3,
    # finger1: rotatory, flexor1, flexor2, flexor3
    0.0, 1.2, 1.3, 1.3,
    # finger2
    0.0, 1.2, 1.3, 1.3,
    # finger3
    0.0, 1.2, 1.3, 1.3,
]


def joint_names(prefix: str = "panda_") -> List[str]:
    return [
        prefix + "joint1",
        prefix + "joint2",
        prefix + "joint3",
        prefix + "joint4",
        prefix + "joint5",
        prefix + "joint6",
        prefix + "joint7",
    ]


def base_link_name(prefix: str = "panda_") -> str:
    return prefix + "link0"


def end_effector_name(prefix: str = "panda_") -> str:
    return "allegro_palm_link"


def gripper_joint_names(prefix: str = "panda_") -> List[str]:
    return [
        "allegro_thumb_rotatory_joint",
        "allegro_thumb_flexor_1_joint",
        "allegro_thumb_flexor_2_joint",
        "allegro_thumb_flexor_3_joint",
        "allegro_finger_1_rotatory_joint",
        "allegro_finger_1_flexor_1_joint",
        "allegro_finger_1_flexor_2_joint",
        "allegro_finger_1_flexor_3_joint",
        "allegro_finger_2_rotatory_joint",
        "allegro_finger_2_flexor_1_joint",
        "allegro_finger_2_flexor_2_joint",
        "allegro_finger_2_flexor_3_joint",
        "allegro_finger_3_rotatory_joint",
        "allegro_finger_3_flexor_1_joint",
        "allegro_finger_3_flexor_2_joint",
        "allegro_finger_3_flexor_3_joint",
    ]

#!/usr/bin/env python3
"""
Pick and place v4 - Unified MoveIt2 architecture.

Design:
  - ALL motions go through MoveIt2 (single control channel)
  - Large motions use move_to_configuration() with OMPL planning
  - Vertical approach/retreat use move_to_pose(cartesian=True)
  - Safe transit via TRANSIT_JOINTS waypoint (arm raised, mid-rotation)

ros2 run pymoveit2 pick_and_place.py --ros-args -p target_color:=R
"""

from threading import Thread
import time
import math
import traceback
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.action import ActionClient
from rclpy.duration import Duration
from std_msgs.msg import String
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration as DurationMsg
import tf2_ros

from pymoveit2 import MoveIt2
from pymoveit2.robots import panda
from experiment_logger import ExperimentLogger

# ================================================================
# Constants
# ================================================================
SAFE_Z = 0.55            # Safe height above table (panda_link0 frame)
GRASP_Z_OFFSET = -0.99   # Detector z -> grasp height
GRASP_X_OFFSET = -0.004  # Fine-tune: shift grasp x backward 2mm
GRASP_Y_OFFSET = -0.003
PRE_GRASP_HEIGHT = 0.12  # How high above grasp point to start vertical descent
QUAT_XYZW = [0.0, 0.707, 0.0, 0.707]  # Palm facing down

# Joint configurations (radians)
START_JOINTS = [0.0, 0.0, 0.0, -0.5, 0.0, 0.1, math.radians(-125.0)]
DROP_JOINTS = [
    math.radians(-161.0), math.radians(30.0), math.radians(-20.0),
    math.radians(-124.0), math.radians(44.0), math.radians(163.0),
    math.radians(7.0),
]
# Safe mid-rotation waypoint: arm high, halfway between front and back
# Avoids table collision during large rotation
TRANSIT_JOINTS = [
    math.radians(-80.0), math.radians(-10.0), 0.0,
    math.radians(-90.0), 0.0, math.radians(90.0), math.radians(-60.0),
]


class DirectGripper:
    """Direct FollowJointTrajectory to gripper_controller (bypasses MoveIt)."""

    def __init__(self, node, callback_group):
        self.node = node
        self.joint_names = panda.gripper_joint_names()
        self._result_future = None
        self._action_client = ActionClient(
            node, FollowJointTrajectory,
            "/gripper_controller/follow_joint_trajectory",
            callback_group=callback_group,
        )
        self.node.get_logger().info("Waiting for gripper_controller...")
        self._action_client.wait_for_server()
        self.node.get_logger().info("gripper_controller connected.")

    def _send(self, positions, duration_sec=1.0):
        pt = JointTrajectoryPoint()
        pt.positions = [float(p) for p in positions]
        pt.time_from_start = DurationMsg(sec=int(duration_sec), nanosec=0)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory(joint_names=self.joint_names, points=[pt])
        future = self._action_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=5.0)
        gh = future.result()
        if gh and gh.accepted:
            self._result_future = gh.get_result_async()
        else:
            self.node.get_logger().error("Gripper goal rejected!")

    def open(self):
        self.node.get_logger().info("Gripper -> OPEN")
        self._send(panda.OPEN_GRIPPER_JOINT_POSITIONS)

    def close(self):
        self.node.get_logger().info("Gripper -> CLOSE")
        self._send(panda.CLOSED_GRIPPER_JOINT_POSITIONS)

    def wait(self):
        if self._result_future is None:
            return
        rclpy.spin_until_future_complete(self.node, self._result_future, timeout_sec=10.0)
        self._result_future = None


class PickAndPlace(Node):
    def __init__(self):
        super().__init__("pick_and_place")

        self.declare_parameter("target_color", "R")
        self.target_color = self.get_parameter("target_color").value.upper()

        self.already_moved = False
        self.target_coords = None
        self.step_results = []
        self.callback_group = ReentrantCallbackGroup()

        # Experiment logger
        self.logger = ExperimentLogger(self.target_color)

        # TF
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # MoveIt2 (unified motion control)
        self.moveit2 = MoveIt2(
            node=self,
            joint_names=panda.joint_names(),
            base_link_name=panda.base_link_name(),
            end_effector_name=panda.end_effector_name(),
            group_name=panda.MOVE_GROUP_ARM,
            callback_group=self.callback_group,
        )
        self.moveit2.max_velocity = 0.55
        self.moveit2.max_acceleration = 0.1
        self.moveit2.allowed_planning_time = 5.0
        self.moveit2.num_planning_attempts = 10

        # Gripper
        self.gripper = DirectGripper(self, self.callback_group)

        # Color subscriber
        self.sub = self.create_subscription(
            String, "/color_coordinates", self.coords_callback, 10
        )
        self.get_logger().info(f"Waiting for {self.target_color} from /color_coordinates...")

        # Wait for joint states
        self.get_logger().info("Waiting for joint states...")
        deadline = time.time() + 30.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.5)
            if self.moveit2.joint_state is not None:
                break
        else:
            self.get_logger().error("Timeout waiting for joint states!")
            return
        self.get_logger().info("Joint states OK. Moving to start...")

        # Go to start position
        self._move_to_joints(START_JOINTS, label="init_start")
        # Open gripper ready
        self.gripper.open()
        self.gripper.wait()

    # ================================================================
    # MoveIt2 motion helpers
    # ================================================================

    def _move_to_joints(self, target_joints, label="move"):
        """Move to joint config via MoveIt2 OMPL planning."""
        self.get_logger().info(f"[OMPL] {label}: move_to_configuration")
        self.logger.begin_step()
        self.moveit2.move_to_configuration(target_joints)
        ok = self.moveit2.wait_until_executed()
        time.sleep(0.5)
        pos = self._log_tf(label)
        js = self.moveit2.joint_state
        joints = list(js.position) if js else None
        self.logger.record_step(label, None, pos, None, ok, joints)
        return ok

    def _move_to_joints_via(self, waypoint_configs, label="via"):
        """Move through multiple joint configs sequentially via MoveIt2."""
        for i, config in enumerate(waypoint_configs):
            if not self._move_to_joints(config, label=f"{label}_wp{i+1}"):
                return False
        return True

    def _wait_state_sync(self, timeout=3.0):
        """Wait until MoveIt2 joint_state is stable (no longer changing)."""
        stable_count = 0
        prev_positions = None
        deadline = time.time() + timeout
        while time.time() < deadline and stable_count < 3:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.moveit2.joint_state is not None:
                current = list(self.moveit2.joint_state.position)
                if prev_positions is not None:
                    max_diff = max(
                        abs(c - p) for c, p in zip(current, prev_positions)
                    )
                    if max_diff < 0.001:
                        stable_count += 1
                    else:
                        stable_count = 0
                prev_positions = current
            time.sleep(0.1)
        if stable_count >= 3:
            self.get_logger().info("[SYNC] Joint state stable")
        else:
            self.get_logger().warn("[SYNC] Timeout waiting for stable joint state")

    def _ik_joint_move(self, position, quat_xyzw, label="ik_move"):
        """Solve IK for target pose, then move via joint-space OMPL planning."""
        self.get_logger().info(
            f"[IK] {label}: target=[{position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}]"
        )
        self._wait_state_sync()
        ik_result = self.moveit2.compute_ik(
            position, quat_xyzw, ik_link_name="allegro_palm_link"
        )
        if ik_result is None:
            self.get_logger().error(f"[IK] {label}: IK solve failed!")
            return False
        # Extract arm joint positions in correct order
        arm_names = list(panda.joint_names())
        target_joints = []
        for name in arm_names:
            if name in ik_result.name:
                idx = ik_result.name.index(name)
                target_joints.append(ik_result.position[idx])
            else:
                self.get_logger().error(f"[IK] {label}: joint {name} missing!")
                return False
        self.get_logger().info(
            f"[IK] {label}: joints={[round(j, 3) for j in target_joints]}"
        )
        self.logger.begin_step()
        self.moveit2.move_to_configuration(target_joints)
        ok = self.moveit2.wait_until_executed()
        time.sleep(0.3)
        self._verify_pose(label, position)
        js = self.moveit2.joint_state
        joints = list(js.position) if js else None
        self.logger.record_joint_snapshot(label, joints)
        return ok

    # ================================================================
    # Cartesian helpers
    # ================================================================

    def _cartesian_move(self, position, quat_xyzw, label="cartesian"):
        """Cartesian straight-line move via MoveIt2."""
        self.get_logger().info(
            f"[CART] {label}: target=[{position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}]"
        )
        self.moveit2.move_to_pose(position=position, quat_xyzw=quat_xyzw, cartesian=True)
        ok = self.moveit2.wait_until_executed()
        time.sleep(0.3)
        result = self._verify_pose(label, position)
        result["executed"] = ok
        return result

    # ================================================================
    # TF helpers
    # ================================================================

    def _get_ee_pose(self):
        try:
            t = self.tf_buffer.lookup_transform(
                "panda_link0", "allegro_palm_link",
                rclpy.time.Time(), timeout=Duration(seconds=2.0)
            )
            p = t.transform.translation
            q = t.transform.rotation
            return [p.x, p.y, p.z], [q.x, q.y, q.z, q.w]
        except Exception as e:
            self.get_logger().warn(f"TF lookup failed: {e}")
            return None, None

    def _log_tf(self, label):
        pos, quat = self._get_ee_pose()
        if pos:
            self.get_logger().info(
                f"[TF] {label}: pos=[{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]"
            )
        return pos

    def _verify_pose(self, label, target_pos):
        pos, _ = self._get_ee_pose()
        result = {"step": label, "pos": pos, "target": target_pos}
        if pos and target_pos:
            err = [pos[i] - target_pos[i] for i in range(3)]
            dist = math.sqrt(sum(e**2 for e in err))
            self.get_logger().info(
                f"[TF] {label}: actual=[{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]  "
                f"|err|={dist:.4f}m"
            )
            result["distance_error"] = dist
            self.logger.record_step(label, target_pos, pos, dist, True)
        self.step_results.append(result)
        return result

    # ================================================================
    # Main sequence
    # ================================================================

    def coords_callback(self, msg):
        if self.already_moved:
            return

        try:
            color_id, x, y, z = msg.data.split(",")
            if color_id.strip().upper() != self.target_color:
                return

            self.target_coords = [float(x), float(y), float(z)]
            self.already_moved = True

            tx, ty, tz = self.target_coords
            self.get_logger().info(f"TARGET {self.target_color}: [{tx:.3f}, {ty:.3f}, {tz:.3f}]")
            self.logger.set_detected(self.target_coords)

            # Compute key positions
            grasp_z = tz + GRASP_Z_OFFSET
            grasp_x = tx + GRASP_X_OFFSET
            grasp_y = ty + GRASP_Y_OFFSET
            above_target = [grasp_x, grasp_y, SAFE_Z]
            pre_grasp = [grasp_x, grasp_y, grasp_z + PRE_GRASP_HEIGHT]
            grasp = [grasp_x, grasp_y, grasp_z]
            post_grasp = [grasp_x, grasp_y, SAFE_Z]

            self.get_logger().info("[PLAN] above:     " + str([round(v, 3) for v in above_target]))
            self.get_logger().info("[PLAN] pre_grasp: " + str([round(v, 3) for v in pre_grasp]))
            self.get_logger().info("[PLAN] grasp:     " + str([round(v, 3) for v in grasp]))
            self.logger.set_grasp_target(grasp)

            # ==============================================================
            # PHASE 1: PICK (IK + joint-space planning for all moves)
            # ==============================================================
            self.get_logger().info("=" * 50 + " PHASE 1: PICK")
            self.logger.begin_phase("pick_s")

            # 0. Open gripper before approaching
            self.gripper.open()
            self.gripper.wait()
            time.sleep(0.3)

            # 1. IK + OMPL to above target
            self._ik_joint_move(above_target, QUAT_XYZW, "above_target")

            # 2. IK + OMPL down to pre_grasp
            self._ik_joint_move(pre_grasp, QUAT_XYZW, "pre_grasp_down")

            # 3. IK + OMPL down to grasp point
            self._ik_joint_move(grasp, QUAT_XYZW, "grasp")

            # 4. Close gripper
            self.gripper.close()
            self.gripper.wait()
            time.sleep(0.3)
            self._log_tf("grabbed")

            # 5. IK + OMPL up to safe height
            self._ik_joint_move(post_grasp, QUAT_XYZW, "safe_up")

            # ==============================================================
            # PHASE 2: PLACE (MoveIt2 OMPL joint moves)
            # ==============================================================
            self.get_logger().info("=" * 50 + " PHASE 2: PLACE")
            self.logger.begin_phase("place_s")

            # 6-7. OMPL: current -> TRANSIT -> DROP
            self._move_to_joints_via(
                [TRANSIT_JOINTS, DROP_JOINTS], label="to_drop"
            )

            # 8. Release
            self.gripper.open()
            self.gripper.wait()
            time.sleep(0.5)
            self._log_tf("dropped")

            # ==============================================================
            # PHASE 3: RETURN (MoveIt2 OMPL joint moves)
            # ==============================================================
            self.get_logger().info("=" * 50 + " PHASE 3: RETURN")
            self.logger.begin_phase("return_s")

            # 9. OMPL: DROP -> TRANSIT -> START
            self.gripper.close()
            self.gripper.wait()
            self._move_to_joints_via(
                [TRANSIT_JOINTS, START_JOINTS], label="return"
            )

            # ==============================================================
            # SUMMARY
            # ==============================================================
            self.get_logger().info("=" * 50 + " DONE")
            for r in self.step_results:
                if r.get("pos"):
                    p = r["pos"]
                    step = r["step"]
                    line = f"  {step}: [{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}]"
                    if r.get("distance_error") is not None:
                        de = r["distance_error"]
                        line += f"  err={de:.4f}m"
                    self.get_logger().info(line)

            self.get_logger().info("Pick-and-place complete!")

            # 生成实验图表
            self.logger.end_phase()
            self.logger.generate(result="success")

            rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f"Error: {e}")
            traceback.print_exc()


def main():
    rclpy.init()
    node = PickAndPlace()
    executor = rclpy.executors.MultiThreadedExecutor(2)
    executor.add_node(node)
    t = Thread(target=executor.spin, daemon=True)
    t.start()
    try:
        t.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

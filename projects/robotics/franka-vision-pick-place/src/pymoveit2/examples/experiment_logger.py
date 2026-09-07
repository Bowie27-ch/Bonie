#!/usr/bin/env python3
"""
experiment_logger.py — 抓取实验数据记录 + 自动出图

用法：在 pick_and_place.py 中 import，运行结束后调用 generate() 自动生成图表。
"""
import os
import json
import time
import math
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # 无头模式，不需要显示器
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.font_manager import FontProperties
import numpy as np


class ExperimentLogger:
    """抓取实验记录器。"""

    def __init__(self, color: str, base_dir: str = None):
        self.color = color.upper()
        self.t0 = time.time()
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.trial_id = f"{self.ts}_{self.color}"

        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "..", "experiments"
            )
        self.out_dir = os.path.join(base_dir, f"trial_{self.trial_id}")
        os.makedirs(self.out_dir, exist_ok=True)

        self.detected_coords = None
        self.grasp_target = None
        self.steps = []           # [{name, target, actual, error_m, duration_s, plan_ok}]
        self.joint_snapshots = [] # [{name, joints: [7 floats]}]
        self.phase_times = {}     # {pick_s, place_s, return_s, total_s}
        self._step_t0 = None
        self._phase_t0 = None
        self._current_phase = None

    # ── 记录接口 ──

    def set_detected(self, coords):
        self.detected_coords = list(coords)

    def set_grasp_target(self, coords):
        self.grasp_target = list(coords)

    def begin_phase(self, name):
        if self._current_phase and self._phase_t0:
            self.phase_times[self._current_phase] = time.time() - self._phase_t0
        self._current_phase = name
        self._phase_t0 = time.time()

    def end_phase(self):
        if self._current_phase and self._phase_t0:
            self.phase_times[self._current_phase] = time.time() - self._phase_t0
        self._current_phase = None

    def begin_step(self):
        self._step_t0 = time.time()

    def record_step(self, name, target, actual, error_m, plan_ok, joint_positions=None):
        duration = time.time() - self._step_t0 if self._step_t0 else 0
        self.steps.append({
            "name": name,
            "target": target,
            "actual": actual,
            "error_m": error_m,
            "duration_s": round(duration, 2),
            "plan_ok": plan_ok,
        })
        if joint_positions is not None:
            self.joint_snapshots.append({
                "name": name,
                "joints": [round(j, 4) for j in joint_positions[:7]],
            })

    def record_joint_snapshot(self, name, joint_positions):
        if joint_positions is not None:
            self.joint_snapshots.append({
                "name": name,
                "joints": [round(j, 4) for j in joint_positions[:7]],
            })

    # ── 生成全部输出 ──

    def generate(self, result="success"):
        self.phase_times["total_s"] = round(time.time() - self.t0, 1)
        self._save_json(result)
        self._plot_position_error()
        self._plot_step_timing()
        self._plot_trajectory_3d()
        self._plot_joint_angles()
        self._plot_summary_table(result)
        print(f"\n📊 实验结果已保存到 {self.out_dir}/")
        for f in sorted(os.listdir(self.out_dir)):
            print(f"  ├── {f}")

    # ── JSON ──

    def _save_json(self, result):
        data = {
            "trial_id": self.trial_id,
            "timestamp": datetime.now().isoformat(),
            "target_color": self.color,
            "detected_coords": self.detected_coords,
            "grasp_target": self.grasp_target,
            "steps": self.steps,
            "joint_snapshots": self.joint_snapshots,
            "phases": self.phase_times,
            "result": result,
        }
        path = os.path.join(self.out_dir, "trial_data.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── 图1：位置误差柱状图 ──

    def _plot_position_error(self):
        steps_with_err = [s for s in self.steps if s.get("error_m") is not None]
        if not steps_with_err:
            return

        names = [s["name"] for s in steps_with_err]
        errors = [s["error_m"] * 1000 for s in steps_with_err]  # mm

        fig, ax = plt.subplots(figsize=(10, 5))
        colors = ["#1565C0" if e < 10 else "#F57C00" if e < 20 else "#D32F2F" for e in errors]
        bars = ax.bar(range(len(names)), errors, color=colors, edgecolor="white", linewidth=0.5)

        # 数值标注
        for bar, val in zip(bars, errors):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)

        ax.axhline(y=10, color="#D32F2F", linestyle="--", alpha=0.5, label="10mm threshold")
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
        ax.set_ylabel("Position Error (mm)")
        ax.set_title(f"End-Effector Position Error per Step — Color: {self.color}")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "position_error.png"), dpi=150)
        plt.close(fig)

    # ── 图2：各步骤耗时 ──

    def _plot_step_timing(self):
        if not self.steps:
            return

        names = [s["name"] for s in self.steps]
        durations = [s["duration_s"] for s in self.steps]

        # 按阶段着色
        phase_colors = {
            "above_target": "#1565C0", "pre_grasp_down": "#1565C0",
            "grasp": "#1565C0", "safe_up": "#1565C0",
            "to_drop_wp1": "#2E7D32", "to_drop_wp2": "#2E7D32",
            "return_wp1": "#F57C00", "return_wp2": "#F57C00",
        }
        colors = [phase_colors.get(n, "#757575") for n in names]

        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar(range(len(names)), durations, color=colors, edgecolor="white")

        for bar, val in zip(bars, durations):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"{val:.1f}s", ha="center", va="bottom", fontsize=9)

        # 图例
        from matplotlib.patches import Patch
        legend_items = [
            Patch(facecolor="#1565C0", label="PICK"),
            Patch(facecolor="#2E7D32", label="PLACE"),
            Patch(facecolor="#F57C00", label="RETURN"),
        ]
        ax.legend(handles=legend_items)

        total = self.phase_times.get("total_s", sum(durations))
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
        ax.set_ylabel("Duration (s)")
        ax.set_title(f"Step Duration — Total: {total:.1f}s — Color: {self.color}")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "step_timing.png"), dpi=150)
        plt.close(fig)

    # ── 图3：3D 轨迹 ──

    def _plot_trajectory_3d(self):
        pts = [s for s in self.steps if s.get("actual")]
        if len(pts) < 2:
            return

        xs = [s["actual"][0] for s in pts]
        ys = [s["actual"][1] for s in pts]
        zs = [s["actual"][2] for s in pts]
        names = [s["name"] for s in pts]

        fig = plt.figure(figsize=(9, 7))
        ax = fig.add_subplot(111, projection="3d")
        ax.plot(xs, ys, zs, "o-", color="#1565C0", markersize=6, linewidth=1.5)

        # 标注关键点
        key_steps = {"above_target", "grasp", "safe_up", "init_start"}
        for i, name in enumerate(names):
            if name in key_steps or i == 0 or i == len(names) - 1:
                ax.text(xs[i], ys[i], zs[i] + 0.02, name, fontsize=7, ha="center")

        # 标注抓取点
        grasp_pts = [s for s in pts if s["name"] == "grasp"]
        if grasp_pts:
            g = grasp_pts[0]["actual"]
            ax.scatter([g[0]], [g[1]], [g[2]], color="#D32F2F", s=100, marker="*", zorder=5)

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_title(f"End-Effector 3D Trajectory — Color: {self.color}")
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "trajectory_3d.png"), dpi=150)
        plt.close(fig)

    # ── 图4：关节角度 ──

    def _plot_joint_angles(self):
        if len(self.joint_snapshots) < 2:
            return

        names = [s["name"] for s in self.joint_snapshots]
        joints = np.array([s["joints"] for s in self.joint_snapshots])
        joints_deg = np.degrees(joints)

        fig, ax = plt.subplots(figsize=(11, 5))
        joint_colors = ["#1565C0", "#2E7D32", "#D32F2F", "#F57C00",
                        "#7B1FA2", "#00838F", "#546E7A"]
        for j in range(7):
            ax.plot(range(len(names)), joints_deg[:, j], "o-",
                    color=joint_colors[j], label=f"J{j+1}", markersize=4, linewidth=1.2)

        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("Joint Angle (deg)")
        ax.set_title(f"Joint Angles at Key Steps — Color: {self.color}")
        ax.legend(ncol=7, fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "joint_angles.png"), dpi=150)
        plt.close(fig)

    # ── 图5：汇总表格 ──

    def _plot_summary_table(self, result):
        fig, ax = plt.subplots(figsize=(10, 4 + len(self.steps) * 0.35))
        ax.axis("off")

        # 表头
        headers = ["Step", "Target (x,y,z)", "Actual (x,y,z)", "Error (mm)", "Time (s)", "OK"]
        rows = []
        for s in self.steps:
            t = s.get("target")
            a = s.get("actual")
            t_str = f"({t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f})" if t else "—"
            a_str = f"({a[0]:.3f}, {a[1]:.3f}, {a[2]:.3f})" if a else "—"
            e_str = f"{s['error_m']*1000:.1f}" if s.get("error_m") is not None else "—"
            ok_str = "✓" if s.get("plan_ok", True) else "✗"
            rows.append([s["name"], t_str, a_str, e_str, f"{s['duration_s']:.1f}", ok_str])

        table = ax.table(
            cellText=rows, colLabels=headers,
            cellLoc="center", loc="center",
            colColours=["#E3F2FD"] * len(headers),
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.4)

        # 标题
        total = self.phase_times.get("total_s", 0)
        det = self.detected_coords
        det_str = f"({det[0]:.3f}, {det[1]:.3f}, {det[2]:.3f})" if det else "—"
        title = (f"Trial: {self.trial_id}  |  Color: {self.color}  |  "
                 f"Detected: {det_str}  |  Total: {total:.1f}s  |  Result: {result}")
        ax.set_title(title, fontsize=10, pad=15)

        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "summary_table.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

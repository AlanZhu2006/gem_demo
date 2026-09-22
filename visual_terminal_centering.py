"""Shared RGB-only image centering for a separately labeled demo profile.

Uses robust matched-ray bearing to center the target view, not essential-matrix
rotation as a pose command. Translation/parallax can make those disagree.
No goal position, distance, depth or simulator pose enters this estimator.
"""
import math
from pathlib import Path
import sys

sys.path.insert(0, '/home/asus/Research/Nav-graph-blind')
from MemNavData.visual_yaw_refinement import estimate_visual_yaw


class VisualTerminalCentering:
    def __init__(self, goal_jpg, intrinsic, encode):
        self.goal_jpg, self.intrinsic, self.encode = goal_jpg, intrinsic, encode
        self.turns = 0
        self.last_bearing = None
        self.last_step = None
        self.streak = 0
        self.cooldown_until = -1

    def observe(self, rgb, *, step):
        estimate = estimate_visual_yaw(self.encode(rgb), self.goal_jpg, self.intrinsic)
        bearing = estimate.bearing_correction_deg
        usable = (estimate.matches >= 35 and estimate.inliers >= 30
                  and estimate.inlier_ratio >= .65
                  and estimate.off_axis_deg is not None and estimate.off_axis_deg <= 10
                  and estimate.bearing_mad_deg is not None and estimate.bearing_mad_deg <= 2
                  and bearing is not None and 3 < abs(bearing) <= 45)
        consistent = (usable and self.last_bearing is not None
                      and self.last_step == step-1 and abs(bearing-self.last_bearing) <= 10)
        self.streak = self.streak+1 if consistent else int(usable)
        self.last_bearing, self.last_step = bearing if usable else None, step
        turn = 0.
        if step >= self.cooldown_until and self.streak >= 2:
            if self.turns >= 18:
                self.turns=0;self.cooldown_until=step+16
            else:
                turn=math.radians(max(-5.,min(5.,bearing)));self.turns+=1
        if not usable:self.turns=0
        return dict(yaw_delta_rad=turn, estimate=estimate.to_dict(),
                    confidence_gate_passed=usable, consecutive_support=self.streak,
                    authority='shared_rgb_bearing_centering_demo')

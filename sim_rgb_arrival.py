"""ROS-free simulator adapter for the archived real-robot RGB arrival verifier.

Input is RGB, never BGR. Make a new gate for every arm and every goal. Call
observe before executing an action; a latched gate must stop further actions.
The visual gate is not a positioning/heading controller or a metric certificate.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

VENDOR = Path(__file__).resolve().parent / 'vendor/realworld_arrival'
sys.path.insert(0, str(VENDOR))
from rgb_goal_arrival import RgbGoalArrivalVerifier
from image_goal_io import load_rgb_image


class SimRgbArrivalGate:
    def __init__(self, target_rgb, *, arm_grace_s=0.75, **verifier_options):
        if not math.isfinite(arm_grace_s) or arm_grace_s < 0:
            raise ValueError('arm_grace_s must be finite and nonnegative')
        self.verifier = RgbGoalArrivalVerifier(target_rgb, **verifier_options)
        self.arm_grace_s = arm_grace_s
        self.started_at = None
        self.last_step = -1
        self.last_time = -math.inf
        self.arrival_latched = False
        self.latch_step = None
        self.last_result = None

    def observe(self, rgb, *, step, sim_time_s):
        if not math.isfinite(sim_time_s) or sim_time_s < 0:
            raise ValueError('invalid simulation time')
        if step <= self.last_step or sim_time_s <= self.last_time:
            raise ValueError('arrival requires a fresh, ordered observation')
        self.last_step, self.last_time = step, sim_time_s
        if self.started_at is None:
            self.started_at = sim_time_s
        armed = sim_time_s - self.started_at >= self.arm_grace_s
        if armed and not self.arrival_latched:
            self.last_result = self.verifier.evaluate(rgb)
            if self.last_result.confirmed:
                self.arrival_latched = True
                self.latch_step = step
        return dict(schema='sim_rgb_arrival_v1', step=step,
                    sim_time_s=sim_time_s, armed=armed and not self.arrival_latched,
                    arrival_latched=self.arrival_latched, latch_step=self.latch_step,
                    result=None if self.last_result is None else self.last_result.to_dict())


def provenance():
    receipt = json.loads((VENDOR / 'provenance.json').read_text())
    for name, entry in receipt.items():
        if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError(f'Archived implementation changed: {name}')
    return receipt

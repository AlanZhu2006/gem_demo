"""Run an initialized Habitat policy leg with the real-robot RGB stop gate.

Call from an initialized evaluator, separately from the formal Table II runner.
The caller owns policy servers, camera calibration, goals and simulator state.
No ROS or GPU model is required by the arrival detector itself.
"""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from sim_rgb_arrival import SimRgbArrivalGate, provenance


def run_visual_policy_leg(base, sim, pf, pos, psi, goal_jpg, goal_xz, geo_dist,
                          *, out, step_period_s, visual_centering=False,
                          arrival_options=None, **policy_options):
    if not np.isfinite(step_period_s) or step_period_s <= 0:
        raise ValueError('Supply the explicit demo seconds-per-step convention')
    if 'rgb_arrival_observer' in policy_options:
        raise ValueError('The visual demo owns its arrival observer')
    implementation = provenance()
    decoded = cv2.imdecode(np.frombuffer(goal_jpg, np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError('Invalid goal image')
    arrival_options=dict(arrival_options or {})
    gate = SimRgbArrivalGate(cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB),**arrival_options)
    if visual_centering:
        from visual_terminal_centering import VisualTerminalCentering
        controller=VisualTerminalCentering(goal_jpg, policy_options['camera_intrinsic'],base.jpg_bytes)
        policy_options['rgb_terminal_controller']=controller.observe
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'rgb').mkdir()
    (out / 'goal.jpg').write_bytes(goal_jpg)
    frames = []

    def observe(rgb, *, step):
        payload = base.jpg_bytes(rgb)
        path = out / 'rgb' / f'{step:06d}.jpg'
        path.write_bytes(payload)
        event = gate.observe(rgb, step=step, sim_time_s=step * step_period_s)
        event['rgb_sha256'] = hashlib.sha256(payload).hexdigest()
        frames.append(dict(step=step, path=str(path.resolve()),
                           sha256=event['rgb_sha256']))
        with (out / 'arrival.jsonl').open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        return event

    leg = base.run_policy_leg(sim, pf, pos, psi, goal_jpg, goal_xz, geo_dist,
                              rgb_arrival_observer=observe, **policy_options)
    # Record the actual post-action endpoint even when stuck/budget termination
    # happens after the last observation. This image does not invent a latch.
    terminal_rgb, _ = base.render(sim, np.asarray(leg['end_pos']) +
                                  np.array([0, base.CAM_H, 0]), leg['end_psi'])
    cv2.imwrite(str(out / 'terminal.png'), cv2.cvtColor(terminal_rgb, cv2.COLOR_RGB2BGR))
    leg['benchmark_distance_reached'] = leg['reached']
    leg['reached'] = bool(leg['rgb_arrival_latched'])
    leg['success_definition'] = 'realworld_rgb_visual_arrival_demo'
    leg['formal_population'] = False
    leg['shared_visual_centering'] = visual_centering
    leg['rgb_arrival_options'] = arrival_options
    leg['rgb_arrival_provenance'] = implementation
    leg['rgb_arrival_clock'] = dict(step_period_s=step_period_s,
                                    source='explicit demo convention, not measured wall time')
    (out / 'rgb_manifest.json').write_text(json.dumps(dict(frames=frames,
        terminal_rgb=str((out / 'terminal.png').resolve())), indent=2))
    def encode(value):
        if isinstance(value, np.ndarray): return value.tolist()
        if isinstance(value, np.generic): return value.item()
        raise TypeError(f'Unsupported result type: {type(value)}')
    (out / 'result.json').write_text(json.dumps(leg, indent=2, default=encode))
    return leg

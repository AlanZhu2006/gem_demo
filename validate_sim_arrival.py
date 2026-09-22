"""CPU checks for RGB latch state and the actual evaluator's stop boundary."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from sim_rgb_arrival import SimRgbArrivalGate, load_rgb_image, provenance


def main():
    provenance()
    cv2.setNumThreads(1)
    goal = load_rgb_image('outputs/table2_expansion113_rgb/goal_A.jpg')
    blank = np.zeros_like(goal)
    gate = SimRgbArrivalGate(goal, arm_grace_s=0, required_consecutive_matches=2)
    assert not gate.observe(goal, step=0, sim_time_s=0)['arrival_latched']
    assert not gate.observe(blank, step=1, sim_time_s=.1)['arrival_latched']
    assert not gate.observe(goal, step=2, sim_time_s=.2)['arrival_latched']
    assert gate.observe(goal, step=3, sim_time_s=.3)['arrival_latched']
    assert gate.observe(blank, step=4, sim_time_s=.4)['arrival_latched']
    try:
        gate.observe(goal, step=4, sim_time_s=.4)
    except ValueError:
        pass
    else:
        raise AssertionError('duplicate frame was accepted')
    fresh = SimRgbArrivalGate(goal)
    assert not fresh.observe(goal, step=0, sim_time_s=0)['arrival_latched']
    assert fresh.observe(goal, step=8, sim_time_s=.8)['arrival_latched']

    # Load only the actual function AST: importing this evaluator would parse
    # CLI flags and load Habitat. Unprovided planner/action dependencies cause
    # immediate failure if the stop boundary accidentally executes them.
    source = Path('/home/asus/Research/Nav-graph-blind/MemNavData/eval_2leg_habitat.py')
    tree = ast.parse(source.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_policy_leg')
    args = SimpleNamespace(arrival_shadow='off', success_dist=1.,
        trajectory_selector='default', trajectory_selector_scope='all',
        max_steps=0, terminal_budget=0, loop_cos_min=None,
        server_backend='rgb_imagegoal', terminal_visual_refine='off',
        cec_initial_bearing_alignment='off', certified_stagnation_graph='off')
    namespace = dict(np=np, args=args, CAM_H=.5,
        trajectory_selector_for_leg=lambda *a: 'default',
        render=lambda *a: (goal, None), jpg_bytes=lambda rgb: rgb.tobytes(),
        bytes_sha256=lambda b: hashlib.sha256(b).hexdigest())
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec'), namespace)
    run = namespace['run_policy_leg']
    gate = SimRgbArrivalGate(goal, arm_grace_s=0)
    latch = run(None, None, np.array([0., 0., 0.]), 0., b'goal', [5., 5.], 7.,
                rgb_arrival_observer=lambda rgb, step: gate.observe(rgb, step=step, sim_time_s=float(step)))
    assert latch['rgb_arrival_latched'] and latch['termination_reason'] == 'rgb_visual_arrival'
    assert latch['steps'] == 0 and latch['path_len'] == 0
    assert not latch['reached']  # visual match never overwrites GT diagnostics
    no_latch = run(None, None, np.zeros(3), 0., b'goal', [5., 5.], 7.,
                   rgb_arrival_observer=lambda rgb, step: dict(arrival_latched=False))
    assert no_latch['termination_reason'] == 'max_steps'
    assert len(no_latch['rollout_trace']) == 1 and no_latch['steps'] == 0
    legacy = run(None, None, np.zeros(3), 0., b'goal', [5., 5.], 7.)
    assert 'rgb_arrival_latched' not in legacy and legacy['rollout_trace'] == []

    # Exercise the evaluator's real post-action distance block without policy
    # dependencies: entering 1 m must stop legacy mode and continue RGB mode.
    loop = next(n for n in fn.body if isinstance(n, ast.For))
    distance = next(n for n in loop.body if isinstance(n, ast.If)
                    and ast.unparse(n.test) == 'benchmark_goal_distance(pos) < success_dist')
    probe = ast.parse('def probe():\n pass\n').body[0]
    distance_loop = ast.parse('for _ in range(1):\n pass').body[0]
    distance_loop.body = [distance]
    probe.body = [ast.parse('reached_position = True').body[0], distance_loop,
                  ast.Return(value=ast.Constant(value='continued'))]
    scope = dict(benchmark_goal_distance=lambda pos: .5, pos=np.zeros(3), success_dist=1.,
                 rgb_arrival_observer=object(), terminal_mode='off', arrival_detector=None,
                 result=lambda *a, **kw: kw['termination_reason'], step=0)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[])),
                 str(source), 'exec'), scope)
    assert scope['probe']() == 'continued'
    scope['rgb_arrival_observer'] = None
    assert scope['probe']() == 'success'
    report = dict(passed=True, checks=['consecutive reset on mismatch', 'sticky latch',
        'fresh goal state', 'arming grace', 'duplicate rejection', 'stop before any action',
        'visual success separate from distance', 'post-action budget observation',
        'legacy default unchanged at boundary', 'distance success does not stop visual mode'],
        limitation='CPU boundary checks and real RGB matching; not a closed-loop navigation trial.')
    Path('outputs/sim_arrival_validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

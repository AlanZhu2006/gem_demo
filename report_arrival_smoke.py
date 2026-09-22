"""Summarize an actual RGB-arrival smoke without relabeling visual failures."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    args = ap.parse_args()
    root = args.run / 'evaluation/visual_leg'
    result = json.loads((root / 'result.json').read_text())
    manifest = json.loads((args.run / 'manifest.json').read_text())
    events = [json.loads(x) for x in (root / 'arrival.jsonl').read_text().splitlines()]
    actions = [json.loads(x) for x in (args.run / 'evaluation/executor_actions.jsonl').read_text().splitlines()]
    goal = np.asarray(manifest['goal']['floor_position'])[[0, 2]]
    distance = [float(np.linalg.norm(np.asarray(a['actual_position'])[[0, 2]] - goal)) for a in actions]
    latched = [e for e in events if e['arrival_latched']]
    if latched:
        assert result['reached'] and result['termination_reason'] == 'rgb_visual_arrival'
        assert len(actions) == latched[0]['step'], 'An action was executed after arrival'
    else:
        assert not result['reached']
    assert len(actions) == result['steps']
    assert cv2.imread(str(root / 'terminal.png')) is not None
    best = max((e for e in events if e['result']), key=lambda e: e['result']['good_matches'])
    closest_index = int(np.argmin(distance)) if distance else None
    closest_action = None if closest_index is None else actions[closest_index]
    closest_yaw = None if closest_action is None else abs(float(np.degrees(np.arctan2(
        np.sin(closest_action['actual_yaw'] - manifest['goal']['yaw_rad']),
        np.cos(closest_action['actual_yaw'] - manifest['goal']['yaw_rad'])))))
    initial_distance = float(np.linalg.norm(np.asarray(manifest['source']['start_position'])[[0, 2]] - goal))
    first = 0 if initial_distance < 1. else next((i+1 for i, d in enumerate(distance) if d < 1.), None)
    report = dict(visual_arrival=result['reached'], termination=result['termination_reason'],
        actions=len(actions), observations=len(events), first_distance_success_action=first,
        continued_actions_after_1m=None if first is None else len(actions)-first,
        initial_distance_m=initial_distance,
        final_distance_m=result['final_goal_dist_m'], min_distance_m=min([initial_distance, *distance]),
        final_yaw_error_deg=result['post_turn_yaw_err_deg'],
        first_visual_latch_step=None if not latched else latched[0]['step'],
        closest_action=None if closest_index is None else closest_index+1,
        closest_action_yaw_error_deg=closest_yaw,
        best_match_step=best['step'], best_match=best['result'],
        checks='Action count and stop boundary verified against executor log; terminal RGB saved.',
        scope=manifest['scope'])
    (args.run / 'verified.json').write_text(json.dumps(report, indent=2))
    closest_path = root / 'rgb' / f'{closest_index+1:06d}.jpg' if closest_index is not None else root / 'terminal.png'
    if not closest_path.exists(): closest_path = root / 'terminal.png'
    panels = [('Target', root / 'goal.jpg'),
              (f'Closest: action {closest_index+1}, yaw {closest_yaw:.1f} deg' if closest_index is not None else 'Terminal', closest_path),
              (f'Best feature overlap: step {best["step"]}', root / 'rgb' / f'{best["step"]:06d}.jpg'),
              ('Actual terminal RGB', root / 'terminal.png')]
    canvas = np.full((675, 960, 3), 22, np.uint8)
    for i, (label, path) in enumerate(panels):
        rgb = cv2.imread(str(path)); assert rgb is not None
        x, y = (i % 2)*480, (i // 2)*320
        canvas[y+38:y+308, x:x+480] = cv2.resize(rgb, (480, 270))
        cv2.putText(canvas, label, (x+10, y+26), cv2.FONT_HERSHEY_SIMPLEX, .57,
                    (240, 240, 240), 1, cv2.LINE_AA)
    cv2.putText(canvas, f'Visual arrival: {result["reached"]} | {result["termination_reason"]} | '
                f'{len(actions)} actions | final {result["final_goal_dist_m"]:.3f} m / '
                f'{result["post_turn_yaw_err_deg"]:.1f} deg', (10, 663),
                cv2.FONT_HERSHEY_SIMPLEX, .56, (100, 200, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(args.run / 'comparison.jpg'), canvas)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

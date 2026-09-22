"""Evaluate real-world arrival on archived RGB; never rewrite rollout success."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import cv2
from sim_rgb_arrival import SimRgbArrivalGate, load_rgb_image, provenance


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--step-period', type=float, default=.1,
                    help='Assumed replay seconds/step; archive has no measured clock.')
    args = ap.parse_args()
    if args.step_period <= 0:
        ap.error('step-period must be positive')
    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    receipt = provenance()
    pair_path = args.source / 'paired.json'
    pair = json.loads(pair_path.read_text())
    args.out.mkdir(parents=True, exist_ok=False)
    goals = {g['stage']: g for g in pair['goals']}
    summaries = []
    for arm, data in pair['arms'].items():
        for leg in data['legs']:
            stage = leg['stage']
            gate = SimRgbArrivalGate(load_rgb_image(args.source / goals[stage]['path']))
            reasons = Counter()
            first = None
            with (args.out / f'{arm}_{stage}.jsonl').open('w') as stream:
                for row in data['frames'][leg['start']:leg['stop']]:
                    rgb = load_rgb_image(row['path'])
                    event = gate.observe(rgb, step=row['arm_step'],
                                         sim_time_s=row['leg_step'] * args.step_period)
                    event['rgb_sha256'] = row['sha256']
                    event['goal_sha256'] = goals[stage]['sha256']
                    stream.write(json.dumps(event) + '\n')
                    if not gate.arrival_latched and event['result']:
                        reasons[event['result']['reason']] += 1
                    if gate.arrival_latched and first is None:
                        first = dict(event, path=row['path'])
                        cv2.imwrite(str(args.out / f'{arm}_{stage}_latch.jpg'),
                                    cv2.cvtColor(gate.verifier.last_debug_rgb, cv2.COLOR_RGB2BGR))
            summary = dict(arm=arm, stage=stage, first_latch=first,
                           original_benchmark_reached=leg['reached'],
                           original_termination=leg['termination'],
                           frames=leg['stop']-leg['start'], rejection_counts=dict(reasons))
            summaries.append(summary)
            print(arm, stage, 'latch', gate.latch_step, dict(reasons), flush=True)
    report = dict(source=str(args.source.resolve()),
                  paired_sha256=hashlib.sha256(pair_path.read_bytes()).hexdigest(),
                  implementation=receipt, opencv=cv2.__version__,
                  mode='offline shadow replay; not a new closed-loop rollout',
                  clock=f'Assumed {args.step_period} s/step, 0.75 s arming grace; not recorded wall time.',
                  config='Archived verifier defaults; required_consecutive_matches=1; no threshold tuning.',
                  limitation='Original rollouts stop at 1 m. Later archived legs are not counterfactual continuations after a visual stop.',
                  legs=summaries)
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Isolated Table II source-A rollout with real-world RGB arrival authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path('/home/asus/Research/Nav-graph-blind')
HERE = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))


def worker():
    sys.argv.remove('worker')
    from MemNavData.run_habitat_minimal_repair_local import evaluate

    def query():
        import numpy as np
        import eval_2leg_habitat as base
        from run_sim_visual_leg import run_visual_policy_leg
        manifest = json.loads(Path(os.environ['VISUAL_ARRIVAL_MANIFEST']).read_text())
        source, goal = manifest['source'], manifest['goal']
        if base.args.contract_dry_run:
            print('VISUAL_ARRIVAL_PREFLIGHT: independent A; RGB stop; no history replay')
            return
        base.CAM_H = source['camera_height_m']
        sim = base.make_sim(source['asset'], '', agent_radius=.30)
        try:
            prefix = manifest.get('recovery_prefix', [])
            base.srv_reset(camera_height=base.CAM_H, seed=source['seed'],
                episode_len=len(prefix) + base.args.max_steps + 1,
                camera_intrinsic=np.asarray(source['camera_intrinsic']))
            for index, row in enumerate(prefix):
                frame = Path(row['path']).read_bytes()
                if hashlib.sha256(frame).hexdigest() != row['sha256']:
                    raise ValueError('Recovery prefix image changed')
                base.srv_memory(frame)
                if index % base.args.exec_horizon == 0:
                    base.srv_navdp_memory_replay(frame)
                if index % 80 == 0:
                    print('RECOVERY_RGB_PREFIX', index, '/', len(prefix), flush=True)
            leg = run_visual_policy_leg(base, sim, sim.pathfinder,
                np.asarray(source['start_position']), source['start_yaw'],
                Path(manifest['goal_image']).read_bytes(),
                np.asarray(goal['floor_position'])[[0, 2]], goal['geodesic_m'],
                out=Path(base.args.out) / 'visual_leg', step_period_s=.1,
                terminal_mode='off', goal_yaw=goal['yaw_rad'],
                camera_intrinsic=np.asarray(source['camera_intrinsic']),
                policy_backend='navdp_auto', success_dist=1.,
                episode_seed=source['seed'], leg_index=0)
            print('VISUAL_ARRIVAL_RESULT', json.dumps({k: leg[k] for k in
                ('reached', 'benchmark_distance_reached', 'termination_reason',
                 'steps', 'step_at_reach', 'final_goal_dist_m', 'post_turn_yaw_err_deg')}), flush=True)
        finally:
            sim.close()

    evaluate('role_pair', query_main=query)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--rgb-source', type=Path, required=True)
    ap.add_argument('--asset', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=19880)
    ap.add_argument('--seed', type=int, help='Explicit new-demo policy seed; never relabel as original benchmark.')
    ap.add_argument('--from-archived-endpoint', action='store_true',
                    help='Separate suffix diagnostic with archived A RGB history; not full navigation.')
    args = ap.parse_args()
    from MemNavData.run_repaired_fullmono_local import (
        private_servers, evaluator_command, execution_environment, run_child)
    from MemNavData.run_cec_stream_depth_closed_loop import open_port
    if any(open_port(p) for p in (args.port, args.port + 1)):
        raise RuntimeError('Private demo ports occupied')
    with tarfile.open(args.archive) as archive:
        source = json.load(archive.extractfile('task/source.json'))
        goal = json.load(archive.extractfile('task/A_query.json'))
    asset = args.asset.resolve()
    if hashlib.sha256(asset.read_bytes()).hexdigest() != source['asset_sha256']:
        raise ValueError('Local scene differs from archived scene')
    goal_image = (args.rgb_source / 'goal_A.jpg').resolve()
    if hashlib.sha256(goal_image.read_bytes()).hexdigest() != goal['goal_rgb_sha256']:
        raise ValueError('Goal RGB differs from archived goal')
    source['asset'] = str(asset)
    archived_seed=source['seed']
    if args.seed is not None:
        source['seed']=args.seed;goal['seed']=args.seed
    recovery_prefix = []
    if args.from_archived_endpoint:
        paired = json.loads((args.rgb_source / 'paired.json').read_text())
        leg = paired['arms']['gem']['legs'][0]
        recovery_prefix = paired['arms']['gem']['frames'][leg['start']:leg['stop']]
        source['start_position'] = leg['end_position']
        source['start_yaw'] = leg['end_yaw']
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'logs').mkdir()
    manifest = out / 'manifest.json'
    manifest.write_text(json.dumps(dict(source=source, goal=goal,
        goal_image=str(goal_image), formal_population=False,
        scope=('Archived A endpoint + RGB history suffix diagnostic; no claim of exact policy state restoration'
               if recovery_prefix else 'Independent source A visual-arrival smoke; not a Table II result'),
        recovery_prefix=recovery_prefix,
        source_archive=str(args.archive.resolve()), max_steps=600,
        archived_seed=archived_seed,
        arrival='archived real-world RGB verifier; original defaults'), indent=2))
    command = evaluator_command(source, out / 'evaluation', args.port, args.port + 1,
                                arm='cec', role='novel', benchmark=out)
    command[2:4] = [str(HERE), 'worker']
    command[command.index('--leg1_mode') + 1] = 'policy'
    environment = dict(execution_environment(), VISUAL_ARRIVAL_MANIFEST=str(manifest),
                       OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    run_child(command + ['--contract_dry_run'], out / 'logs/preflight.log', environment=environment)
    with private_servers(out, args.port, args.port + 1, memory_control=True):
        run_child(command, out / 'logs/evaluation.log', environment=environment)
    print('DONE', out, flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        worker()
    else:
        main()

"""Package newly executed paired visual-arrival legs for reconstruction/video."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    run=args.run.resolve();summary=json.loads((run/'pair_summary.json').read_text())
    protocol=json.loads((run/'protocol.json').read_text())
    if protocol.get('screening_only'):
        raise ValueError('GEM-only screening is not a paired video source; execute both arms first.')
    source=json.loads((run/'source.json').read_text())
    sequence=summary['sequence'];assert sequence==protocol['sequence']
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    goals=[]
    for entry in summary['stages']:
        if 'queries' not in entry:continue
        query=json.loads(Path(next(iter(entry['queries'].values()))).read_text())
        payload=Path(query['goal_rgb']).read_bytes();digest=hashlib.sha256(payload).hexdigest()
        assert digest==entry['goal_sha256']
        stage=entry['stage'];filename=f'goal_{stage}.jpg';(out/filename).write_bytes(payload)
        goals.append(dict(stage=stage,path=filename,sha256=digest,
                          position=query['floor_position'],yaw=query['yaw_rad']))
    arms={};checks=[]
    for alias,arm in [('gem','cec'),('base','native')]:
        frames=[];legs=[];previous=None
        for stage in 'ABC':
            directory=run/arm/'evaluation'/f'leg_{stage}'
            if not (directory/'result.json').exists():continue
            result=json.loads((directory/'result.json').read_text())
            rgb=json.loads((directory/'rgb_manifest.json').read_text())['frames']
            events=[json.loads(x) for x in (directory/'arrival.jsonl').read_text().splitlines()]
            trace=result['rollout_trace'];assert len(rgb)==len(trace)==len(events)
            if previous is not None:
                np.testing.assert_allclose([trace[0][k] for k in 'xyz'],previous['end_pos'],atol=1e-8,rtol=0)
                assert abs(trace[0]['yaw']-previous['end_psi'])<1e-8
            start=len(frames);arrival=None
            for pose,image,event in zip(trace,rgb,events):
                path=Path(image['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
                assert digest==pose['jpg_sha256']==event['rgb_sha256']==image['sha256']
                step=len(frames)
                frames.append(dict(key=step,arm=alias,leg=stage,arm_step=step,
                    leg_step=pose['step'],path=str(path),timestamp_ns=step*100_000_000,
                    gt_camera=[pose['x'],pose['y']+source['camera_height_m'],pose['z']],
                    gt_yaw=pose['yaw'],sha256=digest,arrival_latched=event['arrival_latched']))
                if event['arrival_latched'] and arrival is None:arrival=step
            assert bool(result['reached'])==(arrival is not None)
            if arrival is not None:
                assert arrival==len(frames)-1 and result['steps']==trace[-1]['step']
                assert result['termination_reason']=='rgb_visual_arrival'
            legs.append(dict(stage=stage,start=start,stop=len(frames),reached=result['reached'],
                steps=result['steps'],observations=len(trace),path_m=result['path_len'],
                arrival_step=arrival,termination=result['termination_reason'],
                end_position=result['end_pos'],end_yaw=result['end_psi'],
                endpoint_note='Visual success includes the actual post-action arrival frame.',
                final_goal_dist_m=result['final_goal_dist_m'],
                final_yaw_error_deg=result['post_turn_yaw_err_deg']))
            checks.append(dict(arm=alias,stage=stage,hashes_verified=len(trace),
                               continuity_verified=previous is not None,arrival_step=arrival))
            previous=result
        assert frames
        arms[alias]=dict(frames=frames,legs=legs)
        manifest=dict(scene=source['scene'],sequence=sequence,frames=frames,
            camera_height_m=source['camera_height_m'],
            ordering='Original continuous forward RGB from new visual-arrival demo.',
            clock='Synthetic observation index * 0.1 s; display labels steps, not real wall time.')
        (out/f'manifest_forward_{alias}.json').write_text(json.dumps(manifest,indent=2))
    assert arms['gem']['frames'][0]['sha256']==arms['base']['frames'][0]['sha256']
    pair=dict(scene=source['scene'],source=source,sequence=sequence,task_index='visual_demo',
        success_definition='rgb_visual_arrival',formal_population=False,
        shared_visual_centering=protocol.get('shared_visual_centering',False),
        novel_max_route_angle_deg=protocol.get('novel_max_route_angle_deg',60),
        goal_view_variant=protocol.get('goal_view_variant'),
        arrival_profile=protocol.get('arrival_profile','realworld'),
        arrival_options=protocol.get('arrival_options',{}),
        proposal_options=protocol.get('proposal_options',{}),
        planning_seeds=protocol.get('planning_seeds'),
        history_depth_source=protocol.get('history_depth_source','see_construction_receipts'),
        run=str(run),arms=arms,goals=goals,checks=checks)
    (out/'paired.json').write_text(json.dumps(pair,indent=2))
    (out/'pair_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({a:dict(frames=len(v['frames']),legs=v['legs']) for a,v in arms.items()},indent=2))


if __name__=='__main__':main()

"""Check completed video timing/counts and export four actual decoded frames."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video',type=Path,required=True)
    ap.add_argument('--require-gem-three-visual',action='store_true')
    ap.add_argument('--require-sequence',choices=['NNN','NNR','NRN','NRR'])
    args=ap.parse_args()
    audit=json.loads(args.video.with_suffix('.audit.json').read_text())
    source=Path(audit['source']);pair=json.loads((source/'paired.json').read_text())
    if args.require_sequence:
        assert pair['sequence']==audit['sequence']==args.require_sequence
    if args.require_gem_three_visual:
        assert pair.get('success_definition')=='rgb_visual_arrival'
        assert [l['stage'] for l in pair['arms']['gem']['legs']]==list('ABC')
        assert all(l['reached'] and l.get('arrival_step') is not None for l in pair['arms']['gem']['legs'])
    root=Path(audit['reconstruction']);meta=json.loads((root/'reconstruction.json').read_text())
    manifest=json.loads(Path(meta['source_manifest']).read_text());lookup={r['key']:r for r in manifest['frames']}
    steps={a:[] for a in pair['arms']}
    for row in meta['frames']:
        if row['warming']:continue
        r=lookup[row['key']]
        if r['arm']=='context':continue
        steps[r['arm']].append(r['arm_step'])
        if r.get('also_arm'):steps[r['also_arm']].append(r['arm_step'])
    steps={a:np.array(v) for a,v in steps.items()}
    last=-1;last_fused=0;local_plan_frames={a:0 for a in pair['arms']}
    for row in audit['frames']:
        assert row['source_step']>=last;last=row['source_step']
        expected=0
        for a,data in pair['arms'].items():
            step=min(row['source_step'],len(data['frames'])-1)
            assert row['arm_step'][a]==step
            expected+=int((steps[a]<=step).sum())
        assert row['shown_frames']==expected,(row,expected)
        for a,plan in row.get('local_plans',{}).items():
            now=row['arm_step'][a];at=plan['plan_step']
            assert 0<=now-at<=30
            assert pair['arms'][a]['frames'][at]['leg']==pair['arms'][a]['frames'][now]['leg']
            assert abs(plan['ground_height_m']-.02)<1e-6
            local_plan_frames[a]+=1
        if audit.get('cloud_mode')=='tsdf':
            assert row['fused_frames']>=last_fused
            last_fused=row['fused_frames']
            for a,step in row['latest_fused_step'].items():
                assert step<=row['arm_step'][a],('Future observation in fused cloud',row)
                assert step==-1 or step%audit['cloud_fusion']['source_step_stride']==0
    if audit.get('cloud_mode')=='tsdf':
        assert last_fused==audit['cloud_fusion']['integrated_frames']>0
    if audit.get('local_trajectory'):
        assert all(n>0 for n in local_plan_frames.values())
    arrival_checks=[]
    if pair.get('success_definition')=='rgb_visual_arrival':
        shown_steps={f['source_step'] for f in audit['frames']}
        for arm,data in pair['arms'].items():
            for leg in data['legs']:
                at=leg.get('arrival_step')
                assert (at is not None)==bool(leg['reached'])
                if at is not None:
                    assert at in shown_steps
                    assert data['frames'][at]['arrival_latched']
                    event_frames=[f['video_frame'] for f in audit['frames'] if f['source_step']==at]
                    assert len(event_frames)>=int(audit.get('arrival_hold_s',0)*audit['fps'])+1
                    if audit.get('arrival_hold_s')==0 and at<audit.get('baseline_tail_start_step',float('inf')):
                        assert len(event_frames)<=int(np.ceil(audit['fps']/audit['steps_per_second']))
                    arrival_checks.append(dict(arm=arm,stage=leg['stage'],source_step=at,
                                               video_frame=event_frames[0],hold_frames=len(event_frames)))
    c=cv2.VideoCapture(str(args.video));n=int(c.get(cv2.CAP_PROP_FRAME_COUNT));fps=c.get(cv2.CAP_PROP_FPS)
    assert n==len(audit['frames'])
    assert abs(fps-audit['fps'])<1e-6
    sample=[0,int(.5*n),int(.85*n),n-1]
    events=sorted({r['video_frame'] for r in arrival_checks})
    wanted=set(sample+events);decoded={};count=0;shape=None
    while True:
        ok,frame=c.read()
        if not ok:break
        shape=frame.shape
        if count in wanted:decoded[count]=cv2.resize(frame,(960,540))
        count+=1
    c.release()
    assert count==n,(count,n)
    images=[decoded[i] for i in sample]
    cv2.imwrite(str(args.video.with_suffix('.jpg')),np.vstack([np.hstack(images[:2]),np.hstack(images[2:])]))
    if events:
        cv2.imwrite(str(args.video.with_suffix('.arrivals.jpg')),np.vstack([decoded[i] for i in events]))
    report=dict(video=str(args.video.resolve()),frames=n,fps=fps,duration_seconds=n/fps,
        sequence=pair['sequence'],baseline_tail_seconds=audit.get('baseline_tail_seconds',0),
        arrival_hold_s=audit.get('arrival_hold_s',0),end_hold_s=audit.get('end_hold_s',3),
        baseline_tail_speed=audit.get('baseline_tail_speed',1),
        all_frames_decoded=count,resolution=[shape[1],shape[0]],
        visibility_counts_verified=True,monotonic_step_clock=True,sampled_decoded_frames=sample,
        cloud_mode=audit.get('cloud_mode','raw'),
        fusion_clock_verified=audit.get('cloud_mode')=='tsdf',
        local_trajectory_frames_verified=local_plan_frames,
        final_arm_steps=audit['frames'][-1]['arm_step'],
        visual_arrivals_verified=arrival_checks,
        final_leg_results={a:[dict(stage=l['stage'],reached=l['reached'],termination=l['termination'])
                            for l in data['legs']] for a,data in pair['arms'].items()})
    args.video.with_suffix('.verified.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()

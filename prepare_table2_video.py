"""Recover paired RGB/GT by recorded SHA256, without replaying the simulator."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--prime-reverse-start', action='store_true',
                    help='Prepend a moving recorded Baseline suffix before reversing; offline context only.')
    ap.add_argument('--share-prefix', action='store_true',
                    help='Reconstruct verified identical prefix once, then traverse each branch continuously.')
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'images').mkdir()
    records, blobs = {}, {}
    with tarfile.open(args.archive) as archive:
        for member in archive:
            if not member.isfile():
                continue
            if member.name.endswith('.json'):
                records[member.name] = json.load(archive.extractfile(member))
            elif member.name.endswith(('.jpg', '.png', '.jpeg')):
                blob = archive.extractfile(member).read()
                digest = hashlib.sha256(blob).hexdigest()
                blobs.setdefault(digest, (blob, member.name))
    source = records['task/source.json']
    summary = records['task/pair_summary.json']
    arms, goals = {}, []
    for stage in summary['stages']:
        if 'goal_sha256' not in stage:
            continue
        digest = stage['goal_sha256']
        matches = [v for k,v in records.items() if 'query' in k and isinstance(v,dict)
                   and v.get('goal_rgb_sha256') == digest]
        q = matches[0]
        blob, member = blobs[digest]
        filename = f'goal_{stage["stage"]}.jpg'
        (out/filename).write_bytes(blob)
        goals.append(dict(stage=stage['stage'], sha256=digest, path=filename,
                          position=q['floor_position'], yaw=q['yaw_rad'], archive_member=member))
    checks = []
    for arm, alias in [('cec','gem'), ('native','base')]:
        frames, legs = [], []
        previous_end = None
        for stage in 'ABC':
            name = f'task/{arm}/evaluation/leg_{stage}/actual_trace.json'
            if name not in records:
                continue
            trace = records[name]
            poses = trace['poses']
            first = np.array([poses[0][k] for k in 'xyz'])
            if previous_end is not None:
                error = float(np.linalg.norm(first-previous_end))
                assert error < 1e-6, (arm,stage,error)
                checks.append(dict(arm=arm,stage=stage,endpoint_continuity_error_m=error))
            offset = len(frames)
            for pose in poses:
                digest = pose['jpg_sha256']
                blob, member = blobs[digest]  # missing RGB is a hard failure
                dest = out/'images'/f'{digest}.jpg'
                if not dest.exists():
                    dest.write_bytes(blob)
                camera = [pose['x'],pose['y']+source['camera_height_m'],pose['z']]
                step = len(frames)
                frames.append(dict(key=step,arm=alias,leg=stage,arm_step=step,leg_step=pose['step'],
                    path=str(dest),timestamp_ns=step*100_000_000,
                    gt_camera=camera,gt_yaw=pose['yaw'],sha256=digest,archive_member=member))
            legs.append(dict(stage=stage,start=offset,stop=len(frames),reached=trace['reached'],
                steps=trace['steps'],path_m=trace['path_len'],termination=trace['termination_reason'],
                end_position=trace['end_position'],end_yaw=trace['end_yaw'],
                endpoint_note='Last saved RGB precedes final executed action; no invented endpoint image.'))
            previous_end = np.array(trace['end_position'])
        arms[alias] = dict(frames=frames,legs=legs)
    a,b=arms['base']['frames'][0],arms['gem']['frames'][0]
    assert a['sha256']==b['sha256']
    joint = list(reversed(arms['base']['frames'])) + arms['gem']['frames']
    joint = [dict(row,key=i) for i,row in enumerate(joint)]
    manifest = dict(scene=source['scene'],frames=joint,
        clock='synthetic arm step * 0.1 seconds; display uses steps, not measured wall time',
        ordering='Baseline reversed, then GEM forward; offline shared reconstruction',
        seam_index=len(arms['base']['frames']),camera_height_m=source['camera_height_m'],
        source_archive=str(args.archive.resolve()),sequence=summary['sequence'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if args.share_prefix:
        gem,base=arms['gem']['frames'],arms['base']['frames']
        common=0
        for a,b in zip(gem,base):
            if a['sha256']!=b['sha256']:
                break
            np.testing.assert_allclose(a['gt_camera'],b['gt_camera'],atol=1e-7,rtol=0)
            assert abs(a['gt_yaw']-b['gt_yaw'])<1e-7
            common+=1
        if common<8:
            raise ValueError('Insufficient identical prefix for shared initialization.')
        branch=base[common:]
        seq=[dict(r,also_arm='base') for r in gem[:common]]+branch
        seq += [dict(r,arm='context') for r in reversed(branch)]+gem[common:]
        shared=dict(manifest,frames=[dict(r,key=i) for i,r in enumerate(seq)],
            shared_prefix_frames=common,context_frames=len(branch),seam_index=common+2*len(branch),
            ordering='Identical RGB/GT prefix once, Baseline branch forward, reverse branch context, GEM branch forward; offline visualization')
        (out/'manifest_shared.json').write_text(json.dumps(shared,indent=2))
    if args.prime_reverse_start:
        base=arms['base']['frames']
        positions=np.array([r['gt_camera'] for r in base])
        eligible=[i for i in range(len(base)-8)
                  if np.linalg.norm(np.diff(positions[i:i+8],axis=0),axis=1).sum()>.12]
        if not eligible:
            raise ValueError('No moving 8-frame suffix for reverse-start initialization.')
        primer=[dict(r,arm='context',context_for='reverse-start initialization') for r in base[max(eligible):]]
        warm=dict(manifest,frames=[dict(r,key=i) for i,r in enumerate(primer+joint)],
            context_frames=len(primer),seam_index=manifest['seam_index']+len(primer),
            ordering='Forward Baseline suffix for initialization, Baseline reversed, then GEM forward; offline visualization',
            initialization_note='Recorded moving suffix; context excluded from displayed geometry and tracks. Selection uses GT only for offline preparation.')
        (out/'manifest_warmstart.json').write_text(json.dumps(warm,indent=2))
    metadata = dict(scene=source['scene'],source=source,sequence=summary['sequence'],
        task_index=summary['task_index'],arms=arms,goals=goals,continuity_checks=checks,
        identical_start_image=True,all_frame_hashes_verified=True,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest())
    (out/'paired.json').write_text(json.dumps(metadata,indent=2))
    (out/'pair_summary.json').write_text(json.dumps(summary,indent=2))
    for arm in ('gem','base'):
        forward=dict(scene=source['scene'],sequence=summary['sequence'],frames=arms[arm]['frames'],
            camera_height_m=source['camera_height_m'],
            ordering='Original forward observations of '+arm+'; same initialization and keyframe policy for both arms',
            clock='synthetic step * 0.1 seconds; display labeled in steps')
        (out/f'manifest_forward_{arm}.json').write_text(json.dumps(forward,indent=2))
    panels=[]
    for alias in ['gem','base']:
        row=arms[alias]['frames']; cells=[]
        for i in np.linspace(0,len(row)-1,6).astype(int):
            cell=cv2.resize(cv2.imread(row[i]['path']),(320,180))
            cv2.putText(cell,f'{alias} {row[i]["leg"]} step {i}',(7,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
            cells.append(cell)
        panels.append(np.hstack(cells))
    cv2.imwrite(str(out/'source_contact.jpg'),np.vstack(panels))
    print(json.dumps(dict(scene=source['scene'],sequence=summary['sequence'],
        frame_counts={k:len(v['frames']) for k,v in arms.items()},joint_frames=len(joint),
        legs={k:v['legs'] for k,v in arms.items()},hashes_verified=True),indent=2))


if __name__ == '__main__':
    main()

"""Validate a single joint LingBot frame against simulation GT; no pose warping."""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    meta=json.loads((args.input/'reconstruction.json').read_text())
    manifest=json.loads(Path(meta['source_manifest']).read_text())
    lookup={r['key']:r for r in manifest['frames']}
    C,G,arms,keys=[],[],[],[]
    for row in meta['frames']:
        info=lookup[row['key']]
        if row['warming'] or info['arm']=='context':continue
        with np.load(args.input/row['prediction']) as p:center=p['c2w'][:,3].copy()
        for arm in [info['arm']]+([info['also_arm']] if info.get('also_arm') else []):
            C.append(center);G.append(info['gt_camera']);arms.append(arm);keys.append(row['key'])
    C,G=np.array(C),np.array(G); arms=np.array(arms)
    X,Y=G-G.mean(0),C-C.mean(0)
    U,D,Vt=np.linalg.svd(Y.T@X/len(X));S=np.eye(3);S[-1,-1]=np.linalg.det(U@Vt)
    R=U@S@Vt;s=float(np.sum(D*np.diag(S))/np.mean(np.sum(X*X,axis=1)))
    t=C.mean(0)-s*R@G.mean(0)
    residual=np.linalg.norm(G@(s*R).T+t-C,axis=1)/s
    n=-R[:,1]
    foot=G.copy();foot[:,1]-=manifest['camera_height_m']
    d=float(np.median((foot@(s*R).T+t)@n))
    bystep={a:{lookup[k]['arm_step']:c for k,c,arm in zip(keys,C,arms) if arm==a} for a in ['gem','base']}
    paired=json.loads((Path(meta['source_manifest']).parent/'paired.json').read_text())
    ga,ba=paired['arms']['gem']['frames'],paired['arms']['base']['frames']
    common=[i for i in range(min(len(ga),len(ba))) if ga[i]['sha256']==ba[i]['sha256'] and i in bystep['gem'] and i in bystep['base']]
    disagreement=np.array([np.linalg.norm(bystep['gem'][i]-bystep['base'][i])/s for i in common])
    branch_steps={}
    split=manifest.get('shared_prefix_frames',0)
    if split:
        for arm in ['gem','base']:
            if split-1 in bystep[arm] and split in bystep[arm]:
                actual=paired['arms'][arm]['frames']
                branch_steps[arm]=dict(source_step=split,
                    inferred_translation_m=float(np.linalg.norm(bystep[arm][split]-bystep[arm][split-1])/s),
                    gt_translation_m=float(np.linalg.norm(np.array(actual[split]['gt_camera'])-actual[split-1]['gt_camera'])))
    out=dict(root=str(args.input.resolve()),manifest=meta['source_manifest'],scale=s,R=R.tolist(),t=t.tolist(),
        floor_n=n.tolist(),floor_d=d,mount_h=manifest['camera_height_m'],
        gt_fit_rmse_m=float(np.sqrt(np.mean(residual**2))),gt_fit_p95_m=float(np.percentile(residual,95)),
        arm_rmse_m={a:float(np.sqrt(np.mean(residual[arms==a]**2))) for a in ['gem','base']},
        identical_image_pairs=len(common),identical_image_position_rmse_m=float(np.sqrt(np.mean(disagreement**2))),
        identical_image_position_p95_m=float(np.percentile(disagreement,95)),
        coordinate_policy='One GT-to-LingBot similarity for scale, up, floor and goals only; raw c2w and depths remain unchanged.',
        inference_order=manifest['ordering'],context_frames=manifest.get('context_frames',0),
        shared_prefix_frames=manifest.get('shared_prefix_frames',0),
        branch_steps=branch_steps,
        identical_image_note='Shared prefix poses are identical by construction when shared_prefix_frames > 0; not an independent accuracy test.')
    args.out.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))


if __name__=='__main__':main()

"""Merge two forward reconstructions only after verifying their common frame.

No alignment transform or trajectory corrections are applied. Identical input
prefix must yield identical camera matrices and depth (within float tolerance).
"""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--gem',type=Path,required=True)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    source=args.source.resolve();pair=json.loads((source/'paired.json').read_text())
    roots={'gem':args.gem.resolve(),'base':args.base.resolve()}
    metas={a:json.loads((root/'reconstruction.json').read_text()) for a,root in roots.items()}
    assert metas['gem']['config']==metas['base']['config'],'Different inference settings'
    inputs={a:pair['arms'][a]['frames'] for a in roots}
    input_checks={}
    for arm,meta in metas.items():
        recorded=json.loads(Path(meta['source_manifest']).read_text())['frames']
        assert len(recorded)==len(inputs[arm]),'Reconstruction/source frame count differs'
        for original,actual in zip(recorded,inputs[arm]):
            assert original['key']==actual['key']
            assert original['sha256']==actual['sha256'],'Reconstruction used different RGB'
            assert original['timestamp_ns']==actual['timestamp_ns']
        input_checks[arm]=dict(manifest=meta['source_manifest'],verified_rgb_frames=len(recorded))
    common=0
    for a,b in zip(inputs['gem'],inputs['base']):
        if a['sha256']!=b['sha256']:break
        np.testing.assert_allclose(a['gt_camera'],b['gt_camera'],atol=1e-7,rtol=0)
        assert abs(a['gt_yaw']-b['gt_yaw'])<1e-7
        common+=1
    bykey={a:{r['key']:r for r in meta['frames']} for a,meta in metas.items()}
    pose_error=0.;depth_error=0.;checked=0
    for i in range(common):
        ga,ba=bykey['gem'][i],bykey['base'][i]
        assert ga['warming']==ba['warming']
        if ga['warming']:continue
        with np.load(roots['gem']/ga['prediction']) as g,np.load(roots['base']/ba['prediction']) as b:
            pose_error=max(pose_error,float(np.max(np.abs(g['c2w']-b['c2w']))))
            depth_error=max(depth_error,float(np.max(np.abs(g['depth']-b['depth']))))
        checked+=1
    if pose_error>1e-5 or depth_error>1e-4:
        raise ValueError(f'Common-frame parity failed: pose={pose_error}, depth={depth_error}')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'frames').mkdir()
    manifest_rows=[];saved_rows=[]
    for arm in ['gem','base']:
        for row in metas[arm]['frames']:
            if arm=='base' and row['key']<common:continue
            original=inputs[arm][row['key']]
            info=dict(original,key=len(manifest_rows))
            if arm=='gem' and row['key']<common:info['also_arm']='base'
            manifest_rows.append(info)
            record=dict(row,key=info['key'])
            if not row['warming']:
                name=f'frames/{info["key"]:06d}.npz'
                (out/name).symlink_to(roots[arm]/row['prediction'])
                record['prediction']=name
            saved_rows.append(record)
    parity=dict(input_prefix_frames=common,checked_predictions=checked,
        input_manifest_checks=input_checks,
        max_abs_c2w_difference=pose_error,max_abs_depth_difference=depth_error,
        transforms_applied=0,source_reconstructions={a:str(root) for a,root in roots.items()})
    manifest=dict(scene=pair['scene'],sequence=pair['sequence'],frames=manifest_rows,
        camera_height_m=pair['source']['camera_height_m'],context_frames=0,shared_prefix_frames=common,
        ordering='Two original forward streams with identical prefix, identical inference settings and verified prefix outputs; no reverse frames or cross-arm observations in inference.',
        parity=parity)
    target=source/'manifest_forward_merged.json';target.write_text(json.dumps(manifest,indent=2))
    meta=dict(metas['gem'],source_manifest=str(target),frames=saved_rows,
        mode='Shared initial coordinate frame, independently forward causal branch inference',parity=parity)
    (out/'reconstruction.json').write_text(json.dumps(meta,indent=2))
    (out/'prefix_parity.json').write_text(json.dumps(parity,indent=2));print(json.dumps(parity,indent=2))


if __name__=='__main__':main()

"""Resolve pose direction using independently tracked image correspondences.

No trajectory fitting or geometric optimization: compare the two SE(3)
interpretations by reprojection through saved depth and K. Optionally export
a separate corrected dataset, retaining original predictions.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def invert(T):
    H = np.eye(4); H[:3, :4] = T[:3, :4]
    return np.linalg.inv(H)[:3].astype(np.float32)


def main(args):
    root = Path(args.input)
    meta = json.loads((root/'reconstruction.json').read_text())
    rows = [r for r in meta['frames'] if not r['warming']]
    pairs = []
    for i in range(0, len(rows)-args.gap, args.stride):
        with np.load(root/rows[i]['prediction']) as a, np.load(root/rows[i+args.gap]['prediction']) as b:
            ga = cv2.cvtColor(a['rgb'], cv2.COLOR_RGB2GRAY)
            gb = cv2.cvtColor(b['rgb'], cv2.COLOR_RGB2GRAY)
            p = cv2.goodFeaturesToTrack(ga, 500, .01, 8)
            if p is None:
                continue
            q, status, _ = cv2.calcOpticalFlowPyrLK(ga, gb, p, None)
            back, status2, _ = cv2.calcOpticalFlowPyrLK(gb, ga, q, None)
            ok = (status[:, 0]>0) & (status2[:, 0]>0) & (np.linalg.norm(back[:, 0]-p[:, 0], axis=1)<1)
            p, q = p[:, 0][ok], q[:, 0][ok]
            uv = np.rint(p).astype(int)
            ok = (uv[:, 0]>=0) & (uv[:, 0]<ga.shape[1]) & (uv[:, 1]>=0) & (uv[:, 1]<ga.shape[0])
            p, q, uv = p[ok], q[ok], uv[ok]
            z = a['depth'][uv[:, 1], uv[:, 0]]
            ok = np.isfinite(z) & (z>0)
            p, q, z = p[ok], q[ok], z[ok]
            if len(p)<20:
                continue
            camera = (np.c_[p, np.ones(len(p))] @ np.linalg.inv(a['K']).T)*z[:, None]
            record = dict(first_key=rows[i]['key'], second_key=rows[i+args.gap]['key'], tracks=len(p),
                          observed_flow_px=float(np.median(np.linalg.norm(p-q, axis=1))))
            for name in ('saved', 'inverted'):
                A = np.eye(4); A[:3] = a['c2w']
                B = np.eye(4); B[:3] = b['c2w']
                if name == 'inverted':
                    A, B = np.linalg.inv(A), np.linalg.inv(B)
                relative = np.linalg.inv(B)@A
                pc = camera @ relative[:3, :3].T + relative[:3, 3]
                predicted = pc @ b['K'].T
                visible = predicted[:, 2]>1e-6
                residual = np.full(len(p), np.inf)
                residual[visible] = np.linalg.norm(predicted[visible, :2]/predicted[visible, 2, None]-q[visible], axis=1)
                record[name+'_reprojection_px'] = float(np.median(residual))
            pairs.append(record)
    if not pairs:
        raise SystemExit('No usable tracked frame pairs.')
    report = dict(input=str(root.resolve()), frame_gap=args.gap, sample_stride=args.stride,
                  pair_count=len(pairs), method='Forward/backward LK tracks (<1px cycle error); median reprojection per pair',
                  saved_median_px=float(np.median([p['saved_reprojection_px'] for p in pairs])),
                  inverted_median_px=float(np.median([p['inverted_reprojection_px'] for p in pairs])), pairs=pairs)
    if args.official:
        off = Path(args.official)
        first_key = meta['frames'][0]['key']
        errors = []
        for row in rows:
            with np.load(off/f'frame_{row["key"]-first_key:06d}.npz') as ref, np.load(root/row['prediction']) as p:
                errors.append([np.max(np.abs(ref['depth'].squeeze()-p['depth'])),
                               np.max(np.abs(ref['extrinsic'].squeeze()-p['c2w'])),
                               np.max(np.abs(ref['intrinsic'].squeeze()-p['K']))])
        report['official_comparison'] = dict(frames=len(errors),
                    max_abs_error=dict(zip(('depth', 'extrinsic', 'intrinsic'), np.max(errors, axis=0).astype(float))),
                    meaning='Agreement with official exported arrays does not independently validate their pose convention.')
    (root/'pose_convention_audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='pairs'}, indent=2))
    if args.export_inverted:
        if report['inverted_median_px'] >= report['saved_median_px']*.5:
            raise SystemExit('Inversion lacks strong reprojection evidence; refusing export.')
        out = Path(args.export_inverted)
        out.mkdir(parents=True, exist_ok=False)
        (out/'frames').mkdir()
        for row in rows:
            with np.load(root/row['prediction']) as p:
                arrays = dict(p)
            arrays['wrapper_c2w'] = arrays['c2w'].copy()
            arrays['c2w'] = invert(arrays['c2w'])
            np.savez_compressed(out/row['prediction'], **arrays)
        meta.update(pose_convention='OpenCV c2w verified by image reprojection; inverse of legacy wrapper export',
                    pose_adapter='raw-c2w', corrected_from=str(root.resolve()),
                    pose_convention_audit=str((root/'pose_convention_audit.json').resolve()))
        (out/'reconstruction.json').write_text(json.dumps(meta, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--gap', type=int, default=5)
    ap.add_argument('--stride', type=int, default=15)
    ap.add_argument('--official', help='Official batch_demo per-frame NPZ directory for the same input window.')
    ap.add_argument('--export-inverted', help='Fresh output directory; no inference or pose optimization.')
    main(ap.parse_args())

"""Check saved streaming predictions against the backbone's batch streaming path."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def main(args):
    root = Path(args.input)
    meta = json.loads((root/'reconstruction.json').read_text())
    source = Path(meta['source_manifest']).parent
    rows = meta['frames'][:args.frames]
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'AnchorScale'))
    from anchorscale.backbone.lingbot import LingBotBackbone, LingBotConfig
    bb = LingBotBackbone(LingBotConfig(**meta['config']))
    reference = bb.reconstruct([str(source/r['path']) for r in rows])
    errors = []
    for i, row in enumerate(rows):
        if row['warming']:
            continue
        with np.load(root/row['prediction']) as p:
            depth = reference.depth[i]
            valid = np.isfinite(depth) & (depth > 0) & np.isfinite(p['depth'])
            relative = np.median(np.abs(p['depth'][valid]-depth[valid])/depth[valid])
            A, B = reference.extrinsic_c2w[i], p['c2w']
            if meta.get('pose_adapter') == 'raw-c2w':
                homogeneous = np.eye(4); homogeneous[:3] = A
                A = np.linalg.inv(homogeneous)[:3]
            delta = A[:3, :3] @ B[:3, :3].T
            angle = np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2, -1, 1)))
            trans = np.linalg.norm(A[:3, 3]-B[:3, 3])
            errors.append(dict(key=row['key'], depth_absrel=float(relative),
                               translation_model_units=float(trans), rotation_deg=float(angle)))
    passed = bool(errors) and all(e['depth_absrel'] < .01 and e['rotation_deg'] < .5 and
                                 e['translation_model_units'] < .01 for e in errors)
    report = dict(passed=passed, compared_frames=len(errors), errors=errors,
                  scope='streaming implementation parity only; not global geometry or metric accuracy')
    (root/'parity_validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--frames', type=int, default=24)
    main(ap.parse_args())

"""Run demo.main unchanged through inference; capture its actual viewer geometry.

Replaces only the viewer constructor to avoid opening a network server. The
original viewer's _process_pred_dict still computes geometry for sampled frames.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np


def main():
    repo = Path('/home/asus/Research/lingbot-map')
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', type=Path, default=root/'outputs/cec_090850_translation_pose_verified')
    ap.add_argument('--out', type=Path, default=root/'outputs/demo_entrypoint_audit')
    ap.add_argument('--export', action='store_true', help='Save timestamped predictions for incremental playback.')
    ap.add_argument('--backend', choices=['sdpa', 'flashinfer'], default='sdpa')
    ap.add_argument('--keyframe-interval', type=int, default=None)
    args = ap.parse_args()
    reference = args.reference.resolve()
    meta = json.loads((reference/'reconstruction.json').read_text())
    source = Path(meta['source_manifest']).parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.export:
        (out/'frames').mkdir()
    sys.path.insert(0, str(repo))
    import demo
    import lingbot_map.vis as vis
    from lingbot_map.utils.geometry import closed_form_inverse_se3
    Viewer = vis.PointCloudViewer

    class CaptureViewer:
        def __init__(self, pred_dict, **kwargs):
            data = pred_dict
            camera = closed_form_inverse_se3(data['extrinsic'])[:, :3]
            errors, geometry = [], []
            for i, row in enumerate(meta['frames']):
                if row['warming']:
                    continue
                with np.load(reference/row['prediction']) as p:
                    d = data['depth'][i].squeeze()
                    valid = np.isfinite(d) & (d>0) & (p['depth']>0)
                    errors.append(dict(key=row['key'], depth_absrel=float(np.median(np.abs(d[valid]-p['depth'][valid])/p['depth'][valid])),
                        c2w_max_abs=float(np.max(np.abs(camera[i]-p['c2w'])))))
                    # Compare exact official viewer projection against our formula
                    # using identical inputs, independent of bf16-weight effects.
                    if i % 20 == 0:
                        one = {k:v[i:i+1] for k,v in data.items() if isinstance(v,np.ndarray) and v.shape[0]==len(meta['frames'])}
                        viewer = Viewer.__new__(Viewer)
                        pcs, _, _, cams = Viewer._process_pred_dict(viewer, one, False, False, None)
                        v,u = np.mgrid[:d.shape[0],:d.shape[1]]
                        rays = np.stack((u,v,np.ones_like(u)), axis=-1)@np.linalg.inv(data['intrinsic'][i]).T
                        expected = (rays*d[...,None])@camera[i,:3,:3].T+camera[i,:3,3]
                        geometry.append(float(np.max(np.abs(pcs[0]-expected))))
                    if args.export:
                        conf = data['depth_conf'][i].squeeze()
                        K = data['intrinsic'][i]
                        rgb = np.rint(data['images'][i].transpose(1,2,0)*255).clip(0,255).astype(np.uint8)
                        valid = np.isfinite(d) & (d>0) & np.isfinite(conf)
                        threshold = np.percentile(conf[valid], meta['confidence_percentile']) if valid.any() else np.inf
                        sample = np.zeros_like(valid)
                        sample[::meta['pixel_stride'], ::meta['pixel_stride']] = True
                        v,u = np.nonzero(valid & sample & (conf>=threshold))
                        points = (np.column_stack((u,v,np.ones(len(u))))@np.linalg.inv(K).T)*d[v,u,None]
                        name = f'frames/{row["key"]:06d}.npz'
                        np.savez_compressed(out/name, depth=d, conf=conf, K=K, c2w=camera[i],
                            rgb=rgb, local_points=points.astype(np.float32), point_rgb=rgb[v,u],
                            timestamp_ns=np.int64(row['timestamp_ns']))
                        row.update(prediction=name, points=len(points), conf_threshold=float(threshold))
                if i % 100 == 0:
                    print(f'Compared/exported {i+1}/{len(meta["frames"])}', flush=True)
            np.savez_compressed(out/'demo_camera_depth_sample.npz', c2w=camera,
                                depth=data['depth'][::20], intrinsic=data['intrinsic'][::20])
            report = dict(entrypoint=str(repo/'demo.py'), input_frames=len(meta['frames']),
                execution='demo.main with original model loading, precision conversion, inference and postprocess; only server launch replaced',
                dtype_policy='demo.py casts aggregator to bf16; heads fp32; bf16 autocast',
                compared_with=str(reference), compared_frames=len(errors),
                depth_absrel_median=float(np.median([e['depth_absrel'] for e in errors])),
                depth_absrel_max=float(max(e['depth_absrel'] for e in errors)),
                c2w_max_abs=float(max(e['c2w_max_abs'] for e in errors)),
                viewer_geometry_max_abs=float(max(geometry)),
                sampled_viewer_frames=len(geometry), backend=args.backend,
                keyframe_interval=args.keyframe_interval or (len(meta['frames'])+319)//320, errors=errors)
            if args.export:
                for stale in ('corrected_from', 'pose_convention_audit'):
                    meta.pop(stale, None)
                meta.update(pose_convention='OpenCV c2w matching original demo viewer',
                            pose_adapter='official-viewer', mode='official demo.py streaming; timestamped replay',
                            entrypoint=str(repo/'demo.py'))
                meta['config'].update(keyframe_interval=report['keyframe_interval'],
                    use_sdpa=args.backend=='sdpa', max_frame_num=1024, aggregator_dtype='bfloat16')
                for row in meta['frames']:
                    row.pop('inference_seconds', None)
                (out/'reconstruction.json').write_text(json.dumps(meta, indent=2))
            (out/'report.json').write_text(json.dumps(report, indent=2))
            print(json.dumps({k:v for k,v in report.items() if k!='errors'},indent=2))

        def run(self):
            pass

    vis.PointCloudViewer = CaptureViewer
    with tempfile.TemporaryDirectory(prefix='lingbot-demo-input-') as tmp:
        folder = Path(tmp)
        for i,row in enumerate(meta['frames']):
            (folder/f'{i:06d}.png').symlink_to(source/row['path'])
        sys.argv = ['demo.py', '--image_folder', str(folder), '--model_path',
                    str(repo/'weights/lingbot-map-long.pt'), '--offload_to_cpu']
        if args.backend == 'sdpa':
            sys.argv.append('--use_sdpa')
        if args.keyframe_interval is not None:
            sys.argv.extend(['--keyframe_interval', str(args.keyframe_interval)])
        demo.main()


if __name__ == '__main__':
    main()

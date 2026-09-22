"""Run the official demo.py on an RGB manifest and export timestamped frames.

`audit_demo_entrypoint.py` needs an existing reconstruction to borrow timestamps
and to compare against, so it cannot start a new scene.  This entry point reads
only the RGB manifest, which is what a fresh run has.

Inference is untouched: demo.main does the model loading, precision conversion,
streaming and postprocess; only the viewer constructor -- which would launch a
web server -- is replaced by an exporter.  Camera poses follow the original
viewer convention (see lingbot_deployment.md 2.1).
"""
import argparse, json, sys, tempfile
from pathlib import Path

import numpy as np

REPO = Path('/home/asus/Research/lingbot-map')
WARMING = 7          # frames before the first emitted prediction, as in cec_090850


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, required=True, help='RGB manifest.json')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--backend', choices=['sdpa', 'flashinfer'], default='flashinfer')
    ap.add_argument('--keyframe-interval', type=int, default=None,
                    help='omit to let demo.py choose ceil(N/320)')
    ap.add_argument('--conf-percentile', type=float, default=65)
    ap.add_argument('--pixel-stride', type=int, default=4)
    ap.add_argument('--max-frame-num', type=int, default=1024)
    args = ap.parse_args()

    manifest = args.manifest.resolve()
    src = json.loads(manifest.read_text())
    rows = src['frames']
    source_dir = manifest.parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'frames').mkdir()

    sys.path.insert(0, str(REPO))
    import demo
    import lingbot_map.vis as vis
    from lingbot_map.utils.geometry import closed_form_inverse_se3

    meta_frames = [dict(key=r['key'], path=r['path'], timestamp_ns=r['timestamp_ns'],
                        sensor_timestamp_ns=r.get('sensor_timestamp_ns'),
                        warming=r['key'] < WARMING) for r in rows]

    class CaptureViewer:
        def __init__(self, pred_dict, **kwargs):
            data = pred_dict
            camera = closed_form_inverse_se3(data['extrinsic'])[:, :3]
            kept = 0
            for i, row in enumerate(meta_frames):
                if row['warming']:
                    continue
                d = data['depth'][i].squeeze()
                conf = data['depth_conf'][i].squeeze()
                K = data['intrinsic'][i]
                rgb = np.rint(data['images'][i].transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8)
                valid = np.isfinite(d) & (d > 0) & np.isfinite(conf)
                thr = np.percentile(conf[valid], args.conf_percentile) if valid.any() else np.inf
                sample = np.zeros_like(valid)
                sample[::args.pixel_stride, ::args.pixel_stride] = True
                v, u = np.nonzero(valid & sample & (conf >= thr))
                pts = (np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T) * d[v, u, None]
                name = f'frames/{row["key"]:06d}.npz'
                np.savez_compressed(out / name, depth=d, conf=conf, K=K, c2w=camera[i],
                                    rgb=rgb, local_points=pts.astype(np.float32),
                                    point_rgb=rgb[v, u],
                                    timestamp_ns=np.int64(row['timestamp_ns']))
                row.update(prediction=name, points=len(pts), conf_threshold=float(thr))
                kept += 1
                if kept % 100 == 0:
                    print(f'Exported {kept}', flush=True)
            meta = dict(source_manifest=str(manifest),
                        units='LingBot model units (not metres)',
                        pose_convention='OpenCV c2w matching original demo viewer',
                        pose_adapter='official-viewer',
                        mode='official demo.py streaming; timestamped replay',
                        entrypoint=str(REPO / 'demo.py'), scale=1.0,
                        confidence_percentile=args.conf_percentile,
                        pixel_stride=args.pixel_stride,
                        config=dict(weights=str(REPO / 'weights/lingbot-map-long.pt'),
                                    image_size=518, patch_size=14, enable_3d_rope=True,
                                    max_frame_num=args.max_frame_num, num_scale_frames=8,
                                    kv_cache_sliding_window=64, camera_num_iterations=4,
                                    use_sdpa=args.backend == 'sdpa',
                                    keyframe_interval=args.keyframe_interval
                                                      or (len(rows) + 319) // 320,
                                    aggregator_dtype='bfloat16', offload_to_cpu=True),
                        frames=meta_frames)
            (out / 'reconstruction.json').write_text(json.dumps(meta, indent=2))
            print(f'Exported {kept} frames -> {out}')

        def run(self):
            pass

    vis.PointCloudViewer = CaptureViewer
    with tempfile.TemporaryDirectory(prefix='lingbot-manifest-') as tmp:
        folder = Path(tmp)
        for i, row in enumerate(rows):
            (folder / f'{i:06d}.png').symlink_to(source_dir / row['path'])
        sys.argv = ['demo.py', '--image_folder', str(folder), '--model_path',
                    str(REPO / 'weights/lingbot-map-long.pt'), '--offload_to_cpu',
                    '--max_frame_num', str(args.max_frame_num)]
        if args.backend == 'sdpa':
            sys.argv.append('--use_sdpa')
        if args.keyframe_interval is not None:
            sys.argv += ['--keyframe_interval', str(args.keyframe_interval)]
        demo.main()


if __name__ == '__main__':
    main()

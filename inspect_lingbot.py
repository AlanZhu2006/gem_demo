"""Independent trajectory comparison against recorded Go2 telemetry (not GT)."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def similarity_fit(X, Y):
    x, y = X-X.mean(0), Y-Y.mean(0)
    U, singular, Vt = np.linalg.svd(x.T@y)
    D = np.eye(3); D[-1, -1] = np.linalg.det(U@Vt)
    rotation = U@D@Vt
    scale = float((singular*np.diag(D)).sum()/(x*x).sum())
    return (X-X.mean(0))@rotation*scale+Y.mean(0), scale


def main(args):
    root = Path(args.input)
    meta = json.loads((root/'reconstruction.json').read_text())
    source = Path(meta['source_manifest']).parent
    rows = [r for r in meta['frames'] if not r['warming']]
    points, colors, keys, poses = [], [], [], []
    for row in rows:
        with np.load(root/row['prediction']) as p:
            T = p['c2w']
            poses.append(T)
            points.append(p['local_points'] @ T[:3, :3].T + T[:3, 3])
            colors.append(p['point_rgb'])
            keys.append(np.full(len(points[-1]), row['key'], np.uint32))
    cloud = np.concatenate(points)
    rgb = np.concatenate(colors)
    vertices = np.empty(len(cloud), dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
                         ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'), ('frame_key', '<u4')])
    for j, axis in enumerate(('x', 'y', 'z')):
        vertices[axis] = cloud[:, j]
    for j, channel in enumerate(('red', 'green', 'blue')):
        vertices[channel] = rgb[:, j]
    vertices['frame_key'] = np.concatenate(keys)
    with (root/'cloud_raw.ply').open('wb') as f:
        f.write(('ply\nformat binary_little_endian 1.0\ncomment LingBot raw model units, OpenCV world\n'
                 f'element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n'
                 'property uchar red\nproperty uchar green\nproperty uchar blue\n'
                 'property uint frame_key\nend_header\n').encode())
        vertices.tofile(f)
    poses = np.asarray(poses)
    centers = poses[:, :3, 3]
    tel = np.load(source/'telemetry_reference.npy')
    ts = np.array([r['timestamp_ns'] for r in rows], np.int64)
    valid_time = (ts >= tel[0, 0]) & (ts <= tel[-1, 0])
    ref = np.column_stack([np.interp(ts, tel[:, 0], tel[:, j]) for j in (1, 2, 3)])
    # Fit a single similarity for diagnostic comparison, not a map correction.
    X, Y = centers[valid_time], ref[valid_time]
    x, y = X-X.mean(0), Y-Y.mean(0)
    U, singular, Vt = np.linalg.svd(x.T@y)
    D = np.eye(3); D[-1, -1] = np.linalg.det(U@Vt)
    rotation = U@D@Vt
    scale = float((singular*np.diag(D)).sum()/(x*x).sum())
    aligned = (centers-X.mean(0))@rotation*scale+Y.mean(0)
    err = np.linalg.norm(aligned-ref, axis=1)
    seconds = (ts-ts[0])/1e9
    source_start = json.loads((source/'manifest.json').read_text())['frames'][0]['timestamp_ns']
    motion = []
    for start in np.arange(0, (ts[-1]-source_start)/1e9, 5):
        sel = tel[((tel[:, 0]-source_start)/1e9 >= start) & ((tel[:, 0]-source_start)/1e9 < start+5)]
        if len(sel) < 2:
            continue
        motion.append(dict(start_seconds=float(start),
                           xy_travel_m=float(np.linalg.norm(np.diff(sel[:, 1:3], axis=0), axis=1).sum()),
                           net_yaw_deg=float(np.degrees(np.unwrap(sel[:, 6])[-1]-sel[0, 6]))))
    report = dict(source_window_start_seconds=float((ts[0]-source_start)/1e9),
                  output_frames=len(rows), cloud_samples=len(cloud),
                  finite_cloud=bool(np.isfinite(cloud).all()),
                  diagnostic_sim3_scale=scale, comparison_frames=int(valid_time.sum()),
                  position_rmse_m=float(np.sqrt(np.mean(err[valid_time]**2))),
                  reference_travel_m=float(np.linalg.norm(np.diff(ref, axis=0), axis=1).sum()),
                  raw_model_travel=float(np.linalg.norm(np.diff(centers, axis=0), axis=1).sum()),
                  limitations='Go2 body odometry is not GT; camera/body lever arm is not calibrated. '
                              'Sim3 uses all compared timestamps for diagnosis only, not rendering or metric calibration.',
                  source_motion_5s=motion)
    if args.compare_input:
        other = Path(args.compare_input)
        other_meta = json.loads((other/'reconstruction.json').read_text())
        if other_meta['source_manifest'] != meta['source_manifest']:
            raise ValueError('Matched-window comparison requires the same source manifest.')
        by_key = {r['key']: r for r in other_meta['frames'] if not r['warming']}
        common = np.array([i for i, r in enumerate(rows) if r['key'] in by_key and valid_time[i]])
        if len(common) < 3:
            raise ValueError('Insufficient common frames.')
        other_centers = []
        for i in common:
            with np.load(other/by_key[rows[i]['key']]['prediction']) as p:
                other_centers.append(p['c2w'][:3, 3])
        target = ref[common]
        own_fit, _ = similarity_fit(centers[common], target)
        other_fit, _ = similarity_fit(np.asarray(other_centers), target)
        report['matched_window_comparison'] = dict(
            other_input=str(other.resolve()), common_frames=len(common),
            this_rmse_m=float(np.sqrt(np.mean(np.sum((own_fit-target)**2, axis=1)))),
            other_rmse_m=float(np.sqrt(np.mean(np.sum((other_fit-target)**2, axis=1)))),
            method='Independent best-fit Sim(3) on identical timestamps; reference is body odometry, not GT')
    (root/'trajectory_diagnostic.json').write_text(json.dumps(report, indent=2))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(ref[:, 0], ref[:, 1], color='black', label='Go2 body odometry (reference)')
    axes[0].plot(aligned[:, 0], aligned[:, 1], color='tab:blue', label='LingBot camera, diagnostic Sim(3)')
    axes[0].set_aspect('equal'); axes[0].set_xlabel('x (reference m)'); axes[0].set_ylabel('y (reference m)')
    axes[0].legend(fontsize=8)
    axes[1].plot(seconds[valid_time], err[valid_time], color='tab:blue')
    axes[1].set_xlabel('Seconds after first prediction'); axes[1].set_ylabel('Position discrepancy (m)')
    axes[1].set_title(f'RMSE {report["position_rmse_m"]:.2f} m; not a GT accuracy score')
    for ax in axes:
        ax.grid(alpha=.25)
    fig.suptitle('Independent trajectory check — no corrections applied to the cloud')
    fig.tight_layout(); fig.savefig(root/'trajectory_diagnostic.png', dpi=150); plt.close(fig)
    print(json.dumps({k: v for k, v in report.items() if k != 'source_motion_5s'}, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--compare-input', help='Another session over the same source for matched-window comparison.')
    main(ap.parse_args())

"""Render timestamp-causal cloud growth with a fixed oblique 3D camera.

The full sequence determines framing only. Geometry is added after its actual
source timestamp, including the 8-frame startup latency. No future pose updates.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np


def floor_frame(pred):
    """One startup floor estimate, for a fixed rigid display transform only."""
    depth, K, conf = pred['depth'], pred['K'], pred['conf']
    v, u = np.mgrid[:depth.shape[0]:3, :depth.shape[1]:3]
    z = depth[::3, ::3]
    finite = np.isfinite(conf)
    threshold = np.percentile(conf[finite], 55)
    mask = (v > depth.shape[0]*.55) & np.isfinite(z) & (z > 0) & (conf[::3, ::3] >= threshold)
    P = np.column_stack((u[mask], v[mask], np.ones(mask.sum()))) @ np.linalg.inv(K).T
    P *= z[mask, None]
    rng = np.random.default_rng(0)
    best = None
    if len(P) >= 100:
        tol = np.median(np.linalg.norm(P, axis=1))*.015
        for _ in range(200):
            a, b, c = P[rng.choice(len(P), 3, replace=False)]
            normal = np.cross(b-a, c-a)
            normal /= max(np.linalg.norm(normal), 1e-9)
            if normal[1] < 0:
                normal = -normal
            if normal[1] < .7:
                continue
            inliers = np.abs((P-a) @ normal) < tol
            if best is None or inliers.sum() > best.sum():
                best = inliers
        if best is not None and best.sum() > max(100, .3*len(P)):
            Q = P[best]
            normal = np.linalg.svd(Q-Q.mean(0), full_matrices=False)[2][-1]
            if normal[1] < 0:
                normal = -normal
            c2w = pred['c2w']
            up = -(c2w[:3, :3] @ normal)
            forward = c2w[:3, 2].copy()
            forward -= up * (forward @ up)
            forward /= np.linalg.norm(forward)
            right = np.cross(forward, up)
            R = np.stack((right, forward, up))
            origin = Q.mean(0) @ c2w[:3, :3].T + c2w[:3, 3]
            return R, origin, dict(method='first output frame floor RANSAC; one rigid display transform',
                                   support=int(best.sum()), candidates=len(P),
                                   plane_rms_model_units=float(np.std(Q @ normal)))
    return np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0.]]), np.zeros(3), dict(method='camera-up fallback; no floor detected')


def main(args):
    root = Path(args.input)
    meta = json.loads((root/'reconstruction.json').read_text())
    source = Path(meta['source_manifest'])
    original_start = json.loads(source.read_text())['frames'][0]['timestamp_ns']
    records = meta['frames']
    usable = [r for r in records if not r['warming']]
    if not usable:
        raise SystemExit('No predictions to display.')
    with np.load(root/usable[0]['prediction']) as pred:
        R, origin, floor = floor_frame(pred)
    # Fixed oblique projection in the display frame (right, forward, up).
    az, elev = np.radians(args.azimuth), np.radians(args.elevation)
    direction = np.array([np.cos(elev)*np.cos(az), np.cos(elev)*np.sin(az), np.sin(elev)])
    right = np.array([-np.sin(az), np.cos(az), 0.])
    up = np.cross(direction, right)
    basis = np.stack((right, up, direction))
    bounds, centers = [], []
    for r in usable:
        with np.load(root/r['prediction']) as p:
            T = p['c2w']
            X = p['local_points'] @ T[:3, :3].T + T[:3, 3]
            world = (X-origin) @ R.T
            bounds.append((world[::10] @ basis.T)[:, :2])
            centers.append((T[:3, 3]-origin) @ R.T)
    centers = np.array(centers)
    B = np.concatenate(bounds)
    lo, hi = np.percentile(B, [.5, 99.5], axis=0)
    cp = centers @ basis.T
    lo = np.minimum(lo, cp[:, :2].min(0)); hi = np.maximum(hi, cp[:, :2].max(0))
    mid = (lo+hi)/2
    width, height = 1280, 720
    left, top, mapw, maph = 440, 90, 820, 570
    scale = min(mapw/max(hi[0]-lo[0], 1e-6), maph/max(hi[1]-lo[1], 1e-6))*.92

    def project(points):
        q = points @ basis.T
        uv = np.column_stack(((q[:, 0]-mid[0])*scale + mapw/2,
                              -(q[:, 1]-mid[1])*scale + maph/2))
        return np.rint(uv).astype(int), q[:, 2]

    zbuffer = np.full(mapw*maph, -np.inf)
    raster = np.zeros((maph*mapw, 3), np.uint8)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit('Output exists; choose a new file.')
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                           '-s', f'{width}x{height}', '-r', str(args.fps), '-i', '-',
                           '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', str(output)], stdin=subprocess.PIPE)
    start = records[0]['timestamp_ns']
    stop = records[-1]['timestamp_ns']
    duration = (stop-start)/1e9
    times = np.array([r['timestamp_ns'] for r in records], np.int64)
    nframes = int(np.ceil(duration/args.speed*args.fps))+1
    pending = 0
    point_count = 0
    audits, snapshots = [], {}
    sample_frames = {int(round(frac*(nframes-1))) for frac in (0, .25, .5, 1)}
    try:
        for fi in range(nframes):
            t = min(stop, start+int(fi/args.fps*args.speed*1e9))
            while pending < len(usable) and usable[pending]['timestamp_ns'] <= t:
                row = usable[pending]
                with np.load(root/row['prediction']) as pred:
                    T = pred['c2w']
                    P = ((pred['local_points'] @ T[:3, :3].T + T[:3, 3])-origin) @ R.T
                    uv, zz = project(P)
                    colors = pred['point_rgb'][:, ::-1]
                    # Small screen-space splats; nearest visible sample wins.
                    for dx, dy in ((0, 0), (1, 0), (0, 1)):
                        u, v = uv[:, 0]+dx, uv[:, 1]+dy
                        valid = (u >= 0) & (u < mapw) & (v >= 0) & (v < maph)
                        ids = np.flatnonzero(valid)
                        ids = ids[np.argsort(-zz[ids], kind='stable')]
                        pix = v[ids]*mapw+u[ids]
                        _, first = np.unique(pix, return_index=True)
                        ids, pix = ids[first], pix[first]
                        closer = zz[ids] > zbuffer[pix]
                        zbuffer[pix[closer]] = zz[ids[closer]]
                        raster[pix[closer]] = colors[ids[closer]]
                    point_count += len(P)
                pending += 1
            frame = np.full((height, width, 3), (18, 15, 13), np.uint8)
            frame[top:top+maph, left:left+mapw] = raster.reshape(maph, mapw, 3)
            i = max(0, int(np.searchsorted(times, t, side='right')-1))
            rgb = cv2.imread(str(source.parent/records[i]['path']))
            thumb = cv2.resize(rgb, (400, round(rgb.shape[0]*400/rgb.shape[1])))
            frame[120:120+len(thumb), 20:420] = thumb
            def label(text, x, y, size=.6, col=(220, 220, 220)):
                cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, col, 1, cv2.LINE_AA)
            label('LingBot-Map | RGB-only incremental reconstruction', 20, 38, .85)
            label('GEM run 2026-09-19 09:08:50 UTC', 20, 75, .58)
            label('Onboard RGB', 20, 105)
            label(f'Source time: {(t-start)/1e9:.2f} / {duration:.2f} s', 20, 410)
            label(f'Input frames: {i+1} / {len(records)}', 20, 442)
            label(f'Cloud frames: {pending}', 20, 474)
            label(f'Accepted samples: {point_count:,}', 20, 506)
            label(f'{args.speed:g}x playback | persistent KV cache', 20, 554, .55)
            label('Scale: model units (not metres)', 20, 586, .53)
            label('Raw poses; no loop correction', 20, 618, .53)
            label(f'Source window starts at +{(start-original_start)/1e9:.2f} s', 20, 650, .53)
            label('Fixed oblique 3D view | RGB colors', left, 75)
            label('Framing uses full sequence; cloud visibility follows timestamps.', left, 690, .5)
            if pending:
                path, _ = project(centers[:pending])
                path += np.array([left, top])
                cv2.polylines(frame, [path.astype(np.int32)], False, (255, 160, 70), 2, cv2.LINE_AA)
                cv2.circle(frame, tuple(path[-1]), 5, (255, 210, 130), -1, cv2.LINE_AA)
            else:
                label('Priming 8-frame scale anchor...', left+170, top+maph//2)
            max_t = usable[pending-1]['timestamp_ns'] if pending else None
            assert max_t is None or max_t <= t
            audits.append(dict(video_frame=fi, source_timestamp_ns=t, cloud_frames=pending,
                               accepted_points=point_count, latest_geometry_timestamp_ns=max_t))
            if fi in sample_frames:
                snapshots[fi] = frame.copy()
            ff.stdin.write(frame.tobytes())
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError('ffmpeg failed')
    finally:
        if ff.poll() is None:
            ff.terminate()
            ff.wait()
    panels = [cv2.resize(snapshots[k], (640, 360)) for k in sorted(snapshots)]
    cv2.imwrite(str(output.with_suffix('.jpg')), np.vstack((np.hstack(panels[:2]), np.hstack(panels[2:]))))
    report = dict(reconstruction=str(root.resolve()), floor_display=floor, units=meta['units'],
                  display_rotation=R.tolist(), display_origin=origin.tolist(),
                  causal_visibility_pass=all(a['latest_geometry_timestamp_ns'] is None or
                      a['latest_geometry_timestamp_ns'] <= a['source_timestamp_ns'] for a in audits),
                  full_sequence_used_for='fixed camera bounds only', frames=audits)
    output.with_suffix('.audit.json').write_text(json.dumps(report, indent=2))
    print(f'Rendered {output}; {len(audits)} frames, {pending} cloud chunks; causal visibility PASS')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=15)
    ap.add_argument('--speed', type=float, default=2)
    ap.add_argument('--azimuth', type=float, default=-65)
    ap.add_argument('--elevation', type=float, default=55)
    main(ap.parse_args())

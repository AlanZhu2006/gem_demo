"""Offline RGB replay through a persistent LingBot session; timestamped 3D chunks.

Run with the lingbot-map Python. No sensor depth or telemetry enters reconstruction.
Raw model coordinates are preserved. No metric scale or loop closure is implied.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def extract(args):
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'manifest.json').exists():
        raise SystemExit('Output already contains a manifest; use a new output directory.')
    rgb_dir = out / 'rgb'
    rgb_dir.mkdir(exist_ok=True)
    color = '/camera/camera/color/image_raw'
    cmd = '/navdp/cmd_vel'
    telem = '/navdp/go2/telemetry/sport_state'
    with AnyReader([Path(args.bag)], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as reader:
        motion, tel = [], []
        for con, t, raw in reader.messages(connections=[c for c in reader.connections if c.topic in (cmd, telem)]):
            msg = reader.deserialize(raw, con.msgtype)
            if con.topic == cmd:
                if abs(msg.linear.x) > .02 or abs(msg.linear.y) > .02 or abs(msg.angular.z) > .02:
                    motion.append(t)
            else:
                data = json.loads(msg.data)
                sf = data.get('sdk_fields') or {}
                p, r = sf.get('position'), (sf.get('imu_state') or {}).get('rpy')
                if p and r:
                    tel.append([data.get('received_ros_ns') or t, *p, *r])
        if not motion:
            raise SystemExit('No motion commands; select a revisit bag with /navdp/cmd_vel.')
        start = motion[0] - int(args.preroll * 1e9)
        stop = motion[-1] + 1
        rows = []
        for con, t, raw in reader.messages(connections=[c for c in reader.connections if c.topic == color], start=start, stop=stop):
            msg = reader.deserialize(raw, con.msgtype)
            if msg.encoding not in ('rgb8', 'bgr8'):
                raise ValueError(f'Unsupported RGB encoding: {msg.encoding}')
            buf = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)
            rgb = buf[:, :msg.width * 3].reshape(msg.height, msg.width, 3)
            bgr = rgb[..., ::-1] if msg.encoding == 'rgb8' else rgb
            key = len(rows)
            name = f'rgb/{key:06d}.png'
            if not cv2.imwrite(str(out / name), bgr):
                raise IOError(name)
            stamp = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
            rows.append(dict(key=key, path=name, timestamp_ns=int(t), sensor_timestamp_ns=int(stamp)))
            if args.max_frames and len(rows) >= args.max_frames:
                break
    if not rows:
        raise SystemExit('No RGB frames in motion interval.')
    np.save(out / 'telemetry_reference.npy', np.asarray(tel))
    manifest = dict(bag=str(Path(args.bag).resolve()), clock='ROS bag log timestamp, integer ns',
                    motion_start_ns=motion[0], motion_end_ns=motion[-1], frames=rows,
                    reconstruction_inputs='RGB only; telemetry saved for independent comparison')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Extracted {len(rows)} RGB frames, {(rows[-1]["timestamp_ns"]-rows[0]["timestamp_ns"])/1e9:.2f}s -> {out}', flush=True)


def reconstruct(args):
    root = Path(args.input)
    manifest = json.loads((root / 'manifest.json').read_text())
    first_ns = manifest['frames'][0]['timestamp_ns']
    rows = [r for r in manifest['frames'] if r['timestamp_ns'] >= first_ns+int(args.start_seconds*1e9)]
    rows = rows[:args.max_frames or None]
    if len(rows) < 8:
        raise SystemExit('At least 8 input frames are required for priming.')
    out = Path(args.out)
    if out.exists():
        raise SystemExit('Use a new reconstruction output directory to preserve provenance.')
    out.mkdir(parents=True)
    (out / 'frames').mkdir()
    sys.path.insert(0, str(Path(args.anchor).resolve()))
    sys.path.insert(0, str(Path(args.session_dir).resolve()))
    from anchorscale.backbone.lingbot import LingBotBackbone, LingBotConfig
    from streaming_session import StreamingSession
    cfg = LingBotConfig(use_sdpa=True, kv_cache_sliding_window=args.kv_window,
                        keyframe_interval=1, max_frame_num=max(1024, len(rows)+64), student_ckpt='')
    sess = StreamingSession(LingBotBackbone(cfg))
    records = []
    for index, row in enumerate(rows):
        rgb = cv2.cvtColor(cv2.imread(str(root / row['path'])), cv2.COLOR_BGR2RGB)
        begin = time.perf_counter()
        pred = sess.push(rgb)
        elapsed = time.perf_counter() - begin
        record = dict(row, inference_seconds=elapsed, warming=bool(pred.get('warming')))
        if not pred.get('warming'):
            # Exact same resize/crop as inference, including portrait inputs.
            aligned, _ = sess._preprocess(rgb)
            colors = np.rint(aligned[0].permute(1, 2, 0).cpu().numpy()*255).astype(np.uint8)
            depth, conf, K = pred['depth'], pred['conf'], pred['K']
            valid = np.isfinite(depth) & (depth > 0) & np.isfinite(conf)
            threshold = np.percentile(conf[valid], args.conf_percentile) if valid.any() else np.inf
            mask = valid & (conf >= threshold)
            sampled = np.zeros_like(mask)
            sampled[::args.pixel_stride, ::args.pixel_stride] = True
            v, u = np.nonzero(mask & sampled)
            rays = np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T
            points = rays * depth[v, u, None]
            name = f'frames/{row["key"]:06d}.npz'
            camera_pose = pred['c2w']
            if args.pose_convention == 'raw-c2w':
                # This checkpoint's raw decoded pose is c2w, as independently
                # verified by image reprojection. Undo the legacy wrapper inversion.
                homogeneous = np.eye(4)
                homogeneous[:3] = camera_pose
                camera_pose = np.linalg.inv(homogeneous)[:3].astype(np.float32)
            np.savez_compressed(out / name, depth=depth, conf=conf, K=K, c2w=camera_pose,
                                wrapper_c2w=pred['c2w'],
                                rgb=colors, local_points=points.astype(np.float32), point_rgb=colors[v, u],
                                timestamp_ns=np.int64(row['timestamp_ns']))
            record.update(prediction=name, points=len(points), conf_threshold=float(threshold))
        records.append(record)
        if index % 25 == 0:
            print(f'{index+1}/{len(rows)} frame, {elapsed:.3f}s, warming={record["warming"]}', flush=True)
    meta = dict(source_manifest=str((root/'manifest.json').resolve()), units='LingBot model units (not metres)',
                pose_convention='OpenCV c2w', pose_adapter=args.pose_convention,
                mode='persistent causal KV streaming; no pose optimization',
                scale=1.0, start_seconds=args.start_seconds,
                confidence_percentile=args.conf_percentile, pixel_stride=args.pixel_stride,
                config=vars(cfg), frames=records)
    (out / 'reconstruction.json').write_text(json.dumps(meta, indent=2))
    print(f'Saved {sum(not r["warming"] for r in records)} timestamped predictions -> {out}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    ex = sub.add_parser('extract')
    ex.add_argument('--bag', required=True)
    ex.add_argument('--out', required=True)
    ex.add_argument('--preroll', type=float, default=1.0)
    ex.add_argument('--max-frames', type=int, default=0)
    ex.set_defaults(func=extract)
    re = sub.add_parser('reconstruct')
    re.add_argument('--input', required=True)
    re.add_argument('--out', required=True)
    re.add_argument('--max-frames', type=int, default=0)
    re.add_argument('--start-seconds', type=float, default=0, help='Explicit source-window offset; starts a fresh session.')
    re.add_argument('--pose-convention', choices=('raw-c2w', 'wrapper-c2w'), required=True,
                    help='Explicit checkpoint convention. Current long checkpoint: raw-c2w, verified by reprojection.')
    re.add_argument('--anchor', default=str(Path(__file__).resolve().parent.parent/'AnchorScale'))
    re.add_argument('--session-dir', default=str(Path(__file__).resolve().parent.parent/'go2_mono_nav/perception_server'))
    re.add_argument('--kv-window', type=int, default=64)
    re.add_argument('--conf-percentile', type=float, default=65)
    re.add_argument('--pixel-stride', type=int, default=4)
    re.set_defaults(func=reconstruct)
    args = ap.parse_args()
    args.func(args)

"""Line a phone clip up against the robot clock by cross-correlating motion.

EXIF creation_time gets within a couple of seconds, but the phone and the Go2
keep separate clocks, so the offset is measured rather than assumed: frame-to
-frame image change in the clip against the robot's own speed from telemetry.
"""
import sys, json, subprocess
import numpy as np

mov, tag, t_exif = sys.argv[1], sys.argv[2], float(sys.argv[3])
FPS, W, H = 10, 160, 284

raw = subprocess.run(
    ['ffmpeg', '-v', 'error', '-i', mov, '-vf', f'fps={FPS},scale={W}:{H},format=gray',
     '-f', 'rawvideo', '-'], capture_output=True).stdout
V = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
mot = np.r_[0.0, np.abs(np.diff(V, axis=0)).mean(axis=(1, 2))]
vt = t_exif + np.arange(len(mot)) / FPS

T = np.load(f'demo_{tag}/tel.npy')
w = json.load(open(f'demo_{tag}/win.json'))
gr = np.arange(T[0, 0], T[-1, 0], 1.0 / FPS)
x = np.interp(gr, T[:, 0], T[:, 1]); y = np.interp(gr, T[:, 0], T[:, 2])
yw = np.degrees(np.interp(gr, T[:, 0], np.unwrap(T[:, 6])))
n = FPS // 2
spd = np.zeros_like(gr)
spd[n:] = np.hypot(x[n:] - x[:-n], y[n:] - y[:-n]) / (n / FPS) + \
          np.abs(yw[n:] - yw[:-n]) / (n / FPS) / 60.0

z = lambda a: (a - a.mean()) / (a.std() + 1e-9)
best = (-9, 0.0)
for off in np.arange(-25, 25, 0.1):
    s = np.interp(vt + off, gr, spd, left=np.nan, right=np.nan)
    m = ~np.isnan(s)
    if m.sum() < len(mot) * 0.5: continue
    c = float(np.mean(z(s[m]) * z(mot[m])))
    if c > best[0]: best = (c, off)
c, off = best
print(f"{tag}: EXIF 起点 {t_exif:.1f}, 最佳偏移 {off:+.2f}s, 相关 {c:.3f}")
print(f"  -> 视频 t=0 对应机器人时刻 {t_exif + off:.2f} (指令窗口起点 {w['t0']:.2f}, "
      f"即视频 {w['t0'] - (t_exif + off):+.1f}s 处)")
json.dump(dict(t_video0=t_exif + off, corr=c, exif=t_exif, off=off),
          open(f'sync_{tag}.json', 'w'))

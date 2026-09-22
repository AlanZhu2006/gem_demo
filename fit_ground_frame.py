"""Put the Go2 odometry and the LingBot reconstruction into one frame, and find
the floor plane inside the LingBot cloud.

Two things the trajectory overlay needs and the reconstruction does not provide:

*  A similarity odometry -> LingBot.  GEM's run exists in both frames (body
   odometry, and the LingBot camera track), so Umeyama on the shared timestamps
   fits it.  Baseline shares the same odometry frame -- same session, robot not
   rebooted -- so the same transform carries it in.
*  A floor plane.  Fitting the cloud failed before; the camera track is the
   better cue, since the robot walks at a fixed height over a flat floor.  The
   plane through the camera centres is parallel to the floor, and the measured
   mount height, scaled into model units, drops it onto the floor.
"""
import glob, json
import numpy as np

S = '/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad'
EXP = 'outputs/cec_090850_demo_flashinfer/frames'

fs = sorted(glob.glob(f'{EXP}/*.npz'))
C, T, Rc = [], [], []
for f in fs:
    d = np.load(f)
    c2w = d['c2w']
    C.append(c2w[:, 3]); Rc.append(c2w[:, :3]); T.append(int(d['timestamp_ns']))
C = np.array(C); Rc = np.array(Rc); T = np.array(T, np.int64)
print(f"LingBot 相机轨迹 {len(C)} 帧, 时间 {T[0]} .. {T[-1]}")

# --- does the LingBot run correspond to the scratchpad alias n_cec1?
tel = np.load(f'{S}/n_cec1.npz')['tel']
w = json.load(open(f'{S}/demo_n_cec1/win.json'))
ts_s = T / 1e9
print(f"重建时间范围 {ts_s[0]:.2f}..{ts_s[-1]:.2f}  n_cec1 遥测范围 "
      f"{tel[0,0]:.2f}..{tel[-1,0]:.2f}  指令窗口 {w['t0']:.2f}..{w['t1']:.2f}")
inside = ((ts_s >= tel[0, 0]) & (ts_s <= tel[-1, 0])).mean()
print(f"重建时间戳落在 n_cec1 遥测区间内的比例: {inside*100:.1f}%  -> "
      f"{'同一场次' if inside > 0.99 else '不匹配'}")

# --- Umeyama: odometry (metres) -> LingBot (model units)
def odom_at(tag, t):
    A = np.load(f'{S}/{tag}.npz')['tel']
    return np.c_[np.interp(t, A[:, 0], A[:, 1]),
                 np.interp(t, A[:, 0], A[:, 2]),
                 np.interp(t, A[:, 0], A[:, 3])]

P = odom_at('n_cec1', ts_s)

def umeyama(src, dst):
    mu_s, mu_d = src.mean(0), dst.mean(0)
    X, Y = src - mu_s, dst - mu_d
    Sig = Y.T @ X / len(src)
    U, D, Vt = np.linalg.svd(Sig)
    Sm = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sm[2, 2] = -1
    R = U @ Sm @ Vt
    var = (X ** 2).sum() / len(src)
    s = float(np.trace(np.diag(D) @ Sm) / var)
    return s, R, mu_d - s * R @ mu_s

s, R, t = umeyama(P, C)
res = np.linalg.norm((s * (R @ P.T).T + t) - C, axis=1)
print(f"\nSim(3) 里程计->LingBot: 尺度 {s:.4f} 模型单位/米, "
      f"残差 RMSE {np.sqrt((res**2).mean())/s:.3f} m, 中位 {np.median(res)/s:.3f} m")

# --- floor plane from the camera track
mu = C.mean(0)
n = np.linalg.svd(C - mu, full_matrices=False)[2][-1]
down = Rc[:, :, 1].mean(0)                     # optical +y, roughly world-down
if n @ down < 0: n = -n                        # make n point down
flat = np.abs((C - mu) @ n)
print(f"相机轨迹平面拟合: 厚度 中位 {np.median(flat)/s*100:.1f} cm, "
      f"p95 {np.percentile(flat,95)/s*100:.1f} cm (越薄说明地面越平、轨迹越可信)")

MOUNT_H = 0.386                                # calib_mount3 on this run
floor_d = float((mu @ n) + MOUNT_H * s)        # plane: n . x = floor_d
print(f"地面平面 n={np.round(n,4)}  d={floor_d:.4f}  (相机面下移 {MOUNT_H} m)")

json.dump(dict(scale=s, R=R.tolist(), t=t.tolist(), floor_n=n.tolist(),
               floor_d=floor_d, mount_h=MOUNT_H,
               rmse_m=float(np.sqrt((res**2).mean())/s),
               n_pairs=len(C)), open('ground_frame.json', 'w'), indent=1)
print('-> ground_frame.json')

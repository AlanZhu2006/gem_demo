"""Per-run ground frame: gravity from the camera track, scale from odometry.

Fitting the floor in the cloud failed on this scene.  The camera track is the
better cue -- the robot walks at a fixed height over a flat floor, so the plane
through the camera centres is parallel to the floor and the measured mount
height, converted to model units, drops it onto the floor.
"""
import glob, json
import numpy as np

S = '/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad'
RUNS = {'gem': ('outputs/cec_090850_demo_flashinfer', 'n_cec1', 0.386),
        'base': ('outputs/base_091940_demo_flashinfer', 'n_base1', 0.399)}


def umeyama(src, dst):
    ms, md = src.mean(0), dst.mean(0)
    X, Y = src - ms, dst - md
    U, D, Vt = np.linalg.svd(Y.T @ X / len(src))
    Sm = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sm[2, 2] = -1
    R = U @ Sm @ Vt
    s = float(np.trace(np.diag(D) @ Sm) / ((X ** 2).sum() / len(src)))
    return s, R, md - s * R @ ms


out = {}
for k, (root, tag, mh) in RUNS.items():
    C, Rc, T = [], [], []
    for f in sorted(glob.glob(f'{root}/frames/*.npz')):
        d = np.load(f); c = d['c2w']
        C.append(c[:, 3]); Rc.append(c[:, :3]); T.append(int(d['timestamp_ns']) / 1e9)
    C, Rc, T = np.array(C), np.array(Rc), np.array(T)
    A = np.load(f'{S}/{tag}.npz')['tel']
    P = np.c_[np.interp(T, A[:, 0], A[:, 1]), np.interp(T, A[:, 0], A[:, 2]),
              np.interp(T, A[:, 0], A[:, 3])]
    s, R, t = umeyama(P, C)
    res = np.linalg.norm((s * (R @ P.T).T + t) - C, axis=1) / s

    mu = C.mean(0)
    n = np.linalg.svd(C - mu, full_matrices=False)[2][-1]
    if n @ Rc[:, :, 1].mean(0) < 0: n = -n        # +n points down
    flat = np.abs((C - mu) @ n) / s
    d_floor = float((mu @ n) + mh * s)
    out[k] = dict(root=root, tag=tag, scale=s, R=R.tolist(), t=t.tolist(),
                  floor_n=n.tolist(), floor_d=d_floor, mount_h=mh,
                  odom_rmse_m=float(np.sqrt((res ** 2).mean())),
                  track_plane_p95_cm=float(np.percentile(flat, 95) * 100),
                  n_frames=len(C), t0=float(T[0]), t1=float(T[-1]))
    print(f"{k:5s} {len(C)} 帧 | 尺度 {s:.4f} 单位/米 | 里程计 RMSE {out[k]['odom_rmse_m']:.3f} m "
          f"| 轨迹平面 p95 {out[k]['track_plane_p95_cm']:.1f} cm")

json.dump(out, open('ground_frames.json', 'w'), indent=1)
print('-> ground_frames.json')

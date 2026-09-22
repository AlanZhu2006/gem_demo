"""Refine Baseline -> GEM with trimmed similarity ICP on the overlap.

The odometry chain lands within ~30 cm, which still doubles walls.  ICP is run
from that initialisation, keeping scale free because the two LingBot sessions
genuinely differ in scale, and trimming correspondences so the non-overlapping
parts of each pass do not drag the fit.
"""
import glob, json
import numpy as np
from scipy.spatial import cKDTree

GEM = 'outputs/cec_090850_demo_flashinfer'
BASE = 'outputs/base_091940_demo_flashinfer'
reg = json.load(open('register_base_to_gem.json'))
sA = reg['gem']['s']


def cloud(root, step=3, cap=600000):
    X = []
    for f in sorted(glob.glob(f'{root}/frames/*.npz'))[::step]:
        d = np.load(f); T = d['c2w']
        X.append(d['local_points'] @ T[:3, :3].T + T[:3, 3])
    X = np.concatenate(X)
    rng = np.random.default_rng(0)
    return X[rng.choice(len(X), min(cap, len(X)), replace=False)]


def umeyama(src, dst):
    ms, md = src.mean(0), dst.mean(0)
    X, Y = src - ms, dst - md
    U, D, Vt = np.linalg.svd(Y.T @ X / len(src))
    Sm = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sm[2, 2] = -1
    R = U @ Sm @ Vt
    s = float(np.trace(np.diag(D) @ Sm) / ((X ** 2).sum() / len(src)))
    return s, R, md - s * R @ ms


A, B = cloud(GEM), cloud(BASE)
tree = cKDTree(A)
s, R, t = reg['s'], np.array(reg['R']), np.array(reg['t'])
print(f"初值: 尺度 {s:.4f}")
for it, thr_m in enumerate([0.60, 0.45, 0.35, 0.25, 0.20, 0.15, 0.12, 0.10, 0.10, 0.10]):
    Bt = s * (R @ B.T).T + t
    dist, idx = tree.query(Bt, k=1)
    keep = dist / sA < thr_m
    if keep.sum() < 2000:
        print(f"  iter {it}: 对应点不足 ({keep.sum()})，停止"); break
    ds, dR, dt = umeyama(Bt[keep], A[idx[keep]])
    s, R, t = ds * s, dR @ R, ds * (dR @ t) + dt
    med = np.median(dist[keep]) / sA
    print(f"  iter {it}: 阈值 {thr_m*100:.0f} cm, 对应 {keep.sum():6d}, 中位残差 {med*100:5.1f} cm")

Bt = s * (R @ B.T).T + t
dist, _ = tree.query(Bt, k=1)
near = dist / sA < 0.6
dd = dist[near] / sA
print(f"\n精修后重叠区 ({near.sum()} 点): 中位 {np.median(dd)*100:.1f} cm, "
      f"p90 {np.percentile(dd,90)*100:.1f} cm")
rot = np.degrees(np.arccos(np.clip((np.trace(R @ np.array(reg['R']).T) - 1) / 2, -1, 1)))
print(f"相对初值: 旋转改变 {rot:.2f}°, 尺度改变 {s/reg['s']:.4f}")
reg.update(icp=dict(s=s, R=R.tolist(), t=t.tolist(),
                    overlap_median_cm=float(np.median(dd) * 100),
                    overlap_p90_cm=float(np.percentile(dd, 90) * 100),
                    overlap_points=int(near.sum())))
json.dump(reg, open('register_base_to_gem.json', 'w'), indent=1)
print('-> register_base_to_gem.json (含 icp)')

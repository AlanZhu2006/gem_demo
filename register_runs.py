"""Bring the Baseline reconstruction into the GEM reconstruction's frame.

Each LingBot session has its own frame and scale.  Both runs were recorded in
one session of the robot, so their body odometry shares a frame; fitting
odometry -> LingBot for each run gives a chain B -> odometry -> A.

The chain composes two fitted similarities, so it is not assumed to be good --
the overlap between the two clouds near the shared release area is measured,
and the number is printed whether or not it is acceptable.
"""
import glob, json
import numpy as np
from scipy.spatial import cKDTree

S = '/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad'
RUNS = {'gem': ('outputs/cec_090850_demo_flashinfer', 'n_cec1'),
        'base': ('outputs/base_091940_demo_flashinfer', 'n_base1')}


def track(root):
    C, T = [], []
    for f in sorted(glob.glob(f'{root}/frames/*.npz')):
        d = np.load(f); C.append(d['c2w'][:, 3]); T.append(int(d['timestamp_ns']) / 1e9)
    return np.array(C), np.array(T)


def odom(tag, t):
    A = np.load(f'{S}/{tag}.npz')['tel']
    return np.c_[np.interp(t, A[:, 0], A[:, 1]), np.interp(t, A[:, 0], A[:, 2]),
                 np.interp(t, A[:, 0], A[:, 3])]


def umeyama(src, dst):
    ms, md = src.mean(0), dst.mean(0)
    X, Y = src - ms, dst - md
    U, D, Vt = np.linalg.svd(Y.T @ X / len(src))
    Sm = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sm[2, 2] = -1
    R = U @ Sm @ Vt
    s = float(np.trace(np.diag(D) @ Sm) / ((X ** 2).sum() / len(src)))
    return s, R, md - s * R @ ms


fit = {}
for k, (root, tag) in RUNS.items():
    C, T = track(root)
    P = odom(tag, T)
    s, R, t = umeyama(P, C)
    r = np.linalg.norm((s * (R @ P.T).T + t) - C, axis=1) / s
    fit[k] = dict(s=s, R=R, t=t)
    print(f"{k:5s}: {len(C)} 帧, 尺度 {s:.4f} 单位/米, 里程计残差 RMSE {np.sqrt((r**2).mean()):.3f} m")

# B -> odometry -> A
sA, RA, tA = fit['gem']['s'], fit['gem']['R'], fit['gem']['t']
sB, RB, tB = fit['base']['s'], fit['base']['R'], fit['base']['t']
s_ba = sA / sB
R_ba = RA @ RB.T
t_ba = tA - s_ba * R_ba @ tB
print(f"\nB->A 相似变换: 尺度比 {s_ba:.4f}, 旋转 {np.degrees(np.arccos(np.clip((np.trace(R_ba)-1)/2,-1,1))):.1f}°")


def cloud(root, step=5, cap=400000):
    X = []
    for f in sorted(glob.glob(f'{root}/frames/*.npz'))[::step]:
        d = np.load(f); T = d['c2w']
        X.append(d['local_points'] @ T[:3, :3].T + T[:3, 3])
    X = np.concatenate(X)
    return X[np.random.default_rng(0).choice(len(X), min(cap, len(X)), replace=False)]


A = cloud(RUNS['gem'][0])
B = cloud(RUNS['base'][0])
Bt = s_ba * (R_ba @ B.T).T + t_ba
tree = cKDTree(A)
dist, _ = tree.query(Bt, k=1)
near = dist / sA < 0.6                      # only where the two passes actually overlap
print(f"\n重叠检验: B 变换后共 {len(Bt)} 点, 其中 {near.sum()} 点在 A 的 0.6 m 内")
if near.sum() > 500:
    dd = dist[near] / sA
    print(f"  重叠区最近邻距离: 中位 {np.median(dd)*100:.1f} cm, "
          f"p90 {np.percentile(dd,90)*100:.1f} cm, 均值 {dd.mean()*100:.1f} cm")
else:
    print("  重叠点太少，无法判定")
json.dump(dict(s=s_ba, R=R_ba.tolist(), t=t_ba.tolist(),
               gem=dict(s=sA, R=RA.tolist(), t=tA.tolist()),
               base=dict(s=sB, R=RB.tolist(), t=tB.tolist())),
          open('register_base_to_gem.json', 'w'), indent=1)
print('-> register_base_to_gem.json')

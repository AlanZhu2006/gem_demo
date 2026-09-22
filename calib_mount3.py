"""Mount attitude from ground normals, constrained by the body's own attitude.

Per frame the ground plane is fitted in the camera frame, which is reliable.
The mount (pitch, roll) is then whichever fixed rotation carries those normals
onto world-vertical once the robot's measured attitude is applied -- a Wahba
problem in two parameters, with no threshold to game.
"""
import sys, json
import numpy as np

tag = sys.argv[1]
R_bc = np.array([[0., 0., 1.], [-1., 0., 0.], [0., -1., 0.]])
def Rz(t): c, s = np.cos(t), np.sin(t); return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def Ry(t): c, s = np.cos(t), np.sin(t); return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def Rx(t): c, s = np.cos(t), np.sin(t); return np.array([[1,0,0],[0,c,-s],[0,s,c]])

D = np.load(f'rgbd_{tag}/depth.npy', mmap_mode='r'); K = np.load(f'rgbd_{tag}/K.npy')
ts = np.load(f'rgbd_{tag}/times.npy')
T = np.load(f'{tag}.npz')['tel']; w = json.load(open(f'demo_{tag}/win.json'))
j = np.clip(np.searchsorted(T[:, 0], ts), 0, len(T) - 1)
fx, fy, cx, cy = K; h, wd = D.shape[1], D.shape[2]
vg, ug = np.mgrid[0:h:2, 0:wd:2]
rng = np.random.default_rng(0)

A, B, H = [], [], []
for i in range(len(D)):
    if not (w['t0'] <= ts[i] <= w['t1']): continue
    z = np.asarray(D[i][::2, ::2]).astype(np.float32) / 1000.0
    m = (z > 0.5) & (z < 3.0) & (vg > h * 0.5)
    if m.sum() < 500: continue
    X = (ug[m] - cx) * z[m] / fx; Y = (vg[m] - cy) * z[m] / fy
    P = np.stack([X, Y, z[m]], 1)
    best = None
    for _ in range(80):
        k = rng.choice(len(P), 3, replace=False); Q3 = P[k]
        n = np.cross(Q3[1] - Q3[0], Q3[2] - Q3[0]); nn = np.linalg.norm(n)
        if nn < 1e-6: continue
        n = n / nn
        if n[1] < 0: n = -n
        if n[1] < 0.80: continue
        d = float(n @ Q3[0])
        inl = np.abs(P @ n - d) < 0.04
        if best is None or inl.sum() > best[0]: best = (inl.sum(), n, d)
    if best is None or best[0] < 0.30 * len(P): continue
    inl = np.abs(P @ best[1] - best[2]) < 0.04
    Q = P[inl]; c = Q.mean(0)
    n = np.linalg.svd(Q - c, full_matrices=False)[2][-1]
    if n[1] < 0: n = -n
    Rb = Rz(T[j[i], 6]) @ Ry(T[j[i], 5]) @ Rx(T[j[i], 4])
    A.append(n)                              # ground normal, camera optical frame
    B.append(Rb.T @ np.array([0., 0., -1.]))  # world-down, expressed in body frame
    H.append(float(n @ c))
A = np.array(A); B = np.array(B); H = np.array(H)
print(f"{tag}: {len(A)} 帧拟合到地面")

def err(p, r):
    M = Ry(np.radians(p)) @ Rx(np.radians(r)) @ R_bc
    return np.degrees(np.arccos(np.clip((A @ M.T * B).sum(1), -1, 1)))

best = (9e9, 0, 0)
for p in np.arange(-20, 25.1, 0.5):
    for r in np.arange(-6, 6.1, 0.5):
        e = np.median(err(p, r))
        if e < best[0]: best = (e, p, r)
e, p, r = best
for _ in range(3):
    for dp in np.arange(-0.5, 0.51, 0.05) + p:
        for dr in np.arange(-0.5, 0.51, 0.05) + r:
            v = np.median(err(dp, dr))
            if v < e: e, p, r = v, dp, dr
hgt = float(np.median(H))
print(f"  俯角 {p:+.2f}°  横滚 {r:+.2f}°  高 {hgt:.3f} m   法向残差 中位 {e:.2f}° "
      f"(p90 {np.percentile(err(p,r),90):.2f}°)")
np.save(f'rgbd_{tag}/mount2.npy', np.array([hgt, p, r]))

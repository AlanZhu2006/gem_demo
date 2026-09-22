"""Register the survey onto the revisit frame from image correspondences.

Matching one goal frame fixes a single pose pair, and pinning the transform on
it means trusting that GEM stopped exactly where the goal was shot.  Instead
every revisit frame is looked up against the survey by appearance; each
confident hit gives a (survey pose, revisit pose) pair, and a rigid transform
is fitted to them under RANSAC.
"""
import glob, json
import numpy as np
from PIL import Image

def descs(files):
    out = np.empty((len(files), 36 * 64), np.float32)
    for i, f in enumerate(files):
        a = np.asarray(Image.open(f).convert('L').resize((64, 36), Image.BILINEAR), np.float32)
        a -= a.mean(); out[i] = (a / (np.linalg.norm(a) + 1e-9)).ravel()
    return out

def poses(tag, ts):
    T = np.load(f'{tag}.npz')['tel']
    return np.c_[np.interp(ts, T[:, 0], T[:, 1]), np.interp(ts, T[:, 0], T[:, 2]),
                 np.interp(ts, T[:, 0], np.unwrap(T[:, 6]))]

sf = sorted(glob.glob('demo_n_survey/rgb/*.jpg'))
sts = np.load('demo_n_survey/times.npy')
SD = descs(sf); SP = poses('n_survey', sts)

pairs = []
for tag in ('n_cec1', 'n_base1'):
    rf = sorted(glob.glob(f'demo_{tag}/rgb/*.jpg'))
    rts = np.load(f'demo_{tag}/times.npy')
    w = json.load(open(f'demo_{tag}/win.json'))
    sel = [i for i in range(0, len(rf), 8) if w['t0'] <= rts[i] <= w['t1']]
    RD = descs([rf[i] for i in sel]); RP = poses(tag, rts[sel])
    C = RD @ SD.T
    b = C.argmax(1); s = C.max(1)
    for k in range(len(sel)):
        if s[k] > 0.72: pairs.append((SP[b[k]], RP[k], s[k], tag))
    print(f"{tag}: {len(sel)} 帧查询, {int((s>0.72).sum())} 条置信匹配 (最高 {s.max():.3f})")

A = np.array([p[0][:2] for p in pairs]); B = np.array([p[1][:2] for p in pairs])
print(f"共 {len(A)} 对")

def fit(a, b):
    ca, cb = a.mean(0), b.mean(0)
    H = (a - ca).T @ (b - cb)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0: Vt[-1] *= -1; R = Vt.T @ U.T
    return R, cb - R @ ca

rng = np.random.default_rng(0)
best = (0, None, None, None)
for _ in range(4000):
    i = rng.choice(len(A), 2, replace=False)
    if np.linalg.norm(A[i[0]] - A[i[1]]) < 1.0: continue
    R, t = fit(A[i], B[i])
    r = np.linalg.norm(A @ R.T + t - B, axis=1)
    inl = r < 0.5
    if inl.sum() > best[0]: best = (int(inl.sum()), R, t, inl)
n, R, t, inl = best
R, t = fit(A[inl], B[inl])                       # refit on the consensus
r = np.linalg.norm(A @ R.T + t - B, axis=1)
inl = r < 0.5
R, t = fit(A[inl], B[inl])
r = np.linalg.norm(A @ R.T + t - B, axis=1)
dth = float(np.arctan2(R[1, 0], R[0, 0]))
print(f"内点 {inl.sum()}/{len(A)}, 内点残差 中位 {np.median(r[inl]):.3f} m 最大 {r[inl].max():.3f} m")
print(f"变换: dθ {np.degrees(dth):+.2f}°, t ({t[0]:+.3f},{t[1]:+.3f})")

gj = json.load(open('goal_in_survey.json'))
gp = R @ np.array([gj['x'], gj['y']]) + t
Tg = np.load('n_cec1.npz')['tel']; w = json.load(open('demo_n_cec1/win.json'))
Q = Tg[(Tg[:, 0] >= w['t0']) & (Tg[:, 0] <= w['t1'])]
print(f"目标点 -> ({gp[0]:.2f},{gp[1]:.2f});  GEM 终点 ({Q[-1,1]:.2f},{Q[-1,2]:.2f});  "
      f"相距 {np.hypot(gp[0]-Q[-1,1], gp[1]-Q[-1,2]):.2f} m")
json.dump(dict(dtheta=dth, tx=float(t[0]), ty=float(t[1]), inliers=int(inl.sum()),
               n=len(A), goal_xy=[float(gp[0]), float(gp[1])]), open('survey_reg.json', 'w'))

"""Ground orthophoto in two layers: what the survey already mapped, and what
the revisit arms observe as they go.

The static layer is a per-cell median over the survey pass -- the map GEM
carries into the revisit.  The progressive layer is emitted as time buckets of
cell contributions, so playback can accumulate them and the floor fills in
under each robot instead of appearing all at once.
"""
import sys, os, argparse, json
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--static', nargs='*', default=[], help='runs composited once, up front')
ap.add_argument('--prog', nargs='+', required=True, help='runs emitted as time buckets')
ap.add_argument('--out', required=True)
ap.add_argument('--res', type=float, default=0.025)
ap.add_argument('--rmax', type=float, default=3.2)
ap.add_argument('--zg', type=float, default=0.10)
ap.add_argument('--pad', type=float, default=1.2)
ap.add_argument('--bucket', type=float, default=0.4)
ap.add_argument('--xform', default='{}', help='JSON {run: [dtheta_rad, tx, ty]} onto the reference frame')
a = ap.parse_args()
S = os.path.dirname(os.path.abspath(__file__))
XF = {k: np.asarray(v, float) for k, v in json.loads(a.xform).items()}

def xform_tel(k, T):
    """Poses of a pass recorded in its own odometry frame, brought onto the reference."""
    if k not in XF: return T
    dth, tx, ty = XF[k]
    c, s_ = np.cos(dth), np.sin(dth)
    T = T.copy()
    x, y = T[:, 1].copy(), T[:, 2].copy()
    T[:, 1] = c * x - s_ * y + tx
    T[:, 2] = s_ * x + c * y + ty
    T[:, 6] = T[:, 6] + dth
    return T

R_bc = np.array([[0., 0., 1.], [-1., 0., 0.], [0., -1., 0.]])
def Rz(t): c, s = np.cos(t), np.sin(t); return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def Ry(t): c, s = np.cos(t), np.sin(t); return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def Rx(t): c, s = np.cos(t), np.sin(t); return np.array([[1,0,0],[0,c,-s],[0,s,c]])

runs = list(dict.fromkeys(a.static + a.prog))
xy = np.concatenate([xform_tel(k, np.load(os.path.join(S, f'{k}.npz'))['tel'])[:, 1:3]
                     for k in runs])
LO = xy.min(0) - a.pad - a.rmax * 0.75
HI = xy.max(0) + a.pad + a.rmax * 0.75
NX, NY = int((HI[0] - LO[0]) / a.res) + 1, int((HI[1] - LO[1]) / a.res) + 1
print(f"栅格 {NY}x{NX} @ {a.res} m, x {LO[0]:.1f}..{HI[0]:.1f}  y {LO[1]:.1f}..{HI[1]:.1f}")


def ground_cells(k):
    """Yield (timestamp, linear cell index, rgb) for every frame of one run."""
    d = os.path.join(S, f'rgbd_{k}')
    D = np.load(d + '/depth.npy', mmap_mode='r'); C = np.load(d + '/color.npy', mmap_mode='r')
    K = np.load(d + '/K.npy'); ts = np.load(d + '/times.npy')
    MH, MP, MR = np.load(d + '/mount.npy')
    T = xform_tel(k, np.load(os.path.join(S, f'{k}.npz'))['tel'])
    j = np.clip(np.searchsorted(T[:, 0], ts), 0, len(T) - 1)
    fx, fy, cx, cy = K; h, w = D.shape[1], D.shape[2]
    SS = 2; vg, ug = np.mgrid[0:h:SS, 0:w:SS]
    M0 = Ry(np.radians(MP)) @ Rx(np.radians(-MR)) @ R_bc
    for i in range(len(D)):
        z = np.asarray(D[i][::SS, ::SS]).astype(np.float32) / 1000.0
        m = (z > 0.4) & (z < a.rmax)
        if m.sum() < 200: continue
        X = (ug[m] - cx) * z[m] / fx; Y = (vg[m] - cy) * z[m] / fy
        P = np.stack([X, Y, z[m]], 1) @ M0.T
        Wp = P @ Rz(T[j[i], 6]).T + np.array([T[j[i], 1], T[j[i], 2], MH])
        g = np.abs(Wp[:, 2]) < a.zg
        if g.sum() < 50: continue
        q = Wp[g]
        ii = ((q[:, 0] - LO[0]) / a.res).astype(np.int64)
        jj = ((q[:, 1] - LO[1]) / a.res).astype(np.int64)
        ok = (ii >= 0) & (ii < NX) & (jj >= 0) & (jj < NY)
        if not ok.any(): continue
        yield ts[i], (jj[ok] * NX + ii[ok]), np.asarray(C[i][::SS, ::SS])[m][g][ok]


def fold(idx, col):
    """Collapse repeated cells to one entry each, with a pixel count."""
    u, inv = np.unique(idx, return_inverse=True)
    n = np.bincount(inv, minlength=len(u))
    s = np.stack([np.bincount(inv, weights=col[:, c].astype(np.float64), minlength=len(u))
                  for c in range(3)], 1)
    return u.astype(np.int64), (s / n[:, None]).astype(np.uint8), np.minimum(n, 65535).astype(np.uint16)


out = dict(lo=LO, res=a.res, shape=np.array([NY, NX]),
           static=np.array(a.static, dtype=object), prog=np.array(a.prog, dtype=object))

if a.static:
    # per-cell mean over the pass, accumulated with bincount: a dict of
    # observations per cell is tens of millions of appends and never finishes
    tot = np.zeros(NX * NY * 3, np.float64)
    cnt = np.zeros(NX * NY, np.int64)
    for k in a.static:
        for _, idx, col in ground_cells(k):
            cnt += np.bincount(idx, minlength=NX * NY)
            for c in range(3):
                tot[c::3] += np.bincount(idx, weights=col[:, c].astype(np.float64),
                                         minlength=NX * NY)
    cells = np.nonzero(cnt)[0]
    rgb = np.stack([tot[c::3][cells] / cnt[cells] for c in range(3)], 1).astype(np.uint8)
    out['static_idx'] = cells.astype(np.int64); out['static_rgb'] = rgb
    print(f"静态层 {len(cells)} 格 (来自 {a.static})")

for k in a.prog:
    bt, bi, br, bn, ptr = [], [], [], [], [0]
    cur_t, ci, cc = None, [], []
    def flush():
        if not ci: return
        u, rgb, n = fold(np.concatenate(ci), np.concatenate(cc))
        bt.append(cur_t); bi.append(u); br.append(rgb); bn.append(n)
        ptr.append(ptr[-1] + len(u))
    for t, idx, col in ground_cells(k):
        if cur_t is None: cur_t = t
        if t - cur_t >= a.bucket:
            flush(); cur_t, ci, cc = t, [], []
        ci.append(idx); cc.append(col)
    flush()
    out[f'{k}_t'] = np.array(bt, float)
    out[f'{k}_ptr'] = np.array(ptr, np.int64)
    out[f'{k}_idx'] = np.concatenate(bi) if bi else np.zeros(0, np.int64)
    out[f'{k}_rgb'] = np.concatenate(br) if br else np.zeros((0, 3), np.uint8)
    out[f'{k}_n'] = np.concatenate(bn) if bn else np.zeros(0, np.uint16)
    print(f"{k}: {len(bt)} 个时间桶, {out[f'{k}_idx'].size} 格次")

np.savez_compressed(a.out, **out)
print('->', a.out)

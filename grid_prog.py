"""A 2.5-D grid map that accumulates: floor colour, obstacle height, coverage.

Points leave holes between them; cells do not.  Each cell carries the colour of
the floor seen in it, the tallest return above the floor, and how many returns
supported each, emitted in time buckets so playback can build the map up.
"""
import os, json, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--runs', nargs='+', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--res', type=float, default=0.04)
ap.add_argument('--rmax', type=float, default=3.4)
ap.add_argument('--zfloor', type=float, default=0.13)
ap.add_argument('--zobs', type=float, default=0.20)
ap.add_argument('--zmax', type=float, default=1.9)
ap.add_argument('--pad', type=float, default=1.6)
ap.add_argument('--bucket', type=float, default=0.4)
ap.add_argument('--robs', type=float, default=2.5,
                help='classify obstacles only within this range: the height\n                      estimate degrades at grazing incidence on a shiny floor')
a = ap.parse_args()
S = os.path.dirname(os.path.abspath(__file__))

R_bc = np.array([[0., 0., 1.], [-1., 0., 0.], [0., -1., 0.]])
def Rz(t): c, s = np.cos(t), np.sin(t); return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def Ry(t): c, s = np.cos(t), np.sin(t); return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def Rx(t): c, s = np.cos(t), np.sin(t); return np.array([[1,0,0],[0,c,-s],[0,s,c]])

xy = np.concatenate([np.load(os.path.join(S, f'{k}.npz'))['tel'][:, 1:3] for k in a.runs])
LO = xy.min(0) - a.pad - a.rmax * 0.8
HI = xy.max(0) + a.pad + a.rmax * 0.8
NX, NY = int((HI[0]-LO[0])/a.res)+1, int((HI[1]-LO[1])/a.res)+1
N = NX * NY
print(f"栅格 {NY}x{NX} @ {a.res} m")


def frames(k):
    d = os.path.join(S, f'rgbd_{k}')
    D = np.load(d+'/depth.npy', mmap_mode='r'); C = np.load(d+'/color.npy', mmap_mode='r')
    K = np.load(d+'/K.npy'); ts = np.load(d+'/times.npy')
    mf = d + ('/mount2.npy' if os.path.exists(d + '/mount2.npy') else '/mount.npy')
    MH, MP, MR = np.load(mf)
    T = np.load(os.path.join(S, f'{k}.npz'))['tel']
    w = json.load(open(os.path.join(S, f'demo_{k}/win.json')))
    j = np.clip(np.searchsorted(T[:, 0], ts), 0, len(T)-1)
    fx, fy, cx, cy = K; h, wd = D.shape[1], D.shape[2]
    SS = 1; vg, ug = np.mgrid[0:h:SS, 0:wd:SS]
    # calib_mount3 writes mount2 using +roll in its fitted rotation.
    mount_roll = MR if mf.endswith('/mount2.npy') else -MR
    M0 = Ry(np.radians(MP)) @ Rx(np.radians(mount_roll)) @ R_bc
    for i in range(len(D)):
        if not (w['t0'] <= ts[i] <= w['t1']): continue
        z = np.asarray(D[i][::SS, ::SS]).astype(np.float32)/1000.0
        m = (z > 0.4) & (z < a.rmax)
        if m.sum() < 200: continue
        X = (ug[m]-cx)*z[m]/fx; Y = (vg[m]-cy)*z[m]/fy
        P = np.stack([X, Y, z[m]], 1) @ M0.T
        # full body attitude: yaw alone leaves up to ~25 cm of height error at
        # 3 m, which is enough to turn floor into phantom obstacles
        Rb = Rz(T[j[i], 6]) @ Ry(T[j[i], 5]) @ Rx(T[j[i], 4])
        Wp = P @ Rb.T + np.array([T[j[i], 1], T[j[i], 2], MH])
        col = np.asarray(C[i][::SS, ::SS])[m]
        ii = ((Wp[:, 0]-LO[0])/a.res).astype(np.int64)
        jj = ((Wp[:, 1]-LO[1])/a.res).astype(np.int64)
        ok = (ii >= 0) & (ii < NX) & (jj >= 0) & (jj < NY) & (Wp[:, 2] > -0.25) & (Wp[:, 2] < a.zmax)
        if not ok.any(): continue
        yield (ts[i], jj[ok]*NX + ii[ok], Wp[ok, 2], col[ok],
               z[m][ok] if False else np.asarray(z[m])[ok])


out = dict(lo=LO, res=a.res, shape=np.array([NY, NX]), runs=np.array(a.runs, dtype=object),
           time_basis=np.array('absolute_ros_seconds'), bucket_timestamp=np.array('last_observation'))
for k in a.runs:
    bt, B, ptr = [], [], [0]
    cur, last_t, acc = None, None, []
    def flush():
        if not acc: return
        cell = np.concatenate([x[0] for x in acc])
        zz = np.concatenate([x[1] for x in acc])
        cc = np.concatenate([x[2] for x in acc])
        rg = np.concatenate([x[3] for x in acc])
        u, inv = np.unique(cell, return_inverse=True)
        gm = zz < a.zfloor
        nf = np.bincount(inv[gm], minlength=len(u))
        rgb = np.zeros((len(u), 3), np.float64)
        for ch in range(3):
            rgb[:, ch] = np.bincount(inv[gm], weights=cc[gm, ch].astype(np.float64),
                                     minlength=len(u))
        rgb = np.where(nf[:, None] > 0, rgb / np.maximum(nf[:, None], 1), 0).astype(np.uint8)
        om = (zz > a.zobs) & (rg < a.robs)
        no = np.bincount(inv[om], minlength=len(u))
        hm = np.zeros(len(u), np.float32)
        np.maximum.at(hm, inv[om], zz[om].astype(np.float32))
        # A bucket must not become visible before its newest observation.
        bt.append(last_t); B.append((u, rgb, nf, no, hm)); ptr.append(ptr[-1] + len(u))
    for t, cell, zz, cc, rg in frames(k):
        if cur is None: cur = t
        if t - cur >= a.bucket:
            flush(); cur, acc = t, []
        acc.append((cell, zz, cc, rg)); last_t = t
    flush()
    out[f'{k}_t'] = np.array(bt, float)
    out[f'{k}_ptr'] = np.array(ptr, np.int64)
    out[f'{k}_idx'] = np.concatenate([b[0] for b in B])
    out[f'{k}_rgb'] = np.concatenate([b[1] for b in B])
    out[f'{k}_nf'] = np.concatenate([b[2] for b in B]).astype(np.uint16)
    out[f'{k}_no'] = np.concatenate([b[3] for b in B]).astype(np.uint16)
    out[f'{k}_h'] = np.concatenate([b[4] for b in B]).astype(np.float16)
    print(f"{k}: {len(bt)} 桶, {out[f'{k}_idx'].size} 格次")
np.savez_compressed(a.out, **out)
print('->', a.out)

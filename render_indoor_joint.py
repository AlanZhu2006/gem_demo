"""Final indoor demo: one LingBot reconstruction, both routes in it.

The two revisit runs are separate LingBot sessions whose frames do not line up
(see lingbot_deployment.md 2.7: ~26 cm apart over the shared area, which no
single similarity removes).  So instead of registering two reconstructions,
both runs are fed to LingBot as ONE streaming session: Baseline reversed, then
GEM forward.  Both runs were released from the same pose, so that join is the
smallest motion available between them -- the seam ends up 4.2 cm, against a
2.9 cm typical inter-frame step.

The payoff is that both camera tracks come out of one frame, so the two
trajectories need no registration at all: they are the reconstruction's own
poses.  Odometry is used only to pick each run's playback clock.

Trajectories are dense samples on the shared floor plane, splatted through the
same z-buffer as the cloud, so the map occludes them and they paint onto the
floor rather than floating over it.
"""
import argparse, glob, json, subprocess
from pathlib import Path

import cv2
import numpy as np

S = '/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad'
W, H = 1920, 1080
TP = 524
ROW_Y = (14, 552)
MAP_X, MAP_Y, MAP_W, MAP_H = 556, 14, 1346, 1062
PIP_W, PIP_H = 258, 146
COL = {'gem': (230, 155, 77), 'base': (72, 87, 240)}      # BGR
GOLD = (60, 200, 255)
CAP = ('/home/asus/Research/Nav-graph-blind/projects/realworld/runtime/'
       'experiment_archives/jetson_20260919/jetson/runtime/go2/experiment_capture')
GOAL_IMG = f'{CAP}/episode_20260919T090850_042322Z/media/revisit_goal.png'
NAME = {'gem': 'GEM', 'base': 'Baseline'}
TAG = {'gem': 'n_cec1', 'base': 'n_base1'}
SRC = {'gem': 'outputs/cec_090850_rgb', 'base': 'outputs/base_091940_rgb'}


def ribbon(pts3, up, width_u, step_u):
    pts3 = np.asarray(pts3, float)
    if len(pts3) < 2: return np.zeros((0, 3))
    seg = np.diff(pts3, axis=0)
    L = np.linalg.norm(seg, axis=1)
    keep = L > 1e-9
    if not keep.any(): return np.zeros((0, 3))
    pts3, seg, L = pts3[np.r_[True, keep]], seg[keep], L[keep]
    cum = np.r_[0, np.cumsum(L)]
    m = max(2, int(cum[-1] / step_u) + 1)
    sq = np.linspace(0, cum[-1], m)
    idx = np.clip(np.searchsorted(cum, sq) - 1, 0, len(L) - 1)
    centre = pts3[idx] + seg[idx] * ((sq - cum[idx]) / L[idx])[:, None]
    # tangent from the resampled centreline, not per source segment: a
    # piecewise-constant side direction leaves a notch at every bend, which
    # reads as a scalloped edge
    tang = np.gradient(centre, axis=0)
    bad = np.linalg.norm(tang, axis=1) < 1e-12
    if bad.any(): tang[bad] = (seg[idx] / L[idx][:, None])[bad]
    side = np.cross(tang, up)
    side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-12
    k = max(2, int(width_u / step_u) + 1)
    off = np.linspace(-width_u / 2, width_u / 2, k)
    return (centre[:, None, :] + side[:, None, :] * off[None, :, None]).reshape(-1, 3)


def _frame(up):
    e1 = np.cross(up, [1., 0, 0])
    if np.linalg.norm(e1) < 1e-6: e1 = np.cross(up, [0, 1., 0])
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(up, e1)


def disc(c, up, r, step):
    a = np.arange(-r, r + step, step)
    gx, gy = np.meshgrid(a, a)
    m = gx ** 2 + gy ** 2 <= r ** 2
    e1, e2 = _frame(up)
    return c + gx[m][:, None] * e1 + gy[m][:, None] * e2


def ring(c, up, r, w, step):
    a = np.arange(-r - w, r + w + step, step)
    gx, gy = np.meshgrid(a, a)
    rr = np.hypot(gx, gy)
    m = (rr >= r - w) & (rr <= r + w)
    e1, e2 = _frame(up)
    return c + gx[m][:, None] * e1 + gy[m][:, None] * e2


class Arm:
    """Playback clock and external footage for one run."""

    def __init__(self, key):
        self.key = key
        tag = TAG[key]
        self.tel = np.load(f'{S}/{tag}.npz')['tel']
        self.plans = list(np.load(f'{S}/demo_{tag}/plans.npy', allow_pickle=True))
        man = json.loads((Path(SRC[key]) / 'manifest.json').read_text())
        self.src_dir = Path(SRC[key])
        self.rows = man['frames']
        self.rt = np.array([r['timestamp_ns'] for r in self.rows], np.int64)
        self.ms = man['motion_start_ns'] / 1e9
        self.tend = self.rt[-1] / 1e9
        tp = json.loads(Path(f'{S}/tp30_{tag}_stab/index.json').read_text())
        self.tp_dir, self.tp_t0, self.tp_fps, self.tp_n, self.tp_last = (
            Path(f'{S}/tp30_{tag}_stab'), tp['t_first'], tp['fps'], tp['n'], tp['t_last'])
        # when the onboard RGB matched the goal image, from the run's own
        # arrival module -- the only thing that says which arm succeeded
        arr = json.loads(Path(f'{S}/demo_{tag}/arrival.json').read_text())
        lat = [r[0] for r in arr if r[1].get('arrival_latched')]
        self.latch_t = min(lat) if lat else None
        self._clock()

    def _clock(self, dt=0.05, min_stall=2.5, keep_in=0.5, keep_out=0.3):
        T = self.tel
        Q = T[(T[:, 0] >= self.ms) & (T[:, 0] <= self.tend)]
        mv = ((np.linalg.norm(Q[:, 1:3] - Q[0, 1:3], axis=1) > 0.03) |
              (np.degrees(np.abs(np.unwrap(Q[:, 6]) - Q[0, 6])) > 3.0))
        self.onset = float(Q[int(np.argmax(mv)), 0]) if mv.any() else self.ms
        gr = np.arange(self.onset, self.tend, dt)
        x = np.interp(gr, T[:, 0], T[:, 1]); y = np.interp(gr, T[:, 0], T[:, 2])
        yw = np.degrees(np.interp(gr, T[:, 0], np.unwrap(T[:, 6])))
        n = max(1, int(round(0.5 / dt)))
        sp = np.zeros_like(gr); tw = np.zeros_like(gr)
        sp[n:] = np.hypot(x[n:] - x[:-n], y[n:] - y[:-n]) / (n * dt)
        tw[n:] = np.abs(yw[n:] - yw[:-n]) / (n * dt)
        still = (sp < 0.04) & (tw < 4.0)
        segs, i = [], 0
        while i < len(still):
            if still[i]:
                j = i
                while j < len(still) and still[j]: j += 1
                segs.append([i, j]); i = j
            else: i += 1
        merged = []
        for sg in segs:
            if merged and (sg[0] - merged[-1][1]) * dt < 2.5: merged[-1][1] = sg[1]
            else: merged.append(sg)
        cut = np.zeros_like(still)
        for i, j in merged:
            span = (j - i) * dt
            if span < min_stall: continue
            if np.hypot(x[j - 1] - x[i], y[j - 1] - y[i]) / span > 0.02: continue
            if abs(yw[j - 1] - yw[i]) / span > 1.0: continue
            a = i + int(round(keep_in / dt)); b = j - int(round(keep_out / dt))
            if b > a: cut[a:b] = True
        self.kept = gr[~cut]; self.dt = dt
        self.cut_s = float(cut.sum() * dt)
        self.play = len(self.kept) * dt

    def at(self, e):
        return float(self.kept[int(np.clip(e / self.dt, 0, len(self.kept) - 1))])

    def third(self, t):
        k = int(round((t - self.tp_t0) * self.tp_fps))
        return (self.tp_dir / f'{np.clip(k, 0, self.tp_n - 1) + 1:05d}.jpg',
                t <= self.tp_last + 1e-6)

    def fpv(self, t):
        i = max(0, int(np.searchsorted(self.rt, t * 1e9, side='right') - 1))
        return self.src_dir / self.rows[i]['path']

    def plan(self, t, hold=3.0):
        best = None
        for p in self.plans:
            if p['sel'] is None or not len(p['sel']): continue
            if p['t'] <= t and (best is None or p['t'] > best['t']): best = p
        return best if best is not None and t - best['t'] <= hold else None


class JointMap:
    """The single reconstruction both runs live in."""

    def __init__(self, w, h, elev=68.0, margin=0.96, zmax_m=1.10,
                 config='joint_frame.json', manifest='outputs/joint_rgb/manifest.json'):
        g = json.loads(Path(config).read_text())
        self.root = Path(g['root']); self.s = g['scale']
        self.n = np.array(g['floor_n']); self.d = g['floor_d']
        self.w, self.h, self.zmax = w, h, zmax_m
        man = json.loads(Path(manifest).read_text())
        info = {r['key']: r for r in man['frames']}
        self.items = []                       # (timestamp_s, arm, npz path, c2w)
        for f in sorted(glob.glob(str(self.root / 'frames/*.npz'))):
            k = int(Path(f).stem)
            if info[k]['arm'] not in ('gem', 'base'):
                continue
            with np.load(f) as d:
                self.items.append((int(d['timestamp_ns']) / 1e9, info[k]['arm'],
                                   f, d['c2w'].copy()))
                if info[k].get('also_arm') in ('gem', 'base'):
                    self.items.append((int(d['timestamp_ns']) / 1e9, info[k]['also_arm'],
                                       f, d['c2w'].copy()))
        self.C = np.array([it[3][:, 3] for it in self.items])
        self.arm = np.array([it[1] for it in self.items])
        self.ts = np.array([it[0] for it in self.items])
        up = -self.n
        v = self.C[-1] - self.C[0]; v -= up * (v @ up)
        self.R = np.stack((np.cross(v / np.linalg.norm(v), up), v / np.linalg.norm(v), up))
        self.origin = self.to_floor(self.C[0][None])[0]
        # order each arm's track by its own time, so the ribbon follows the walk
        self.order = {a: np.argsort(self.ts[self.arm == a]) for a in ('gem', 'base')}
        self.idx = {a: np.flatnonzero(self.arm == a) for a in ('gem', 'base')}
        self.path = {a: self._build_path(a) for a in ('gem', 'base')}
        self.head = {a: self._build_fwd(a) for a in ('gem', 'base')}

        pts = []
        for i in range(0, len(self.items), 6):
            with np.load(self.items[i][2]) as p:
                q, _ = self.frame_points(p)
                T = self.items[i][3]
                pts.append(self.cut(q[::4] @ T[:3, :3].T + T[:3, 3]))
        P = self._disp(np.concatenate(pts + [self.C]))
        best = None
        for deg in range(0, 360, 3):
            b = self._basis(np.radians(deg), np.radians(elev))
            q = P @ b.T
            lo, hi = np.percentile(q[:, :2], [1.5, 98.5], axis=0)
            sc = min(w / max(hi[0] - lo[0], 1e-6), h / max(hi[1] - lo[1], 1e-6))
            if best is None or sc > best[0]: best = (sc, deg, b, lo, hi)
        _, self.az, self.basis, lo, hi = best
        cp = (self._disp(self.C) @ self.basis.T)[:, :2]
        lo = np.minimum(lo, cp.min(0)); hi = np.maximum(hi, cp.max(0))
        self.mid = (lo + hi) / 2
        self.scale = min(w / max(hi[0] - lo[0], 1e-6), h / max(hi[1] - lo[1], 1e-6)) * margin
        self.step_u = 0.40 / self.scale
        self.z = np.full(w * h, -np.inf)
        # a second depth buffer holding only geometry above the floor.  The
        # ribbons test against this one, so floor points -- whose height is
        # noisy by ~10 cm -- can never occlude a marking painted on the floor,
        # while furniture and plants still do.
        self.z_obs = np.full(w * h, -np.inf)
        self.raster = np.zeros((h * w, 3), np.uint8)
        self.shown = np.zeros(len(self.items), bool)

    @staticmethod
    def _basis(az, elev):
        d = np.array([np.cos(elev) * np.cos(az), np.cos(elev) * np.sin(az), np.sin(elev)])
        r = np.array([-np.sin(az), np.cos(az), 0.])
        return np.stack((r, np.cross(d, r), d))

    def _disp(self, X):
        return (np.atleast_2d(X) - self.origin) @ self.R.T

    def to_floor(self, X, lift=0.0):
        X = np.atleast_2d(np.asarray(X, float))
        return X - self.n * ((X @ self.n - self.d) - lift * self.s)[:, None]

    def cut(self, X, rgb=None):
        hh = (self.d - np.asarray(X) @ self.n) / self.s
        m = (hh > -0.08) & (hh < self.zmax)
        return X[m] if rgb is None else (X[m], rgb[m])

    def frame_points(self, npz):
        d, conf, K = npz['depth'], npz['conf'], npz['K']
        h, w = d.shape
        ok = np.isfinite(d) & (d > 0) & np.isfinite(conf)
        pad = np.pad(np.where(ok, d, np.nan), 1, constant_values=np.nan)
        nb = np.stack([pad[i:i + h, j:j + w] for i in range(3) for j in range(3)])
        spread = np.nanmax(nb, 0) - np.nanmin(nb, 0)
        flat = np.isfinite(spread) & (spread < 0.035 * d)
        thr = np.percentile(conf[ok], 65) if ok.any() else np.inf
        sample = np.zeros_like(ok); sample[::4, ::4] = True
        v, u = np.nonzero(ok & flat & sample & (conf >= thr))
        pts = (np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T) * d[v, u, None]
        return pts.astype(np.float32), npz['rgb'][v, u]

    def project(self, X):
        q = self._disp(X) @ self.basis.T
        uv = np.column_stack(((q[:, 0] - self.mid[0]) * self.scale + self.w / 2,
                              -(q[:, 1] - self.mid[1]) * self.scale + self.h / 2))
        return np.rint(uv).astype(int), q[:, 2]

    def splat(self, X, colors, raster, zbuf, spread=((0, 0), (1, 0), (0, 1)), tol=0.0,
              update_z=True):
        if not len(X): return
        uv, zz = self.project(X)
        colors = np.asarray(colors)
        if colors.ndim == 1: colors = np.repeat(colors[None], len(X), 0)
        for dx, dy in spread:
            u, v = uv[:, 0] + dx, uv[:, 1] + dy
            ok = (u >= 0) & (u < self.w) & (v >= 0) & (v < self.h)
            ids = np.flatnonzero(ok)
            if not len(ids): continue
            ids = ids[np.argsort(-zz[ids], kind='stable')]
            pix = v[ids] * self.w + u[ids]
            _, first = np.unique(pix, return_index=True)
            ids, pix = ids[first], pix[first]
            nearer = zz[ids] > zbuf[pix] - tol
            if update_z: zbuf[pix[nearer]] = zz[ids[nearer]]
            if raster is not None: raster[pix[nearer]] = colors[ids[nearer]]

    def reveal(self, cut_time):
        """Show every frame whose own run has already played past it."""
        for i, (t, a, path, T) in enumerate(self.items):
            if self.shown[i] or t > cut_time[a]: continue
            with np.load(path) as p:
                q, c = self.frame_points(p)
                X, C = self.cut(q @ T[:3, :3].T + T[:3, 3], c[:, ::-1])
                self.splat(X, C, self.raster, self.z)
                above = (self.d - X @ self.n) / self.s > 0.25
                if above.any():
                    self.splat(X[above], None, None, self.z_obs)
            self.shown[i] = True

    def _build_path(self, a, smooth=13, step_m=0.09):
        """The whole walked path, smoothed and thinned ONCE.

        Recomputing this per frame re-quantises the entire polyline every time
        a sample is appended, which shimmers along its full length.  Built once,
        playback just takes the prefix up to the current time.

        Smoothing takes the Go2's step-to-step sway out of the drawing; the
        poses themselves are untouched.
        """
        sel = self.idx[a][self.order[a]]
        P, T = self.C[sel], self.ts[sel]
        if len(P) < 2: return P, T
        k = min(smooth | 1, len(P) if len(P) % 2 else len(P) - 1)
        if k >= 3:
            pad = np.pad(P, ((k // 2, k // 2), (0, 0)), mode='edge')
            ker = np.ones(k) / k
            P = np.stack([np.convolve(pad[:, i], ker, mode='valid') for i in range(3)], 1)
        step = step_m * self.s
        keep = [0]
        for i in range(1, len(P)):
            if np.linalg.norm(P[i] - P[keep[-1]]) >= step: keep.append(i)
        if keep[-1] != len(P) - 1: keep.append(len(P) - 1)
        return P[keep], T[keep]

    def _build_fwd(self, a, win=15):
        """Heading along the floor, smoothed over the gait."""
        sel = self.idx[a][self.order[a]]
        up = -self.n
        F = np.array([self.items[i][3][:, 2] for i in sel])
        F = F - np.outer(F @ up, up)
        F /= np.linalg.norm(F, axis=1, keepdims=True) + 1e-12
        k = min(win | 1, len(F) if len(F) % 2 else len(F) - 1)
        if k >= 3:
            pad = np.pad(F, ((k // 2, k // 2), (0, 0)), mode='edge')
            ker = np.ones(k) / k
            F = np.stack([np.convolve(pad[:, i], ker, mode='valid') for i in range(3)], 1)
            F /= np.linalg.norm(F, axis=1, keepdims=True) + 1e-12
        return F, self.ts[sel]

    @staticmethod
    def _interp(V, T, t):
        if len(V) == 1: return V[0]
        t = float(np.clip(t, T[0], T[-1]))
        i = int(np.clip(np.searchsorted(T, t) - 1, 0, len(T) - 2))
        f = (t - T[i]) / max(T[i + 1] - T[i], 1e-9)
        return V[i] + (V[i + 1] - V[i]) * f

    def pos_at(self, a, t):
        """Current position ON the drawn path.

        Taking the raw camera centre instead puts the marker ~3 cm off the
        smoothed ribbon and moving with the gait, which reads as the marker
        shaking along an otherwise steady line.
        """
        P, T = self.path[a]
        return self._interp(P, T, t)

    def fwd_at(self, a, t):
        F, T = self.head[a]
        v = self._interp(F, T, t)
        return v / max(np.linalg.norm(v), 1e-9)

    def track(self, a, t):
        P, T = self.path[a]
        return P[T <= t]

    def pose(self, a, t):
        sel = self.idx[a][self.order[a]]
        j = int(np.clip(np.searchsorted(self.ts[sel], t) - 1, 0, len(sel) - 1))
        return self.items[sel[j]][3]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--speed', type=float, default=2.0)
    ap.add_argument('--preview', type=float, default=None)
    a = ap.parse_args()

    arms = {k: Arm(k) for k in ('gem', 'base')}
    M = JointMap(MAP_W, MAP_H)
    for k, r in arms.items():
        print(f'{k}: 起动偏移 {r.onset - r.rt[0]/1e9:+.2f}s, 剪卡顿 {r.cut_s:.1f}s, '
              f'播放 {r.play:.1f}s')
    print(f'map: azimuth {M.az}deg, {M.scale * M.s:.1f} px/m, {len(M.items)} 帧')

    TAIL = 3.0                                  # hold the finished state
    dur = max(r.play for r in arms.values()) + TAIL

    def arrived(k, el):
        """That run declared it matched the goal image.

        The latch lands a fraction of a second past the last pose the
        reconstruction exported -- it is what ended the run -- so the trigger is
        'this run finished and it latched', not a source-time crossing.
        """
        lt = arms[k].latch_t
        return lt is not None and (el >= arms[k].play or arms[k].at(min(el, arms[k].play)) >= lt)
    nfr = int(np.ceil(dur / a.speed * a.fps)) + 1
    idx = [int(round(a.preview / a.speed * a.fps))] if a.preview is not None else range(nfr)
    ff = None
    if a.preview is None:
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                               '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(a.fps),
                               '-i', '-', '-c:v', 'libx264', '-crf', '19',
                               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out],
                              stdin=subprocess.PIPE)
    up = -M.n
    goal = cv2.imread(GOAL_IMG)
    gw = 300
    goal = cv2.resize(goal, (gw, round(goal.shape[0] * gw / goal.shape[1])))
    gx, gy = MAP_X + 22, MAP_Y + 22
    audits = []
    for fi in idx:
        el = fi / a.fps * a.speed
        if a.preview is not None:                 # replay so reveal order is honest
            for e in np.arange(0, el, 0.4):
                M.reveal({k: r.at(min(e, r.play)) for k, r in arms.items()})
        cut = {k: r.at(min(el, r.play)) for k, r in arms.items()}
        M.reveal(cut)

        raster = M.raster.copy(); z = M.z_obs.copy()
        tol = 0.0
        for k in ('base', 'gem'):
            t_s, col = cut[k], np.array(COL[k], np.uint8)
            P = M.to_floor(M.track(k, t_s), 0.020)
            if len(P) > 3:
                M.splat(ribbon(P, up, 0.34 * M.s, M.step_u), col * 0.92, raster, z,
                        ((0, 0), (1, 0), (0, 1), (1, 1)), tol=tol)
                M.splat(ribbon(P, up, 0.12 * M.s, M.step_u),
                        np.minimum(col.astype(int) + 70, 255), raster, z, tol=tol)
            here = M.to_floor(M.pos_at(k, t_s)[None], 0.028)[0]
            fwd = M.fwd_at(k, t_s)
            side = np.cross(fwd, up)
            p = arms[k].plan(t_s)
            if p is not None and el <= arms[k].play:
                q = np.array(p['q'], float) if len(p['q']) else np.zeros(len(p['cand']))
                lo_, hi_ = (np.nanmin(q), np.nanmax(q)) if len(q) else (0., 1.)
                to_w = lambda A: (here + np.asarray(A)[:, :1] * fwd * M.s
                                  + np.asarray(A)[:, 1:2] * side * M.s)
                # the fan changes wholesale every policy step (~2.8 Hz), so a
                # bright wide version pops; keep it a faint short ground marking
                for j, cc in enumerate(p['cand']):
                    if cc is None or len(cc) < 2: continue
                    w = 0.5 if hi_ - lo_ < 1e-6 else (q[j] - lo_) / (hi_ - lo_)
                    M.splat(ribbon(to_w(cc[:int(len(cc) * .6)]), up, 0.045 * M.s, M.step_u),
                            np.full(3, int(58 + 70 * (0.35 + 0.55 * w))),
                            raster, z, ((0, 0),), tol=tol)
                M.splat(ribbon(to_w(p['sel'][:int(len(p['sel']) * .8)]), up,
                               0.085 * M.s, M.step_u),
                        np.minimum(col.astype(int) + 70, 255).astype(np.uint8),
                        raster, z, tol=tol)
            if arrived(k, el):
                lt = min(arms[k].latch_t, arms[k].at(arms[k].play))
                at = M.to_floor(M.pos_at(k, lt)[None], 0.024)[0]
                M.splat(ring(at, up, 0.40 * M.s, 0.055 * M.s, M.step_u),
                        np.array(GOLD, np.uint8), raster, z, tol=tol)
                M.splat(ring(at, up, 0.26 * M.s, 0.030 * M.s, M.step_u),
                        np.array(GOLD, np.uint8), raster, z, tol=tol)
            M.splat(ring(here, up, 0.19 * M.s, 0.035 * M.s, M.step_u),
                    np.array([255, 255, 255], np.uint8), raster, z, tol=tol)
            M.splat(disc(here, up, 0.085 * M.s, M.step_u), col, raster, z, tol=tol)

        frame = np.full((H, W, 3), (16, 14, 12), np.uint8)
        frame[MAP_Y:MAP_Y + MAP_H, MAP_X:MAP_X + MAP_W] = raster.reshape(MAP_H, MAP_W, 3)
        for k, y0 in (('gem', ROW_Y[0]), ('base', ROW_Y[1])):
            r = arms[k]
            t_s = cut[k]
            done = el > r.play
            tp, live = r.third(t_s)
            im = cv2.imread(str(tp))
            if im is not None:
                frame[y0:y0 + TP, 18:18 + TP] = cv2.resize(im, (TP, TP))
                if done and not arrived(k, el):   # grey means finished without the goal
                    sub = frame[y0:y0 + TP, 18:18 + TP]
                    frame[y0:y0 + TP, 18:18 + TP] = (sub * 0.45).astype(np.uint8)
            fv = cv2.imread(str(r.fpv(t_s)))
            if fv is not None:
                px, py = 18 + TP - PIP_W - 12, y0 + TP - PIP_H - 12
                frame[py:py + PIP_H, px:px + PIP_W] = cv2.resize(fv, (PIP_W, PIP_H))
                cv2.rectangle(frame, (px - 1, py - 1), (px + PIP_W, py + PIP_H),
                              (235, 235, 235), 1, cv2.LINE_AA)
            if arrived(k, el):
                cv2.rectangle(frame, (18, y0), (18 + TP - 1, y0 + TP - 1),
                              (120, 215, 90), 6)
            cv2.rectangle(frame, (18, y0), (18 + 128, y0 + 34), COL[k], -1)
            cv2.putText(frame, NAME[k], (30, y0 + 25), cv2.FONT_HERSHEY_SIMPLEX,
                        .72, (255, 255, 255), 2, cv2.LINE_AA)
            audits.append(dict(video_frame=fi, run=k, source_time_s=t_s,
                               shown_frames=int(M.shown.sum())))
        frame[gy:gy + goal.shape[0], gx:gx + gw] = goal
        cv2.rectangle(frame, (gx - 2, gy - 2), (gx + gw + 1, gy + goal.shape[0] + 1),
                      GOLD, 3)
        cv2.putText(frame, 'goal image', (gx + 4, gy + goal.shape[0] + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, .55, GOLD, 1, cv2.LINE_AA)
        cv2.putText(frame, f'{el:5.1f} s   x{a.speed:g}', (W - 250, 46),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (190, 190, 190), 2, cv2.LINE_AA)
        if a.preview is not None:
            cv2.imwrite(a.out, frame); print('preview ->', a.out); return
        ff.stdin.write(frame.tobytes())
        if fi % 60 == 0: print(f'  {fi}/{nfr}', flush=True)
    ff.stdin.close()
    if ff.wait() != 0: raise RuntimeError('ffmpeg failed')
    late = [i for i, (t, arm_, _, _) in enumerate(M.items)
            if M.shown[i] and t > max(r.at(r.play) for r in arms.values())]
    Path(a.out).with_suffix('.audit.json').write_text(json.dumps(dict(
        reconstruction=str(M.root), joint_session=True,
        seam='Baseline reversed then GEM forward; shared release pose',
        scale_units_per_m=M.s,
        trajectories='reconstruction camera tracks, no registration',
        arrival={k: (None if r.latch_t is None else
                     dict(latched_at_run_s=r.latch_t - r.onset)) for k, r in arms.items()},
        goal_marker='ring at the pose where that run\'s own arrival module latched '
                    'on the goal image; not an independently surveyed goal position',
        display_choices=dict(path_smoothing_frames=13, path_decimation_m=0.09,
                             ribbon_occluded_by='only geometry >0.25 m above the floor',
                             ceiling_cut_m=1.10, elevation_deg=68),
        pose_causality='the joint session processed Baseline (recorded 09:19) before '
                       'GEM (09:08), so GEM poses were estimated with frames recorded '
                       'later in wall clock; the causal check below only covers when '
                       'points become visible, not what informed the poses',
        floor='plane through the joint camera track, dropped by mount height',
        clock={k: dict(onset_offset_s=r.onset - r.rt[0] / 1e9, stall_cut_s=r.cut_s,
                       playback_s=r.play) for k, r in arms.items()},
        causal_visibility_pass=not late, frames=len(audits)), indent=2))
    print(f'Rendered {a.out}; causal visibility {"PASS" if not late else "FAIL"}')


if __name__ == '__main__':
    main()

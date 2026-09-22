"""Simulated three-leg episode: one LingBot reconstruction, three coloured legs.

The episode is start -> A -> B(novel) -> C(revisit): B is a goal off leg A that
the agent has never seen (co-visibility 0.0), and C sends it back to a place it
passed on leg A, 402 frames earlier.  It is one continuous walk, so a single
LingBot session already puts all three legs in one frame -- none of the
cross-session registration the real-robot clips needed.

Unlike the robot, the simulator gives ground-truth poses, so the metric scale
and the goal positions are exact rather than fitted to odometry.

Trajectories are dense samples on the floor plane, splatted through the cloud's
z-buffer, and occluded only by geometry above the floor -- the floor's own depth
noise must not eat a marking painted on it.
"""
import argparse, glob, json, subprocess
from pathlib import Path

import cv2
import numpy as np

W, H = 1920, 1080
LX, LW = 18, 542
MAP_X, MAP_Y, MAP_W, MAP_H = 578, 14, 1324, 1052
LEG_COL = [(196, 176, 150), (56, 168, 250), (118, 216, 120)]     # BGR: A, B novel, C revisit
LEG_NAME = ['leg A', 'leg B  novel', 'leg C  revisit']
SRC = Path('/data/diagnostics/nav-graph-blind/multigoal_v4_quickpilot_r1_20260812'
           '/dhjEzFoUFzH/episode_0000')
GOAL_JPG = ['goal_image.jpg', 'goal_1.jpg', 'goal_2.jpg']


def ribbon(pts3, up, width_u, step_u):
    pts3 = np.asarray(pts3, float)
    if len(pts3) < 2: return np.zeros((0, 3))
    seg = np.diff(pts3, axis=0); L = np.linalg.norm(seg, axis=1)
    keep = L > 1e-9
    if not keep.any(): return np.zeros((0, 3))
    pts3, seg, L = pts3[np.r_[True, keep]], seg[keep], L[keep]
    cum = np.r_[0, np.cumsum(L)]
    sq = np.linspace(0, cum[-1], max(2, int(cum[-1] / step_u) + 1))
    idx = np.clip(np.searchsorted(cum, sq) - 1, 0, len(L) - 1)
    centre = pts3[idx] + seg[idx] * ((sq - cum[idx]) / L[idx])[:, None]
    tang = np.gradient(centre, axis=0)
    bad = np.linalg.norm(tang, axis=1) < 1e-12
    if bad.any(): tang[bad] = (seg[idx] / L[idx][:, None])[bad]
    side = np.cross(tang, up)
    side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-12
    k = max(2, int(width_u / step_u) + 1)
    off = np.linspace(-width_u / 2, width_u / 2, k)
    return (centre[:, None, :] + side[:, None, :] * off[None, :, None]).reshape(-1, 3)


def _basis2(up):
    e1 = np.cross(up, [1., 0, 0])
    if np.linalg.norm(e1) < 1e-6: e1 = np.cross(up, [0, 1., 0])
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(up, e1)


def disc(c, up, r, step):
    a = np.arange(-r, r + step, step); gx, gy = np.meshgrid(a, a)
    m = gx ** 2 + gy ** 2 <= r ** 2
    e1, e2 = _basis2(up)
    return c + gx[m][:, None] * e1 + gy[m][:, None] * e2


def ring(c, up, r, w, step):
    a = np.arange(-r - w, r + w + step, step); gx, gy = np.meshgrid(a, a)
    rr = np.hypot(gx, gy); m = (rr >= r - w) & (rr <= r + w)
    e1, e2 = _basis2(up)
    return c + gx[m][:, None] * e1 + gy[m][:, None] * e2


def chevrons(pts3, up, size_u, spacing_u):
    """Small V marks along a path, so overlapping legs still read directionally."""
    pts3 = np.asarray(pts3, float)
    if len(pts3) < 3: return np.zeros((0, 3))
    seg = np.diff(pts3, axis=0); L = np.linalg.norm(seg, axis=1)
    keep = L > 1e-9
    if not keep.any(): return np.zeros((0, 3))
    pts3, seg, L = pts3[np.r_[True, keep]], seg[keep], L[keep]
    cum = np.r_[0, np.cumsum(L)]
    out = []
    step = max(spacing_u, 1e-6)
    for sdist in np.arange(step, cum[-1] - step * 0.2, step):
        i = int(np.clip(np.searchsorted(cum, sdist) - 1, 0, len(L) - 1))
        c = pts3[i] + seg[i] * ((sdist - cum[i]) / L[i])
        t = seg[i] / L[i]
        sd = np.cross(t, up); sd /= np.linalg.norm(sd) + 1e-12
        tip = c + t * size_u
        for arm in (+1, -1):
            back = c - t * size_u * 0.25 + sd * arm * size_u * 0.85
            m = max(3, int(np.linalg.norm(tip - back) / (size_u * 0.12)))
            out.append(np.linspace(back, tip, m))
    return np.concatenate(out) if out else np.zeros((0, 3))


class SimMap:
    def __init__(self, w, h, elev=52.0, margin=0.95, zmax_m=2.2,
                 stride=2, conf_pct=50):
        g = json.loads(Path('sim_frame.json').read_text())
        self.root = Path(g['root']); self.s = g['scale']
        self.n = np.array(g['floor_n']); self.d = g['floor_d']
        self.sw = g['switches']; self.goals = np.array(g['goals_lingbot'])
        self.w, self.h, self.zmax = w, h, zmax_m
        self.stride, self.conf_pct = stride, conf_pct
        self.items = []
        for f in sorted(glob.glob(str(self.root / 'frames/*.npz'))):
            k = int(Path(f).stem)
            with np.load(f) as d: self.items.append((k, f, d['c2w'].copy()))
        self.keys = np.array([i[0] for i in self.items])
        self.C = np.array([i[2][:, 3] for i in self.items])
        self.leg = np.searchsorted(self.sw, self.keys, side='right')
        up = -self.n
        v = self.C[-1] - self.C[0]; v -= up * (v @ up); v /= np.linalg.norm(v)
        self.R = np.stack((np.cross(v, up), v, up))
        self.origin = self.to_floor(self.C[0][None])[0]
        self.gpath, self.gkeys = self._build_path_all()

        pts = []
        for i in range(0, len(self.items), 6):
            with np.load(self.items[i][1]) as p:
                q, _ = self.frame_points(p)
                T = self.items[i][2]
                pts.append(self.cut(q[::4] @ T[:3, :3].T + T[:3, 3]))
        P = self._disp(np.concatenate(pts + [self.C]))
        best = None
        for deg in range(0, 360, 3):
            b = self._bas(np.radians(deg), np.radians(elev))
            q = P @ b.T
            lo, hi = np.percentile(q[:, :2], [1.0, 99.0], axis=0)
            sc = min(w / max(hi[0] - lo[0], 1e-6), h / max(hi[1] - lo[1], 1e-6))
            if best is None or sc > best[0]: best = (sc, deg, b, lo, hi)
        _, self.az, self.basis, lo, hi = best
        cp = (self._disp(self.C) @ self.basis.T)[:, :2]
        lo = np.minimum(lo, cp.min(0)); hi = np.maximum(hi, cp.max(0))
        self.mid = (lo + hi) / 2
        self.scale = min(w / max(hi[0] - lo[0], 1e-6), h / max(hi[1] - lo[1], 1e-6)) * margin
        self.step_u = 0.40 / self.scale
        self.z = np.full(w * h, -np.inf)
        self.z_obs = np.full(w * h, -np.inf)
        self.raster = np.zeros((h * w, 3), np.uint8)
        self.shown = 0

    @staticmethod
    def _bas(az, elev):
        d = np.array([np.cos(elev) * np.cos(az), np.cos(elev) * np.sin(az), np.sin(elev)])
        r = np.array([-np.sin(az), np.cos(az), 0.])
        return np.stack((r, np.cross(d, r), d))

    def _disp(self, X): return (np.atleast_2d(X) - self.origin) @ self.R.T

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
        # curvature, not spread: a floor seen at a grazing angle is a steep but
        # SMOOTH ramp, and a max-min test throws it away past a few metres.  A
        # depth discontinuity instead breaks linearity, which the second
        # difference sees and the ramp does not.
        curv = np.abs(d - np.nanmean(nb, 0))
        spread = np.nanmax(nb, 0) - np.nanmin(nb, 0)
        flat = (np.isfinite(curv) & (curv < 0.012 * d)
                & np.isfinite(spread) & (spread < 0.35 * d))
        thr = np.percentile(conf[ok], self.conf_pct) if ok.any() else np.inf
        samp = np.zeros_like(ok); samp[::self.stride, ::self.stride] = True
        v, u = np.nonzero(ok & flat & samp & (conf >= thr))
        pts = (np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T) * d[v, u, None]
        return pts.astype(np.float32), npz['rgb'][v, u]

    def _build_path_all(self, smooth=13, step_m=0.09):
        """Smooth and thin the WHOLE walk once.

        Doing it per leg leaves a gap at each switch (9 and 12 cm here), because
        the smoothed, decimated ends of neighbouring legs do not meet.  One path
        split afterwards shares the boundary vertex exactly.
        """
        P, K = self.C.copy(), self.keys.copy()
        if len(P) < 2: return P, K
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
        return P[keep], K[keep]

    def leg_points(self, li, upto):
        """Leg li up to `upto`, sharing a vertex with the neighbouring legs."""
        lo = 0 if li == 0 else self.sw[li - 1]
        hi = self.sw[li] if li < len(self.sw) else self.gkeys[-1] + 1
        m = (self.gkeys >= lo) & (self.gkeys <= min(hi, upto))
        idx = np.flatnonzero(m)
        if len(idx) and idx[0] > 0: idx = np.r_[idx[0] - 1, idx]     # join backwards
        return self.gpath[idx]

    def pos_at(self, key):
        """Marker position ON the drawn path, not the raw camera centre: the
        raw one carries per-step sway and visibly shakes along a steady line."""
        K, P = self.gkeys, self.gpath
        j = int(np.clip(np.searchsorted(K, key) - 1, 0, len(K) - 2))
        f = np.clip((key - K[j]) / max(K[j + 1] - K[j], 1), 0, 1)
        return P[j] + (P[j + 1] - P[j]) * f

    def project(self, X):
        q = self._disp(X) @ self.basis.T
        return (np.rint(np.column_stack(
            ((q[:, 0] - self.mid[0]) * self.scale + self.w / 2,
             -(q[:, 1] - self.mid[1]) * self.scale + self.h / 2))).astype(int), q[:, 2])

    def splat(self, X, colors, raster, zbuf, spread=((0, 0), (1, 0), (0, 1)), update_z=True):
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
            near = zz[ids] > zbuf[pix]
            if update_z: zbuf[pix[near]] = zz[ids[near]]
            if raster is not None: raster[pix[near]] = colors[ids[near]]

    def reveal(self, upto_key):
        while self.shown < len(self.items) and self.items[self.shown][0] <= upto_key:
            k, f, T = self.items[self.shown]
            with np.load(f) as p:
                q, c = self.frame_points(p)
                X, C = self.cut(q @ T[:3, :3].T + T[:3, 3], c[:, ::-1])
                self.splat(X, C, self.raster, self.z)
                above = (self.d - X @ self.n) / self.s > 0.25
                if above.any(): self.splat(X[above], None, None, self.z_obs)
            self.shown += 1

    def here(self, key):
        j = int(np.clip(np.searchsorted(self.keys, key), 0, len(self.keys) - 1))
        return self.C[j]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--preview', type=int, default=None, help='source frame index')
    a = ap.parse_args()

    M = SimMap(MAP_W, MAP_H)
    man = json.loads(Path('outputs/sim_3leg_rgb/manifest.json').read_text())
    rgb_path = {r['key']: (Path('outputs/sim_3leg_rgb') / r['path']).resolve()
                for r in man['frames']}
    n_src = len(man['frames'])
    goals = [cv2.imread(str(SRC / g)) for g in GOAL_JPG]
    thumbs = [cv2.resize(g, (166, 94)) for g in goals]
    print(f'map: azimuth {M.az}deg, {M.scale * M.s:.1f} px/m, {len(M.items)} 帧, '
          f'switches {M.sw}')

    idx = [a.preview] if a.preview is not None else range(n_src)
    ff = None
    if a.preview is None:
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                               '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(a.fps),
                               '-i', '-', '-c:v', 'libx264', '-crf', '19',
                               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out],
                              stdin=subprocess.PIPE)
    up = -M.n
    for k in idx:
        if a.preview is not None:
            for kk in range(0, k + 1, 3): M.reveal(kk)
        M.reveal(k)
        leg = int(np.searchsorted(M.sw, k, side='right'))
        raster = M.raster.copy(); z = M.z_obs.copy()

        for li in range(leg + 1):
            P = M.leg_points(li, k)
            if len(P) < 2: continue
            # the three legs share corridors, so let finished ones sit back
            act = li == leg
            wide, dim = (0.34, 1.0) if act else (0.26, 0.72)
            col = (np.array(LEG_COL[li], float) * dim).astype(np.uint8)
            F = M.to_floor(P, 0.020)
            M.splat(ribbon(F, up, wide * M.s, M.step_u), col * 0.92, raster, z,
                    ((0, 0), (1, 0), (0, 1), (1, 1)))
            M.splat(ribbon(F, up, wide * 0.35 * M.s, M.step_u),
                    np.minimum(col.astype(int) + 70, 255), raster, z)
            M.splat(chevrons(F, up, 0.11 * M.s, 0.95 * M.s),
                    np.minimum(col.astype(int) + 120, 255), raster, z, ((0, 0),))
        for gi in range(leg + 1):
            gp = M.to_floor(M.goals[gi][None], 0.026)[0]
            c = np.array(LEG_COL[gi], np.uint8)
            reached = gi < leg
            M.splat(ring(gp, up, 0.42 * M.s, 0.05 * M.s, M.step_u), c, raster, z)
            if reached:
                M.splat(disc(gp, up, 0.16 * M.s, M.step_u), c, raster, z)
        cur = M.to_floor(M.pos_at(k)[None], 0.030)[0]
        M.splat(ring(cur, up, 0.20 * M.s, 0.038 * M.s, M.step_u),
                np.array([255, 255, 255], np.uint8), raster, z)
        M.splat(disc(cur, up, 0.09 * M.s, M.step_u),
                np.array(LEG_COL[leg], np.uint8), raster, z)

        frame = np.full((H, W, 3), (16, 14, 12), np.uint8)
        frame[MAP_Y:MAP_Y + MAP_H, MAP_X:MAP_X + MAP_W] = raster.reshape(MAP_H, MAP_W, 3)
        ob = cv2.imread(str(rgb_path[k]))
        oh = round(ob.shape[0] * LW / ob.shape[1])
        frame[14:14 + oh, LX:LX + LW] = cv2.resize(ob, (LW, oh))
        gy = 14 + oh + 26
        gh = round(goals[leg].shape[0] * LW / goals[leg].shape[1])
        frame[gy:gy + gh, LX:LX + LW] = cv2.resize(goals[leg], (LW, gh))
        cv2.rectangle(frame, (LX - 2, gy - 2), (LX + LW + 1, gy + gh + 1),
                      LEG_COL[leg], 3)
        cv2.putText(frame, 'onboard RGB', (LX + 6, 14 + oh + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, .58, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, 'current goal image', (LX + 6, gy + gh + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, .58, LEG_COL[leg], 1, cv2.LINE_AA)
        ty = gy + gh + 48
        for li in range(3):
            tx = LX + li * 180
            frame[ty:ty + 94, tx:tx + 166] = thumbs[li]
            on = li <= leg
            cv2.rectangle(frame, (tx - 2, ty - 2), (tx + 167, ty + 95),
                          LEG_COL[li] if on else (70, 70, 70), 3 if li == leg else 1)
            cv2.putText(frame, LEG_NAME[li], (tx, ty + 116), cv2.FONT_HERSHEY_SIMPLEX,
                        .46, LEG_COL[li] if on else (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(frame, f'{k / a.fps:5.1f} s', (W - 190, 46),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (190, 190, 190), 2, cv2.LINE_AA)
        if a.preview is not None:
            cv2.imwrite(a.out, frame); print('preview ->', a.out); return
        ff.stdin.write(frame.tobytes())
        if k % 60 == 0: print(f'  {k}/{n_src}', flush=True)
    ff.stdin.close()
    if ff.wait() != 0: raise RuntimeError('ffmpeg failed')
    Path(a.out).with_suffix('.audit.json').write_text(json.dumps(dict(
        reconstruction=str(M.root), source=str(SRC), scene=man['scene'],
        legs=dict(switches=M.sw, kinds=['-', 'novel', 'revisit']),
        scale_units_per_m=M.s,
        scale_and_goals='from ground-truth simulator poses, not fitted to odometry',
        floor='camera-track plane, offset to the cloud height histogram peak',
        trajectories='reconstruction camera tracks; occluded only by geometry '
                     '>0.25 m above the floor',
        playback='one simulator step per video frame', frames=n_src), indent=2))
    print(f'Rendered {a.out}')


if __name__ == '__main__':
    main()

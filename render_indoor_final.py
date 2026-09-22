"""Final indoor demo: GEM vs Baseline, each with its own LingBot reconstruction.

Trajectories are not overlaid on the render.  They are generated as dense
samples lying on the run's own floor plane and splatted through the same
z-buffer as the cloud, so furniture occludes them and they occlude the floor
behind -- they are in the cloud, not on top of it.

The floor plane comes from the camera track (the robot walks at fixed height
over flat floor), and metric scale from a Umeyama fit of body odometry onto the
LingBot camera track; see ground_frames.json.  The two runs are NOT merged:
their reconstructions differ by ~26 cm over the shared area, which no single
similarity removes, so each row shows its own self-consistent session.
"""
import argparse, glob, json, subprocess
from pathlib import Path

import cv2
import numpy as np

SCR = '/home/asus/Research/pengyue/gem_demo/../../..'
S = '/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad'
W, H = 1920, 1080
TP = 524
ROW_Y = (14, 552)
MAP_X, MAP_W = 556, 1346
PIP_W, PIP_H = 258, 146
COL = {'gem': (230, 155, 77), 'base': (72, 87, 240)}      # BGR
NAME = {'gem': 'GEM', 'base': 'Baseline'}


def umeyama_apply(P, g):
    return g['scale'] * (np.array(g['R']) @ np.asarray(P, float).T).T + np.array(g['t'])


class Run:
    def __init__(self, key, g):
        self.key, self.g = key, g
        self.root = Path(g['root'])
        meta = json.loads((self.root / 'reconstruction.json').read_text())
        self.meta = meta
        self.src = Path(meta['source_manifest']).parent
        self.rows = meta['frames']
        self.usable = [r for r in self.rows if not r['warming']]
        self.times = np.array([r['timestamp_ns'] for r in self.rows], np.int64)
        self.t0, self.t1 = self.rows[0]['timestamp_ns'], self.rows[-1]['timestamp_ns']
        self.s = g['scale']
        self.n = np.array(g['floor_n']); self.d = g['floor_d']
        # display frame: up = -floor normal, forward = principal horizontal travel
        up = -self.n
        C = np.array([np.load(self.root / r['prediction'])['c2w'][:, 3] for r in self.usable])
        self.C = C
        v = C[-1] - C[0]; v -= up * (v @ up)
        fwd = v / max(np.linalg.norm(v), 1e-9)
        self.R = np.stack((np.cross(fwd, up), fwd, up))
        self.origin = self.to_floor(C[0][None])[0]
        # odometry -> LingBot, then telemetry / plans in scratchpad
        tag = g['tag']
        self.tel = np.load(f'{S}/{tag}.npz')['tel']
        self.plans = list(np.load(f'{S}/demo_{tag}/plans.npy', allow_pickle=True))
        tp = json.loads(Path(f'{S}/tp_{tag}/index.json').read_text())
        self.tp_dir, self.tp_t0, self.tp_fps, self.tp_n, self.tp_last = (
            Path(f'{S}/tp_{tag}'), tp['t_first'], tp['fps'], tp['n'], tp['t_last'])
        self._clock()

    def _clock(self, dt=0.05, min_stall=2.5, keep_in=0.5, keep_out=0.3):
        """Playback clock: zeroed on the first real movement, with the Go2's
        dead stretches dropped, so the two rows set off together and neither
        sits frozen while the other walks."""
        T, t1 = self.tel, self.t1 / 1e9
        src = json.loads(Path(self.meta['source_manifest']).read_text())
        ms = src['motion_start_ns'] / 1e9
        Q = T[(T[:, 0] >= ms) & (T[:, 0] <= t1)]
        mv = ((np.linalg.norm(Q[:, 1:3] - Q[0, 1:3], axis=1) > 0.03) |
              (np.degrees(np.abs(np.unwrap(Q[:, 6]) - Q[0, 6])) > 3.0))
        onset = float(Q[int(np.argmax(mv)), 0]) if mv.any() else ms
        gr = np.arange(onset, t1, dt)
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
            else:
                i += 1
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
        self.onset = onset
        self.cut_s = float(cut.sum() * dt)
        self.play = len(self.kept) * dt

    def at(self, e):
        """Playback elapsed -> source time (seconds)."""
        return float(self.kept[int(np.clip(e / self.dt, 0, len(self.kept) - 1))])

    # ---- geometry helpers -------------------------------------------------
    def to_floor(self, X, lift=0.0):
        X = np.atleast_2d(np.asarray(X, float))
        return X - self.n * ((X @ self.n - self.d) - lift * self.s)[:, None]

    def odom_floor(self, P_xy, lift=0.015):
        P = np.c_[np.asarray(P_xy, float).reshape(-1, 2), np.zeros(len(np.atleast_2d(P_xy)))]
        return self.to_floor(umeyama_apply(P, self.g), lift)

    def pose(self, t):
        T = self.tel
        return (np.interp(t, T[:, 0], T[:, 1]), np.interp(t, T[:, 0], T[:, 2]),
                np.interp(t, T[:, 0], np.unwrap(T[:, 6])))

    def track_xy(self, t):
        T = self.tel
        m = (T[:, 0] >= self.t0 / 1e9) & (T[:, 0] <= t)
        return T[m][:, 1:3]

    def plan(self, t, hold=3.0):
        best = None
        for p in self.plans:
            if p['sel'] is None or not len(p['sel']): continue
            if p['t'] <= t and (best is None or p['t'] > best['t']): best = p
        return best if best is not None and t - best['t'] <= hold else None

    def third(self, t):
        k = int(round((t - self.tp_t0) * self.tp_fps))
        return (self.tp_dir / f'{np.clip(k, 0, self.tp_n - 1) + 1:05d}.jpg',
                t <= self.tp_last + 1e-6)


def ribbon(pts3, up, width_u, step_u):
    """Dense floor samples for a polyline: a band of width_u, spacing step_u."""
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
    frac = ((sq - cum[idx]) / L[idx])[:, None]
    centre = pts3[idx] + seg[idx] * frac
    tang = seg[idx] / L[idx][:, None]
    side = np.cross(tang, up)
    side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-12
    k = max(2, int(width_u / step_u) + 1)
    off = np.linspace(-width_u / 2, width_u / 2, k)
    return (centre[:, None, :] + side[:, None, :] * off[None, :, None]).reshape(-1, 3)


def disc(centre, up, r_u, step_u):
    a = np.arange(-r_u, r_u + step_u, step_u)
    gx, gy = np.meshgrid(a, a)
    m = gx ** 2 + gy ** 2 <= r_u ** 2
    e1 = np.cross(up, [1., 0, 0])
    if np.linalg.norm(e1) < 1e-6: e1 = np.cross(up, [0, 1., 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    return centre + gx[m][:, None] * e1 + gy[m][:, None] * e2


def ring(centre, up, r_u, w_u, step_u):
    a = np.arange(-r_u - w_u, r_u + w_u + step_u, step_u)
    gx, gy = np.meshgrid(a, a)
    rr = np.hypot(gx, gy)
    m = (rr >= r_u - w_u) & (rr <= r_u + w_u)
    e1 = np.cross(up, [1., 0, 0])
    if np.linalg.norm(e1) < 1e-6: e1 = np.cross(up, [0, 1., 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    return centre + gx[m][:, None] * e1 + gy[m][:, None] * e2


class Panel:
    """One run's fixed-camera raster with a persistent z-buffer."""

    def __init__(self, run, w, h, elev=58.0, margin=0.95, zmax_m=1.45):
        self.run, self.w, self.h = run, w, h
        self.zmax = zmax_m
        pts = []
        for r in run.usable[::5]:
            p = np.load(run.root / r['prediction'])
            T = p['c2w']
            q, _ = self.frame_points(p)
            pts.append(self.cut(q[::4] @ T[:3, :3].T + T[:3, 3]))
        P = self._disp(np.concatenate(pts + [run.C]))
        # pick the azimuth that makes the scene largest in the panel
        best = None
        for deg in range(0, 360, 3):
            b = self._basis(np.radians(deg), np.radians(elev))
            q = P @ b.T
            lo, hi = np.percentile(q[:, :2], [0.3, 99.7], axis=0)
            sc = min(w / max(hi[0] - lo[0], 1e-6), h / max(hi[1] - lo[1], 1e-6))
            if best is None or sc > best[0]: best = (sc, deg, b, lo, hi)
        _, self.az, self.basis, lo, hi = best
        cp = (self._disp(run.C) @ self.basis.T)[:, :2]
        lo = np.minimum(lo, cp.min(0)); hi = np.maximum(hi, cp.max(0))
        self.mid = (lo + hi) / 2
        self.scale = min(w / max(hi[0] - lo[0], 1e-6),
                         h / max(hi[1] - lo[1], 1e-6)) * margin
        self.z = np.full(w * h, -np.inf)
        self.raster = np.zeros((h * w, 3), np.uint8)
        self.pending = 0
        self.step_u = 0.55 / self.scale          # world units per ~half pixel

    def frame_points(self, npz):
        """Unproject one frame, dropping depth-edge artefacts.

        Unprojecting a pixel that straddles a depth discontinuity puts a point
        somewhere between the two surfaces; over a run these form the radial
        curtains that hide the floor and make the map look furry.  A pixel is
        kept only where its 3x3 depth neighbourhood is locally flat.
        """
        d, conf, K = npz['depth'], npz['conf'], npz['K']
        h, w = d.shape
        ok = np.isfinite(d) & (d > 0) & np.isfinite(conf)
        pad = np.where(ok, d, np.nan)
        pad = np.pad(pad, 1, constant_values=np.nan)
        nb = np.stack([pad[i:i + h, j:j + w] for i in range(3) for j in range(3)])
        spread = np.nanmax(nb, 0) - np.nanmin(nb, 0)
        flat = np.isfinite(spread) & (spread < 0.035 * d)
        thr = np.percentile(conf[ok], 65) if ok.any() else np.inf
        sample = np.zeros_like(ok)
        sample[::4, ::4] = True
        v, u = np.nonzero(ok & flat & sample & (conf >= thr))
        pts = (np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T) * d[v, u, None]
        return pts.astype(np.float32), npz['rgb'][v, u]

    def cut(self, X, rgb=None):
        """Drop the ceiling: from above it would hide the floor and the paths."""
        hh = (self.run.d - np.asarray(X) @ self.run.n) / self.run.s
        m = (hh > -0.08) & (hh < self.zmax)
        return X[m] if rgb is None else (X[m], rgb[m])

    @staticmethod
    def _basis(az, elev):
        d = np.array([np.cos(elev) * np.cos(az), np.cos(elev) * np.sin(az), np.sin(elev)])
        r = np.array([-np.sin(az), np.cos(az), 0.])
        return np.stack((r, np.cross(d, r), d))

    def _disp(self, X):
        return (np.atleast_2d(X) - self.run.origin) @ self.run.R.T

    def project(self, X):
        q = self._disp(X) @ self.basis.T
        uv = np.column_stack(((q[:, 0] - self.mid[0]) * self.scale + self.w / 2,
                              -(q[:, 1] - self.mid[1]) * self.scale + self.h / 2))
        return np.rint(uv).astype(int), q[:, 2]

    def splat(self, X, colors, raster, zbuf, spread=((0, 0), (1, 0), (0, 1)), tol=0.0):
        """tol lets a mark be painted onto a surface: it wins against geometry
        within tol of its own depth (the floor, whose points are noisy by a few
        cm at range) but still loses to anything genuinely in front."""
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
            zbuf[pix[nearer]] = zz[ids[nearer]]
            raster[pix[nearer]] = colors[ids[nearer]]

    def add_cloud_until(self, t_ns):
        grew = False
        while self.pending < len(self.run.usable) and \
                self.run.usable[self.pending]['timestamp_ns'] <= t_ns:
            row = self.run.usable[self.pending]
            with np.load(self.run.root / row['prediction']) as p:
                T = p['c2w']
                q, c = self.frame_points(p)
                X, C = self.cut(q @ T[:3, :3].T + T[:3, 3], c[:, ::-1])
                self.splat(X, C, self.raster, self.z)
            self.pending += 1; grew = True
        return grew

    def compose(self, t_s):
        """Cloud plus everything that lies on the floor, in one z-buffer."""
        raster = self.raster.copy(); z = self.z.copy()
        run, up = self.run, -self.run.n
        # the cloud's own floor points scatter a few cm; sit above that spread
        # or they occlude the ribbon from this angle
        lift, step = 0.020, self.step_u
        tol = 0.16 * run.s          # depth slack, in model units
        col = np.array(COL[run.key], np.uint8)

        xy = run.track_xy(t_s)
        if len(xy) > 3:
            P = run.odom_floor(xy[::3], lift)
            self.splat(ribbon(P, up, 0.34 * run.s, step), col * 0.92, raster, z, tol=tol)
            self.splat(ribbon(P, up, 0.12 * run.s, step), np.minimum(col.astype(int) + 70, 255),
                       raster, z, tol=tol)
        p = run.plan(t_s)
        if p is not None:
            x, y, yw = run.pose(t_s)
            Rw = np.array([[np.cos(yw), -np.sin(yw)], [np.sin(yw), np.cos(yw)]])
            w2 = lambda A: run.odom_floor(np.asarray(A)[:, :2] @ Rw.T + [x, y], lift + 0.010)
            q = np.array(p['q'], float) if len(p['q']) else np.zeros(len(p['cand']))
            lo_, hi_ = (np.nanmin(q), np.nanmax(q)) if len(q) else (0., 1.)
            for k, cc in enumerate(p['cand']):
                if cc is None or len(cc) < 2: continue
                a = 0.35 + 0.55 * (0.5 if hi_ - lo_ < 1e-6 else (q[k] - lo_) / (hi_ - lo_))
                self.splat(ribbon(w2(cc), up, 0.055 * run.s, step),
                           np.full(3, int(70 + 165 * a)), raster, z, ((0, 0),), tol=tol)
            self.splat(ribbon(w2(p['sel']), up, 0.11 * run.s, step),
                       np.array([250, 235, 215], np.uint8), raster, z, tol=tol)
        x, y, _ = run.pose(t_s)
        c = run.odom_floor([[x, y]], lift + 0.020)[0]
        self.splat(ring(c, up, 0.19 * run.s, 0.035 * run.s, step),
                   np.array([255, 255, 255], np.uint8), raster, z, tol=tol)
        self.splat(disc(c, up, 0.085 * run.s, step), col, raster, z, tol=tol)
        return raster.reshape(self.h, self.w, 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--speed', type=float, default=2.0)
    ap.add_argument('--preview', type=float, default=None)
    a = ap.parse_args()

    G = json.loads(Path('ground_frames.json').read_text())
    runs = {k: Run(k, G[k]) for k in ('gem', 'base')}
    panels = {k: Panel(r, MAP_W, TP) for k, r in runs.items()}
    for k, p in panels.items():
        print(f'{k}: azimuth {p.az}deg, {p.scale:.1f} px/unit '
              f'({p.scale / runs[k].s:.1f} px/m)')

    goal = None
    gj = Path('ground_frame.json')
    if gj.exists():
        pass                                   # goal marker resolved below from survey reg

    for k, r in runs.items():
        print(f'{k}: 起动 +{r.onset - r.t0/1e9:.2f}s, 剪掉卡顿 {r.cut_s:.1f}s, '
              f'播放 {r.play:.1f}s')
    dur = max(r.play for r in runs.values())
    nfr = int(np.ceil(dur / a.speed * a.fps)) + 1
    idx = [int(round(a.preview / a.speed * a.fps))] if a.preview is not None else range(nfr)

    ff = None
    if a.preview is None:
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                               '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(a.fps),
                               '-i', '-', '-c:v', 'libx264', '-crf', '19',
                               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out],
                              stdin=subprocess.PIPE)
    audits = []
    for fi in idx:
        el = fi / a.fps * a.speed
        frame = np.full((H, W, 3), (16, 14, 12), np.uint8)
        for k, y0 in (('gem', ROW_Y[0]), ('base', ROW_Y[1])):
            run, pan = runs[k], panels[k]
            t_s = run.at(min(el, run.play))
            t_ns = int(round(t_s * 1e9))
            done = el > run.play
            pan.add_cloud_until(t_ns)
            frame[y0:y0 + TP, MAP_X:MAP_X + MAP_W] = pan.compose(t_s)

            tp_path, live = run.third(t_s)
            tp = cv2.imread(str(tp_path))
            if tp is not None:
                frame[y0:y0 + TP, 18:18 + TP] = cv2.resize(tp, (TP, TP))
                if not live or done:
                    sub = frame[y0:y0 + TP, 18:18 + TP]
                    frame[y0:y0 + TP, 18:18 + TP] = (sub * 0.5).astype(np.uint8)
            i = max(0, int(np.searchsorted(run.times, t_ns, side='right') - 1))
            rgb = cv2.imread(str(run.src / run.rows[i]['path']))
            if rgb is not None:
                px, py = 18 + TP - PIP_W - 12, y0 + TP - PIP_H - 12
                frame[py:py + PIP_H, px:px + PIP_W] = cv2.resize(rgb, (PIP_W, PIP_H))
                cv2.rectangle(frame, (px - 1, py - 1), (px + PIP_W, py + PIP_H),
                              (235, 235, 235), 1, cv2.LINE_AA)
            c = COL[k]
            cv2.rectangle(frame, (18, y0), (18 + 128, y0 + 34), c, -1)
            cv2.putText(frame, NAME[k], (30, y0 + 25), cv2.FONT_HERSHEY_SIMPLEX,
                        .72, (255, 255, 255), 2, cv2.LINE_AA)
            audits.append(dict(video_frame=fi, run=k, source_timestamp_ns=int(t_ns),
                               cloud_frames=pan.pending,
                               latest_geometry_timestamp_ns=(
                                   run.usable[pan.pending - 1]['timestamp_ns']
                                   if pan.pending else None)))
        cv2.putText(frame, f'{el:5.1f} s   x{a.speed:g}', (W - 250, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (190, 190, 190), 2, cv2.LINE_AA)
        if a.preview is not None:
            cv2.imwrite(a.out, frame); print('preview ->', a.out); return
        ff.stdin.write(frame.tobytes())
        if fi % 60 == 0: print(f'  {fi}/{nfr}', flush=True)
    ff.stdin.close()
    if ff.wait() != 0: raise RuntimeError('ffmpeg failed')
    ok = all(x['latest_geometry_timestamp_ns'] is None or
             x['latest_geometry_timestamp_ns'] <= x['source_timestamp_ns'] for x in audits)
    Path(a.out).with_suffix('.audit.json').write_text(json.dumps(dict(
        runs={k: dict(root=str(r.root), scale_units_per_m=r.s,
                      odom_rmse_m=G[k]['odom_rmse_m'],
                      track_plane_p95_cm=G[k]['track_plane_p95_cm']) for k, r in runs.items()},
        merged=False,
        clock='zeroed on first real movement; commanded-but-stationary stretches dropped',
        per_run_clock={k: dict(onset_offset_s=r.onset - r.t0 / 1e9,
                               stall_cut_s=r.cut_s, playback_s=r.play)
                       for k, r in runs.items()},
        merge_note='reconstructions not merged: cross-session overlap median 25.8 cm '
                   'after trimmed similarity ICP, so each row shows its own session',
        trajectories='floor-plane ribbons splatted through the cloud z-buffer',
        causal_visibility_pass=bool(ok), frames=audits), indent=2))
    print(f'Rendered {a.out}; causal visibility {"PASS" if ok else "FAIL"}')


if __name__ == '__main__':
    main()

"""Three-view demo for the 2026-09-19 indoor scene: GEM against the Baseline.

Each arm gets a third-person panel from the handheld clip, with its onboard view
inset.  The shared bird's-eye panel is built rather than pre-drawn: the survey
pass is laid down dim, as the map GEM carries in, and the floor each arm sees
fills in as it walks, so the map grows with the run.

Clocks: both arms are zeroed on the moment the robot actually starts moving, and
stretches where the Go2 was commanded forward but stayed put are dropped.
"""
import os, json, argparse, subprocess
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle, FancyArrow
import matplotlib.patheffects as pe
from scipy import ndimage
from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
CAP = ("/home/asus/Research/Nav-graph-blind/projects/realworld/runtime/experiment_archives/"
       "jetson_20260919/jetson/runtime/go2/experiment_capture")
GOAL_IMG = f"{CAP}/episode_20260919T090850_042322Z/media/revisit_goal.png"
GEMC, BASEC, HIST, GOLD = '#4D9BE6', '#F0574A', '#4ECB8D', '#FFC93C'
BG, HALO = '#000000', '#000000'
plt.rcParams.update({'font.family': 'DejaVu Sans'})

W, H = 1920.0, 1080.0
TP = 519                                   # third-person panel, square
TP_X, TP_Y = 18, (14, 547)
PIP_W, PIP_H = 262, 148
BEV_X, BEV_Y, BEV_W, BEV_H = 561, 14, 1341, 1052


class Run:
    def __init__(self, tag, arm_col):
        d = os.path.join(S, f'demo_{tag}')
        self.tag, self.dir, self.col = tag, d, arm_col
        self.times = np.load(d + '/times.npy')
        self.plans = list(np.load(d + '/plans.npy', allow_pickle=True))
        w = json.load(open(d + '/win.json'))
        self.t0, self.t1 = w['t0'], w['t1']
        self.tel = np.load(os.path.join(S, f'{tag}.npz'))['tel']
        arr = json.load(open(d + '/arrival.json'))
        self.at = np.array([r[0] for r in arr], float)
        self.alat = np.array([bool(r[1].get('arrival_latched')) for r in arr])
        tp = json.load(open(os.path.join(S, f'tp_{tag}/index.json')))
        self.tp_dir = os.path.join(S, f'tp_{tag}')
        self.tp_t0, self.tp_fps, self.tp_n = tp['t_first'], tp['fps'], tp['n']
        self.tp_last = tp['t_last']
        self._clock()

    def _clock(self, dt=0.05, min_stall=2.5, keep_in=0.5, keep_out=0.3):
        T = self.tel
        Q = T[(T[:, 0] >= self.t0) & (T[:, 0] <= self.t1)]
        mv = ((np.linalg.norm(Q[:, 1:3] - Q[0, 1:3], axis=1) > 0.03) |
              (np.degrees(np.abs(np.unwrap(Q[:, 6]) - Q[0, 6])) > 3.0))
        if mv.any(): self.t0 = float(Q[int(np.argmax(mv)), 0])
        gr = np.arange(self.t0, self.t1, dt)
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
        self.dur = len(self.kept) * dt

    def src(self, e):
        if e < 0: return self.kept[0] + e
        return float(self.kept[int(np.clip(e / self.dt, 0, len(self.kept) - 1))])

    def fpv(self, t):
        return os.path.join(self.dir, 'rgb',
                            '%05d.jpg' % int(np.argmin(np.abs(self.times - t))))

    def third(self, t):
        k = int(round((t - self.tp_t0) * self.tp_fps))
        return (os.path.join(self.tp_dir, '%05d.jpg' % (np.clip(k, 0, self.tp_n - 1) + 1)),
                t <= self.tp_last + 1e-6)

    def pose(self, t):
        T = self.tel
        return (np.interp(t, T[:, 0], T[:, 1]), np.interp(t, T[:, 0], T[:, 2]),
                np.interp(t, T[:, 0], np.unwrap(T[:, 6])))

    def trace(self, t):
        T = self.tel
        return T[(T[:, 0] >= self.t0) & (T[:, 0] <= max(t, self.t0 + 1e-3)), 1:3]

    def plan(self, t, hold=3.0):
        best = None
        for p in self.plans:
            if p['sel'] is None or not len(p['sel']): continue
            if p['t'] <= t and (best is None or p['t'] > best['t']): best = p
        return best if (best is not None and t - best['t'] <= hold) else None

    def latched(self, t):
        if not len(self.at): return False
        i = int(np.searchsorted(self.at, t) - 1)
        return bool(self.alat[i]) if i >= 0 else False


def rot(P, th):
    c, s = np.cos(th), np.sin(th)
    return np.asarray(P, float) @ np.array([[c, -s], [s, c]]).T


def pick_rotation(pts, aspect, prefer=None):
    sc = []
    for deg in range(0, 360):
        th = np.radians(deg); Q = rot(pts, th)
        w, h = Q[:, 0].ptp() + 2.0, Q[:, 1].ptp() + 2.0
        sc.append((min(aspect / w, 1.0 / h) if w > 0 and h > 0 else 0.0, th))
    best = max(s for s, _ in sc)
    near = [th for s, th in sc if s >= 0.985 * best]
    if prefer is None: return near[0]
    v = np.asarray(prefer, float); v = v / max(np.linalg.norm(v), 1e-9)
    return max(near, key=lambda th: rot(v, th)[0])


def build(out, speed=3.0, fps=30, lead=1.5, tail=3.0, preview=None):
    gem, base = Run('n_cec1', GEMC), Run('n_base1', BASEC)
    reg = json.load(open(os.path.join(S, 'survey_reg.json')))
    goal = np.array(reg['goal_xy'])

    d = np.load(os.path.join(S, 'n_grid.npz'), allow_pickle=True)
    if ('time_basis' not in d or str(d['time_basis']) != 'absolute_ros_seconds'
            or 'bucket_timestamp' not in d or str(d['bucket_timestamp']) != 'last_observation'):
        raise ValueError('Rebuild n_grid.npz with grid_prog.py: legacy buckets use relative/start times.')
    NY, NX = d['shape']; lo = d['lo']; res = float(d['res'])
    ncell = int(NY) * int(NX)

    occ0 = np.zeros(int(NY) * int(NX), bool)
    for k in ('n_cec1', 'n_base1'): occ0[d[f'{k}_idx']] = True
    o0 = np.nonzero(occ0)[0]
    pts = np.vstack([gem.trace(gem.t1), base.trace(base.t1), goal[None, :],
                     np.c_[lo[0] + (o0 % int(NX) + 0.5) * res,
                           lo[1] + (o0 // int(NX) + 0.5) * res][::53]])
    rel = gem.trace(gem.t0 + .2)[0]
    th = pick_rotation(pts, aspect=BEV_W / BEV_H, prefer=goal - rel)
    # the finished map, not just the paths, decides how the panel is framed
    occ = np.zeros(int(NY) * int(NX), bool)
    for k in ('n_cec1', 'n_base1'): occ[d[f'{k}_idx']] = True
    oi = np.nonzero(occ)[0]
    ox = lo[0] + (oi % int(NX) + 0.5) * res
    oy = lo[1] + (oi // int(NX) + 0.5) * res
    allp = np.vstack([rot(gem.trace(gem.t1), th), rot(base.trace(base.t1), th),
                      rot(goal, th)[None, :], rot(np.c_[ox, oy][::37], th)])
    cx = 0.5 * (allp[:, 0].min() + allp[:, 0].max())
    cy = 0.5 * (allp[:, 1].min() + allp[:, 1].max())
    pad = max(1.2, 0.13 * max(allp[:, 0].ptp(), allp[:, 1].ptp()))
    half_w = max(allp[:, 0].ptp() / 2 + pad, (allp[:, 1].ptp() / 2 + pad) * BEV_W / BEV_H)
    half_h = half_w * BEV_H / BEV_W

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    def ax_at(x, y, w, h):
        return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    # ---- third-person panels, onboard view inset
    panes = {}
    for run, name, y0 in [(gem, 'GEM', TP_Y[0]), (base, 'Baseline', TP_Y[1])]:
        a = ax_at(TP_X, y0, TP, TP); a.set_axis_off()
        a.set_xlim(0, 540); a.set_ylim(540, 0)
        im3 = a.imshow(np.zeros((540, 540, 3), np.uint8), extent=[0, 540, 540, 0], zorder=1)
        wash = a.add_patch(Rectangle((0, 0), 540, 540, facecolor='#000000', alpha=0.0,
                                     edgecolor='none', zorder=6))
        ok = a.add_patch(Rectangle((3, 3), 534, 534, facecolor='none', edgecolor='#3FD98A',
                                   lw=7, zorder=7, visible=False))
        a.text(0.018, 0.972, name, transform=a.transAxes, fontsize=19, weight='bold',
               color='white', ha='left', va='top', zorder=9,
               bbox=dict(boxstyle='round,pad=0.32', fc=run.col, ec='none'))
        p = ax_at(TP_X + TP - PIP_W - 10, y0 + TP - PIP_H - 10, PIP_W, PIP_H)
        p.set_xticks([]); p.set_yticks([])
        for sp in p.spines.values(): sp.set_color('#FFFFFF'); sp.set_linewidth(2)
        im1 = p.imshow(np.zeros((480, 848, 3), np.uint8))
        panes[run.tag] = dict(ax=a, im3=im3, im1=im1, wash=wash, ok=ok)

    # ---- bird's-eye
    m = ax_at(BEV_X, BEV_Y, BEV_W, BEV_H)
    m.set_xticks([]); m.set_yticks([])
    for sp in m.spines.values(): sp.set_visible(False)
    m.set_facecolor(BG)
    ext = [lo[0], lo[0] + int(NX) * res, lo[1], lo[1] + int(NY) * res]
    tr = matplotlib.transforms.Affine2D().rotate(th) + m.transData

    grid_im = m.imshow(np.zeros((int(NY), int(NX), 4), np.float32), origin='lower',
                       extent=ext, transform=tr, zorder=2, interpolation='nearest')
    m.plot(*rot(goal, th), marker='*', ms=34, mfc=GOLD, mec=HALO, mew=1.6, zorder=10, ls='none')
    m.plot(*rot(rel, th), marker='o', ms=13, mfc='none', mec='white', mew=2.6, zorder=10, ls='none')

    ends = {r.tag: rot(r.trace(r.t1)[-1], th) for r in (gem, base)}
    endart, trails, dots, fans, plans = {}, {}, {}, {}, {}
    for run in (gem, base):
        trails[run.tag], = m.plot([], [], color=run.col, lw=4.6, solid_capstyle='round',
                                  zorder=6, path_effects=[pe.withStroke(linewidth=7.5,
                                                                        foreground=HALO)])
        fans[run.tag] = m.add_collection(
            LineCollection([], colors='#FFFFFF', linewidths=1.6, zorder=7))
        plans[run.tag], = m.plot([], [], color=run.col, lw=3.0, ls=(0, (2.5, 1.8)), alpha=.95,
                                 zorder=8, path_effects=[pe.withStroke(linewidth=4.6,
                                                                       foreground=HALO)])
        dots[run.tag], = m.plot([], [], marker='o', ms=15, mfc=run.col, mec='white', mew=2.0,
                                zorder=9, ls='none')
    heads = {r.tag: m.add_patch(FancyArrow(0, 0, 0, 0, width=0.001, color='none', zorder=9))
             for r in (gem, base)}

    # ---- the goal image, in whichever corner the runs leave clear
    gi = Image.open(GOAL_IMG).convert('RGB'); gi.thumbnail((300, 300))
    sx = BEV_W / (2 * half_w)
    gw, gh = (gi.width + 30) / sx, (gi.height + 30) / sx
    occ = []
    for kx, ky in ((0, 0), (1, 0), (0, 1), (1, 1)):
        bx = cx - half_w + kx * (2 * half_w - gw)
        by = cy + half_h - gh - ky * (2 * half_h - gh)
        inb = ((allp[:, 0] > bx) & (allp[:, 0] < bx + gw) &
               (allp[:, 1] > by) & (allp[:, 1] < by + gh))
        occ.append((int(inb.sum()), kx, ky))
    _, gkx, gky = min(occ)
    ga = ax_at(BEV_X + 15 + gkx * (BEV_W - gi.width - 30),
               BEV_Y + 15 + gky * (BEV_H - gi.height - 30), gi.width, gi.height)
    ga.imshow(np.asarray(gi)); ga.set_xticks([]); ga.set_yticks([])
    for sp in ga.spines.values(): sp.set_color(GOLD); sp.set_linewidth(3)

    sb = 2.0 if half_w < 9 else 5.0
    # park the scale bar in whichever corner the runs and the survey stay out of
    bw, bh = sb + 0.8, 1.1
    occ = []
    for kx, ky in [c for c in ((0, 0), (1, 0), (0, 1), (1, 1))
                   if c != (gkx, gky)]:
        bx = cx - half_w + 0.3 + kx * (2 * half_w - bw - 0.6)
        by = cy + half_h - 0.3 - bh - ky * (2 * half_h - bh - 0.6)
        inb = ((allp[:, 0] > bx) & (allp[:, 0] < bx + bw) &
               (allp[:, 1] > by) & (allp[:, 1] < by + bh))
        occ.append((int(inb.sum()), kx, ky, bx, by))
    _, _, _, bx, by = min(occ)
    x0, y0s = bx + 0.4, by + 0.62
    m.plot([x0, x0 + sb], [y0s, y0s], color='white', lw=3.4, zorder=11, solid_capstyle='butt')
    m.annotate(f'{sb:.0f} m', (x0 + sb / 2, y0s - 0.12), ha='center', va='top', fontsize=15,
               color='white', weight='bold', zorder=11)

    # ---- the map, accumulated from nothing
    nf = np.zeros(ncell); no = np.zeros(ncell)
    hm = np.zeros(ncell, np.float32); rs = np.zeros(ncell * 3)
    seen = np.full(ncell, -1e9, np.float32); owner = np.zeros(ncell, np.int8)
    nxt = {r.tag: 0 for r in (gem, base)}
    canvas = np.zeros((int(NY), int(NX), 4), np.float32)
    ARM = {gem.tag: 0, base.tag: 1}
    GLOW = np.array([[0.32, 0.63, 0.92], [0.95, 0.36, 0.30]], np.float32)
    FADE, OBS = 1.8, 10                      # lit seconds; hits before a cell is obstacle

    def add_buckets(run, t, el):
        bt = d[f'{run.tag}_t']; ptr = d[f'{run.tag}_ptr']
        k = nxt[run.tag]
        while k < len(bt) and bt[k] <= t:
            sl = slice(ptr[k], ptr[k + 1])
            i2 = d[f'{run.tag}_idx'][sl]
            f2 = d[f'{run.tag}_nf'][sl].astype(np.float64)
            o2 = d[f'{run.tag}_no'][sl].astype(np.float64)
            c2 = d[f'{run.tag}_rgb'][sl].astype(np.float64)
            h2 = d[f'{run.tag}_h'][sl].astype(np.float32)
            nf[:] += np.bincount(i2, weights=f2, minlength=ncell)
            no[:] += np.bincount(i2, weights=o2, minlength=ncell)
            np.maximum.at(hm, i2, h2)
            for ch in range(3):
                rs[ch::3] += np.bincount(i2, weights=c2[:, ch] * f2, minlength=ncell)
            seen[i2] = el; owner[i2] = ARM[run.tag]
            k += 1
        grew = k != nxt[run.tag]
        nxt[run.tag] = k
        return grew

    cache = {}

    def repaint(el, grew):
        if grew or 'base' not in cache:
            known = (nf + no) > 0
            obs = no >= OBS
            g = np.zeros(ncell)
            for ch, wt in zip(range(3), (0.299, 0.587, 0.114)):
                g += rs[ch::3] / np.maximum(nf, 1) * wt
            rgb = np.zeros((ncell, 3), np.float32)
            free = (g / 255.0 * 0.20 + 0.13)
            rgb[:, 0] = free * 0.92; rgb[:, 1] = free * 0.97; rgb[:, 2] = free * 1.15
            hh = np.clip(hm / 1.3, 0, 1)
            rgb[obs, 0] = (0.38 + 0.44 * hh[obs])
            rgb[obs, 1] = (0.45 + 0.38 * hh[obs])
            rgb[obs, 2] = (0.54 + 0.30 * hh[obs])
            cache['base'] = rgb; cache['known'] = known
        rgb, known = cache['base'].copy(), cache['known']
        glow = np.clip(1.0 - (el - seen) / FADE, 0.0, 1.0)
        glow[~known] = 0.0
        gc = GLOW[np.clip(owner, 0, 1)]
        rgb = rgb * (1 - glow[:, None]) + gc * glow[:, None]
        canvas[..., :3] = rgb.reshape(int(NY), int(NX), 3)
        canvas[..., 3] = known.reshape(int(NY), int(NX)).astype(np.float32)
        grid_im.set_data(canvas)

    total = max(gem.dur, base.dur) + lead + tail
    nfr = int(total / speed * fps)
    idx = [int(preview / speed * fps)] if preview is not None else range(nfr)
    proc = None
    if preview is None:
        proc = subprocess.Popen(
            ['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '1920x1080',
             '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
             '-crf', '20', '-preset', 'medium', '-movflags', '+faststart', out],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if preview is not None:                      # replay the map up to the preview instant,
        for e in np.arange(0, preview, 0.2):     # so cells carry the time they were first seen
            for run in (gem, base):
                add_buckets(run, run.src(min(e, run.dur)), float(e))
        cache.clear()

    for fi in idx:
        el = fi / fps * speed - lead
        grew = False
        for run in (gem, base):
            pane = panes[run.tag]
            t = run.src(min(max(el, -lead), run.dur))
            done = el > run.dur
            im, live = run.third(t)
            pane['im3'].set_data(np.asarray(Image.open(im)))
            pane['im1'].set_data(np.asarray(Image.open(run.fpv(t))))
            lat = run.latched(run.t1 + 1.0 if done else t)
            pane['wash'].set_alpha(0.55 if not live else (0.45 if (done and not lat) else 0.0))
            pane['ok'].set_visible(bool(lat))

            if el >= 0: grew |= add_buckets(run, t, el)
            tr_ = rot(run.trace(t), th)
            if len(tr_) < 2: tr_ = np.repeat(rot(run.pose(run.t0)[:2], th)[None, :], 2, 0)
            trails[run.tag].set_data(tr_[:, 0], tr_[:, 1])
            x, y, yw = run.pose(t)
            px, py = rot(np.array([x, y]), th)
            dots[run.tag].set_data([px], [py])
            heads[run.tag].remove()
            heads[run.tag] = m.add_patch(
                FancyArrow(px, py, np.cos(yw + th) * .62, np.sin(yw + th) * .62, width=.07,
                           head_width=.30, head_length=.26, length_includes_head=True,
                           color=run.col, zorder=9,
                           path_effects=[pe.withStroke(linewidth=3.2, foreground=HALO)]))
            p = run.plan(t) if (el >= 0 and not done) else None
            if p is not None:
                Rw = np.array([[np.cos(yw), -np.sin(yw)], [np.sin(yw), np.cos(yw)]])
                to_w = lambda P: rot(np.asarray(P)[:, :2] @ Rw.T + np.array([x, y]), th)
                q = np.array(p['q'], float) if len(p['q']) else np.zeros(len(p['cand']))
                lo_, hi_ = (np.nanmin(q), np.nanmax(q)) if len(q) else (0.0, 1.0)
                sg, cl = [], []
                for k2, cc in enumerate(p['cand']):
                    if cc is None or len(cc) < 2: continue
                    sg.append(to_w(cc))
                    wq = 0.5 if hi_ - lo_ < 1e-6 else float((q[k2] - lo_) / (hi_ - lo_))
                    cl.append((1, 1, 1, 0.30 + 0.50 * wq))
                fans[run.tag].set_segments(sg); fans[run.tag].set_color(cl)
                wp = to_w(p['sel']); plans[run.tag].set_data(wp[:, 0], wp[:, 1])
            else:
                fans[run.tag].set_segments([]); plans[run.tag].set_data([], [])
            if done and run.tag not in endart:
                endart[run.tag] = m.plot(*ends[run.tag], marker='P' if lat else 'X', ms=21,
                                         mfc=run.col, mec='white', mew=2.0, zorder=10, ls='none')
        repaint(el, grew)

        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())
        if preview is not None:
            Image.fromarray(buf[:, :, :3]).save(out); print('preview ->', out); return
        proc.stdin.write(buf.tobytes())
        if fi % 60 == 0: print(f'  {fi}/{nfr}', flush=True)
    proc.stdin.close(); proc.wait()
    print('wrote', out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--speed', type=float, default=3.0)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--preview', type=float, default=None)
    a = ap.parse_args()
    build(a.out, a.speed, a.fps, preview=a.preview)

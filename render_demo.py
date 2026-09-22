"""Render a GEM-vs-Baseline demo clip for one revisit pair.

Left column: the two onboard streams as recorded.  Right: a shared top-down
panel, rotated to whichever heading packs the scene into the panel best, with
the policy's own output on it -- the candidate trajectories it scored and the
one it chose, carried into world frame by the live pose.

Both arms run off a clock zeroed on the moment each robot actually starts
moving, so the two panels set off together however long the policy took to
issue its first command.  Stretches where the robot was commanded forward but
did not move -- the Go2 stalling under a walk command -- are dropped from
playback; the robot is stationary through them, so nothing moves across a cut.
"""
import os, sys, json, argparse, subprocess
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle, FancyArrow
import matplotlib.patheffects as pe
from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
# dark palette: black ground, light ink, colours lifted enough to hold on black
GEMC, BASEC, HIST, GOLD, INK = '#4D9BE6', '#F0574A', '#4ECB8D', '#FFC93C', '#FFFFFF'
BG, HALO = '#000000', '#000000'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'pdf.fonttype': 42})

C37 = "/data/memnav-realworld/jetson_incrementals/20260914T153518Z/repository/runtime/go2/experiment_capture"
C35 = "/data/memnav-realworld/jetson_incrementals/20260914T095349Z/repository/runtime/go2/experiment_capture"
CASES = {
    'p037': dict(goal_img=f"{C37}/episode_20260914T143615_767815Z/media/revisit_goal.png"),
    'p035': dict(goal_img=f"{C35}/episode_20260914T084212_300871Z/media/revisit_goal.png"),
}
REG = {k: np.asarray(v, float) for k, v in json.load(open(os.path.join(S, 'new_reg.json'))).items()}
REG['p035_base'] = np.array([-1.724, 0.378])
XC = 0.30                                   # camera stand-off ahead of base_link

# panel geometry, 1920x1080
W, H = 1920.0, 1080.0
CAM_X, CAM_W, CAM_H = 20, 880, 498
CAM_Y = (28, 554)
MAP_X, MAP_Y, MAP_W, MAP_H = 920, 28, 980, 1024


# ---------------------------------------------------------------- data loading
class Run:
    def __init__(self, tag, arm):
        d = os.path.join(S, f'demo_{tag}_{arm}')
        self.dir, self.arm = d, arm
        self.times = np.load(d + '/times.npy')
        self.K = np.load(d + '/K.npy')
        self.plans = list(np.load(d + '/plans.npy', allow_pickle=True))
        w = json.load(open(d + '/win.json'))
        self.t0, self.t1 = w['t0'], w['t1']
        T = np.load(os.path.join(S, f'{tag}_{arm}.npz'))['tel']
        T = T.copy(); T[:, 1:3] += REG.get(f'{tag}_{arm}', np.zeros(2))
        self.tel = T
        self.mount = np.load(os.path.join(S, f'rgbd_{tag}_{arm}/mount.npy'))
        arr = json.load(open(d + '/arrival.json'))
        self.at = np.array([r[0] for r in arr], float)
        self.alat = np.array([bool(r[1].get('arrival_latched')) for r in arr])
        # zero on the first real movement, not on the first non-zero command:
        # the two arms take different times to get going, and the clip should
        # set them off together
        Q = T[(T[:, 0] >= self.t0) & (T[:, 0] <= self.t1)]
        mv = ((np.linalg.norm(Q[:, 1:3] - Q[0, 1:3], axis=1) > 0.03) |
              (np.degrees(np.abs(np.unwrap(Q[:, 6]) - Q[0, 6])) > 3.0))
        if mv.any(): self.t0 = float(Q[int(np.argmax(mv)), 0])
        self.dur = self.t1 - self.t0
        self._build_clock()

    def _build_clock(self, dt=0.05, min_stall=2.5, keep_in=0.5, keep_out=0.3):
        """Playback clock with the robot's dead stretches taken out."""
        T = self.tel
        gr = np.arange(self.t0, self.t1, dt)
        x = np.interp(gr, T[:, 0], T[:, 1]); y = np.interp(gr, T[:, 0], T[:, 2])
        yw = np.degrees(np.interp(gr, T[:, 0], np.unwrap(T[:, 6])))
        n = max(1, int(round(0.5 / dt)))
        sp = np.zeros_like(gr); tw = np.zeros_like(gr)
        sp[n:] = np.hypot(x[n:] - x[:-n], y[n:] - y[:-n]) / (n * dt)
        tw[n:] = np.abs(yw[n:] - yw[:-n]) / (n * dt)
        still = (sp < 0.04) & (tw < 4.0)          # loose: catch the whole stall
        segs, i = [], 0
        while i < len(still):
            if still[i]:
                j = i
                while j < len(still) and still[j]: j += 1
                segs.append([i, j]); i = j
            else:
                i += 1
        merged = []                               # a twitch does not end a stall
        for sg in segs:
            if merged and (sg[0] - merged[-1][1]) * dt < 2.5:
                merged[-1][1] = sg[1]
            else:
                merged.append(sg)
        cut = np.zeros_like(still)
        for i, j in merged:
            span = (j - i) * dt
            if span < min_stall: continue
            # only cut where the robot really went nowhere over the whole window:
            # a slow on-the-spot turn creeps under any instantaneous threshold,
            # but its net yaw rate gives it away
            net_v = np.hypot(x[j - 1] - x[i], y[j - 1] - y[i]) / span
            net_w = abs(yw[j - 1] - yw[i]) / span
            if net_v > 0.02 or net_w > 1.0: continue
            a = i + int(round(keep_in / dt)); b = j - int(round(keep_out / dt))
            if b > a: cut[a:b] = True
        self.kept = gr[~cut]
        self.cut_s = float(cut.sum() * dt)
        self.dt = dt
        self.dur = len(self.kept) * dt

    def src(self, e):
        """Playback elapsed -> source time."""
        if e < 0: return self.kept[0] + e
        i = int(np.clip(e / self.dt, 0, len(self.kept) - 1))
        return float(self.kept[i])

    def frame(self, t):
        return os.path.join(self.dir, 'rgb', '%05d.jpg' % int(np.argmin(np.abs(self.times - t))))

    def pose(self, t):
        T = self.tel
        return (np.interp(t, T[:, 0], T[:, 1]), np.interp(t, T[:, 0], T[:, 2]),
                np.interp(t, T[:, 0], np.unwrap(T[:, 6])))

    def trace(self, t):
        T = self.tel
        return T[(T[:, 0] >= self.t0) & (T[:, 0] <= max(t, self.t0 + 1e-3)), 1:3]

    def plan(self, t, hold=3.0):
        # the newest message that actually carries a trajectory: a few carry
        # none, and taking them would blink the overlay out
        best = None
        for p in self.plans:
            if p['sel'] is None or not len(p['sel']): continue
            if p['t'] <= t and (best is None or p['t'] > best['t']): best = p
        return best if (best is not None and t - best['t'] <= hold) else None

    def latched(self, t):
        if not len(self.at): return False
        i = int(np.searchsorted(self.at, t) - 1)
        return bool(self.alat[i]) if i >= 0 else False


# -------------------------------------------------------------------- map view
def pick_rotation(pts, aspect, prefer=None):
    """The heading that packs the scene into a panel of this aspect ratio.

    Several headings usually pack about as tightly; among those, take the one
    that lays `prefer` (release -> goal) out to the right, so the clip reads
    left-to-right rather than ending up upside down.
    """
    sc = []
    for deg in range(0, 360):
        th = np.radians(deg)
        Q = rot(pts, th)
        w, h = Q[:, 0].ptp() + 2.2, Q[:, 1].ptp() + 2.2
        sc.append((min(aspect / w, 1.0 / h) if w > 0 and h > 0 else 0.0, th))
    best = max(s for s, _ in sc)
    near = [th for s, th in sc if s >= 0.985 * best]
    if prefer is None: return near[0]
    v = np.asarray(prefer, float); v = v / max(np.linalg.norm(v), 1e-9)
    return max(near, key=lambda th: rot(v, th)[0])


def rot(P, th):
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    return np.asarray(P, float) @ R.T


# ------------------------------------------------------------------- the render
def build(tag, speed, fps, out, lead=1.0, tail=3.0, preview=None):
    cs = CASES[tag]
    gem, base = Run(tag, 'gem'), Run(tag, 'base')
    mem = np.load(os.path.join(S, f'{tag}_mem.npz'))['tel']
    goal = mem[0, 1:3]
    d = np.load(os.path.join(S, f'{tag}_ortho.npz'))
    ortho, mask, lo, res = d['img'], d['mask'], d['lo'], float(d['res'])

    pts = np.vstack([gem.trace(gem.t1), base.trace(base.t1), goal[None, :], mem[::20, 1:3]])
    rel = gem.trace(gem.t0 + .2)[0]
    th = pick_rotation(pts, aspect=MAP_W / MAP_H, prefer=goal - rel)
    Rgoal, Rmem = rot(goal, th), rot(mem[:, 1:3], th)
    allp = np.vstack([rot(gem.trace(gem.t1), th), rot(base.trace(base.t1), th),
                      Rgoal[None, :], Rmem])
    cx = 0.5 * (allp[:, 0].min() + allp[:, 0].max())
    cy = 0.5 * (allp[:, 1].min() + allp[:, 1].max())
    pad = max(1.0, 0.07 * max(allp[:, 0].ptp(), allp[:, 1].ptp()))
    half_w = max(allp[:, 0].ptp() / 2 + pad, (allp[:, 1].ptp() / 2 + pad) * MAP_W / MAP_H)
    half_h = half_w * MAP_H / MAP_W

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    def ax_at(x, y, w, h):
        return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    # ---- the two camera panels
    cams = {}
    for run, name, col, y0 in [(gem, 'GEM', GEMC, CAM_Y[0]), (base, 'Baseline', BASEC, CAM_Y[1])]:
        a = ax_at(CAM_X, y0, CAM_W, CAM_H); a.set_axis_off()
        a.set_xlim(0, 848); a.set_ylim(480, 0)
        im = a.imshow(np.zeros((480, 848, 3), np.uint8), extent=[0, 848, 480, 0], zorder=1)
        wash = a.add_patch(Rectangle((0, 0), 848, 480, facecolor='#000000', alpha=0.0,
                                     edgecolor='none', zorder=6))
        ok = a.add_patch(Rectangle((4, 4), 840, 472, facecolor='none', edgecolor='#3FD98A',
                                   lw=8, zorder=7, visible=False))
        a.text(0.014, 0.965, name, transform=a.transAxes, fontsize=20, weight='bold',
               color='white', ha='left', va='top', zorder=8,
               bbox=dict(boxstyle='round,pad=0.34', fc=col, ec='none'))
        cams[run.arm] = dict(ax=a, im=im, col=col, wash=wash, ok=ok)

    # ---- map panel
    m = ax_at(MAP_X, MAP_Y, MAP_W, MAP_H)
    m.set_xticks([]); m.set_yticks([])
    for s in m.spines.values(): s.set_visible(False)
    m.set_facecolor(BG)
    v = (ortho.astype(np.float32) / 255.0) @ np.array([0.299, 0.587, 0.114])
    rgba = np.zeros((*mask.shape, 4), np.float32)
    rgba[..., :3] = (v * 0.26 + 0.13)[..., None]
    rgba[..., 3] = mask.astype(np.float32) * 0.85
    ny, nx = mask.shape
    tr = matplotlib.transforms.Affine2D().rotate(th) + m.transData
    m.imshow(rgba, origin='lower', extent=[lo[0], lo[0] + nx * res, lo[1], lo[1] + ny * res],
             transform=tr, zorder=1, interpolation='bilinear')
    m.set_xlim(cx - half_w, cx + half_w); m.set_ylim(cy - half_h, cy + half_h)
    m.set_aspect('equal', adjustable='box')

    m.plot(Rmem[:, 0], Rmem[:, 1], color=HIST, lw=2.6, ls=(0, (5, 3)), alpha=.95, zorder=3)
    m.plot(*Rgoal, marker='*', ms=32, mfc=GOLD, mec=HALO, mew=1.6, zorder=9, ls='none')
    st = rot(gem.trace(gem.t0 + .2)[0], th)
    m.plot(*st, marker='o', ms=13, mfc='none', mec='white', mew=2.6, zorder=9, ls='none')

    ends = {r.arm: rot(r.trace(r.t1)[-1], th) for r in (gem, base)}
    endart, trails, dots, fans, plans = {}, {}, {}, {}, {}
    for run, col in [(gem, GEMC), (base, BASEC)]:
        trails[run.arm], = m.plot([], [], color=col, lw=4.4, solid_capstyle='round', zorder=5,
                                  path_effects=[pe.withStroke(linewidth=7, foreground=HALO)])
        fans[run.arm] = m.add_collection(
            LineCollection([], colors='#FFFFFF', linewidths=1.6, zorder=6))
        plans[run.arm], = m.plot([], [], color=col, lw=3.0, ls=(0, (2.5, 1.8)),
                                 alpha=.95, zorder=7,
                                 path_effects=[pe.withStroke(linewidth=4.6, foreground=HALO)])
        dots[run.arm], = m.plot([], [], marker='o', ms=15, mfc=col, mec='white', mew=2.0,
                                zorder=8, ls='none')
    heads = {r.arm: m.add_patch(FancyArrow(0, 0, 0, 0, width=0.001, color='none', zorder=8))
             for r in (gem, base)}

    gi = Image.open(cs['goal_img']).convert('RGB')
    gi.thumbnail((250, 250))
    occ, sx = [], MAP_W / (2 * half_w)
    for kx, ky in ((0, 0), (1, 0), (0, 1), (1, 1)):
        bx = cx - half_w + kx * (2 * half_w - (gi.width + 28) / sx)
        by = cy + half_h - (gi.height + 28) / sx - ky * (2 * half_h - (gi.height + 28) / sx)
        inb = ((allp[:, 0] > bx) & (allp[:, 0] < bx + (gi.width + 28) / sx) &
               (allp[:, 1] > by) & (allp[:, 1] < by + (gi.height + 28) / sx))
        occ.append((inb.sum(), kx, ky))
    _, kx, ky = min(occ)
    ga = ax_at(MAP_X + 14 + kx * (MAP_W - gi.width - 28),
               MAP_Y + 14 + ky * (MAP_H - gi.height - 28), gi.width, gi.height)
    # scale bar into the corner diagonally opposite the thumbnail
    sb = 2.0 if half_w < 9 else 5.0
    x0 = cx - half_w + 0.55 if kx else cx + half_w - 0.55 - sb
    y0 = cy + half_h - 0.55 if ky else cy - half_h + 0.75
    m.plot([x0, x0 + sb], [y0, y0], color='white', lw=3.4, zorder=10, solid_capstyle='butt')
    m.annotate(f'{sb:.0f} m', (x0 + sb / 2, y0 - 0.14), ha='center', va='top', fontsize=15,
               color='white', weight='bold', zorder=10)
    ga.imshow(np.asarray(gi)); ga.set_xticks([]); ga.set_yticks([])
    for s in ga.spines.values(): s.set_color(GOLD); s.set_linewidth(3)

    # ---- frames
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

    for fi in idx:
        el = fi / fps * speed - lead
        for run in (gem, base):
            c = cams[run.arm]
            t = run.src(min(max(el, -lead), run.dur))
            done = el > run.dur
            c['im'].set_data(np.asarray(Image.open(run.frame(t))))
            p = run.plan(t) if el >= 0 and not done else None
            lat = run.latched(run.t1 + 1.0 if done else t)
            c['wash'].set_alpha(0.45 if (done and not lat) else 0.0)
            c['ok'].set_visible(bool(lat))

            tr_ = rot(run.trace(t), th)
            if len(tr_) < 2: tr_ = np.repeat(rot(run.pose(run.t0)[:2], th)[None, :], 2, 0)
            trails[run.arm].set_data(tr_[:, 0], tr_[:, 1])
            x, y, yw = run.pose(t)
            px, py = rot(np.array([x, y]), th)
            dots[run.arm].set_data([px], [py])
            heads[run.arm].remove()
            heads[run.arm] = m.add_patch(
                FancyArrow(px, py, np.cos(yw + th) * .62, np.sin(yw + th) * .62, width=.07,
                           head_width=.30, head_length=.26, length_includes_head=True,
                           color=c['col'], zorder=8,
                           path_effects=[pe.withStroke(linewidth=3.2, foreground=HALO)]))
            if p is not None:
                Rw = np.array([[np.cos(yw), -np.sin(yw)], [np.sin(yw), np.cos(yw)]])
                to_world = lambda P: rot(np.asarray(P)[:, :2] @ Rw.T + np.array([x, y]), th)
                q = np.array(p['q'], float) if len(p['q']) else np.zeros(len(p['cand']))
                lo_, hi_ = (np.nanmin(q), np.nanmax(q)) if len(q) else (0.0, 1.0)
                sg, cl = [], []
                for k, cc in enumerate(p['cand']):
                    if cc is None or len(cc) < 2: continue
                    sg.append(to_world(cc))
                    wq = 0.5 if hi_ - lo_ < 1e-6 else float((q[k] - lo_) / (hi_ - lo_))
                    cl.append((1, 1, 1, 0.30 + 0.50 * wq))
                fans[run.arm].set_segments(sg); fans[run.arm].set_color(cl)
                wp = to_world(p['sel'])
                plans[run.arm].set_data(wp[:, 0], wp[:, 1])
            else:
                fans[run.arm].set_segments([]); plans[run.arm].set_data([], [])
            if done and run.arm not in endart:
                endart[run.arm] = m.plot(*ends[run.arm], marker='P' if lat else 'X', ms=21,
                                         mfc=c['col'], mec='white', mew=2.0, zorder=9, ls='none')

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
    ap.add_argument('tag'); ap.add_argument('out')
    ap.add_argument('--speed', type=float, default=3.0)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--preview', type=float, default=None)
    a = ap.parse_args()
    build(a.tag, a.speed, a.fps, a.out, preview=a.preview)

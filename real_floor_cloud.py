"""Conservative, past-observation-only supplementation of real floor points."""
from collections import deque
import numpy as np
from render_indoor_joint import JointMap


def depth_masks(depth, conf):
    valid = np.isfinite(depth) & (depth > 0) & np.isfinite(conf)
    h, w = depth.shape
    pad = np.pad(np.where(valid, depth, np.nan), 1, constant_values=np.nan)
    nb = np.stack([pad[i:i+h, j:j+w] for i in range(3) for j in range(3)])
    spread = np.nanmax(nb, axis=0) - np.nanmin(nb, axis=0)
    flat = valid & np.isfinite(spread) & (spread < .035 * depth)
    thr = np.percentile(conf[valid], [40, 65]) if valid.any() else [np.inf, np.inf]
    return flat & (conf >= thr[0]), flat & (conf >= thr[1])


class FloorSupportedMap(JointMap):
    def __init__(self, *args, **kwargs):
        # Fit the original camera before enabling supplementary points.
        super().__init__(*args, **kwargs)
        self.history = {a: deque(maxlen=8) for a in ('gem', 'base')}
        self.stats = dict(observations=0, candidates=0, accepted=0)

    def supported(self, X, t, arm, T):
        votes = np.zeros(len(X), np.uint8)
        for pt, oldT, d, K, mask in self.history[arm]:
            # Distinct earlier views, rather than repeated stationary frames.
            if not .18 <= t-pt <= 1.6:
                continue
            if np.linalg.norm(T[:3, 3]-oldT[:3, 3])/self.s < .03:
                continue
            q = (X-oldT[:3, 3]) @ oldT[:3, :3]
            projected = q @ K.T
            uv = np.rint(projected[:, :2]/np.maximum(projected[:, 2:3], 1e-9)).astype(int)
            u, v = uv.T
            good = (q[:, 2] > 0) & (u >= 0) & (v >= 0) & (u < d.shape[1]) & (v < d.shape[0])
            ids = np.flatnonzero(good)
            u, v = u[ids], v[ids]
            # 5 cm metric allowance, with 1% range allowance for distant floor.
            tolerance = np.maximum(.05*self.s, .01*q[ids, 2])
            agrees = mask[v, u] & (np.abs(d[v, u]-q[ids, 2]) <= tolerance)
            votes[ids[agrees]] += 1
            assert pt < t
        return votes >= 2

    def reveal(self, cut_time):
        eligible = [i for i, (t, a, _, _) in enumerate(self.items)
                    if not self.shown[i] and t <= cut_time[a]]
        # Baseline inference files are reversed; support follows playback time.
        for i in sorted(eligible, key=lambda j: (self.items[j][1], self.items[j][0])):
            t, arm, path, T = self.items[i]
            with np.load(path) as p:
                d, conf, K = p['depth'], p['conf'], p['K']
                relaxed, strict = depth_masks(d, conf)
                sample = np.zeros_like(strict); sample[::4, ::4] = True
                v, u = np.nonzero(relaxed & sample)
                q = (np.column_stack((u, v, np.ones(len(u)))) @ np.linalg.inv(K).T)*d[v, u, None]
                X = q.astype(np.float32) @ T[:3, :3].T + T[:3, 3]
                h = (self.d-X@self.n)/self.s
                original = strict[v, u] & (h > -.08) & (h < self.zmax)
                candidates = ~original & (h > -.30) & (h < .20)
                ids = np.flatnonzero(candidates)
                accepted = self.supported(X[ids], t, arm, T)
                keep = original.copy(); keep[ids[accepted]] = True
                colors = p['rgb'][v, u, ::-1]
                self.splat(X[keep], colors[keep], self.raster, self.z)
                above = original & (h > .25)
                self.splat(X[above], None, None, self.z_obs)
                self.stats['observations'] += 1
                self.stats['candidates'] += len(ids)
                self.stats['accepted'] += int(accepted.sum())
                history = self.history[arm]
                if not history or t-history[-1][0] >= .18:
                    history.append((t, T, d.copy(), K.copy(), relaxed.copy()))
            self.shown[i] = True

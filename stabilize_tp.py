"""Steady the handheld third-person clips.

The operator walks behind the robot, so the footage carries both an intended
pan and a per-step shake.  Zeroing all motion would fight the pan; instead the
accumulated camera path is smoothed and each frame is warped by the difference,
which removes the shake and leaves the follow.  A small zoom hides the borders
the warp exposes.
"""
import argparse, json, shutil
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--smooth', type=float, default=1.2, help='seconds of smoothing')
    ap.add_argument('--zoom', type=float, default=1.06)
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    idx = json.loads((src / 'index.json').read_text())
    files = sorted(src.glob('*.jpg'))
    prev = cv2.cvtColor(cv2.imread(str(files[0])), cv2.COLOR_BGR2GRAY)
    dx = [np.zeros(3)]
    for f in files[1:]:
        cur = cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2GRAY)
        p0 = cv2.goodFeaturesToTrack(prev, 400, .01, 12, blockSize=7)
        step = np.zeros(3)
        if p0 is not None and len(p0) > 20:
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, p0, None)
            if st is not None and st.sum() > 15:
                A, _ = cv2.estimateAffinePartial2D(p0[st.ravel() == 1], p1[st.ravel() == 1])
                if A is not None:
                    step = np.array([A[0, 2], A[1, 2], np.arctan2(A[1, 0], A[0, 0])])
        dx.append(step); prev = cur
    path = np.cumsum(np.array(dx), axis=0)
    w = max(3, int(a.smooth * idx['fps']) | 1)
    pad = np.pad(path, ((w // 2, w // 2), (0, 0)), mode='edge')
    ker = np.ones(w) / w
    smooth = np.stack([np.convolve(pad[:, i], ker, mode='valid') for i in range(3)], 1)
    corr = smooth - path
    h0, w0 = cv2.imread(str(files[0])).shape[:2]
    for f, c in zip(files, corr):
        img = cv2.imread(str(f))
        ca, sa = np.cos(c[2]) * a.zoom, np.sin(c[2]) * a.zoom
        M = np.array([[ca, -sa, c[0]], [sa, ca, c[1]]], np.float64)
        M[:, 2] += np.array([w0, h0]) / 2 - M[:, :2] @ (np.array([w0, h0]) / 2)
        cv2.imwrite(str(out / f.name),
                    cv2.warpAffine(img, M, (w0, h0), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE))
    shutil.copy(src / 'index.json', out / 'index.json')
    r = np.linalg.norm(corr[:, :2], axis=1)
    print(f'{src.name}: {len(files)} 帧, 补偿位移 中位 {np.median(r):.1f} px '
          f'p95 {np.percentile(r, 95):.1f} px -> {out}')


if __name__ == '__main__':
    main()

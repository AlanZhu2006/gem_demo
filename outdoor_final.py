"""Outdoor p035 playback adapter; shares clocks, plans and final visual primitives."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from render_indoor_joint import Arm, JointMap
from final_video_style import COLORS, GREEN, failed_image
from refined_sim_style import label

class OutdoorArm(Arm):
    def __init__(self, key, inputs):
        self.key=key;self.src_dir=Path(inputs)/key
        self.tel=np.load(self.src_dir/'telemetry.npz')['tel']
        self.plans=list(np.load(self.src_dir/'plans.npy',allow_pickle=True))
        times=np.load(self.src_dir/'times.npy')
        self.rt=np.rint(times*1e9).astype(np.int64)
        self.rows=[dict(path=f'rgb/{i:05d}.jpg',timestamp_ns=int(t)) for i,t in enumerate(self.rt)]
        win=json.loads((self.src_dir/'win.json').read_text());self.ms=win['t0']
        arr=json.loads((self.src_dir/'arrival.json').read_text())
        lat=[r[0] for r in arr if r[1].get('arrival_latched')]
        self.latch_t=min(lat) if lat else None
        self.tend=self.latch_t if lat else win['t1']
        self._clock()

    def at(self, elapsed):
        # Include the recorded terminal event exactly, beyond the 50 ms clock grid.
        return float(self.tend) if elapsed >= self.play else super().at(elapsed)


def draw_outdoor_panels(frame,arms,cut,elapsed,arrived,goal,speed):
    canvas=Image.fromarray(frame[:,:,::-1]);d=ImageDraw.Draw(canvas)
    for arm,y in [('gem',216),('base',652)]:
        success=arrived(arm,elapsed);failed=elapsed>=arms[arm].play and not success
        label(d,(28,y-36),'GEM' if arm=='gem' else 'Baseline',30,COLORS[arm],True)
        if success or failed:
            label(d,(378,y-29),'Arrived' if success else 'Stopped',21,GREEN if success else (110,116,122),True)
        path=arms[arm].fpv(cut[arm]);fpv=cv2.imread(str(path))
        if fpv is None:raise FileNotFoundError(path)
        if failed:fpv=failed_image(fpv)
        canvas.paste(Image.fromarray(fpv[:,:,::-1]).resize((480,270),Image.Resampling.LANCZOS),(28,y))
        if success:d.rectangle((27,y-1,508,y+270),outline=GREEN,width=2)
    x,y,w,h=560,26,224,126
    canvas.paste(Image.fromarray(goal[:,:,::-1]).resize((w,h),Image.Resampling.LANCZOS),(x,y))
    for arm,pad in [('gem',6),('base',1)]:
        if arrived(arm,elapsed):d.rectangle((x-pad,y-pad,x+w-1+pad,y+h-1+pad),outline=COLORS[arm],width=3)
    label(d,(x,y+h+10),'Revisit',22,(51,57,63),True)
    label(d,(1830,28),f'{speed:g}×',22,(115,122,129),True)
    frame[:]=np.asarray(canvas)[:,:,::-1]


class FloorFixedMap(JointMap):
    """Original point-quality mask with the established -30 cm floor cutoff."""
    def cut(self, X, rgb=None):
        h=(self.d-np.asarray(X)@self.n)/self.s
        keep=(h>-.30)&(h<self.zmax)
        return X[keep] if rgb is None else (X[keep],rgb[keep])

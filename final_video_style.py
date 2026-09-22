"""Shared final typography, arrival colors and true grayscale failure treatment."""
import cv2
import numpy as np
from PIL import Image,ImageDraw
from refined_sim_style import label
from render_indoor_joint import COL

COLORS={a:tuple(COL[a][::-1]) for a in ('gem','base')}
GREEN=(48,144,93)

def failed_image(bgr):
    gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
    gray=np.rint(gray*.48).astype(np.uint8)
    return cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)

def draw_real_panels(frame,arms,cut,elapsed,arrived,goal,speed):
    canvas=Image.fromarray(frame[:,:,::-1]);d=ImageDraw.Draw(canvas)
    for arm,y in [('gem',160),('base',638)]:
        success=arrived(arm,elapsed);failed=elapsed>=arms[arm].play and not success
        label(d,(28,y-42),'GEM' if arm=='gem' else 'Baseline',30,COLORS[arm],True)
        if success or failed:label(d,(378,y-35),'Arrived' if success else 'Stopped',21,GREEN if success else (110,116,122),True)
        path,_=arms[arm].third(cut[arm]);external=cv2.imread(str(path))
        fpv=cv2.imread(str(arms[arm].fpv(cut[arm])))
        if external is None or fpv is None:raise FileNotFoundError(path)
        if failed:external,fpv=failed_image(external),failed_image(fpv)
        canvas.paste(Image.fromarray(external[:,:,::-1]).resize((420,420),Image.Resampling.LANCZOS),(28,y))
        px,py=214,y+284
        canvas.paste(Image.fromarray(fpv[:,:,::-1]).resize((224,126),Image.Resampling.LANCZOS),(px,py))
        d.rectangle((px-1,py-1,px+224,py+126),outline=(255,255,255),width=1)
        if success:d.rectangle((27,y-1,448,y+420),outline=GREEN,width=2)
    x,y,w,h=560,26,224,126
    canvas.paste(Image.fromarray(goal[:,:,::-1]).resize((w,h),Image.Resampling.LANCZOS),(x,y))
    for arm,pad in [('gem',6),('base',1)]:
        if arrived(arm,elapsed):d.rectangle((x-pad,y-pad,x+w-1+pad,y+h-1+pad),outline=COLORS[arm],width=3)
    label(d,(x,y+h+10),'Revisit',22,(51,57,63),True)
    label(d,(1830,28),f'{speed:g}×',22,(115,122,129),True)
    frame[:]=np.asarray(canvas)[:,:,::-1]

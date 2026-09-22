"""White presentation with aligned image cards and readable, restrained type."""
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from joint_sim_style import goal_state

INK=(35,45,56);MUTED=(113,124,134);LINE=(224,229,234)
GREEN=(42,142,91);AMBER=(184,130,35);RED=(192,79,75)
COLORS={'gem':(65,139,208),'base':(222,99,84)}
@lru_cache(None)
def font(size,bold=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/lato/Lato-'+('Semibold' if bold else 'Regular')+'.ttf',size)

def label(d,xy,s,size=18,color=INK,bold=False):
    d.text(xy,s,font=font(size,bold),fill=color)

def state_icon(d,x,y,state):
    color={'arrived':GREEN,'active':AMBER,'stopped':RED,'pending':MUTED}[state]
    if state=='arrived':d.line([(x,y+5),(x+4,y+9),(x+12,y)],fill=color,width=2)
    elif state=='stopped':
        d.line([(x+1,y),(x+10,y+9)],fill=color,width=2);d.line([(x+10,y),(x+1,y+9)],fill=color,width=2)
    elif state=='active':d.ellipse((x+2,y+2,x+10,y+10),fill=color)
    else:d.line((x+1,y+5,x+11,y+5),fill=LINE,width=2)
    return color

def rounded_image(canvas,array,box,radius=7):
    x,y,w,h=box
    image=Image.fromarray(array[:,:,::-1]).resize((w,h),Image.Resampling.LANCZOS)
    mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=255)
    canvas.paste(image,(x,y),mask)

def draw_refined(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second):
    canvas=Image.fromarray(frame[:,:,::-1]);d=ImageDraw.Draw(canvas)
    label(d,(28,30),'SIMULATION',13,MUTED,True)
    label(d,(28,61),'Image-goal navigation',30,INK,True)
    label(d,(28,108),'Two methods. Three sequential goals.',18,MUTED)
    d.line((28,160,508,160),fill=LINE,width=1)
    label(d,(28,184),'GEM',17,COLORS['gem'],True)
    label(d,(104,184),'vs.',16,MUTED)
    label(d,(145,184),'Baseline',17,COLORS['base'],True)
    for arm,y in [('gem',286),('base',678)]:
        obs=pair['arms'][arm]['frames'][current[arm]]
        state=goal_state(pair,arm,obs['leg'],current,step)
        d.rounded_rectangle((28,y,34,y+24),radius=3,fill=COLORS[arm])
        label(d,(46,y-3),'GEM' if arm=='gem' else 'Baseline',24,INK,True)
        status=obs['leg']+'  ·  '+dict(arrived='Arrived',active='Navigating',stopped='Stopped',pending='Waiting')[state]
        color=GREEN if state=='arrived' else RED if state=='stopped' else MUTED
        label(d,(330,y+3),status,16,color)
        import cv2
        rgb=cv2.imread(obs['path'])
        if state=='stopped':rgb=(rgb*.80+255*.20).astype(np.uint8)
        rounded_image(canvas,rgb,(28,y+39,480,270))
        d.rounded_rectangle((27,y+38,509,y+310),radius=8,outline=GREEN if state=='arrived' else LINE,width=2 if state=='arrived' else 1)
    d.line((532,278,532,1033),fill=(237,240,243),width=1)
    for i,stage in enumerate('ABC'):
        x,y,w,h=558+i*296,28,280,232
        states={a:goal_state(pair,a,stage,current,step) for a in pair['arms']}
        issued=any(s!='pending' for s in states.values())
        done=all(s=='arrived' for s in states.values());active=any(s=='active' for s in states.values())
        edge=GREEN if done else AMBER if active else LINE
        d.rounded_rectangle((x,y,x+w,y+h),radius=10,fill=(255,255,255),outline=edge,width=2 if done or active else 1)
        d.rounded_rectangle((x+12,y+10,x+37,y+35),radius=5,fill=(241,244,246))
        label(d,(x+19,y+11),stage,17,INK,True)
        label(d,(x+48,y+10),'Novel' if pair['sequence'][i]=='N' else 'Revisit',20,INK,True)
        if issued:rounded_image(canvas,goals[stage]['image'],(x+12,y+45,256,144),5)
        else:
            d.rounded_rectangle((x+12,y+45,x+268,y+189),radius=5,fill=(246,248,250))
            label(d,(x+91,y+106),'Up next',17,MUTED)
        for j,arm in enumerate(['gem','base']):
            xx=x+14+j*133;yy=y+207
            color=state_icon(d,xx,yy,states[arm])
            name='GEM' if arm=='gem' else 'Baseline'
            label(d,(xx+20,yy-5),name,15,color,states[arm]=='arrived')
    d.rounded_rectangle((1590,28,1888,124),radius=10,fill=(247,249,250))
    label(d,(1610,42),'PLAYBACK',12,MUTED,True)
    label(d,(1610,66),f'{steps_per_second*.1:g}×',28,INK,True)
    label(d,(1720,70),f'{min(step,longest)*.1:04.1f} s',24,INK)
    if tail_speed>1 and gem_end<=step<longest:
        label(d,(1598,140),f'Baseline tail · {tail_speed:.1f}× faster',16,MUTED)
    # A compact key makes the split arrival state explicit without verbose cards.
    state_icon(d,1598,192,'arrived');label(d,(1619,184),'Arrived',14,MUTED)
    state_icon(d,1712,192,'active');label(d,(1733,184),'Active',14,MUTED)
    state_icon(d,1810,192,'stopped');label(d,(1831,184),'Stopped',14,MUTED)
    frame[:]=np.asarray(canvas)[:,:,::-1]

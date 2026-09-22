"""Minimal white composition: two FPVs, three targets, map, no dashboard chrome."""
import cv2
import numpy as np
from PIL import Image,ImageDraw
from joint_sim_style import goal_state
from refined_sim_style import label
from render_indoor_joint import COL
from final_video_style import failed_image

INK=(51,57,63);MUTED=(145,151,157);GREEN=(48,144,93)
COLORS={arm:tuple(COL[arm][::-1]) for arm in ('gem','base')}

def draw_minimal(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second):
    im=Image.fromarray(frame[:,:,::-1]);d=ImageDraw.Draw(im)
    for arm,y in [('gem',216),('base',652)]:
        obs=pair['arms'][arm]['frames'][current[arm]]
        state=goal_state(pair,arm,obs['leg'],current,step)
        name='GEM' if arm=='gem' else 'Baseline'
        label(d,(28,y-36),name,30,COLORS[arm],True)
        if state in ('arrived','stopped'):
            label(d,(378,y-29),'Arrived' if state=='arrived' else 'Stopped',21,GREEN if state=='arrived' else MUTED,True)
        rgb=cv2.imread(obs['path'])
        if state=='stopped':rgb=failed_image(rgb)
        im.paste(Image.fromarray(rgb[:,:,::-1]).resize((480,270),Image.Resampling.LANCZOS),(28,y))
        if state=='arrived':d.rectangle((27,y-1,508,y+270),outline=GREEN,width=2)
    for i,stage in enumerate('ABC'):
        x,y,w,h=560+i*248,26,224,126
        states={a:goal_state(pair,a,stage,current,step) for a in pair['arms']}
        issued=any(v!='pending' for v in states.values())
        if issued:
            image=Image.fromarray(goals[stage]['image'][:,:,::-1]).resize((w,h),Image.Resampling.LANCZOS)
            im.paste(image,(x,y))
        else:d.rectangle((x,y,x+w-1,y+h-1),fill=(247,248,249))
        # Independent latched outcomes: outer blue GEM, inner coral Baseline.
        # Fixed positions avoid shifting a border when the other arm arrives.
        for arm,pad in [('gem',6),('base',1)]:
            if states[arm]=='arrived':
                d.rectangle((x-pad,y-pad,x+w-1+pad,y+h-1+pad),outline=COLORS[arm],width=3)
        role='Novel' if pair['sequence'][i]=='N' else 'Revisit'
        label(d,(x,y+h+10),f'{stage} · {role}',22,INK if issued else MUTED,True)
    label(d,(1830,28),f'{steps_per_second*.1:g}×',22,MUTED,True)
    if tail_speed>1 and gem_end<=step<longest:
        label(d,(1600,60),f'Baseline tail · {tail_speed:.1f}× faster',18,MUTED,True)
    frame[:]=np.asarray(im)[:,:,::-1]

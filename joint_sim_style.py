"""Real joint-video presentation using recorded simulator RGB and NavDP plans."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from render_indoor_joint import ribbon, ring, disc, COL, GOLD


class RecordedPlans:
    def __init__(self,pair):
        self.rows={};self.sources={}
        for arm,folder in [('gem','cec'),('base','native')]:
            root=Path(pair['run'])/folder/'evaluation'
            path=root/'full_plan_outputs.jsonl'
            full=[json.loads(line) for line in path.read_text().splitlines() if line]
            byseed={r['receipt']['diffusion_seed']:r for r in full}
            assert len(byseed)==len(full)
            rows=[]
            for leg in pair['arms'][arm]['legs']:
                result=json.loads((root/f"leg_{leg['stage']}"/'result.json').read_text())
                for entry in result['plans']:
                    r=byseed[entry['diffusion_seed']]
                    selected=np.asarray(r['selected_trajectory'],dtype='<f8')
                    digest=hashlib.sha256(np.ascontiguousarray(selected).tobytes()).hexdigest()
                    assert digest==entry['selected_trajectory_sha256']
                    step=leg['start']+entry['step']
                    obs=pair['arms'][arm]['frames'][step]
                    np.testing.assert_allclose(np.asarray(obs['gt_camera'])[[0,2]],np.asarray(r['position'])[[0,2]],atol=1e-5)
                    assert abs(obs['gt_yaw']-r['yaw'])<1e-5
                    candidates=np.asarray(r['all_trajectory'],float)
                    if candidates.size:candidates=candidates.reshape(-1,*candidates.shape[-2:])
                    rows.append(dict(step=step,leg=leg['stage'],selected=selected,
                        candidates=candidates,values=np.asarray(r['all_values'],float).ravel()))
            assert len(rows)==len(full)
            self.rows[arm]=sorted(rows,key=lambda x:x['step'])
            self.sources[arm]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),plans=len(rows))

    def at(self,arm,step,pair):
        data=pair['arms'][arm]
        if step>=len(data['frames'])-1:return None
        leg=next(x for x in data['legs'] if x['stage']==data['frames'][step]['leg'])
        if leg.get('arrival_step') is not None and step>=leg['arrival_step']:return None
        rows=[r for r in self.rows[arm] if r['leg']==leg['stage'] and r['step']<=step]
        return rows[-1] if rows and step-rows[-1]['step']<=30 else None


def local_to_floor(m,arm,plan_step,points):
    # NavDP coordinates are metres: x forward, y LEFT, third column yaw.
    up=-m.n;fwd=m.fwd_at(arm,plan_step*.1)
    left=np.cross(up,fwd);left/=np.linalg.norm(left)
    origin=m.pos_at(arm,plan_step*.1)
    p=np.asarray(points)
    world=origin+p[:,:1]*fwd*m.s+p[:,1:2]*left*m.s
    return m.to_floor(world,0.)+up*.02*m.s


def draw_tracks(m,raster,z,current,pair,plans,widths,center_width=.12,show_candidates=True):
    up=-m.n;drawn={}
    for arm in ['base','gem']:
        t=current[arm]*.1
        if t<m.path[arm][1][0]:continue
        col=np.array(COL[arm],np.uint8);bright=np.minimum(col.astype(int)+70,255)
        path=m.to_floor(m.track(arm,t),0.)+up*.02*m.s
        m.splat(ribbon(path,up,widths[arm]*m.s,m.step_u),col*.92,raster,z,update_z=False)
        m.splat(ribbon(path,up,center_width*m.s,m.step_u),bright,raster,z,update_z=False)
        plan=plans.at(arm,current[arm],pair)
        if plan is not None and plan['step']*.1>=m.path[arm][1][0]:
            vals=plan['values'];lo=float(np.min(vals)) if len(vals) else 0.;hi=float(np.max(vals)) if len(vals) else 1.
            for j,c in enumerate(plan['candidates'] if show_candidates else []):
                if len(c)<2:continue
                q=.5 if hi-lo<1e-6 or j>=len(vals) else (vals[j]-lo)/(hi-lo)
                pts=local_to_floor(m,arm,plan['step'],c[:max(2,int(len(c)*.6))])
                m.splat(ribbon(pts,up,.045*m.s,m.step_u),np.full(3,int(58+70*(.35+.55*q))),raster,z,((0,0),),update_z=False)
            c=plan['selected'];pts=local_to_floor(m,arm,plan['step'],c[:max(2,int(len(c)*.8))])
            assert np.max(np.abs((m.d-pts@m.n)/m.s-.02))<1e-6
            m.splat(ribbon(pts,up,.085*m.s,m.step_u),bright,raster,z,update_z=False)
            drawn[arm]=dict(plan_step=plan['step'],ground_height_m=.02,candidates=len(plan['candidates']) if show_candidates else 0)
        here=m.to_floor(m.pos_at(arm,t)[None],0.)[0]+up*.028*m.s
        m.splat(ring(here,up,.19*m.s,.035*m.s,m.step_u),[255,255,255],raster,z,update_z=False)
        m.splat(disc(here,up,.085*m.s,m.step_u),col,raster,z,update_z=False)
    return drawn


def text(im,s,xy,scale=.6,color=(190,190,190),weight=1):
    cv2.putText(im,s,xy,cv2.FONT_HERSHEY_SIMPLEX,scale,tuple(map(int,color)),weight,cv2.LINE_AA)


def draw_panels_dark(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second=15):
    stages=[]
    for arm,y in [('gem',14),('base',552)]:
        data=pair['arms'][arm];r=data['frames'][current[arm]]
        leg=next(x for x in data['legs'] if x['stage']==r['leg'])
        arrived=leg.get('arrival_step') is not None and current[arm]>=leg['arrival_step']
        finished=step>=len(data['frames'])-1
        rgb=cv2.imread(r['path']);h,w=rgb.shape[:2]
        scale=min(524/w,440/h);nw,nh=round(w*scale),round(h*scale)
        px,py=18+(524-nw)//2,y+(524-nh)//2
        if finished and not leg['reached']:rgb=(rgb*.45).astype(np.uint8)
        frame[py:py+nh,px:px+nw]=cv2.resize(rgb,(nw,nh))
        if arrived:cv2.rectangle(frame,(px,py),(px+nw-1,py+nh-1),(120,215,90),5)
        cv2.rectangle(frame,(px,py),(px+128,py+34),COL[arm],-1)
        text(frame,'GEM' if arm=='gem' else 'Baseline',(px+12,py+25),.72,(255,255,255),2)
        status=('Arrived' if arrived else 'Stopped: '+leg['termination'] if finished else 'Navigating')
        text(frame,f"{r['leg']}  {'Novel' if pair['sequence'][ord(r['leg'])-65]=='N' else 'Revisit'}  |  {status}",(18,y+480),.64)
        for i,l in enumerate(data['legs']):
            done=l.get('arrival_step') is not None and current[arm]>=l['arrival_step']
            text(frame,l['stage']+('  OK' if done else ''),(18+i*110,y+512),.52,(120,215,90) if done else (140,140,140))
        if r['leg'] not in stages:stages.append(r['leg'])
    for i,stage in enumerate(stages):
        goal=goals[stage]['image'];gw=300;gh=round(goal.shape[0]*gw/goal.shape[1]);gx=578+i*320;gy=36
        frame[gy:gy+gh,gx:gx+gw]=cv2.resize(goal,(gw,gh))
        cv2.rectangle(frame,(gx-2,gy-2),(gx+gw+1,gy+gh+1),GOLD,3)
        text(frame,f'goal image  {stage}',(gx+4,gy+gh+26),.55,GOLD)
    cv2.rectangle(frame,(1655,16),(1890,57),(16,14,12),-1)
    text(frame,f'{min(step,longest)*.1:5.1f} s   x{steps_per_second*.1:g}',(1670,46),.8,(190,190,190),2)
    if tail_speed>1 and gem_end<=step<longest:
        text(frame,f'Baseline remainder  x{tail_speed:.1f}',(1460,78),.6,(235,235,235))


GREEN=(65,155,45)
INK=(55,55,55)
AMBER=(30,145,205)


def goal_state(pair,arm,stage,current,step):
    data=pair['arms'][arm]
    leg=next((l for l in data['legs'] if l['stage']==stage),None)
    if leg is None or current[arm]<leg['start']:return 'pending'
    at=leg.get('arrival_step')
    if at is not None and current[arm]>=at:return 'arrived'
    if current[arm]>=leg['stop']-1 and not leg['reached']:return 'stopped'
    return 'active'


def draw_panels(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second=20,theme='white'):
    if theme=='minimal':
        from minimal_sim_style import draw_minimal
        return draw_minimal(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second)
    if theme=='refined':
        from refined_sim_style import draw_refined
        return draw_refined(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second)
    if theme=='dark':
        return draw_panels_dark(frame,pair,goals,current,step,tail_speed,gem_end,longest,steps_per_second)
    for arm,y in [('gem',14),('base',552)]:
        data=pair['arms'][arm];obs=data['frames'][current[arm]]
        state=goal_state(pair,arm,obs['leg'],current,step)
        rgb=cv2.imread(obs['path']);h,w=rgb.shape[:2]
        scale=min(524/w,440/h);nw,nh=round(w*scale),round(h*scale)
        px,py=18+(524-nw)//2,y+(524-nh)//2
        if state=='stopped':rgb=(rgb*.65+255*.35).astype(np.uint8)
        frame[py:py+nh,px:px+nw]=cv2.resize(rgb,(nw,nh))
        cv2.rectangle(frame,(px,py),(px+nw-1,py+nh-1),GREEN if state=='arrived' else (215,215,215),4 if state=='arrived' else 1)
        cv2.rectangle(frame,(px,py),(px+128,py+34),COL[arm],-1)
        text(frame,'GEM' if arm=='gem' else 'Baseline',(px+12,py+25),.72,(255,255,255),2)
        label=obs['leg']+('  ARRIVED' if state=='arrived' else '  STOPPED' if state=='stopped' else '  ACTIVE')
        x=px+nw-175
        cv2.rectangle(frame,(x,py+nh-31),(px+nw-1,py+nh-1),(255,255,255),-1)
        text(frame,label,(x+8,py+nh-10),.47,GREEN if state=='arrived' else INK)
    for i,stage in enumerate('ABC'):
        states={a:goal_state(pair,a,stage,current,step) for a in pair['arms']}
        issued=any(v!='pending' for v in states.values())
        all_done=all(v=='arrived' for v in states.values())
        active=any(v=='active' for v in states.values())
        # Split status strips prevent a GEM success from implying Baseline success.
        border=GREEN if all_done else AMBER if active else (210,210,210)
        gx,gy,gw,gh=578+i*280,24,260,146
        cv2.rectangle(frame,(gx-3,gy-3),(gx+gw+2,gy+gh+65),(248,248,248),-1)
        if issued:
            frame[gy:gy+gh,gx:gx+gw]=cv2.resize(goals[stage]['image'],(gw,gh))
        else:
            cv2.rectangle(frame,(gx,gy),(gx+gw-1,gy+gh-1),(243,243,243),-1)
            text(frame,'Awaiting goal',(gx+55,gy+82),.55,(145,145,145))
        cv2.rectangle(frame,(gx-2,gy-2),(gx+gw+1,gy+gh+1),border,3)
        role='Novel' if pair['sequence'][i]=='N' else 'Revisit'
        text(frame,f'{stage}  /  {role}',(gx+8,gy+gh+26),.62,INK,2)
        for j,arm in enumerate(['gem','base']):
            state=states[arm];x=gx+j*130
            color=GREEN if state=='arrived' else AMBER if state=='active' else (70,80,195) if state=='stopped' else (150,150,150)
            cv2.rectangle(frame,(x,gy+gh+38),(x+126,gy+gh+62),(255,255,255),-1)
            cv2.circle(frame,(x+8,gy+gh+49),4,color,-1,cv2.LINE_AA)
            label=('GEM' if arm=='gem' else 'Base')+' '+dict(arrived='OK',active='active',stopped='stopped',pending='--')[state]
            text(frame,label,(x+18,gy+gh+55),.39,color)
            if state=='arrived':cv2.line(frame,(x,gy+gh+64),(x+126,gy+gh+64),GREEN,3)
    text(frame,f'{min(step,longest)*.1:5.1f} s  |  x{steps_per_second*.1:g}',(1655,46),.7,INK,2)
    if tail_speed>1 and gem_end<=step<longest:
        text(frame,f'Baseline tail x{tail_speed:.1f}',(1635,78),.48,INK)

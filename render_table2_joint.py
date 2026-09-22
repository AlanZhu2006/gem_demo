"""Table II paired three-leg video using the gem_indoor_joint shared-map presentation."""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from render_indoor_joint import JointMap, ribbon, ring, disc

COL={'gem':np.array([230,155,77],np.uint8),'base':np.array([72,87,240],np.uint8)}
NAME={'gem':'GEM','base':'Baseline'}
W,H=1920,1080
MX,MY,MW,MH=570,68,1332,960


class SimulationMap(JointMap):
    def __init__(self,*args,floor_min_height=-.30,cloud_mode='raw',**kwargs):
        # The pose-derived floor is not an exact plane for predicted depth.
        # The real-video -8 cm cut removes this sequence's reconstructed floor.
        self.floor_min_height=floor_min_height
        super().__init__(*args,**kwargs)
        self.fusion=None
        self.fused_paths=set()
        self.latest_fused_step={'gem':-1,'base':-1}
        if cloud_mode=='tsdf':
            from cloud_surface_fusion import SurfaceFusion
            self.fusion=SurfaceFusion(self.s)

    def reveal(self,cut_time):
        if self.fusion is None:
            return super().reveal(cut_time)
        changed=False
        pending=[i for i,(t,a,_,_) in enumerate(self.items)
                 if not self.shown[i] and t<=cut_time[a]]
        for i in sorted(pending,key=lambda i:(self.items[i][0],self.items[i][1])):
            t,a,path,T=self.items[i]
            step=round(t*10)
            if path not in self.fused_paths and step%3==0:
                with np.load(path) as p:
                    self.fusion.integrate(p,self.quality_mask(p),T)
                self.fused_paths.add(path)
                self.latest_fused_step[a]=step
                changed=True
            self.shown[i]=True
        if changed:
            from cloud_surface_fusion import rasterize_surface
            X,C=self.cut(*self.fusion.extract())
            rasterize_surface(self,X,C,self.fusion.voxel_m)

    def fusion_audit(self):
        return (dict(fused_frames=self.fusion.frames,
                     latest_fused_step=self.latest_fused_step.copy()) if self.fusion else {})

    def cut(self,X,rgb=None):
        height=(self.d-np.asarray(X)@self.n)/self.s
        keep=(height>self.floor_min_height)&(height<self.zmax)
        return X[keep] if rgb is None else (X[keep],rgb[keep])

    @staticmethod
    def quality_mask(p):
        d,c,rgb=p['depth'],p['conf'],p['rgb']
        h,w=d.shape
        valid=np.isfinite(d)&(d>0)&np.isfinite(c)&(rgb.max(2)>12)
        pad=np.pad(np.where(valid,d,np.nan),1,constant_values=np.nan)
        neighbours=np.stack([pad[i:i+h,j:j+w] for i in range(3) for j in range(3)])
        with np.errstate(invalid='ignore'):
            count=np.sum(np.isfinite(neighbours),axis=0)
            mean=np.nansum(neighbours,axis=0)/np.maximum(count,1)
        flat=(np.abs(d-mean)<.012*d)&(count>=6)
        threshold=np.percentile(c[valid],65) if valid.any() else np.inf
        return valid&flat&(c>=threshold)

    def frame_points(self,p):
        d,K,rgb=p['depth'],p['K'],p['rgb']
        valid=self.quality_mask(p)
        sample=np.zeros_like(valid);sample[::3,::3]=True
        v,u=np.nonzero(valid&sample)
        pts=(np.column_stack((u,v,np.ones(len(u))))@np.linalg.inv(K).T)*d[v,u,None]
        return pts.astype(np.float32),rgb[v,u]


def text(im,s,xy,scale=.7,color=(220,220,220),thickness=1):
    cv2.putText(im,s,xy,cv2.FONT_HERSHEY_SIMPLEX,scale,tuple(int(x) for x in color),thickness,cv2.LINE_AA)


def main():
    global MX,MY,MW,MH
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--frame',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--fps',type=int,default=30)
    ap.add_argument('--steps-per-second',type=float,default=15)
    ap.add_argument('--preview',type=int,help='Render one cumulative source step.')
    ap.add_argument('--arrival-hold',type=float,default=1.5,
                    help='Shared playback pause at each visual arrival; neither arm advances.')
    ap.add_argument('--end-hold',type=float,default=3.,help='Final result hold in seconds.')
    ap.add_argument('--baseline-tail-seconds',type=float,default=0,
                    help='Compress the remaining shared clock after GEM ends; 0 preserves full timing.')
    ap.add_argument('--gem-track-width',type=float,default=.18,help='Displayed ribbon width in metres.')
    ap.add_argument('--baseline-track-width',type=float,default=.34,help='Keep wider than GEM to expose a shared prefix.')
    ap.add_argument('--floor-min-height',type=float,default=-.30,
                    help='Lower cloud height relative to the pose-derived floor, in metres.')
    ap.add_argument('--cloud-mode',choices=['raw','tsdf'],default='raw',
                    help='Raw accumulated points or causal 2.5 cm TSDF surface fusion.')
    ap.add_argument('--presentation',choices=['joint','legacy'],default='joint')
    ap.add_argument('--theme',choices=['white','dark','refined','minimal'],default='white')
    ap.add_argument('--hide-local-candidates',action='store_true',help='Show only the selected NavDP local path.')
    args=ap.parse_args()
    if args.arrival_hold<0 or args.end_hold<0:
        ap.error('Hold durations must be nonnegative.')
    if args.presentation=='joint':
        MX,MY,MW,MH=(556,246,1346,816) if args.theme!='dark' else (556,14,1346,1062)
        if args.theme=='refined':MX,MY,MW,MH=548,278,1344,774
        if args.theme=='minimal':MX,MY,MW,MH=548,198,1344,854
    if not 0<args.gem_track_width<args.baseline_track_width:
        ap.error('Require positive GEM width and a wider Baseline ribbon.')
    if not np.isfinite(args.floor_min_height) or args.floor_min_height>=1.10:
        ap.error('Floor minimum must be finite and below the 1.10 m upper cut.')
    pair=json.loads((args.source/'paired.json').read_text());g=json.loads(args.frame.read_text())
    visual=pair.get('success_definition')=='rgb_visual_arrival'
    sequence=pair['sequence'];roles=dict(zip('ABC',sequence))
    M=SimulationMap(MW,MH,elev=67,zmax_m=1.10,floor_min_height=args.floor_min_height,
                    cloud_mode=args.cloud_mode,config=args.frame,manifest=g['manifest'])
    plans=None
    if args.presentation=='joint':
        from joint_sim_style import RecordedPlans,draw_tracks,draw_panels
        plans=RecordedPlans(pair)
    goals={x['stage']:x for x in pair['goals']}
    for goal in goals.values():
        goal['image']=cv2.imread(str(args.source/goal['path']))
        goal['model']=g['scale']*np.array(g['R'])@np.array(goal['position'])+np.array(g['t'])
    longest=max(len(a['frames']) for a in pair['arms'].values())
    nframes=int(np.ceil((longest/args.steps_per_second+args.end_hold)*args.fps))
    timeline=[int(i/args.fps*args.steps_per_second) for i in range(nframes)]
    gem_end=len(pair['arms']['gem']['frames']);tail_speed=1.
    if args.baseline_tail_seconds>0 and longest>gem_end:
        main_frames=int(np.ceil(gem_end/args.steps_per_second*args.fps))
        remaining=longest-gem_end
        tail_frames=max(1,min(int(np.ceil(remaining/args.steps_per_second*args.fps)),
                              round(args.baseline_tail_seconds*args.fps)))
        timeline=[int(i/args.fps*args.steps_per_second) for i in range(main_frames)]
        timeline += np.linspace(gem_end,longest-1,tail_frames).astype(int).tolist()
        timeline += [longest]*round(args.end_hold*args.fps)
        tail_speed=remaining/(tail_frames/args.fps*args.steps_per_second)
    if visual:
        arrivals={leg['arrival_step'] for arm in pair['arms'].values()
                  for leg in arm['legs'] if leg.get('arrival_step') is not None}
        # Never skip a real arrival when sampling the accelerated tail.
        for at in sorted(arrivals-set(timeline)):
            timeline.insert(int(np.searchsorted(timeline,at)),at)
        expanded=[];held=set()
        for step in timeline:
            expanded.append(step)
            if step in arrivals and step not in held:
                expanded.extend([step]*max(0,int(args.arrival_hold*args.fps)))
                held.add(step)
        timeline=expanded;nframes=len(timeline)
    writer=None
    if args.preview is None:
        writer=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24',
            '-s',f'{W}x{H}','-r',str(args.fps),'-i','-','-c:v','libx264','-crf','19',
            '-pix_fmt','yuv420p','-movflags','+faststart',str(args.out)],stdin=subprocess.PIPE)
    audits=[];up=-M.n
    previous_state=None;encoded_frame=None;local_audit={}
    indexes=[0] if args.preview is not None else range(nframes)
    for fi in indexes:
        step=args.preview if args.preview is not None else timeline[fi]
        current={a:min(step,len(v['frames'])-1) for a,v in pair['arms'].items()}
        tick_state=min(step,longest)
        if writer is not None and tick_state==previous_state:
            writer.stdin.write(encoded_frame)
            audits.append(dict(video_frame=fi,source_step=step,arm_step=current,shown_frames=int(M.shown.sum()),local_plans=local_audit,**M.fusion_audit()))
            continue
        cuts={a:idx*.1 for a,idx in current.items()}
        M.reveal(cuts)
        raster,z=M.raster.copy(),M.z_obs.copy()
        if args.theme!='dark':raster[~np.isfinite(M.z)]=255
        local_audit={}
        if plans is not None:
            local_audit=draw_tracks(M,raster,z,current,pair,plans,dict(gem=args.gem_track_width,base=args.baseline_track_width),center_width=.085 if args.theme in ('refined','minimal') else .12,show_candidates=not args.hide_local_candidates)
        else:
            for a in ['base','gem']:
                if cuts[a] < M.path[a][1][0]:
                    continue
                P=M.to_floor(M.track(a,cuts[a]),.02)
                width=args.baseline_track_width if a=='base' else args.gem_track_width
                M.splat(ribbon(P,up,width*M.s,M.step_u),COL[a],raster,z,((0,0),(1,0),(0,1)),update_z=False)
                pos=M.to_floor(M.pos_at(a,cuts[a])[None],.032)[0]
                M.splat(ring(pos,up,.19*M.s,.035*M.s,M.step_u),np.array([255,255,255]),raster,z,update_z=False)
                M.splat(disc(pos,up,.10*M.s,M.step_u),COL[a],raster,z,update_z=False)
        frame=np.full((H,W,3),(255,255,255) if args.theme!='dark' else (16,14,12),np.uint8)
        issued=set()
        if args.presentation=='legacy':
            for a,yy in [('gem',76),('base',574)]:
                arm=pair['arms'][a];r=arm['frames'][current[a]];leg=next(x for x in arm['legs'] if x['stage']==r['leg'])
                finished=step>=len(arm['frames'])
                completed=sum(bool(x['reached']) for x in arm['legs'])
                status=(f'{completed}/3 complete' if leg['reached'] else 'Stopped: '+leg['termination']) if finished else f'Leg {r["leg"]}  '+('Novel' if roles[r['leg']]=='N' else 'Revisit')
                if visual and leg.get('arrival_step') is not None and current[a]>=leg['arrival_step']:
                    status='Visual arrival '+r['leg']
                cv2.rectangle(frame,(18,yy-35),(550,yy+2),tuple(int(x) for x in COL[a]),-1)
                text(frame,NAME[a],(30,yy-9),.8,(255,255,255),2)
                text(frame,status,(170,yy-9),.62,(255,255,255),1)
                rgb=cv2.imread(r['path'])
                if finished and not leg['reached']:rgb=(rgb*.45).astype(np.uint8)
                frame[yy+10:yy+309,18:550]=cv2.resize(rgb,(532,299))
                goal=goals[r['leg']];issued.add(r['leg'])
                frame[yy+323:yy+413,18:178]=cv2.resize(goal['image'],(160,90))
                text(frame,'Current goal '+r['leg'],(194,yy+347),.64)
                text(frame,f'Step {current[a]+1} / {len(arm["frames"])}',(194,yy+379),.6)
                for li,label in enumerate([f'{stage}  {roles[stage]}' for stage in 'ABC']):
                    found=next((x for x in arm['legs'] if x['stage']==label[0]),None)
                    state=''
                    done_at=(found.get('arrival_step') if visual and found and found.get('arrival_step') is not None
                             else (found['stop'] if found else None))
                    if found and step>=done_at:state=' OK' if found['reached'] else ' FAIL'
                    elif not found and finished:state=' --'
                    text(frame,label+state,(20+li*177,yy+446),.59,COL[a])
        for stage in ([] if visual else issued):
            goal=goals[stage];point=M.to_floor(goal['model'][None],.04)[0]
            M.splat(ring(point,up,.30*M.s,.035*M.s,M.step_u),np.array([60,200,255]),raster,z,update_z=False)
            uv,_=M.project(point[None]);x,y=uv[0]
            if 0<=x<MW and 0<=y<MH:
                text(raster.reshape(MH,MW,3),stage,(x+10,y-8),.7,(60,200,255),2)
        if visual:
            arrival_labels=[];marked_observations=set()
            for arm in ['gem','base']:
                for leg in pair['arms'][arm]['legs']:
                    at=leg.get('arrival_step')
                    if at is None or step<at:continue
                    observation=(leg['stage'],at,pair['arms'][arm]['frames'][at]['sha256'])
                    if observation in marked_observations:continue
                    marked_observations.add(observation)
                    point=M.to_floor(M.pos_at(arm,at*.1)[None],.04)[0]
                    for radius,width in ([(.27,.035)] if args.theme=='minimal' else [(.40,.055),(.26,.030)]):
                        M.splat(ring(point,up,radius*M.s,width*M.s,M.step_u),
                                np.array([60,200,255]),raster,z,update_z=False)
                    uv,_=M.project(point[None]);x,y=uv[0]
                    if 0<=x<MW and 0<=y<MH:
                        arrival_labels.append((leg['stage'],int(x),int(y)))
            # Revisit arrivals can be near one another. Keep their true ring
            # positions, but place leg labels outside the overlapping circles.
            canvas=raster.reshape(MH,MW,3);occupied=[]
            for label,x,y in arrival_labels:
                offset=35 if args.theme=='minimal' else 55
                bx=int(np.clip(x+offset,4,MW-48));by=int(np.clip(y-offset,30,MH-8))
                while any(abs(bx-px)<54 and abs(by-py)<38 for px,py in occupied):
                    by+=40
                    if by>MH-8:bx=max(4,bx-65);by=MH-8
                occupied.append((bx,by))
                if args.theme=='minimal':
                    text(canvas,label,(bx,by),.6,(255,255,255),4)
                    text(canvas,label,(bx,by),.6,(50,75,90),1)
                    continue
                cv2.line(canvas,(x,y),(bx,by-10),(60,200,255),1,cv2.LINE_AA)
                cv2.rectangle(canvas,(bx-5,by-27),(bx+31,by+7),(255,255,255) if args.theme!='dark' else (24,24,24),-1)
                text(canvas,label,(bx,by),.8,(20,125,180) if args.theme!='dark' else (60,200,255),2)
        frame[MY:MY+MH,MX:MX+MW]=raster.reshape(MH,MW,3)
        if plans is not None:
            draw_panels(frame,pair,goals,current,step,tail_speed,gem_end,longest,args.steps_per_second,args.theme)
        else:
            title='RGB arrival demo' if visual else 'Table II'
            text(frame,f'{title}  |  {pair["scene"]}  |  {" - ".join(sequence)}',(MX,42),.78)
            footer=('Both methods + shared RGB centering | blue: GEM  red: Baseline'
                    if pair.get('shared_visual_centering') else
                    'Joint LingBot reconstruction  |  blue: GEM   red: Baseline')
            if pair.get('novel_max_route_angle_deg',60)>60:
                footer='Shared RGB centering + wider novel goals | blue: GEM  red: Baseline'
            if pair.get('goal_view_variant'):
                footer='Predefined A view + shared RGB centering | blue: GEM  red: Baseline'
            if pair.get('arrival_profile','').startswith('aligned'):
                footer='Aligned RGB arrival + shared centering | blue: GEM  red: Baseline'
            text(frame,footer,(MX,1058),.61)
            text(frame,f'Playback: {args.steps_per_second:g} simulator steps/s',(18,1058),.58)
            if tail_speed>1 and gem_end<=step<longest:
                cv2.rectangle(frame,(MX+8,MY+8),(MX+590,MY+48),(24,24,24),-1)
                text(frame,f'Baseline remainder: {tail_speed:.1f}x fast-forward',
                     (MX+20,MY+36),.7,(235,235,235),1)
        visible_steps=[(a,t/.1) for seen,(t,a,_,_) in zip(M.shown,M.items) if seen]
        assert all(s<=current[a]+1e-5 for a,s in visible_steps)
        audits.append(dict(video_frame=fi,source_step=step,arm_step=current,shown_frames=int(M.shown.sum()),local_plans=local_audit,**M.fusion_audit()))
        if args.preview is not None:
            cv2.imwrite(str(args.out),frame);print('Preview',args.out);return
        encoded_frame=frame.tobytes();previous_state=tick_state
        writer.stdin.write(encoded_frame)
        if fi%150==0:print(f'{fi}/{nframes}',flush=True)
    writer.stdin.close()
    if writer.wait()!=0:raise RuntimeError('ffmpeg failed')
    report=dict(source=str(args.source.resolve()),reconstruction=g['root'],scene=pair['scene'],
        task=pair['task_index'],sequence=pair['sequence'],gt_validation=g,
        playback='Shared observation clock; arrival holds; optional labeled acceleration after GEM ends; frozen after actual termination.',
        baseline_tail_seconds=args.baseline_tail_seconds,baseline_tail_speed=tail_speed,
        baseline_tail_start_step=gem_end,
        track_width_m=dict(gem=args.gem_track_width,base=args.baseline_track_width),
        success_definition=pair.get('success_definition','original_benchmark'),
        goal_marker=('Double ring at actual RGB arrival observation; not surveyed goal position.' if visual else 'GT goal capture position.'),
        arrival_hold_s=args.arrival_hold if visual else 0,
        end_hold_s=args.end_hold,
        inference_causality=g['inference_order'],
        display_causality='Cloud visibility follows source steps. Fixed bounds, display similarity and smoothed ribbons use full-run data; this is an offline comparison.',
        geometry=('Raw LingBot poses/depth. One GT similarity supplies metric scale, gravity and floor; visual rings follow actual latch poses.' if visual else
                  'Raw LingBot poses/depth. One GT similarity supplies metric scale, gravity, floor and goal positions only.'),
        cloud_height_range_m=[args.floor_min_height,M.zmax],
        presentation=args.presentation,theme=args.theme,
        goal_cards=('Independent arrival borders: GEM outer blue, Baseline inner coral, matching trajectory colors; future images hidden until issued' if args.theme=='minimal' else 'ABC roles with per-arm status; future goal images hidden until issued'),
        local_candidates_visible=not args.hide_local_candidates,
        local_trajectory=(dict(sources=plans.sources,coordinates="Recorded x forward / y left in metres; third component yaw ignored for floor geometry",anchoring="LingBot pose and heading at plan issuance; held at most 30 source steps within same leg",height_m=.02,occlusion="Existing above-floor obstacle depth buffer") if plans else None),
        cloud_mode=args.cloud_mode,
        cloud_fusion=(dict(voxel_m=.025,truncation_m=.10,max_depth_m=12.,source_step_stride=3,
            integrated_frames=M.fusion.frames,shared_predictions='Integrated once by path',
            policy='Only observations reached by the current shared clock; full-resolution quality mask; TSDF geometry/color averaging; metric surfel footprints.') if M.fusion else None),
        final_cloud_coverage_pixels=dict(total=int(np.isfinite(M.z).sum()),
            left_half=int(np.isfinite(M.z.reshape(MH,MW)[:,:MW//2]).sum())),
        display='Path smoothed 13 frames; base wider than GEM to show shared prefixes. Black source pixels filtered. Top35% confidence, stride3; explicit cloud_height_range_m. Floor markings test obstacles only, avoiding mutual depth fighting.',
        visibility_pass=True,fps=args.fps,steps_per_second=args.steps_per_second,frames=audits)
    args.out.with_suffix('.audit.json').write_text(json.dumps(report,indent=2))
    print('Rendered',args.out)


if __name__=='__main__':main()

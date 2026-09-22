"""Render forward timestamped LingBot chunks in a consistent white display frame."""
from pathlib import Path
import json
import numpy as np,cv2
from render_lingbot import floor_frame
ROOT=Path('outputs/icra_submission/montage_plans');W,H=640,320

def prepare(s):
 root=Path(s['reconstruction']);outdir=Path(s['output_directory']);plan_meta=json.load(open(s['plan_file']));recorded_plans=plan_meta['plans'];meta=json.load(open(root/'reconstruction.json'));rows=[r for r in meta['frames'] if not r['warming']][:s.get('display_frames',110)]
 with np.load(root/rows[0]['prediction']) as p:R,origin,floor=floor_frame(p)
 if floor['method'].startswith('camera-up'):
  for ri in [10,25,45,70]:
   with np.load(root/rows[min(ri,len(rows)-1)]['prediction']) as p:rr,oo,ff=floor_frame(p)
   if not ff['method'].startswith('camera-up') and ff.get('support',0)>=800:
    R,origin,floor=rr,oo,ff;floor['display_reference_frame']=ri;break
 if floor['method'].startswith('camera-up'):
  with np.load(root/rows[0]['prediction']) as p:
   T=p['c2w'];world=p['local_points']@T[:3,:3].T+T[:3,3];q=world@R.T
   origin=R.T@np.array([0,0,np.percentile(q[:,2],5)])
   floor['height_reference']='5th percentile of first-frame points, display only'

 points=[];colors=[];poses=[];forwards=[];local_planes=[]
 for row in rows:
  with np.load(root/row['prediction']) as p:
   if s.get('local_grounding',False):
    lr,lo,lf=floor_frame(p);normal=R@lr[2];center_floor=(lo-origin)@R.T
    camera=(p['c2w'][:3,3]-origin)@R.T
    height=float((p['c2w'][:3,3]-lo)@lr[2])
    local_planes.append((normal,center_floor,height) if not lf['method'].startswith('camera-up') and normal[2]>.985 and height>.002 else None)
   T=p['c2w'];fwd=R@T[:3,2];fwd[2]=0;fwd/=max(np.linalg.norm(fwd),1e-9);forwards.append(fwd);depth=p['depth'];conf=p['conf'];K=p['K'];v,u=np.mgrid[:depth.shape[0]:2,:depth.shape[1]:2];z=depth[::2,::2];c=conf[::2,::2]
   valid=np.isfinite(z)&(z>0)&np.isfinite(c);threshold=np.percentile(c[valid],35)
   rays=np.c_[u[valid],v[valid],np.ones(valid.sum())]@np.linalg.inv(K).T;local=rays*z[valid,None]
   q=((local@T[:3,:3].T+T[:3,3])-origin)@R.T
   # Higher coverage comes from original RGB/depth predictions, never filled surfaces.
   m=c[valid]>=threshold;points.append(q[m]);colors.append(p['rgb'][v[valid],u[valid]][m,::-1]);poses.append((T[:3,3]-origin)@R.T)
 poses=np.array(poses)
 # Recenter the display cut at the lower envelope, avoiding a table mistaken for floor.
 ground=float(np.percentile(np.concatenate(points)[:,2],8))
 for q in points:q[:,2]-=ground
 poses[:,2]-=ground;floor['display_height_offset']=ground
 camera_height=max(abs(np.median(poses[:,2])),.05)
 # Uniform floor/ceiling display filter, no deformation, no GT depth/poses.
 for i,q in enumerate(points):
  m=(q[:,2]>-.3*camera_height)&(q[:,2]<1.65*camera_height)&np.isfinite(q).all(1)
  points[i]=q[m];colors[i]=colors[i][m]
 allp=np.concatenate(points);lo,hi=np.percentile(allp,[1,99],axis=0);mid=(lo+hi)/2
 # Same elevation; choose a yaw that packs geometry well in a landscape tile.
 best=None
 for az in np.arange(0,360,30):
  a,e=np.deg2rad([az,52]);direction=np.array([np.cos(e)*np.cos(a),np.cos(e)*np.sin(a),np.sin(e)])
  right=np.array([-np.sin(a),np.cos(a),0]);up=np.cross(direction,right);basis=np.stack([right,up,direction]);q=allp@basis.T
  l,h=np.percentile(q[:,:2],[1,99],axis=0);span=h-l;scale=min((W-52)/span[0],(H-48)/span[1]);score=scale*scale*np.prod(span)
  if best is None or score>best[0]:best=(score,basis,l,h,scale,int(az))
 _,basis,l,h,scale,az=best;scale*=.82;center=(l+h)/2
 # Ground the reconstructed camera track on the fixed estimated display floor.
 floor_z=-ground+camera_height*.012
 track=poses.copy();track[:,2]=floor_z
 display_planes=[];plan_scales=[]
 previous=(np.array([0.,0.,1.]),np.array([0.,0.,floor_z]),max(abs(float(np.median(poses[:,2]+ground))),.03))
 for i in range(len(rows)):
  if local_planes and local_planes[i] is not None:
   normal,center_floor,height=local_planes[i];center_floor=center_floor.copy();center_floor[2]-=ground
   z=center_floor[2]-np.dot(normal[:2],track[i,:2]-center_floor[:2])/normal[2]
   previous=(np.array([0.,0.,1.]),np.array([track[i,0],track[i,1],z]),height)
  normal,center_floor,height=previous
  if s.get('local_grounding',False):track[i,2]=center_floor[2]-np.dot(normal[:2],track[i,:2]-center_floor[:2])/normal[2]+height*.012
  display_planes.append((normal,center_floor,height));plan_scales.append(height/plan_meta['camera_height_m'])
 zbuf=np.full(W*H,-np.inf);raster=np.full((W*H,3),255,np.uint8);d=outdir/'tiles';d.mkdir(exist_ok=True);aud=[];done=0
 clean=outdir/'tiles_clean';clean.mkdir(exist_ok=True)
 units_per_m=max(abs(float(np.median(poses[:,2]+ground))),.03)/plan_meta['camera_height_m']
 def stroke(im,path,width_px,color):
  p=np.asarray(path,float)
  if len(p)<2:return 0,0
  lengths=np.linalg.norm(np.diff(p,axis=0),axis=1);keep=np.r_[True,lengths>1e-8];p=p[keep]
  if len(p)<2:return 0,0
  distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
  u=np.linspace(0,distance[-1],max(2,min(5000,int(distance[-1]*scale/.45)+1)))
  c=np.column_stack([np.interp(u,distance,p[:,i]) for i in range(3)])
  tang=np.gradient(c,axis=0);side=np.c_[-tang[:,1],tang[:,0],np.zeros(len(c))];side/=np.maximum(np.linalg.norm(side,axis=1,keepdims=True),1e-9)
  offsets=np.linspace(-width_px/scale/2,width_px/scale/2,max(5,int(width_px*3)))
  q=(c[:,None,:]+side[:,None,:]*offsets[None,:,None]).reshape(-1,3)@basis.T
  uv=np.rint(np.c_[(q[:,0]-center[0])*scale+W/2,-(q[:,1]-center[1])*scale+H/2]).astype(int)
  u,v=uv[:,0],uv[:,1];valid=(u>=0)&(u<W)&(v>=0)&(v<H);q=q[valid];pix=v[valid]*W+u[valid]
  visible=q[:,2]>=zbuf[pix]-camera_height*.018
  im.reshape(-1,3)[pix[visible]]=color
  return int(len(np.unique(pix[visible]))),int(len(np.unique(pix[~visible])))
 tile_frames=s.get('tile_frames',150)
 for k in range(tile_frames):
  target=round(k/(tile_frames-1)*len(rows))
  while done<target:
   q=points[done]@basis.T;uv=np.rint(np.c_[(q[:,0]-center[0])*scale+W/2,-(q[:,1]-center[1])*scale+H/2]).astype(int)
   for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
    u,v=uv[:,0]+dx,uv[:,1]+dy;ids=np.flatnonzero((u>=0)&(u<W)&(v>=0)&(v<H));ids=ids[np.argsort(-q[ids,2],kind='stable')];pix=v[ids]*W+u[ids];_,j=np.unique(pix,return_index=True);ids,pix=ids[j],pix[j];m=q[ids,2]>zbuf[pix];zbuf[pix[m]]=q[ids[m],2];raster[pix[m]]=colors[done][ids[m]]
   done+=1
  im=raster.reshape(H,W,3).copy()
  cv2.imwrite(str(clean/f'{k:03d}.jpg'),im,[cv2.IMWRITE_JPEG_QUALITY,95])
  trajectory_visible=0;trajectory_occluded=0;candidate_count=0;candidate_pixels=0;selected_pixels=0;plan_time=None;plan_id=None
  if done>=2:
   trajectory_visible,trajectory_occluded=stroke(im,track[:done],3.2,(135,135,135))
   timestamp=rows[done-1]['timestamp_ns'];eligible=[p for p in recorded_plans if p['timestamp_ns']<=timestamp]
   plan=eligible[-1] if eligible else None
   if plan is not None and timestamp-plan['timestamp_ns']<=3e9:
    plan_time=plan['timestamp_ns'];plan_id=plan['plan_index'];here=track[done-1];fwd=forwards[done-1]
    side=np.cross([0,0,1.],fwd) if s['kind']=='simulation' else np.cross(fwd,[0,0,1.])
    def world(local):
     a=np.asarray(local,float);a=np.vstack([np.zeros((1,a.shape[-1])),a]);unit=plan_scales[done-1] if s.get('local_grounding',False) else units_per_m
     q=here+a[:,:1]*fwd*unit+a[:,1:2]*side*unit;q[:,2]=floor_z
     if s.get('local_grounding',False):
      normal,center_floor,height=display_planes[done-1];q[:,2]=center_floor[2]-(q[:,:2]-center_floor[:2])@normal[:2]/normal[2]+height*.012
     return q
    cand=np.asarray(plan['candidates'],float)
    if cand.size:
     cand=cand.reshape(-1,*cand.shape[-2:])
     for local in cand:
      if len(local)<2:continue
      candidate_count+=1;v,o=stroke(im,world(local[:max(2,int(len(local)*.6))]),1.9,(80,80,80));candidate_pixels+=v
    selected=np.asarray(plan['selected'],float)
    if selected.size and len(selected)>1:
     path=world(selected[:max(2,int(len(selected)*.8))]);stroke(im,path,7.,(255,255,255));selected_pixels,_=stroke(im,path,4.8,(235,135,35))
  cv2.imwrite(str(d/f'{k:03d}.jpg'),im,[cv2.IMWRITE_JPEG_QUALITY,95]);aud.append(dict(frame=k,cloud_frames=done,last_source_timestamp_ns=rows[done-1]['timestamp_ns'] if done else None,visible_pixels=int(np.isfinite(zbuf).sum()),trajectory_visible_pixels=trajectory_visible,trajectory_occluded_pixels=trajectory_occluded,candidate_count=candidate_count,candidate_visible_pixels=candidate_pixels,selected_visible_pixels=selected_pixels,plan_timestamp_ns=plan_time,plan_index=plan_id))
 report=dict(scene=s['name'],source=str(root/'reconstruction.json'),floor=floor,display_yaw=az,elevation=52,framing='Full excerpt bounds for a fixed display camera only',confidence_percentile=35,pixel_stride=2,planning=dict(source=plan_meta['source'],source_sha256=plan_meta['sha256'],convention=plan_meta['coordinate_convention'],units_per_m=units_per_m,hold_seconds=3,style='Recorded gray candidates; one selected blue path with white halo; neutral traveled trail',candidate_width_px=1.9,selected_width_px=4.8,halo_width_px=7.0),trajectory=dict(source='Prefix of reconstructed c2w camera centers',ground_z=float(floor_z),height_lift=float(camera_height*.012),local_grounding=s.get('local_grounding',False),local_grounding_description='Current RGB floor plane, latest valid causal estimate; rigid scene frame stays fixed',occlusion='Shared geometry z-buffer; no screen-space overlay'),geometry='Monotonic forward prefix of official demo.py RGB-only outputs',frames=aud)
 (outdir/'tiles.audit.json').write_text(json.dumps(report,indent=2));print(s['name'],aud[-1]['visible_pixels'],floor,flush=True)

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--scene');ap.add_argument('--selection',default=str(ROOT/'selection.json'));args=ap.parse_args()
 for s in json.load(open(args.selection)):
  if args.scene and s['name']!=args.scene:continue
  if (Path(s['reconstruction'])/'reconstruction.json').exists():prepare(s)

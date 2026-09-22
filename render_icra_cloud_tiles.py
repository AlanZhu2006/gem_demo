"""Render forward timestamped LingBot chunks in a consistent white display frame."""
from pathlib import Path
import json
import numpy as np,cv2
from render_lingbot import floor_frame
ROOT=Path('outputs/icra_submission/montage');W,H=640,320

def prepare(s):
 root=Path(s['reconstruction']);meta=json.load(open(root/'reconstruction.json'));rows=[r for r in meta['frames'] if not r['warming']][:(55 if s['kind']=='real' else 110)]
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

 points=[];colors=[];poses=[]
 for row in rows:
  with np.load(root/row['prediction']) as p:
   T=p['c2w'];depth=p['depth'];conf=p['conf'];K=p['K'];v,u=np.mgrid[:depth.shape[0]:2,:depth.shape[1]:2];z=depth[::2,::2];c=conf[::2,::2]
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
 zbuf=np.full(W*H,-np.inf);raster=np.full((W*H,3),255,np.uint8);d=root.parent/'tiles';d.mkdir(exist_ok=True);aud=[];done=0
 clean=root.parent/'tiles_clean';clean.mkdir(exist_ok=True)
 for k in range(150):
  target=round(k/149*len(rows))
  while done<target:
   q=points[done]@basis.T;uv=np.rint(np.c_[(q[:,0]-center[0])*scale+W/2,-(q[:,1]-center[1])*scale+H/2]).astype(int)
   for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
    u,v=uv[:,0]+dx,uv[:,1]+dy;ids=np.flatnonzero((u>=0)&(u<W)&(v>=0)&(v<H));ids=ids[np.argsort(-q[ids,2],kind='stable')];pix=v[ids]*W+u[ids];_,j=np.unique(pix,return_index=True);ids,pix=ids[j],pix[j];m=q[ids,2]>zbuf[pix];zbuf[pix[m]]=q[ids[m],2];raster[pix[m]]=colors[done][ids[m]]
   done+=1
  im=raster.reshape(H,W,3).copy()
  cv2.imwrite(str(clean/f'{k:03d}.jpg'),im,[cv2.IMWRITE_JPEG_QUALITY,95])
  trajectory_visible=0;trajectory_occluded=0
  if done>=2:
   # Dense 3D ribbon, rasterized through the same point-cloud depth buffer.
   ribbon=[];step=.45/scale;width=2.5/scale
   for a,b in zip(track[:done-1],track[1:done]):
    vec=b-a;length=np.linalg.norm(vec[:2])
    if length<1e-9:continue
    tangent=vec/length;side=np.array([-tangent[1],tangent[0],0.])
    along=np.linspace(0,1,max(2,int(length/step)+1))
    off=np.linspace(-width/2,width/2,7)
    ribbon.append((a+along[:,None]*vec)[:,None,:]+off[None,:,None]*side)
   if ribbon:
    p=np.concatenate([q.reshape(-1,3) for q in ribbon]);q=p@basis.T
    uv=np.rint(np.c_[(q[:,0]-center[0])*scale+W/2,-(q[:,1]-center[1])*scale+H/2]).astype(int)
    u,v=uv[:,0],uv[:,1];valid=(u>=0)&(u<W)&(v>=0)&(v<H);q=q[valid];pix=v[valid]*W+u[valid]
    visible=q[:,2]>=zbuf[pix]-camera_height*.018
    im.reshape(-1,3)[pix[visible]]=(230,155,77)
    trajectory_visible=int(len(np.unique(pix[visible])));trajectory_occluded=int(len(np.unique(pix[~visible])))
  cv2.imwrite(str(d/f'{k:03d}.jpg'),im,[cv2.IMWRITE_JPEG_QUALITY,95]);aud.append(dict(frame=k,cloud_frames=done,last_source_timestamp_ns=rows[done-1]['timestamp_ns'] if done else None,visible_pixels=int(np.isfinite(zbuf).sum()),trajectory_visible_pixels=trajectory_visible,trajectory_occluded_pixels=trajectory_occluded))
 report=dict(scene=s['name'],source=str(root/'reconstruction.json'),floor=floor,display_yaw=az,elevation=52,framing='Full excerpt bounds for a fixed display camera only',confidence_percentile=35,pixel_stride=2,trajectory=dict(source='Prefix of reconstructed c2w camera centers',ground_z=float(floor_z),height_lift=float(camera_height*.012),occlusion='Shared geometry z-buffer; no screen-space overlay'),geometry='Monotonic forward prefix of official demo.py RGB-only outputs',frames=aud)
 (root.parent/'tiles.audit.json').write_text(json.dumps(report,indent=2));print(s['name'],aud[-1]['visible_pixels'],floor,flush=True)

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--scene');args=ap.parse_args()
 for s in json.load(open(ROOT/'selection.json')):
  if args.scene and s['name']!=args.scene:continue
  if (Path(s['reconstruction'])/'reconstruction.json').exists():prepare(s)

"""Fixed-view real-world floor-cut/quality ablation, without changing final media."""
from pathlib import Path
import json
import cv2,numpy as np
from render_indoor_joint import JointMap

out=Path('outputs/real_floor_audit');out.mkdir(exist_ok=True)
m=JointMap(1344,854)
audit=json.loads(Path('outputs/final/realworld.audit.json').read_text());cuts=audit['frames'][-1]['source_times']
items=[r for r in m.items if r[0]<=cuts[r[1]]][::6]
variants=[('Current: -8 cm',-.08,1.1,'filtered'),('Lower cut: -16 cm',-.16,1.1,'filtered'),
          ('Lower cut: -30 cm',-.30,1.1,'filtered'),('Lower cut: -60 cm',-.60,1.1,'filtered'),
          ('No height cut',-1e6,1e6,'filtered'),('No quality filter; -30 cm',-.30,1.1,'raw'),
          ('Confidence only; -30 cm',-.30,1.1,'conf_only'),
          ('Flatness only; -30 cm',-.30,1.1,'flat_only'),
          ('Top 60% + flatness; -30 cm',-.30,1.1,'conf40')]
ras=[np.full_like(m.raster,255) for _ in variants];zs=[np.full_like(m.z,-np.inf) for _ in variants]
heights=[];counts=np.zeros(len(variants),dtype=int);raw_count=0
for i,(_,arm,path,T) in enumerate(items):
 with np.load(path) as p:
  q,c=m.frame_points(p);x=q@T[:3,:3].T+T[:3,3];h=(m.d-x@m.n)/m.s;heights.append(h)
  d,K=p['depth'],p['K'];valid=np.isfinite(d)&(d>0)&np.isfinite(p['conf']);sample=np.zeros_like(valid);sample[::4,::4]=True
  v,u=np.nonzero(valid&sample);rq=(np.column_stack([u,v,np.ones(len(u))])@np.linalg.inv(K).T)*d[v,u,None]
  rx=rq@T[:3,:3].T+T[:3,3];rc=p['rgb'][v,u];rh=(m.d-rx@m.n)/m.s;raw_count+=len(rx)
  pad=np.pad(np.where(valid,d,np.nan),1,constant_values=np.nan);hh,ww=d.shape
  nb=np.stack([pad[i:i+hh,j:j+ww] for i in range(3) for j in range(3)])
  spread=np.nanmax(nb,0)-np.nanmin(nb,0);flat=np.isfinite(spread)&(spread<.035*d)
  conf=p['conf'];c65=conf>=np.percentile(conf[valid],65);c40=conf>=np.percentile(conf[valid],40)
  masks={'conf_only':c65[v,u],'flat_only':flat[v,u],'conf40':(c40&flat)[v,u]}
  for j,(_,lo,hi,kind) in enumerate(variants):
   xx,cc,hh=(x,c,h) if kind=='filtered' else (rx,rc,rh)
   keep=(hh>lo)&(hh<hi)
   if kind in masks:keep &= masks[kind]
   counts[j]+=int(keep.sum());m.splat(xx[keep],cc[keep,::-1],ras[j],zs[j])
 if i%100==0:print(i,len(items),flush=True)
ims=[];stats={};occupied=[np.isfinite(z) for z in zs]
for j,(name,lo,hi,kind) in enumerate(variants):
 im=ras[j].reshape(m.h,m.w,3);cv2.imwrite(str(out/f'variant_{j}.jpg'),im)
 stats[name]=dict(points=int(counts[j]),occupied_pixels=int(occupied[j].sum()),
     added_pixels_vs_current=int((occupied[j]&~occupied[0]).sum()),lower_height_m=lo,upper_height_m=hi,quality=kind)
 panel=np.full((467,672,3),255,np.uint8);panel[40:]=cv2.resize(im,(672,427));cv2.putText(panel,name,(12,27),0,.7,(50,50,50),1,cv2.LINE_AA);ims.append(panel)
cv2.imwrite(str(out/'comparison.jpg'),np.vstack([np.hstack(ims[i:i+3]) for i in range(0,9,3)]))
h=np.concatenate(heights)
report=dict(sampled_observations=len(items),sampling='Every sixth eligible final-video observation, identical final map camera for all variants',
            raw_sampled_points=raw_count,quality_filtered_points=len(h),
            filtered_height_percentiles_m=dict(zip(map(str,[1,5,10,25,50,75,90,99]),np.percentile(h,[1,5,10,25,50,75,90,99]).tolist())),
            variants=stats,note='Screen coverage is not geometry accuracy; raw-filter ablation is diagnostic only.')
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

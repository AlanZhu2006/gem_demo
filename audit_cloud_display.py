"""Compare height cuts on every sixth observation, holding the old view fixed.

Run from the project root with the lingbot-map Python environment. This audits
display filtering only; it does not evaluate reconstruction accuracy.
"""
import json
from pathlib import Path
import numpy as np,cv2
from render_table2_joint import SimulationMap
out=Path('outputs/cloud_display_audit')
out.mkdir(parents=True,exist_ok=True)
g=json.loads(Path('outputs/nnr003_joint_frame.json').read_text())
m=SimulationMap(1332,960,elev=67,floor_min_height=-.08,config='outputs/nnr003_joint_frame.json',manifest=g['manifest'])
variants=[('current',-.08,1.1),('floor_minus_030',-.30,1.1),('floor_minus_060',-.60,1.1),('uncut',-100,100)]
ras=[np.zeros_like(m.raster) for _ in variants]; zs=[np.full_like(m.z,-np.inf) for _ in variants]
heights=[];counts=np.zeros(4,dtype=int)
for i,(_,_,p,T) in enumerate(m.items[::6]):
 with np.load(p) as f:q,c=m.frame_points(f)
 x=q@T[:3,:3].T+T[:3,3];h=(m.d-x@m.n)/m.s;heights.append(h)
 for j,(_,lo,hi) in enumerate(variants):
  keep=(h>lo)&(h<hi);counts[j]+=keep.sum();m.splat(x[keep],c[keep,::-1],ras[j],zs[j])
report={'sampled_frames':len(heights),'height_percentiles':dict(zip(map(str,[0,1,5,10,25,50,75,90,99,100]),np.percentile(np.concatenate(heights),[0,1,5,10,25,50,75,90,99,100]).tolist())),'variants':{}}
ims=[]
for j,(name,lo,hi) in enumerate(variants):
 im=ras[j].reshape(960,1332,3);cv2.imwrite(str(out/(name+'.jpg')),im)
 occupied=np.isfinite(zs[j]).reshape(960,1332)
 report['variants'][name]={'points':int(counts[j]),'pixels':int(occupied.sum()),'left_pixels':int(occupied[:,:666].sum())}
 im=cv2.resize(im,(666,480));cv2.putText(im,name,(15,35),0,1,(255,255,255),2);ims.append(im)
cv2.imwrite(str(out/'height_ablation.jpg'),np.vstack([np.hstack(ims[:2]),np.hstack(ims[2:])]))
(out/'height_ablation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

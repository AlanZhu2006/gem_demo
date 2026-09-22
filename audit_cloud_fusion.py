"""Final-view TSDF parameter comparison; production renderer handles causal playback.

Run from the project root in the lingbot-map environment.
"""
import json
from pathlib import Path
import numpy as np,cv2,open3d as o3d
from render_table2_joint import SimulationMap
out=Path('outputs/cloud_fusion_audit');out.mkdir(exist_ok=True)
g=json.loads(Path('outputs/nnr003_joint_frame.json').read_text());m=SimulationMap(1332,960,elev=67,config='outputs/nnr003_joint_frame.json',manifest=g['manifest'])
volumes=[o3d.pipelines.integration.ScalableTSDFVolume(voxel_length=v,sdf_trunc=.10,color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8) for v in [.025,.04]]
seen=set();n=0
for t,a,path,T in sorted(m.items,key=lambda it:(it[0],it[1])):
 if path in seen:continue
 seen.add(path)
 if round(t*10)%3:continue
 with np.load(path) as p:
  d,c,K,rgb=[p[k] for k in ['depth','conf','K','rgb']];h,w=d.shape
  valid=np.isfinite(d)&(d>0)&np.isfinite(c)&(rgb.max(2)>12)
  pad=np.pad(np.where(valid,d,np.nan),1,constant_values=np.nan)
  nb=np.stack([pad[i:i+h,j:j+w] for i in range(3) for j in range(3)])
  count=np.sum(np.isfinite(nb),axis=0);mean=np.nansum(nb,axis=0)/np.maximum(count,1)
  keep=valid&(np.abs(d-mean)<.012*d)&(count>=6)&(c>=np.percentile(c[valid],65))
  depth=np.where(keep,d/m.s,0).astype(np.float32)
  rgbd=o3d.geometry.RGBDImage.create_from_color_and_depth(o3d.geometry.Image(rgb.copy()),o3d.geometry.Image(depth),depth_scale=1.,depth_trunc=12.,convert_rgb_to_intensity=False)
  intr=o3d.camera.PinholeCameraIntrinsic(w,h,float(K[0,0]),float(K[1,1]),float(K[0,2]),float(K[1,2]))
  pose=np.eye(4);pose[:3,:3]=T[:3,:3];pose[:3,3]=T[:3,3]/m.s
  for vol in volumes:vol.integrate(rgbd,intr,np.linalg.inv(pose))
 n+=1
 if n%100==0:print(n,flush=True)
report={};ims=[]
for v,vol in zip([.025,.04],volumes):
 cloud=vol.extract_point_cloud();X=np.asarray(cloud.points)*m.s;C=np.clip(np.asarray(cloud.colors)[:,::-1]*255,0,255).astype(np.uint8);X,C=m.cut(X,C)
 raster=np.zeros_like(m.raster);z=np.full_like(m.z,-np.inf);m.splat(X,C,raster,z)
 im=raster.reshape(m.h,m.w,3);cv2.imwrite(str(out/f'tsdf_{v}.jpg'),im)
 np.savez_compressed(out/f'tsdf_{v}.npz',points=X,colors=C)
 report[str(v)]={'points':len(X),'pixels':int(np.isfinite(z).sum()),'integrated_frames':n};ims.append(cv2.resize(im,(666,480)))
cv2.imwrite(str(out/'comparison.jpg'),np.hstack(ims));(out/'report.json').write_text(json.dumps(report,indent=2));print(report)

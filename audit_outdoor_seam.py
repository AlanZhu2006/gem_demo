"""Check seam geometry against SIFT correspondences in the actual adjacent RGBs."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--config',default='outputs/outdoor_frame.json');a=ap.parse_args()
g=json.loads(Path(a.config).read_text());root=Path(g['root']);meta=json.loads((root/'reconstruction.json').read_text());man=json.loads(Path(meta['source_manifest']).read_text())
rows=man['frames'];j=next(i for i,r in enumerate(rows) if r['arm']!=rows[0]['arm'])
with np.load(root/f'frames/{j-1:06d}.npz') as p:im0=p['rgb'];d0=p['depth'];K0=p['K'];T0=p['c2w']
with np.load(root/f'frames/{j:06d}.npz') as p:im1=p['rgb'];K1=p['K'];T1=p['c2w']
sift=cv2.SIFT_create();k0,f0=sift.detectAndCompute(cv2.cvtColor(im0,cv2.COLOR_RGB2GRAY),None);k1,f1=sift.detectAndCompute(cv2.cvtColor(im1,cv2.COLOR_RGB2GRAY),None)
matches=[m for m,n in cv2.BFMatcher().knnMatch(f0,f1,k=2) if m.distance<.7*n.distance]
u0=np.array([k0[m.queryIdx].pt for m in matches]);u1=np.array([k1[m.trainIdx].pt for m in matches]);pix=np.rint(u0).astype(int)
d=d0[pix[:,1],pix[:,0]];q=np.column_stack([u0,np.ones(len(u0))])@np.linalg.inv(K0).T*d[:,None]
X=q@T0[:,:3].T+T0[:,3];q1=(X-T1[:,3])@T1[:,:3];uv=q1@K1.T;uv=uv[:,:2]/uv[:,2:]
ok,r,t,ids=cv2.solvePnPRansac(q.astype(np.float32),u1.astype(np.float32),K1,None,iterationsCount=1000,reprojectionError=3,confidence=.999)
report=dict(seam_index=j,matches=len(matches),predicted_pose_reprojection_median_px=float(np.median(np.linalg.norm(uv-u1,axis=1))),predicted_seam_distance_m=float(np.linalg.norm(T0[:,3]-T1[:,3])/g['scale']))
if ok:report.update(pnp_inliers=len(ids),pnp_translation_m=float(np.linalg.norm(t)/g['scale']),prediction_on_pnp_inliers_median_px=float(np.median(np.linalg.norm(uv[ids[:,0]]-u1[ids[:,0]],axis=1))))
print(json.dumps(report,indent=2));Path(a.config).with_suffix('.seam.json').write_text(json.dumps(report,indent=2))

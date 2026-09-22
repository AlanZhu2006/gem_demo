"""Estimate display scale and reference ground from the outdoor joint camera track."""
import json,argparse
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('outputs/outdoor_joint_flashinfer'))
ap.add_argument('--manifest',type=Path,default=Path('outputs/outdoor_inputs/manifest.json'))
ap.add_argument('--out',type=Path,default=Path('outputs/outdoor_frame.json'));args=ap.parse_args()
root=args.root;inputs=args.manifest.parent
rows=json.loads(args.manifest.read_text())['frames'];info={r['key']:r for r in rows}
C=[];Rs=[];ts=[];arms=[];keys=[]
for path in sorted((root/'frames').glob('*.npz')):
 with np.load(path) as p:
  C.append(p['c2w'][:,3]);Rs.append(p['c2w'][:,:3]);ts.append(int(p['timestamp_ns'])/1e9)
  key=int(path.stem);keys.append(key);arms.append(info[key]['arm'])
C=np.array(C);Rs=np.array(Rs);ts=np.array(ts);arms=np.array(arms)
def fit(src,dst):
 x=src-src.mean(0);y=dst-dst.mean(0);u,d,v=np.linalg.svd(y.T@x/len(x))
 sign=np.eye(3);sign[2,2]=np.linalg.det(u@v);R=u@sign@v
 s=float(np.trace(np.diag(d)@sign)/np.mean(np.sum(x*x,axis=1)))
 t=dst.mean(0)-s*(R@src.mean(0));res=np.linalg.norm(src@R.T*s+t-dst,axis=1)/s
 return s,R,t,float(np.sqrt(np.mean(res**2)))
scales={}
for arm in ['gem','base']:
 tel=np.load(inputs/arm/'telemetry.npz')['tel'];sel=arms==arm;t=ts[sel]
 P=np.column_stack([np.interp(t,tel[:,0],tel[:,j]) for j in [1,2,3]])
 # Original render used a 30 cm forward camera stand-off; account for yaw.
 yaw=np.interp(t,tel[:,0],np.unwrap(tel[:,6]));P[:,0]+=.30*np.cos(yaw);P[:,1]+=.30*np.sin(yaw)
 s,R,off,res=fit(P,C[sel]);scales[arm]=dict(scale=s,odom_fit_rmse_m=res)
s=scales['gem']['scale'];mu=C.mean(0);n=np.linalg.svd(C-mu,full_matrices=False)[2][-1]
if n@Rs[:,:,1].mean(0)<0:n=-n
mount=float(np.mean([np.load(inputs/a/'mount.npy')[0] for a in ['gem','base']]))
d=float(mu@n+mount*s)
seam=next(i for i,a in enumerate(arms) if a!=arms[0])
report=dict(root=str(root),manifest=str(args.manifest),inference_order=f'{arms[0]} reversed then {arms[-1]} forward',scale=s,floor_n=n.tolist(),floor_d=d,mount_h=mount,
    scale_diagnostics=scales,camera_plane_p95_m=float(np.percentile(np.abs((C-mu)@n)/s,95)),
    seam_distance_m=float(np.linalg.norm(C[seam]-C[seam-1])/s),
    source='Original LingBot c2w; scale estimated against per-arm recorded odometry; plane fitted to camera centres and shifted by archived mount height. Display calibration only; model points and poses unchanged.')
args.out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

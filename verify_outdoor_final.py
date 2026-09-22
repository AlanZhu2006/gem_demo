"""Verify the outdoor delivery against original clocks, latches and RGB timestamps."""
from pathlib import Path
import json,hashlib
import cv2,numpy as np
from outdoor_final import OutdoorArm

def verify(path):
 path=Path(path);a=json.loads(path.with_suffix('.audit.json').read_text())
 arms={k:OutdoorArm(k,a['input_root']) for k in ['gem','base']}
 rows=json.loads(Path(a['source_manifest']).read_text())['frames'];info={r['key']:r for r in rows}
 meta=json.loads((Path(a['reconstruction'])/'reconstruction.json').read_text())
 times={k:np.array([r['timestamp_ns']/1e9 for r in meta['frames'] if not r['warming'] and info[r['key']]['arm']==k]) for k in arms}
 prev={k:-np.inf for k in arms};events={};plan_counts={k:0 for k in arms}
 for row in a['frames']:
  expected=0
  for k,r in arms.items():
   el=row['elapsed_s'];t=r.at(min(el,r.play));assert abs(t-row['source_times'][k])<1e-6 and t>=prev[k];prev[k]=t
   reached=r.latch_t is not None and (el>=r.play or t>=r.latch_t)
   failed=el>=r.play and not reached
   assert row['arrived'][k]==reached and row['failed'][k]==failed
   if reached or failed:events.setdefault(k,row['video_frame'])
   expected+=int((times[k]<=t).sum())
   idx=max(0,int(np.searchsorted(r.rt,t*1e9,side='right')-1));assert r.rt[idx]/1e9<=t+1e-6
   plan=r.plan(t)
   if plan is not None and el<r.play and not reached:
    assert 0<=t-plan['t']<=3.;plan_counts[k]+=1
  assert row['shown_frames']==expected
 assert a['frames'][-1]['arrived']==dict(gem=True,base=False)
 assert a['speed']==2 and a['arrival_hold_s']==0 and a['end_hold_s']==1
 cap=cv2.VideoCapture(str(path));total=len(a['frames']);n=0;decoded={}
 wanted=set([0,total//4,total//2,total-1]+list(events.values()))
 while True:
  ok,im=cap.read()
  if not ok:break
  assert im.shape==(1080,1920,3)
  if n in wanted:decoded[n]=im.copy()
  # Goal border uses recorded GEM state; Baseline never receives an arrival border.
  blue=im[20:23,570:774].mean(axis=(0,1))
  if n>=events['gem']:
   assert blue[0]>blue[2]+80,blue
  else:
   assert blue.min()>235,blue
  if n>=events['base']:
   region=im[670:910,40:490];spread=np.ptp(region.astype(float),axis=2)
   assert spread.mean()<=3.1 and np.percentile(spread,99)<=4 and region.mean()<125
  n+=1
 fps=cap.get(cv2.CAP_PROP_FPS);cap.release();assert n==total and fps==30
 cv2.imwrite(str(path.with_suffix('.last.jpg')),decoded[total-1])
 for frame,im in decoded.items():cv2.imwrite(str(path.with_name(path.stem+f'.frame_{frame}.jpg')),im)
 cv2.imwrite(str(path.with_suffix('.jpg')),np.vstack([np.hstack([cv2.resize(decoded[i],(960,540)) for i in [0,total//4]]),np.hstack([cv2.resize(decoded[i],(960,540)) for i in [total//2,total-1]])]))
 report=dict(frames=n,fps=fps,duration_s=n/fps,full_decode=True,clock_visibility_verified=True,
   independent_arrivals_verified=True,baseline_grayscale_every_failed_frame_verified=True,
   past_rgb_and_local_plans_verified=True,local_plan_visible_frames=plan_counts,events=events,
   sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reconstruction_caveat=a['pose_causality'])
 path.with_suffix('.verified.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 return report
if __name__=='__main__':
 import sys
 verify(sys.argv[1])

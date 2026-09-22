"""Verify delivery limits, complete decoding, preserved source footage and outcomes."""
from pathlib import Path
import hashlib,json,subprocess
import cv2,numpy as np
ROOT=Path('outputs/icra_submission')
audit=json.loads((ROOT/'assembly.audit.json').read_text());sections=audit['sections']
for s in sections:
 if s['type']=='video':assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['sha256']
for section in sections:
 if section['type']=='video':
  ids=section['source_indices'];assert len(ids)==section['frames'] and ids[0]==0 and ids[-1]==section['source_frames']-1
  assert all(x<y for x,y in zip(ids,ids[1:]))
for p in audit['paper_assets']:assert hashlib.sha256(Path(p['path']).read_bytes()).hexdigest()==p['sha256']
assert sum(s['frames'] for s in sections)==5340
for a,b in zip(sections,sections[1:]):assert a['start_frame']+a['frames']==b['start_frame']

# Master re-encoding may change pixel values slightly, but video content remains
# identical below the explanatory header. Goal cards remain untouched too.
master=ROOT/'GEM_ICRA_master.mp4';mc=cv2.VideoCapture(str(master));comparisons=[]
for s in sections:
 if s['type']!='video':continue
 cap=cv2.VideoCapture(s['source'])
 for i in [s.get('transition_in_frames',0),s['frames']//2,s['frames']-1]:
  source_i=s['source_indices'][i]
  cap.set(cv2.CAP_PROP_POS_FRAMES,source_i);ok,src=cap.read();assert ok
  mc.set(cv2.CAP_PROP_POS_FRAMES,s['start_frame']+i);ok,dst=mc.read();assert ok
  err=np.abs(src[200:].astype(float)-dst[200:].astype(float));assert err.mean()<4,(s['name'],i,err.mean())
  x1=1285 if s['name']=='simulation' else 790
  goal_err=np.abs(src[20:192,552:x1].astype(float)-dst[20:192,552:x1].astype(float)).mean();assert goal_err<4
  comparisons.append(dict(clip=s['name'],source_frame=source_i,output_frame=i,body_mae=float(err.mean()),goal_mae=float(goal_err)))
 cap.release()
# Each 0.4 s boundary starts from the outgoing image, not a white flash.
boundaries=[]
for section in sections[1:]:
 start=section['start_frame'];mc.set(cv2.CAP_PROP_POS_FRAMES,start-1);ok,a=mc.read();assert ok
 ok,b=mc.read();assert ok
 error=float(np.abs(a.astype(float)-b.astype(float)).mean());assert error<3,(section['name'],error)
 boundaries.append(dict(incoming_section=section['name'],first_frame_mae_vs_outgoing=error,transition_frames=section['transition_in_frames']))
mc.release()
reports={}
for stem,width,height,fps,total in [('GEM_ICRA_master',1920,1080,30,5340),('GEM_ICRA_submission',1280,720,24,4188)]:
 p=(ROOT/'visual_cut_v9' if 'submission' in stem else ROOT)/(stem+'.mp4')
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,avg_frame_rate,pix_fmt,field_order:format=duration,size:frame=interlaced_frame','-show_frames','-of','json',str(p)]))
 stream=probe['streams'][0];assert stream['width']==width and stream['height']==height and stream['pix_fmt']=='yuv420p'
 assert len(probe['frames'])==total and all(f['interlaced_frame']==0 for f in probe['frames'])
 assert abs(float(probe['format']['duration'])-5235/30)<.01
 if 'submission' in stem:assert p.stat().st_size<=20_000_000 and float(probe['format']['duration'])<=180 and height>=480 and fps>=20
 cap=cv2.VideoCapture(str(p));assert cap.get(cv2.CAP_PROP_FPS)==fps
 sample_times=[2,14,20,29,36,50,76,113,141,159];want={round(t*fps) for t in sample_times};samples=[];n=0;gray_checked=0
 while True:
  ok,frame=cap.read()
  if not ok:break
  assert frame.shape==(height,width,3)
  if n in want:samples.append((n,frame.copy()))
  if 'submission' in stem:
   t=n/fps
   for s in sections:
    if s['type']!='video':continue
    local=t-s['start_frame']/30
    if not 0<=local<s['frames']/30:continue
    fail_time={'simulation':37.6,'realworld':480/30,'outdoor':1465/30}[s['name']]
    source_i=s['source_indices'][min(s['frames']-1,max(0,round(local*30)))]
    if source_i/30<fail_time+.1:continue
    rois=[(654,900,40,440),(930,1038,220,430)] if s['name']=='realworld' else [(670,910,40,490)]
    for y0,y1,x0,x1 in rois:
     r=frame[round(y0*height/1080):round(y1*height/1080),round(x0*width/1920):round(x1*width/1920)]
     # Decoded source -> BGR master -> YUV upload adds a measured
     # nearly uniform 5/255 channel offset to an originally neutral panel.
     spread=np.ptp(r.astype(float),axis=2);assert spread.mean()<5.1 and np.percentile(spread,99)<=6,(s['name'],local,spread.mean())
     gray_checked+=1
  n+=1
 cap.release();assert n==total
 if 'submission' in stem:
  thumbs=[]
  for i,im in samples:
   cv2.imwrite(str(ROOT/f'check_{i:04d}.jpg'),im)
   thumb=cv2.resize(im,(640,360));cv2.rectangle(thumb,(0,0),(75,24),(255,255,255),-1);cv2.putText(thumb,f'{i/fps:.1f}s',(5,18),0,.5,(40,40,40),1);thumbs.append(thumb)
  cv2.imwrite(str(ROOT/'GEM_ICRA_storyboard.jpg'),np.vstack([np.hstack(thumbs[j:j+2]) for j in range(0,len(thumbs),2)]))
 reports[stem]=dict(frames=n,width=width,height=height,fps=fps,duration_s=n/fps,bytes=p.stat().st_size,full_decode=True,all_frames_progressive=True,failed_gray_regions_checked=gray_checked,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
report=dict(passed=True,limits=dict(max_bytes=20_000_000,max_duration_s=180,min_height=480,min_fps=20,progressive=True),videos=reports,source_frame_comparisons=comparisons,boundary_checks=boundaries,source_hashes_unchanged=True,paper_version_verified=True,upload_performed=False)
(ROOT/'visual_cut_v9/submission.verified.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

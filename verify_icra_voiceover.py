"""Check audio, subtitle timing, unoccluded visuals, source hashes and upload limits."""
from pathlib import Path
import hashlib,json,subprocess
import cv2,numpy as np
R=Path('outputs/icra_submission');a=json.loads((R/'narration/alignment.json').read_text());base=json.loads((R/'assembly.audit.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(R/'GEM_ICRA_master.mp4')==a['visual_master_sha256']
for p in base['paper_assets']:assert sha(p['path'])==p['sha256']
for s in base['sections']:
 if s['type']=='video':assert sha(s['source'])==s['sha256']
reports={}
for name,width,height,fps,total in [('GEM_ICRA_narrated_master.mp4',1920,1080,30,5340),('GEM_ICRA_submission.mp4',1440,810,24,4272)]:
 p=R/name
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]))
 video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
 assert (video['width'],video['height'],video['nb_read_frames'])==(width,height,str(total))
 assert video['avg_frame_rate']==f'{fps}/1' and video['pix_fmt']=='yuv420p'
 fields=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=interlaced_frame','-of','json',str(p)]))['frames']
 assert len(fields)==total and all(f['interlaced_frame']==0 for f in fields)
 assert audio['codec_name']=='aac' and audio['channels']==1
 assert abs(float(probe['format']['duration'])-178)<.08
 assert abs(float(audio['duration'])-178)<.08
 if 'submission' in name:assert p.stat().st_size<=20_000_000 and height>=480 and fps>=20
 subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(p),'-f','null','-'],check=True)
 reports[name]=dict(width=width,height=height,fps=fps,frames=total,duration=float(probe['format']['duration']),bytes=p.stat().st_size,sha256=sha(p),audio=audio['codec_name'],progressive=True,full_decode=True)
 print('Decoded',name,flush=True)
source=cv2.VideoCapture(str(R/'GEM_ICRA_master.mp4'));master=cv2.VideoCapture(str(R/'GEM_ICRA_narrated_master.mp4'));upload=cv2.VideoCapture(str(R/'GEM_ICRA_submission.mp4'))
def frame(cap,t):
 cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read();assert ok;return f
comp=[]
for t in [2,16,22,40,55,70,90,110,128,140,158,168,175]:
 src=cv2.resize(frame(source,t),(1792,1008),interpolation=cv2.INTER_LANCZOS4);dst=frame(master,t)[:1008,64:1856];err=float(np.abs(src.astype(float)-dst.astype(float)).mean());assert err<3,(t,err)
 comp.append(dict(time=t,visual_master_mae=err))
caption_checks=[];previous=0
for c in a['captions']:
 assert 0<=c['start']<c['end']<=178 and c['start']>=previous
 assert '\n' not in c['text'] and len(c['text'])<=64
 assert c['end']-c['start']>=1.1
 previous=c['end'];f=frame(upload,(c['start']+c['end'])/2)
 band=f[758:802,40:1400];dark=int((band.max(axis=2)<170).sum());assert dark>200,(c,dark)
 caption_checks.append(dict(start=c['start'],end=c['end'],ink_pixels=dark))
assert (frame(upload,11.1)[758:807]>245).mean()>.999
a_last=cv2.resize(frame(source,177.8),(1792,1008),interpolation=cv2.INTER_LANCZOS4);b_last=frame(master,177.8)[:1008,64:1856];assert np.abs(a_last.astype(float)-b_last.astype(float)).mean()<3
upload.set(cv2.CAP_PROP_POS_FRAMES,0);gray=0;n=0
while True:
 ok,f=upload.read()
 if not ok:break
 t=n/24
 for s in base['sections']:
  if s['type']!='video':continue
  local=t-s['start_frame']/30
  if not 0<=local<s['frames']/30:continue
  si=s['source_indices'][min(s['frames']-1,max(0,round(local*30)))]
  if si/30<{'simulation':37.6,'realworld':480/30,'outdoor':1465/30}[s['name']]+.1:continue
  rois=[(654,900,40,440),(930,1038,220,430)] if s['name']=='realworld' else [(670,910,40,490)]
  for y0,y1,x0,x1 in rois:
   region=f[round(y0*.7):round(y1*.7),48+round(x0*.7):48+round(x1*.7)].astype(float)
   spread=region.max(axis=2)-region.min(axis=2);assert spread.mean()<5.1 and np.percentile(spread,99)<=6
   gray+=1
 n+=1
assert n==4272
for c in [source,master,upload]:c.release()
# Measure the delivered AAC, not just the intermediate WAV.
p=subprocess.run(['ffmpeg','-hide_banner','-i',str(R/'GEM_ICRA_submission.mp4'),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
loud=json.loads(p.stderr[p.stderr.rfind('{'):]);assert abs(float(loud['input_i'])+16)<1 and float(loud['input_tp'])<-.5
pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(R/'GEM_ICRA_submission.mp4'),'-vn','-ar','24000','-ac','1','-f','f32le','-']),dtype=np.float32)
levels=[]
for b in a['blocks']:
 samples=pcm[round(b['start']*24000):round(b['end']*24000)];rms=float(np.sqrt(np.mean(samples**2)));assert rms>.01
 levels.append(dict(id=b['id'],rms=rms,tempo=b['tempo']))
report=dict(version=24,passed=True,files=reports,source_and_paper_hashes=True,visual_comparisons=comp,captions=caption_checks,caption_count=len(caption_checks),failed_gray_regions_checked=gray,audio_loudness=loud,audio_blocks=levels,order=['opening','indoor','outdoor','environments','simulation','method','results'],visual_cut_verification='visual_cut_v9/submission.verified.json',limits=dict(max_duration=180,max_bytes=20000000,min_height=480,min_fps=20))
(R/'submission.verified.json').write_text(json.dumps(report,indent=2))
print('PASS',len(caption_checks),'captions;',gray,'gray regions;',loud['input_i'],'LUFS',flush=True)

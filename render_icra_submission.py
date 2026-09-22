"""Assemble the anonymous GEM accompanying video from paper art and verified clips."""
from pathlib import Path
import hashlib,json,subprocess
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps
from icra_motion_design import ease

ROOT=Path('outputs/icra_submission');ASSETS=ROOT/'assets';ASSETS.mkdir(parents=True,exist_ok=True)
PAPER=Path('/home/asus/Research/Nav-graph-blind/projects/paper')
FIG=PAPER/'figures/gem_architecture_pic_20260915/GEM_architecture_pic_slide2.png'
W,H,FPS=1920,1080,30
DEMO_SPEED=1.5
INK=(30,44,60);MUTED=(93,106,119);BLUE=(77,155,230);CORAL=(240,87,72);LINE=(220,228,235)
FONT='/usr/share/fonts/truetype/lato/Lato-'
def font(n,bold=False):return ImageFont.truetype(FONT+('Semibold' if bold else 'Regular')+'.ttf',n)
def text(im,xy,s,n=32,color=INK,bold=False):ImageDraw.Draw(im).text(xy,s,font=font(n,bold),fill=color,spacing=12)
def canvas():return Image.new('RGB',(W,H),'white')
def crop_fig(box):
 im=Image.open(FIG).convert('RGB');sx,sy=im.width/2048,im.height/1019
 return im.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box)))
def paste_fit(im,asset,box):
 x,y,w,h=box;asset=ImageOps.contain(asset,(w,h),Image.Resampling.LANCZOS)
 im.paste(asset,(x+(w-asset.width)//2,y+(h-asset.height)//2))
def clip_frame(name,t):
 c=cv2.VideoCapture(str(Path('outputs/final')/(name+'.mp4')));c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=c.read();c.release();assert ok
 return Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB))
CAPTIONS={
 'simulation':[(0,7,'One episode.\nThree successive goals.'),(7,13,'Demo: RGB-based arrival.\nPaper evaluation:\ndistance-based success.'),(13,23,'RGB history and geometry\npersist across goals.'),(23,31,'Earlier observations remain\navailable for the Revisit.'),(31,38.567,'Returning to a place\nobserved earlier in the episode.')],
 'realworld':[(0,7,'A previously surveyed goal,\nqueried from the live view.'),(7,15,'The same frozen NavDP controller;\nGEM adds historical recall.'),(16,24,'Baseline stops without arrival.\nIts view turns gray.'),(25,31.334,'The goal-image border marks\nconfirmed arrival.')],
 'outdoor':[(0,10,'The same revisit task,\nin an outdoor environment.'),(12,25,'Candidate trajectories come from\nthe recorded NavDP planner.'),(29,40,'Local plans update as the robot moves.'),(49,59,'Baseline terminates without arrival.\nGEM continues toward the goal.'),(63,71.767,'Arrival follows the recorded\nRGB arrival latch.')]
}

def overlay(name,local_s=0,speed_x=3):
 im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
 title={'simulation':'Memory across goals','realworld':'Indoor revisit','outdoor':'Outdoor revisit'}[name]
 text(im,(28,28),title,32,INK,True)
 badge=f'{int(speed_x)}×'
 d.rectangle((1810,20,1904,67),fill=(255,255,255,255));text(im,(1822,28),badge,22,MUTED,True)
 return im
def tail_cover():
 im=Image.new('RGBA',(W,H),(0,0,0,0))
 # Match the encoded simulation page color, not pure white.
 ImageDraw.Draw(im).rectangle((1588,52,1810,88),fill=(251,253,250,255))
 return im

# Appear on the map once Baseline can no longer reach the active goal.
STOP={
 # Indoor FPV actually grays at source 480; 467 is still a live camera.
 'realworld':dict(frame=480,box=(1210,368,1635,460),tip=(1008,418),origin=(1210,414)),
 'outdoor':dict(frame=1465,box=(1478,210,1900,302),tip=(1748,948),origin=(1689,302)),
 # Simulation Baseline never fully stops; mark the looping red path once GEM has arrived.
 'simulation':dict(frame=1035,box=(1348,172,1775,264),tip=(1403,364),origin=(1403,264)),
}
STOP_CACHE={}
def stop_card(name,alpha):
 key=(name,round(8*alpha)/8)
 if key in STOP_CACHE:return STOP_CACHE[key]
 spec=STOP[name];im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
 x0,y0,x1,y1=spec['box'];ox,oy=spec['origin'];tx,ty=spec['tip'];col=CORAL+(255,)
 d.line((ox,oy,tx,ty),fill=col,width=3)
 d.ellipse((tx-6,ty-6,tx+6,ty+6),fill=col,outline=(255,255,255,255),width=2)
 d.rounded_rectangle((x0,y0,x1,y1),radius=10,fill=(255,255,255,240),outline=col,width=3)
 text(im,(x0+20,y0+12),'Baseline',26,CORAL,True)
 text(im,(x0+20,y0+46),'stopped before a glass wall' if name=='realworld' else 'does not reach the goal',20,INK,True)
 if key[1]<1:im.putalpha(im.getchannel('A').point(lambda a:round(a*key[1])))
 STOP_CACHE[key]=im;return im

BLEND_CACHE={}
def blend_roi(frame,rgba):
 # Alpha only covers text; existing video pixels remain unchanged elsewhere.
 key=id(rgba)
 if key not in BLEND_CACHE:
  a=np.asarray(rgba).reshape(-1,4);ids=np.flatnonzero(a[:,3]);alpha=a[ids,3:4].astype(np.float32)/255
  BLEND_CACHE[key]=(rgba,ids,a[ids,:3][:,::-1]*alpha,alpha)
 _,ids,col,alpha=BLEND_CACHE[key];flat=frame.reshape(-1,3)
 flat[ids]=np.rint(col+flat[ids]*(1-alpha)).astype(np.uint8)

def sample_segments(n_src,segments):
 idxs=[];speeds=[]
 for a,b,spd,label in segments:
  n=int(round((b-a)/spd));assert n>0,(a,b,spd)
  local=np.minimum(np.rint(a+np.arange(n)*spd).astype(int),n_src-1)
  idxs.append(local);speeds.append(np.full(n,label,np.float32))
 out=np.concatenate(idxs);out[-1]=n_src-1
 return out,np.concatenate(speeds)

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--previews-only',action='store_true');args=ap.parse_args()
 import sys
 from icra_spatial_design import SpatialDesign
 motion=SpatialDesign(sys.modules[__name__])
 cards=[motion.opening(2),motion.opening(7),motion.environments(2.5),motion.method(3),motion.method(7),motion.method(15),motion.method(21.5),motion.method(26),motion.method(30),motion.method(35),motion.method(44),motion.results(6),motion.results(10),motion.results(16),motion.results(24),motion.results(36),motion.results(40)]
 names=['title','title_late','gallery','overview','overview_late','memory','localize','localize_v','localize_g','localize_b','controller','results','results_dsr','results_novel','results_a','results_c','results_c2']
 for name,im in zip(names,cards):im.save(ASSETS/(name+'.png'))
 rows=(len(cards)+1)//2
 contact=Image.new('RGB',(1920,rows*540),'white')
 for i,im in enumerate(cards):contact.paste(im.resize((960,540),Image.Resampling.LANCZOS),((i%2)*960,(i//2)*540))
 contact.save(ROOT/'design_contact.jpg')
 for name in ['realworld','outdoor','simulation']:
  f=np.array(clip_frame(name,10))[:,:,::-1].copy();blend_roi(f,overlay(name,10,3));cv2.imwrite(str(ASSETS/(name+'_overlay_preview.jpg')),f)
 if args.previews_only:return
 out=ROOT/'GEM_ICRA_master.mp4'
 ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],stdin=subprocess.PIPE)
 sections=[];n=0;previous=None;transition_frames=12
 def write_anim(name,seconds,render,fade_in):
  nonlocal n,previous
  begin=n
  for j in range(int(seconds*FPS)):
   f=np.asarray(render(j/FPS))[:,:,::-1].copy()
   if previous is not None and fade_in and j<transition_frames:f=cv2.addWeighted(previous,1-ease(j/(transition_frames-1)),f,ease(j/(transition_frames-1)),0)
   ff.stdin.write(f.tobytes());n+=1
   if j%90==0:print(name,j,flush=True)
  previous=f.copy()
  sections.append(dict(type='animation',name=name,start_frame=begin,frames=n-begin,transition_in_frames=transition_frames if fade_in else 0))
 def write_demo(name,indices,speed_x):
  nonlocal n,previous
  path=Path('outputs/final')/(name+'.mp4');cap=cv2.VideoCapture(str(path));begin=n
  source_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));assert len(indices)==len(speed_x)
  cover=tail_cover() if name=='simulation' else None;source_index=-1;stop=STOP[name]
  jump_from=None;jump_at=None;last_frame=None
  for i,target in enumerate(indices):
   while source_index<target:
    ok,source=cap.read();assert ok, (name,source_index,target);source_index+=1
   if i and target-indices[i-1]>12:
    jump_from=last_frame;jump_at=i
   f=source.copy()
   blend_roi(f,overlay(name,i/FPS,float(speed_x[i])))
   if cover is not None and source_index>=1037:blend_roi(f,cover)
   if source_index>=stop['frame']:blend_roi(f,stop_card(name,min(1,(source_index-stop['frame']+1)/12)))
   last_frame=f.copy()
   if i<transition_frames:f=cv2.addWeighted(previous,1-ease(i/(transition_frames-1)),f,ease(i/(transition_frames-1)),0)
   elif jump_at is not None and i-jump_at<8:
    f=cv2.addWeighted(jump_from,1-ease((i-jump_at)/7),f,ease((i-jump_at)/7),0)
   ff.stdin.write(f.tobytes());n+=1
   if i%300==0:print(name,i,flush=True)
  cap.release();expected=json.loads(path.with_suffix('.verified.json').read_text())['frames'];assert source_frames==expected
  previous=last_frame
  sections.append(dict(type='video',name=name,source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),start_frame=begin,frames=len(indices),source_frames=source_frames,source_indices=indices.tolist(),speed_label=speed_x.tolist(),transition_in_frames=transition_frames,baseline_map_note=dict(source_frame=stop['frame'],text='Baseline stopped before a glass wall' if name=='realworld' else 'Baseline does not reach the goal')))
 write_anim('opening',11,motion.opening,False)
 indoor=np.round(np.arange(630)*939/629).astype(int)
 write_demo('realworld',indoor,np.full(len(indoor),3.0))
 outdoor,out_spd=sample_segments(2153,[(0,225,1.5,3),(225,1883,1658/390,8),(1883,2153,1.5,3)])
 assert len(outdoor)==720,(len(outdoor),outdoor[:3],outdoor[-3:])
 write_demo('outdoor',outdoor,out_spd)
 write_anim('environments',5,motion.environments,True)
 sim_a=np.round(np.linspace(0,364,243)).astype(int)
 sim_c=np.round(np.linspace(365,1034,305)).astype(int)
 sim_e=np.round(np.linspace(1035,1156,82)).astype(int)
 sim=np.concatenate([sim_a,sim_c,sim_e]);sim[-1]=1156
 sim_spd=np.concatenate([np.full(243,3.0),np.full(305,4.0),np.full(82,3.0)])
 assert len(sim)==630,len(sim)
 write_demo('simulation',sim,sim_spd)
 write_anim('method',53,motion.method,True)
 begin=n
 for j in range(43*FPS):
  f=np.asarray(motion.results(j/FPS))[:,:,::-1].copy()
  if j<transition_frames:f=cv2.addWeighted(previous,1-ease(j/(transition_frames-1)),f,ease(j/(transition_frames-1)),0)
  ff.stdin.write(f.tobytes());n+=1
 previous=f.copy()
 sections.append(dict(type='animation',name='results',start_frame=begin,frames=n-begin,transition_in_frames=transition_frames,pages=[dict(name='Table I',start_s=0,duration_s=20),dict(name='Table II(a)',start_s=20,duration_s=12),dict(name='Table II(c)',start_s=32,duration_s=11)]))
 ff.stdin.close();assert ff.wait()==0;assert n==5340,n
 sources=[PAPER/'main.tex',PAPER/'sec/0_abstract.tex',PAPER/'sec/4_method.tex',PAPER/'figures/cec_architecture.tex',PAPER/'tables/realworld.tex',PAPER/'tables/main_matrix.tex',PAPER/'tables/continual_meeting.tex',PAPER/'sec_lg/5_experiments.tex',PAPER/'main.pdf',FIG]
 report=dict(video=str(out),frames=n,fps=FPS,duration_s=n/FPS,sections=sections,companion_captions=CAPTIONS,burned_explanatory_captions=False,design_version=24,order=['opening','realworld','outdoor','environments','simulation','method','results'],
  paper_root=str(PAPER),paper_assets=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],
  audio='Silent visual source; final Ava narration and subtitles are added by encode_icra_voiceover.py.',
  opening_design=dict(reference='outputs/final/ICRA26.mp4, first 10 seconds',hero_scene='indoor',title='GEM',subtitle='A Streaming Geometry Model Is an Episodic Memory',scope=None,title_alignment='Fixed screen center; two-line lockup on a solid bar fitted to glyph bounds; 10px outer fade only; no scope footnote',background_zoom=dict(start=3.0,end=1.0,seconds=[2.5,5.0],from_grid='1x1 centered',to_grid='3x3'),duration_s=11,center_playback_seconds=11,outer_playback_seconds=8.5,outer_stream_start_s=2.5,final_frame_hold=True,grid_rgb='One hero inset fades at 2.5–4 seconds; cloud-only grid with persistent title',grounded_trajectories=True,recorded_candidate_fans=True),
  opening_sources=json.loads(Path('outputs/icra_submission/montage_motion/selection.json').read_text()),
  method_design=dict(source=str(FIG),sequence=['overview 10s','memory 10s','goal localization 17s','controller interfaces 16s'],duration_s=53,panel_transitions_s=[10,20,37],boundary_crossfade_frames=12,explanations='Restored large paper panels and continuous camera tour; professional section titles; core explanatory groups and 1/2/3 steps retained; late supplementary sentences removed; highlights follow actual narration timestamps.'),
  environments_design=dict(duration_s=5,title='Example MP3D environments',layout='2x3 LoGoPlanner-style flat dollhouse, 360 yaw orbit',scenes=['VFuaQ6m2Qom','1LXtFkjw3qL','759xd9YjKW5','1pXnuDYAj8r','EDJbREhghzL','PX4nDJXEHrG'],source='outputs/icra_submission/navmesh_gallery',yaw_frames=90,placement='after real-world, before simulation'),
  outdoor_retiming=dict(source_frames=2153,kept_all_frames=True,segments=['0-225 @1.5 labeled 3x','225-1883 @4.25 labeled 8x includes former skip 1480-1883','1883-2153 @1.5 labeled 3x'],output_frames=720),
  scientific_labels=['Real maps: reconstruction is visualization only','Simulation: qualitative visual-goal replay, RGB arrival distinct from paper distance scoring','Outdoor 25/30 vs 4/30 is the paper-wide real-world table, not the displayed pair','Results: paper-wide benchmark, not selected-clip counts','Baseline map note: indoor/outdoor at FPV stop; simulation once GEM has arrived'],
  results_design=dict(duration_s=43,source='Original PDF Tables I, II(a), II(c)',table_verification='paper_tables/verified.json',pages=['Table I: 20 s','Table II(a): 12 s','Table II(c): 11 s, holds through end'],source_videos_unchanged=True,demonstrations_retimed=True,upload_performed=False))
 (ROOT/'assembly.audit.json').write_text(json.dumps(report,indent=2));print('Master complete:',n,n/FPS)
if __name__=='__main__':main()

"""Select longer, forward-only navigation excerpts and compress pauses by motion.
Telemetry is used only for editorial sampling, never fed to LingBot.
"""
from pathlib import Path
import json,hashlib,numpy as np
ROOT=Path('outputs/icra_submission/montage_motion');ROOT.mkdir(exist_ok=True)
OLD=Path('outputs/icra_submission/montage_plans')
S=Path('/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad')
scenes=[]
def choose(q,yaw,begin,end,count):
 # Motion clock suppresses stationary dwell; retained frames stay chronological.
 q=q[begin:end];yaw=np.unwrap(yaw[begin:end]);d=np.linalg.norm(np.diff(q,axis=0),axis=1)
 weight=d+.10*np.abs(np.diff(yaw));weight[weight<.002]=0
 arc=np.r_[0,np.cumsum(weight)]
 ix=np.unique(np.searchsorted(arc,np.linspace(0,arc[-1],count)))+begin
 return ix,dict(source_begin=begin,source_end_exclusive=end,path_m=float(d.sum()),net_m=float(np.linalg.norm(q[-1]-q[0])),sampling='Forward motion-keyframe time compression; no loops or pose input to model',requested_observations=count,retained_observations=len(ix))
def save(name,kind,rgb,ix,times,plans,provenance,height,metrics):
 d=ROOT/name;d.mkdir(exist_ok=True)
 rows=[dict(key=k,path=str(rgb[int(i)].resolve()),source_index=int(i),timestamp_ns=int(times[i])) for k,i in enumerate(ix)]
 assert all(Path(r['path']).exists() for r in rows)
 (d/'manifest.json').write_text(json.dumps(dict(scene=name,kind=kind,provenance=provenance,motion_selection=metrics,frames=rows),indent=2))
 p=Path(provenance['plans']);(d/'plans.json').write_text(json.dumps(dict(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),coordinate_convention='forward-left' if kind=='simulation' else 'forward-right (recorded ROS marker coordinates, as in render_real_final)',camera_height_m=height,plans=plans)))
 scenes.append(dict(name=name,label=name.title(),kind=kind,manifest=str(d/'manifest.json'),reconstruction=str(d/'cloud'),frames=len(rows),display_frames=len(rows)-7,tile_frames=300,local_grounding=name=='courtyard',plan_file=str(d/'plans.json'),output_directory=str(d),motion_selection=metrics))
for name,run,begin,end,count in [('gallery','visual_pair_138_aligned1',80,560,260),('hall','screen_253_A40_aligned1',0,174,170),('garden','visual_pair_113_seed2',0,240,220),('stage','visual_pair_011_v1',180,580,260),('terrace','formal_038',0,230,220),('living','expansion_241',0,350,260)]:
 archived=run in ['formal_038','expansion_241']
 root=OLD/'sources'/run/'task/cec/evaluation' if archived else Path('outputs')/run/'cec/evaluation'
 rgb=sorted((root/('history_before_B/rgb' if archived else 'leg_A/rgb')).glob('*.jpg'))
 trace=root/'leg_A/actual_trace.json';j=json.load(open(trace));poses=j['poses'];q=np.array([[r['x'],r['z']] for r in poses]);yaw=np.array([r['yaw'] for r in poses]);ix,metrics=choose(q,yaw,begin,min(end,len(rgb),len(q)),count);metrics['scene']=j['source_scene']
 p=root/'full_plan_outputs.jsonl';full=[json.loads(x) for x in p.read_text().splitlines() if x];leg=[]
 for r in full:
  if leg and r['next_action_index']<leg[-1]['next_action_index']:break
  leg.append(r)
 plans=[dict(source_step=r['next_action_index'],timestamp_ns=1700000000000000000+r['next_action_index']*100000000,selected=r['selected_trajectory'],candidates=r['all_trajectory'],plan_index=r['plan_index']) for r in leg if ix[0]-30<=r['next_action_index']<=ix[-1]]
 save(name,'simulation',rgb,ix,1700000000000000000+np.arange(len(rgb))*100000000,plans,dict(rgb=str(rgb[0].parent),plans=str(p),trace=str(trace)),.5,metrics)
for name,tag,begin,end,count,height in [('courtyard','p035_gem',660,1560,310,.41523778),('atrium','p037_gem',900,1500,230,.35252619),('indoor','n_cec2',375,930,260,.40474924)]:
 root=S/f'demo_{tag}';times=np.load(root/'times.npy');tel=np.load(root/'tel.npy');q=np.column_stack([np.interp(times,tel[:,0],tel[:,i]) for i in [1,2]]);yaw=np.interp(times,tel[:,0],np.unwrap(tel[:,6]));ix,metrics=choose(q,yaw,begin,end,count);p=root/'plans.npy';recorded=np.load(p,allow_pickle=True);plans=[]
 for i,r in enumerate(recorded):
  if r['sel'] is None or not len(r['sel']) or r['t']<times[ix[0]]-3 or r['t']>times[ix[-1]]:continue
  plans.append(dict(timestamp_ns=int(r['t']*1e9),selected=np.asarray(r['sel']).tolist(),candidates=[np.asarray(c).tolist() for c in r['cand'] if c is not None and len(c)>1],plan_index=i))
 rgb=[root/'rgb'/f'{i:05d}.jpg' for i in range(len(times))];metrics['source_duration_s']=float(times[ix[-1]]-times[ix[0]])
 save(name,'real',rgb,ix,times*1e9,plans,dict(rgb=str(root/'rgb'),plans=str(p),timestamps=str(root/'times.npy'),editorial_telemetry=str(root/'tel.npy')),height,metrics)
assert len(scenes)==9
(ROOT/'selection.json').write_text(json.dumps(scenes,indent=2))
for s in scenes:print(s['name'],s['frames'],s['motion_selection'],flush=True)

"""Use RGB excerpts with real recorded candidates; no generated fan-shaped paths."""
from pathlib import Path
import json,numpy as np,hashlib
ROOT=Path('outputs/icra_submission/montage_plans');S=Path('/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad');scenes=[]
def save(name,kind,paths,source_indices,times,plans,provenance,height,reuse=None):
 d=ROOT/name;d.mkdir(exist_ok=True);rows=[dict(key=k,path=str(p.resolve()),source_index=int(i),timestamp_ns=int(t)) for k,(p,i,t) in enumerate(zip(paths,source_indices,times))]
 assert all(Path(r['path']).exists() for r in rows)
 (d/'manifest.json').write_text(json.dumps(dict(scene=name,kind=kind,provenance=provenance,frames=rows),indent=2))
 # Store only literal recorded trajectories; selection isn't re-ranked for appearance.
 (d/'plans.json').write_text(json.dumps(dict(source=provenance['plans'],sha256=hashlib.sha256(Path(provenance['plans']).read_bytes()).hexdigest(),coordinate_convention='forward-left' if kind=='simulation' else 'forward-right (recorded ROS marker coordinates, as in render_real_final)',camera_height_m=height,plans=plans)))
 scenes.append(dict(name=name,label=name.replace('_',' ').title(),kind=kind,manifest=str(d/'manifest.json'),reconstruction=reuse or str(d/'cloud'),frames=len(rows),plan_file=str(d/'plans.json'),output_directory=str(d)))
def simplify_sim(path,begin,end):
 full=[json.loads(x) for x in Path(path).read_text().splitlines() if x];leg=[]
 for r in full:
  if leg and r['next_action_index']<leg[-1]['next_action_index']:break
  leg.append(r)
 return [dict(source_step=r['next_action_index'],timestamp_ns=1700000000000000000+r['next_action_index']*100000000,selected=r['selected_trajectory'],candidates=r['all_trajectory'],plan_index=r['plan_index']) for r in leg if begin-30<=r['next_action_index']<end]
for name,run,reuse in [('gallery','visual_pair_138_aligned1',True),('hall','visual_pair_253_aligned1',True),('garden','visual_pair_113_centered2',True),('stage','screen_385_A60',False)]:
 root=Path('outputs')/run/'cec/evaluation';rgb=sorted((root/'leg_A/rgb').glob('*.jpg'));ix=np.arange(min(150,len(rgb)));p=root/'full_plan_outputs.jsonl'
 save(name,'simulation',[rgb[i] for i in ix],ix,1700000000000000000+ix*100000000,simplify_sim(p,0,len(ix)),dict(rgb=str(root/'leg_A/rgb'),plans=str(p)),.5,str(Path('outputs/icra_submission/montage')/name/'cloud') if reuse else None)
for name,source,begin in [('terrace','formal_038',0),('living','expansion_241',155)]:
 root=ROOT/'sources'/source/'task/cec/evaluation';rgb=sorted((root/'history_before_B/rgb').glob('*.jpg'));ix=np.arange(begin,min(begin+150,len(rgb)));p=root/'full_plan_outputs.jsonl'
 save(name,'simulation',[rgb[i] for i in ix],ix,1700000000000000000+ix*100000000,simplify_sim(p,int(ix[0]),int(ix[-1]+1)),dict(rgb=str(root/'history_before_B/rgb'),plans=str(p),trace=str(root/'leg_A/actual_trace.json')),.5)
for name,tag,begin,height in [('atrium','p037_gem',700,.35252619),('courtyard','p035_gem',850,.41523778),('indoor','n_cec2',110,.40474924)]:
 root=S/f'demo_{tag}';times=np.load(root/'times.npy');ix=np.arange(begin,begin+150);p=root/'plans.npy';recorded=np.load(p,allow_pickle=True);plans=[]
 for i,r in enumerate(recorded):
  if r['sel'] is None or not len(r['sel']) or r['t']<times[ix[0]]-3 or r['t']>times[ix[-1]]:continue
  plans.append(dict(timestamp_ns=int(r['t']*1e9),selected=np.asarray(r['sel']).tolist(),candidates=[np.asarray(c).tolist() for c in r['cand'] if c is not None and len(c)>1],plan_index=i))
 save(name,'real',[root/'rgb'/f'{i:05d}.jpg' for i in ix],ix,times[ix]*1e9,plans,dict(rgb=str(root/'rgb'),plans=str(p),timestamps=str(root/'times.npy')),height)
for scene in scenes:scene['display_frames']={'stage':65,'living':75}.get(scene['name'],110)
assert len(scenes)==9
(ROOT/'selection.json').write_text(json.dumps(scenes,indent=2));print([(s['name'],s['frames'],len(json.load(open(s['plan_file']))['plans'])) for s in scenes])

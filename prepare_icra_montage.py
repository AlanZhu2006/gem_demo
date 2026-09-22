"""Select independent historical RGB excerpts, never cropped final video frames."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
ROOT=Path('outputs/icra_submission/montage');ROOT.mkdir(exist_ok=True)
S=Path('/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad')
scenes=[]
def save(name,label,kind,paths,indices,times,source):
 d=ROOT/name;d.mkdir(exist_ok=True);rows=[]
 for k,(path,idx,t) in enumerate(zip(paths,indices,times)):
  rows.append(dict(key=k,path=str(Path(path).resolve()),timestamp_ns=int(t),source_index=int(idx)))
 j=dict(scene=name,label=label,kind=kind,provenance=source,selection='Contiguous forward excerpt, uniformly sampled; no final-video pixels',frames=rows)
 (d/'manifest.json').write_text(json.dumps(j,indent=2));scenes.append(dict(name=name,label=label,kind=kind,manifest=str(d/'manifest.json'),reconstruction=str(d/'cloud'),frames=len(rows)))
for name,label,tag,begin,end in [('atrium','Atrium','p037_mem',270,570),('corridor','Corridor','i8_survey',180,480),('courtyard','Courtyard','p035_mem',300,600)]:
 d=ROOT/name/'rgb';d.mkdir(parents=True,exist_ok=True);p=S/f'rgbd_{tag}'
 a=np.load(p/'color.npy',mmap_mode='r');ts=np.load(p/'times.npy');ix=np.arange(begin,end,2);paths=[]
 for k,i in enumerate(ix):
  dest=d/f'{k:06d}.png';Image.fromarray(a[i]).save(dest);paths.append(dest)
 save(name,label,'real',paths,ix,ts[ix]*1e9,dict(rgb=str(p/'color.npy'),timestamps=str(p/'times.npy'),rgb_sha256=hashlib.sha256((p/'color.npy').read_bytes()).hexdigest(),input='RGB only; sensor depth unused'))
for name,label,root in [('gallery','Gallery','visual_pair_138_aligned1'),('hall','Hallway','visual_pair_253_aligned1'),('garden','Garden','visual_pair_113_centered2')]:
 p=Path('outputs')/root/'cec/evaluation/leg_A/rgb_manifest.json';j=json.load(open(p));allpaths=[Path(f['path']) for f in j['frames']];ix=np.arange(min(len(allpaths),150));save(name,label,'simulation',[allpaths[i] for i in ix],ix,1700000000000000000+ix*100000000,dict(manifest=str(p),clock='ordered simulator steps, synthetic 10 Hz display clock'))
p=Path('outputs/sim_3leg_rgb/manifest.json');j=json.load(open(p));ix=np.arange(0,300,2);save('kitchen','Kitchen','simulation',[p.parent/j['frames'][i]['path'] for i in ix],ix,[j['frames'][i]['timestamp_ns'] for i in ix],dict(manifest=str(p)))
for name,label,scene in [('bedroom','Bedroom','17DRP5sb8fy'),('living','Living room','1LXtFkjw3qL')]:
 d=Path('/home/asus/Research/datasets/memnav_sweep_quick_fixed/mp3d_sweep')/scene/'trajectory_000/videos/chunk-000/observation.images.rgb';ps=sorted(d.glob('*.jpg'),key=lambda p:int(p.stem));ix=np.arange(len(ps));save(name,label,'simulation',ps,ix,1700000000000000000+ix*100000000,dict(directory=str(d),scene=scene,clock='ordered RGB sweep frames; synthetic 10 Hz display clock'))
assert len(scenes)==9
(ROOT/'selection.json').write_text(json.dumps(scenes,indent=2))
print([(s['name'],s['frames']) for s in scenes])

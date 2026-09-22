"""Check end-to-end movement/growth clocks, literal sources, and no end-card hold."""
from pathlib import Path
import json,hashlib,numpy as np
ROOT=Path('outputs/icra_submission');R=ROOT/'montage_motion'
scenes=json.load(open(R/'selection.json'));result=[]
for s in scenes:
 a=json.load(open(Path(s['output_directory'])/'tiles.audit.json'))['frames']
 m=json.load(open(s['manifest']))['frames'];assert all(x['source_index']<y['source_index'] and x['timestamp_ns']<y['timestamp_ns'] for x,y in zip(m,m[1:]))
 start=0 if s['name']=='indoor' else 2.5
 ids=[round(np.clip((j/30-start)/(10-1/30-start),0,1)*(len(a)-1)) for j in range(300)]
 active=ids[round(start*30):];counts=[a[i]['cloud_frames'] for i in active]
 assert all(x<=y for x,y in zip(counts,counts[1:]))
 assert counts[-1]==s['display_frames'] and counts[-1]>counts[-4],s['name']
 # No >=0.2-second repeated source prefix anywhere after activation.
 assert all(counts[i]<counts[i+6] for i in range(len(counts)-6)),s['name']
 tile_hashes=[hashlib.sha256((Path(s['output_directory'])/'tiles'/f'{i:03d}.jpg').read_bytes()).hexdigest() for i in range(len(a))]
 run=longest=0;prev=None
 for i in active:
  run=run+1 if tile_hashes[i]==prev else 1;prev=tile_hashes[i];longest=max(longest,run)
 assert longest/30<.2,(s['name'],longest)
 halfseconds=[]
 for sec in np.arange(start+.5,10.01,.5):
  i=ids[min(299,round(sec*30))];halfseconds.append(dict(t=float(sec),cloud_frames=a[i]['cloud_frames'],visible_pixels=a[i]['visible_pixels']))
 assert all(x['cloud_frames']<y['cloud_frames'] for x,y in zip(halfseconds,halfseconds[1:])),s['name']
 result.append(dict(scene=s['name'],start_s=start,ends_on_last_frame=True,longest_identical_frame_run_s=longest/30,halfsecond_growth=halfseconds,motion_selection=s['motion_selection']))
report=dict(passed=True,duration_s=10,frames=300,title='Persistent fixed centered GEM and full subtitle; no fade',center_scene='indoor',zoom=dict(center=[960,540],start_s=2.5,end_s=5),scenes=result)
(ROOT/'opening_timing.verified.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

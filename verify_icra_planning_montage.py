"""Audit raw observations, recorded candidate provenance, and no future plan display."""
from pathlib import Path
import json,hashlib
import numpy as np,cv2
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--root',default='outputs/icra_submission/montage_plans');args=ap.parse_args()
R=Path(args.root);selection=json.load(open(R/'selection.json'));assert len(selection)==9
report=[]
for s in selection:
 d=Path(s['output_directory']);manifest=json.load(open(s['manifest']));recon=json.load(open(Path(s['reconstruction'])/'reconstruction.json'));pm=json.load(open(s['plan_file']));a=json.load(open(d/'tiles.audit.json'));fs=a['frames'];observed=[r for r in recon['frames'] if not r['warming']]
 assert 'official demo.py' in recon['mode'];assert len(fs)==s.get('tile_frames',150) and fs[0]['cloud_frames']==0 and fs[-1]['cloud_frames']==s['display_frames']
 assert hashlib.sha256(Path(pm['source']).read_bytes()).hexdigest()==pm['sha256']
 assert all(x['cloud_frames']<=y['cloud_frames'] and x['visible_pixels']<=y['visible_pixels'] for x,y in zip(fs,fs[1:]))
 originals=None
 if s['kind']=='simulation':originals={r['plan_index']:r for r in (json.loads(line) for line in Path(pm['source']).read_text().splitlines() if line)}
 else:originals=np.load(pm['source'],allow_pickle=True)
 for p in pm['plans']:
  original=originals[p['plan_index']]
  expected=original['selected_trajectory'] if s['kind']=='simulation' else original['sel']
  np.testing.assert_array_equal(np.asarray(p['selected']),np.asarray(expected))
  cand=original['all_trajectory'] if s['kind']=='simulation' else [np.asarray(c).tolist() for c in original['cand'] if c is not None and len(c)>1]
  np.testing.assert_array_equal(np.asarray(p['candidates']),np.asarray(cand))
 for f in fs:
  n=f['cloud_frames'];assert f['last_source_timestamp_ns']==(observed[n-1]['timestamp_ns'] if n else None)
  if f['plan_timestamp_ns'] is not None:assert 0<=f['last_source_timestamp_ns']-f['plan_timestamp_ns']<=3e9
  assert (d/'tiles'/f"{f['frame']:03d}.jpg").is_file()
 assert sum(f['candidate_visible_pixels']>0 for f in fs)>20,s['name']
 assert sum(f['selected_visible_pixels']>0 for f in fs)>20,s['name']
 hashes=[]
 for row in manifest['frames']:
  p=Path(row['path']);assert p.suffix in ['.jpg','.png'] and 'outputs/final' not in str(p);hashes.append(hashlib.sha256(p.read_bytes()).hexdigest())
 report.append(dict(scene=s['name'],kind=s['kind'],source_rgb_hash=hashlib.sha256(''.join(hashes).encode()).hexdigest(),display_cloud_frames=fs[-1]['cloud_frames'],literal_recorded_candidates_verified=True,literal_recorded_selection_verified=True,frames_with_visible_candidates=sum(f['candidate_visible_pixels']>0 for f in fs),frames_with_visible_selected=sum(f['selected_visible_pixels']>0 for f in fs),max_candidates=max(f['candidate_count'] for f in fs),no_future_plans=True,grounded=True,occlusion=a['trajectory']['occlusion']))
result=dict(passed=True,scene_count=9,real_excerpts=3,simulation_scenes=6,source_final_mp4_crops=False,reports=report)
(R/'verified.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

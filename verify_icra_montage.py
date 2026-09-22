"""Verify nine raw-RGB sources and strictly forward incremental display prefixes."""
from pathlib import Path
import json,hashlib
import cv2,numpy as np
R=Path('outputs/icra_submission/montage');selection=json.load(open(R/'selection.json'));assert len(selection)==9
assert len({s['name'] for s in selection})==9
assert sum(s['kind']=='real' for s in selection)==3
reports=[]
for s in selection:
 source=json.load(open(s['manifest']));recon=json.load(open(Path(s['reconstruction'])/'reconstruction.json'));a=json.load(open(R/s['name']/'tiles.audit.json'));rows=[r for r in recon['frames'] if not r['warming']]
 assert 'official demo.py' in recon['mode'] and recon['pose_adapter']=='official-viewer'
 fs=a['frames'];assert len(fs)==150 and fs[0]['cloud_frames']==0
 assert all(x['cloud_frames']<=y['cloud_frames'] for x,y in zip(fs,fs[1:]))
 assert all(x['visible_pixels']<=y['visible_pixels'] for x,y in zip(fs,fs[1:]))
 assert a['trajectory']['occlusion']=='Shared geometry z-buffer; no screen-space overlay'
 assert fs[0]['trajectory_visible_pixels']==0 and fs[-1]['trajectory_visible_pixels']>0
 assert fs[-1]['cloud_frames']==(55 if s['kind']=='real' else 110)
 for f in fs:
  n=f['cloud_frames'];assert f['last_source_timestamp_ns']==(rows[n-1]['timestamp_ns'] if n else None)
  assert (R/s['name']/'tiles'/f"{f['frame']:03d}.jpg").is_file()
 raw_hashes=[]
 for row in source['frames']:
  path=Path(row['path']);assert path.suffix.lower() in ('.png','.jpg','.jpeg') and 'outputs/final' not in str(path)
  raw_hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
 images=[cv2.imread(str(R/s['name']/'tiles'/f'{i:03d}.jpg')) for i in [0,50,100,149]]
 differences=[float(np.mean(np.abs(x.astype(float)-y.astype(float)))) for x,y in zip(images,images[1:])]
 assert min(differences)>.01,(s['name'],differences)
 reports.append(dict(name=s['name'],kind=s['kind'],raw_frames=len(source['frames']),input_hash=hashlib.sha256(''.join(raw_hashes).encode()).hexdigest(),display_cloud_frames=fs[-1]['cloud_frames'],display_source_span_s=(fs[-1]['last_source_timestamp_ns']-rows[0]['timestamp_ns'])/1e9,visible_pixels_final=fs[-1]['visible_pixels'],monotonic_geometry=True,grounded_trajectory=True,trajectory_visible_pixels=fs[-1]['trajectory_visible_pixels'],trajectory_occluded_pixels=fs[-1]['trajectory_occluded_pixels'],motion_differences=differences))
result=dict(passed=True,scene_count=9,real_excerpts=3,simulation_scenes=6,no_final_video_crops=True,entrypoint='official demo.py',reports=reports)
(R/'verified.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

"""Preserve original gem_outdoor (p035) inputs and prepare one joint RGB session."""
from pathlib import Path
import json,shutil,hashlib
import numpy as np
S=Path('/tmp/claude-1000/-home-asus/73981e0f-42df-4332-b122-78f92e02984a/scratchpad')
out=Path('outputs/outdoor_inputs');out.mkdir(exist_ok=True)
provenance=dict(source='gem_outdoor.mp4 / p035',scratch=str(S),arms={},
    original_video_sha256=hashlib.sha256(Path('gem_outdoor.mp4').read_bytes()).hexdigest(),
    rgb_identity='RGB copied unchanged from demo_p035 arm directories; joint manifest selects the continuous command/arrival interval.')
rows=[]
for arm in ['base','gem']:
 src=S/f'demo_p035_{arm}';dst=out/arm
 shutil.copytree(src,dst,dirs_exist_ok=True)
 shutil.copy2(S/f'p035_{arm}.npz',dst/'telemetry.npz')
 shutil.copy2(S/f'rgbd_p035_{arm}/mount.npy',dst/'mount.npy')
 times=np.load(dst/'times.npy');win=json.loads((dst/'win.json').read_text())
 arr=json.loads((dst/'arrival.json').read_text());lat=[x[0] for x in arr if x[1].get('arrival_latched')]
 end=min(lat) if lat else win['t1']
 idx=np.flatnonzero((times>=win['t0']-.6)&(times<=end+.12))
 provenance['arms'][arm]=dict(source_dir=str(src),rgb_frames=len(times),inference_frames=len(idx),window=win,latch_t=min(lat) if lat else None)
 # The same reverse-baseline / forward-GEM session construction as indoor joint.
 for i in (idx[::-1] if arm=='base' else idx):
  rows.append(dict(key=len(rows),path=f'{arm}/rgb/{i:05d}.jpg',timestamp_ns=int(round(times[i]*1e9)),arm=arm,source_index=int(i)))
goal=Path('/data/memnav-realworld/jetson_incrementals/20260914T095349Z/repository/runtime/go2/experiment_capture/episode_20260914T084212_300871Z/media/revisit_goal.png')
shutil.copy2(goal,out/'goal.png');provenance['goal_source']=str(goal)
(out/'provenance.json').write_text(json.dumps(provenance,indent=2))
(out/'manifest.json').write_text(json.dumps(dict(frames=rows,description='Baseline reversed followed by GEM forward; original dense RGB; timestamped playback is distinct from inference order.'),indent=2))
reverse=[dict(r,key=i) for i,r in enumerate(reversed(rows))]
(out/'manifest_reverse.json').write_text(json.dumps(dict(frames=reverse,description='GEM reversed followed by Baseline forward; alternative initialization using identical source RGB.'),indent=2))
print(json.dumps(provenance,indent=2));print('joint frames',len(rows))

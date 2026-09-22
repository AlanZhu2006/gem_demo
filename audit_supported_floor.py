"""Compare complete playback prefixes with an identical original map camera."""
import json
from pathlib import Path
import cv2
import numpy as np
from real_floor_cloud import FloorSupportedMap
from render_indoor_joint import JointMap
out = Path('outputs/real_floor_audit'); out.mkdir(exist_ok=True)
rows = json.loads(Path('outputs/final/realworld.audit.json').read_text())['frames']
old = JointMap(1344,854); new = FloorSupportedMap(1344,854)
assert np.array_equal(old.basis,new.basis) and old.scale == new.scale
report = []
for i,row in enumerate(rows):
    if i % 6 and i != len(rows)-1: continue
    old.reveal(row['source_times']); new.reveal(row['source_times'])
    if i in (300,600,len(rows)-1):
        ims=[]
        for name,m in [('original',old),('supported',new)]:
            im=m.raster.copy(); im[~np.isfinite(m.z)]=255;im=im.reshape(m.h,m.w,3)
            cv2.imwrite(str(out/f'{name}_{i}.jpg'),im);ims.append(im)
        cv2.imwrite(str(out/f'supported_comparison_{i}.jpg'),np.hstack(ims))
        occupied=np.isfinite(new.z); before=np.isfinite(old.z)
        report.append(dict(frame=i,original_pixels=int(before.sum()),supported_pixels=int(occupied.sum()),added_pixels=int((occupied&~before).sum()),stats=new.stats.copy()))
    if i%150==0: print(i, len(rows),new.stats,flush=True)
(out/'supported_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

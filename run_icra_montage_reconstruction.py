"""Reconstruct selected raw RGB excerpts with the documented LingBot environment."""
import json,subprocess,os
from pathlib import Path
os.environ['CUDA_HOME']='/home/asus/miniconda3/envs/lingbot-map'
os.environ['PATH']='/home/asus/miniconda3/envs/lingbot-map/bin:'+os.environ['PATH']
os.environ['LIBRARY_PATH']='/home/asus/miniconda3/envs/lingbot-map/targets/x86_64-linux/lib'
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--selection',default='outputs/icra_submission/montage/selection.json');args=ap.parse_args()
for s in json.load(open(args.selection)):
 out=Path(s['reconstruction'])
 if (out/'reconstruction.json').exists():continue
 print('BEGIN',s['name'],flush=True)
 with open(out.parent/'inference.log','w') as log:
  subprocess.run(['/home/asus/miniconda3/envs/lingbot-map/bin/python','run_lingbot_manifest.py','--manifest',s['manifest'],'--out',str(out),'--backend','flashinfer','--keyframe-interval','1'],stdout=log,stderr=subprocess.STDOUT,check=True)
 print('DONE',s['name'],flush=True)

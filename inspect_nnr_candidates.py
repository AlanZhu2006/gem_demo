"""Build archived NNR route and RGB review sheets from read-only sparse samples."""
import json
import argparse
from pathlib import Path
import tarfile

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ap=argparse.ArgumentParser();ap.add_argument('--archive',default='samples.tar');ap.add_argument('--tasks',nargs='+',default=['381','138','253']);ap.add_argument('--population',choices=['expansion','formal'],default='expansion');args=ap.parse_args()
out=Path('outputs/nnr_selection')
inventory=json.loads(Path('outputs/table2_inventory/all_tasks.json').read_text())['tasks']
reports=[]
with tarfile.open(out/args.archive) as archive:
    for task in args.tasks:
        records=json.load(archive.extractfile(task+'/records.json'))
        source=records['task/source.json'];summary=records['task/pair_summary.json']
        row=next(t for t in inventory if args.population in t['population'] and t['task']==task)
        canvas=np.full((730,1600,3),22,np.uint8)
        cv2.putText(canvas,f"{summary['sequence']} {task} | {source['scene']} | ARCHIVED distance-success run",(15,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
        fig,ax=plt.subplots(figsize=(8,7));all_gem=[]
        for arm,color,width in [('native','#ed6058',4),('cec','#4099e7',2)]:
            for stage in 'ABC':
                trace=records.get(f'task/{arm}/evaluation/leg_{stage}/actual_trace.json')
                if trace is None:continue
                poses=trace['poses'];P=np.array([[p['x'],p['z']] for p in poses])
                ax.plot(P[:,0],P[:,1],color=color,lw=width,alpha=.85,label=arm if stage=='A' else None)
                if arm=='cec':
                    all_gem.extend(P);ax.annotate(stage,P[-1],xytext=(7,7),textcoords='offset points',fontsize=13,fontweight='bold')
                    event=next(s for s in summary['stages'] if s['stage']==stage)
                    hashes=[event['goal_sha256']]+[poses[round(j*(len(poses)-1)/4)]['jpg_sha256'] for j in [0,1,2,4]]
                    y=65+'ABC'.index(stage)*220
                    for j,digest in enumerate(hashes):
                        data=archive.extractfile(f'{task}/images/{digest}.jpg').read()
                        im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
                        canvas[y+25:y+205,j*320:(j+1)*320]=cv2.resize(im,(320,180))
                        label=f'{stage}: '+(['Goal','Start','25%','50%','Last saved'][j])
                        cv2.putText(canvas,label,(j*320+8,y+17),cv2.FONT_HERSHEY_SIMPLEX,.55,(235,235,235),1)
        P=np.array(all_gem);extent=np.ptp(P,axis=0)
        ax.set_aspect('equal');ax.set_xlabel('Simulator x (m)');ax.set_ylabel('Simulator z (m)');ax.grid(alpha=.25);ax.legend()
        ax.set_title(f"{summary['sequence']} {task}: {source['scene']}\nArchived trajectories; original distance-based stopping")
        fig.tight_layout();fig.savefig(out/f'{task}_route.png',dpi=150);plt.close(fig)
        cv2.imwrite(str(out/f'{task}_rgb.jpg'),canvas)
        traces={arm:[records[f'task/{arm}/evaluation/leg_{s}/actual_trace.json'] for s in 'ABC'] for arm in ['cec','native']}
        report=dict(task=task,scene=source['scene'],sequence=summary['sequence'],
                    gem_path_m=row['arms']['cec']['path_m'],gem_extent_xz_m=extent.tolist(),
                    gem_geodesic_sum_m=sum(l['geodesic_m'] for l in row['arms']['cec']['legs']),
                    arms={arm:[dict(stage=s,steps=t['steps'],termination=t['termination_reason'],reached=t['reached'],path_m=t['path_len']) for s,t in zip('ABC',ts)] for arm,ts in traces.items()})
        reports.append(report)
(out/('inspected.json' if args.tasks==['381','138','253'] else 'inspected_'+'_'.join(args.tasks)+'.json')).write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2))

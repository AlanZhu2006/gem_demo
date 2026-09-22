"""Remove obsolete exported video assets after final-delivery verification.

Default is an inventory only. --apply requires matching verified final hashes.
Raw reconstruction, recording inputs, trajectories and experiment records stay.
"""
import argparse,hashlib,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path('outputs');final=root/'final';files=set()
    for p in root.rglob('*.mp4'):
        if final in p.parents or root/'icra_submission' in p.parents:continue
        files.add(p)
        for suffix in ['.jpg','.png','.audit.json','.verified.json','.arrivals.jpg','.tail.jpg','.local_traj.jpg','.render.log']:
            side=p.with_suffix(suffix)
            if side.is_file():files.add(side)
    for pattern in ['*.jpg','*.png','render*.log','*preview.log','*.render.log']:
        files.update(p for p in root.glob(pattern) if p.is_file())
    for folder in ['cloud_display_audit','cloud_fusion_audit']:
        for ext in ['*.jpg','*.png']:files.update((root/folder).glob(ext))
    rows=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)]
    report=dict(status='planned',files=rows,count=len(rows),bytes=sum(r['bytes'] for r in rows),
                scope='Obsolete exported videos, render previews and associated render audits/logs only; raw inputs and experiment evidence preserved.')
    if args.apply:
        verification=json.loads((final/'delivery.verified.json').read_text())
        for name in ['simulation','realworld']:
            assert verification[name]['full_decode']
            assert hashlib.sha256((final/(name+'.mp4')).read_bytes()).hexdigest()==verification[name]['sha256']
        (final/'cleanup_manifest.json').write_text(json.dumps(report,indent=2))
        for p in sorted(files):p.unlink()
        report['status']='completed'
        assert all(not Path(r['path']).exists() for r in rows)
    (final/'cleanup_manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))

if __name__=='__main__':main()

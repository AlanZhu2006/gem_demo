"""Read archived traces and sparse RGB; write a small tar to stdout on the archive host."""
import hashlib
import argparse
import io
import json
from pathlib import Path
import sys
import tarfile

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--population', choices=['expansion','formal'], default='expansion')
ap.add_argument('tasks',nargs='+')
args=ap.parse_args()
population=('table2_continuous_expansion_20260912_v2' if args.population=='expansion'
            else 'table2_continuous_formal_20260912_v1')
root=Path('/scratch/yz11502/Research/Nav-axis-uturn-results')/population/'tasks'
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as output:
    def add(name,payload):
        info=tarfile.TarInfo(name);info.size=len(payload)
        output.addfile(info,io.BytesIO(payload))
    for task in args.tasks:
        records={};wanted=set();archive=root/task/'artifacts.tar.gz'
        with tarfile.open(archive,'r|gz') as stream:
            for member in stream:
                if not member.isfile() or not member.name.endswith('.json'):continue
                if (member.name in ['task/source.json','task/pair_summary.json']
                    or member.name.endswith('/actual_trace.json') or 'query' in member.name):
                    records[member.name]=json.load(stream.extractfile(member))
        for name,record in records.items():
            if not isinstance(record,dict):continue
            if record.get('goal_rgb_sha256'):wanted.add(record['goal_rgb_sha256'])
            if name.endswith('/actual_trace.json'):
                poses=record['poses']
                for i in sorted({round(j*(len(poses)-1)/8) for j in range(9)}):
                    wanted.add(poses[i]['jpg_sha256'])
        add(task+'/records.json',json.dumps(records).encode())
        remaining=set(wanted)
        with tarfile.open(archive,'r|gz') as stream:
            for member in stream:
                if not member.isfile() or not member.name.endswith(('.jpg','.jpeg','.png')):continue
                payload=stream.extractfile(member).read();digest=hashlib.sha256(payload).hexdigest()
                if digest in remaining:
                    add(task+'/images/'+digest+'.jpg',payload);remaining.remove(digest)
                if not remaining:break
        if remaining:raise RuntimeError((task,'missing RGB',sorted(remaining)))
        print(task, 'sampled',len(wanted),'images',file=sys.stderr,flush=True)

"""Read-only inventory of both Table II populations; execute on the archive host."""
import json
from pathlib import Path

base = Path('/scratch/yz11502/Research/Nav-axis-uturn-results')
report = {'populations': [], 'tasks': []}
for name in ('table2_continuous_formal_20260912_v1', 'table2_continuous_expansion_20260912_v2'):
    root = base/name
    folders = sorted((root/'tasks').iterdir())
    pop = dict(name=name, directory=str(root), task_directories=len(folders), summaries=0,
               cec_complete=0, native_complete=0, errors=[])
    for folder in folders:
        try:
            summary = json.loads((folder/'summary.json').read_text())
            row = dict(population=name, task=folder.name, source=summary.get('source_id'),
                       sequence=summary.get('sequence'), arms={}, archive=str(folder/'artifacts.tar.gz'))
            for arm in ('cec', 'native'):
                a = summary.get('arms', {}).get(arm, {})
                measures = a.get('measurements', [])
                row['arms'][arm] = dict(completed=a.get('goals_completed'), status=a.get('status'),
                    path_m=sum(x.get('measurement', {}).get('actual_path_len_m',0) for x in measures),
                    legs=[dict(stage=x.get('stage'), **x.get('measurement',{})) for x in measures])
                pop[arm+'_complete'] += a.get('goals_completed') == 3
            pop['summaries'] += 1
            report['tasks'].append(row)
        except Exception as exc:
            pop['errors'].append(dict(task=folder.name,error=str(exc)))
    report['populations'].append(pop)
print(json.dumps(report,indent=2))

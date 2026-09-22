"""Crop the submitted manuscript's original tables; verify numeric tokens vs TeX."""
from pathlib import Path
from PIL import Image
import json,hashlib,re,subprocess,collections
P=Path('/home/asus/Research/Nav-graph-blind/projects/paper');R=Path('outputs/icra_submission/paper_tables')
page=Image.open(R/'page5.png').convert('RGB');sx,sy=page.width/612,page.height/792
boxes={'table_i':(109,91,500,211),'table_ii_a':(311,313,560,451),'table_ii_b':(311,459,560,529),'table_ii_c':(311,532,560,602)}
for name,box in boxes.items():page.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))).save(R/(name+'.png'))
text=subprocess.check_output(['pdftotext','-f','5','-l','5','-layout',str(P/'main.pdf'),'-']).decode();tokens=collections.Counter(re.findall(r'\d+/\d+|\d+\.\d+',text))
checks=[]
for f in ['tables/main_matrix.tex','tables/continual_meeting.tex']:
 raw=(P/f).read_text();wanted=collections.Counter(re.findall(r'\d+/\d+|\d+\.\d+','\n'.join(line for line in raw.splitlines() if '&' in line)));missing={k:n-tokens[k] for k,n in wanted.items() if n>tokens[k]};assert not missing,(f,missing)
 checks.append(dict(source=f,sha256=hashlib.sha256((P/f).read_bytes()).hexdigest(),numerical_tokens_verified=dict(wanted)))
assert re.search(r'A[–—-]B[–—-]C completed\s+12\s+64',text)
report=dict(passed=True,pdf=str(P/'main.pdf'),pdf_sha256=hashlib.sha256((P/'main.pdf').read_bytes()).hexdigest(),pdf_page_one_based=5,crops_pdf_points=boxes,checks=checks,rendering='Original PDF table pixels; no retyped table values')
(R/'verified.json').write_text(json.dumps(report,indent=2));print('Original Tables I/II cropped and numerical tokens verified.')

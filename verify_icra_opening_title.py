"""Check the actual encoded title persists through all opening frames."""
from pathlib import Path
import json,cv2,numpy as np
from PIL import Image,ImageDraw
from render_icra_submission import font
root=Path('outputs/icra_submission');mask=Image.new('L',(1920,1080));d=ImageDraw.Draw(mask)
for y,label,size in [(488,'GEM',124),(601,'A Streaming Geometry Model Is an Episodic Memory',36)]:d.text((960,y),label,font=font(size,True),anchor='mm',fill=255)
core=cv2.erode(np.array(mask),np.ones((3,3),np.uint8))>250
cap=cv2.VideoCapture(str(root/'GEM_ICRA_master.mp4'));scores=[]
for i in range(300):
 ok,im=cap.read();assert ok
 score=float((np.min(im[core],axis=1)>210).mean());band=float(im[450:620,10:35].mean())
 assert score>.98 and band<160,(i,score,band)
 scores.append(score)
cap.release();p=root/'opening_timing.verified.json';a=json.loads(p.read_text());a['encoded_title_check']=dict(frames_checked=300,min_bright_title_fraction=min(scores),persistent=True);p.write_text(json.dumps(a,indent=2));print(a['encoded_title_check'])

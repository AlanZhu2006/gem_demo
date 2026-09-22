"""Camera tour of paper Fig. 1. One claim per beat; no footnote chrome."""
from PIL import Image,ImageDraw
from icra_voice_timing import cue_time
import numpy as np
from icra_motion_design import ease

PURPLE=(123,58,181);ORANGE=(243,138,31);GREEN=(40,164,124)
AREA=(32,164,1888,900)

class PaperMethod:
 def __init__(self,r):
  self.r=r
  self.beats={k:cue_time(block,phrase)-82 for k,block,phrase in [
   ("verify","readout","and uses archived depth"),("bridge","readout","The shared geometry"),
   ("bearing","readout","to the current camera"),("navdp","interfaces","NavDP receives"),
   ("vint","interfaces","while ViNT"),("fallback","interfaces","if verification fails")] }
  original=Image.open(r.FIG).convert('RGB');sx=original.width/2048;sy=original.height/1019
  self.boxes=[(0,0,2048,325),(0,340,605,1019),(620,340,2048,1019),(0,0,2048,1019)]
  self.panels=[original.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))) for box in self.boxes[:3]]
  self.views=[self.fit(self.boxes[0],top=True),self.fit(self.boxes[1],area=(48,176,952,844)),self.fit(self.boxes[2],area=(32,164,1888,730)),self.fit(self.boxes[3])]
  self.weights=[(1,0,0),(0,1,0),(0,0,1),(1,1,1)]

 def fit(self,box,area=AREA,top=False):
  x,y,w,h=area;bw,bh=box[2]-box[0],box[3]-box[1]
  scale=min(w/bw,h/bh)
  oy=y-box[1]*scale+(18 if top else (h-bh*scale)/2)
  return np.array([scale, x-box[0]*scale+(w-bw*scale)/2, oy])

 def state(self,t):
  phase=0 if t<10 else 1 if t<20 else 2 if t<37 else 3
  starts=[0,10,20,37];u=ease((t-starts[phase])/.7) if phase else 1
  old=max(0,phase-1)
  view=self.views[old]*(1-u)+self.views[phase]*u
  weights=np.array(self.weights[old],float)*(1-u)+np.array(self.weights[phase],float)*u
  return phase,u,view,weights

 def ink(self,a,color=None):
  c=self.r.INK if color is None else color
  a=float(np.clip(a,0,1))
  return tuple(round(255+(v-255)*a) for v in c)

 def diagram(self,t,phase,view,weights):
  r=self.r;im=r.canvas();scale,ox,oy=view
  for box,pic,alpha in zip(self.boxes[:3],self.panels,weights):
   if alpha<=.001:continue
   tile=pic.resize((round((box[2]-box[0])*scale),round((box[3]-box[1])*scale)),Image.Resampling.LANCZOS)
   if alpha<.999:tile=Image.blend(Image.new('RGB',tile.size,'white'),tile,float(alpha))
   im.paste(tile,(round(ox+box[0]*scale),round(oy+box[1]*scale)))
  overlay=Image.new('RGBA',im.size,(0,0,0,0));od=ImageDraw.Draw(overlay)
  def rect(box,color,alpha=1,kind='pill'):
   if alpha<=0:return
   pad=6
   x0,y0,x1,y1=box[0]-pad,box[1]-pad,box[2]+pad,box[3]+pad
   x0,y0,x1,y1=[round(v*scale+(ox if i%2==0 else oy)) for i,v in enumerate((x0,y0,x1,y1))]
   w,h=max(1,x1-x0),max(1,y1-y0)
   if kind=='pill': rad=max(8,min(w,h)//2)
   elif kind=='photo': rad=max(6,round(min(w,h)*0.055))
   else: rad=max(12,round(min(w,h)*0.09))
   fill=tuple(color)+(round(40*alpha),)
   outline=tuple(self.ink(1,color))+(round(235*alpha),)
   od.rounded_rectangle((x0,y0,x1,y1),radius=rad,fill=fill,outline=outline,width=5)
  def dotpath(points,progress,color):
   if progress<=0 or progress>=1:return
   q=np.array(points,float);lens=np.linalg.norm(np.diff(q,axis=0),axis=1);cum=np.r_[0,np.cumsum(lens)];a=progress*cum[-1]
   i=min(len(lens)-1,np.searchsorted(cum,a,side='right')-1);point=q[i]+(q[i+1]-q[i])*((a-cum[i])/lens[i]);x,y=point*scale+[ox,oy]
   ImageDraw.Draw(im).ellipse((x-8,y-8,x+8,y+8),fill=color,outline='white',width=2)
  FPHI=(287,96,529,253);DENSE=(1072,102,1422,186);SPARSE=(1072,186,1422,293)
  ADAPTER=(1519,75,1759,298);GOAL=(647,479,942,627);HIST=(1156,479,1451,627)
  LOC=(633,884,895,990);VER=(959,886,1245,991);CACHE=(1296,890,1551,993);BEARING=(1613,890,1863,994)
  if phase==0:
   rect(FPHI,r.BLUE,ease((t-0.9)/.4),'pill')
   dotpath([(206,174),(233,174),(233,271),(617,271)],(t-1.4)/3.4,r.BLUE)
   if t>5.0:
    a=ease((t-5.0)/.4)
    rect(DENSE,PURPLE,a,'pill')
    rect(SPARSE,PURPLE,a,'pill')
  elif phase==1:
   if t<cue_time('memory','with an archive')-82:
    rect((26,414,571,502),r.BLUE,ease((t-10.7)/.4),'card')
   else:
    rect((43,869,564,997),PURPLE,ease((t-(cue_time('memory','with an archive')-82))/.4),'card')
  elif phase==2:
   local=t-20
   if t<self.beats['verify']:
    a=ease(local/.35)
    rect(GOAL,r.BLUE,a,'photo');rect(HIST,PURPLE,a,'photo')
    for y,col in [(534,r.BLUE),(555,GREEN),(589,(229,85,91))]:dotpath([(944,y),(1157,y)],(local-0.35)/2.2,col)
   elif t<self.beats['bridge']:
    a=ease((t-self.beats['verify'])/.35)
    rect(LOC,ORANGE,a,'pill');rect(VER,ORANGE,a,'pill')
   elif t<self.beats['bearing']:
    a=ease((t-self.beats['bridge'])/.35)
    rect(GOAL,r.BLUE,a,'photo');rect(CACHE,PURPLE,a,'pill')
    dotpath([(944,555),(1455,555)],(t-self.beats['bridge']-.2)/2.6,PURPLE)
   else:
    a=ease((t-self.beats['bearing'])/.35)
    rect(CACHE,PURPLE,a,'pill');rect(BEARING,r.BLUE,a,'pill')
    dotpath([(1455,555),(1688,555)],(t-self.beats['bearing']-.1)/1.8,r.BLUE)
  elif phase==3:
   if t<self.beats['navdp']:
    a=ease((t-37.7)/.4);rect(CACHE,PURPLE,a);rect(BEARING,r.BLUE,a)
   elif t<self.beats['vint']:
    rect((1519,131,1759,211),r.BLUE,ease((t-self.beats['navdp'])/.35),'card')
   elif t<self.beats['fallback']:
    rect((1519,217,1759,296),r.BLUE,ease((t-self.beats['vint'])/.35),'card')
   else:
    rect(ADAPTER,r.BLUE,ease((t-self.beats['fallback'])/.35),'card')
  im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB')
  return im

 def main_notes(self,im,t,phase,u):
  # Core bullets appear with the page; no later supplementary sentences.
  r=self.r;d=ImageDraw.Draw(im);alpha=u if phase else ease((t-.5)/.4)
  def group(x,y,title,lines,color):
   if alpha<=0:return
   d.rectangle((x,y+5,x+5,y+38),fill=self.ink(alpha,color))
   r.text(im,(x+22,y),title,32,self.ink(alpha,color),True)
   for i,line in enumerate(lines):r.text(im,(x+22,y+53+40*i),line,27,self.ink(alpha))
  if phase==0:
   group(64,615,'Streaming geometry',['RGB observations → pose and depth'],r.BLUE)
   group(698,615,'Sparse readout',['Verified view + goal direction'],PURPLE)
   group(1330,615,'Dense readout',['Current depth for local control'],r.BLUE)
  elif phase==1:
   group(1030,275,'Working state',['Context for streaming pose and depth'],r.BLUE)
   group(1030,485,'Indexed archive',['RGB, descriptor and pose','Depth and confidence'],PURPLE)
   group(1030,735,'Across goals',['Retained until episode reset'],r.BLUE)
  elif phase==2:
   group(64,942,'1  Retrieve',['Goal image → historical view'],r.BLUE)
   group(698,942,'2  Localize and verify',['Archived depth + image matches'],ORANGE)
   group(1330,942,'3  Read the bearing',['History → current camera'],PURPLE)

 def header(self,im,t,phase,u):
  r=self.r;d=ImageDraw.Draw(im)
  d.rectangle((0,0,1920,156),fill='white')
  titles=['System Overview','Episodic Memory','Goal Localization from History','Frozen Controller Interfaces']
  r.text(im,(56,34),titles[phase],40,self.ink(1 if phase==0 else u),True)

 def frame(self,t):
  phase,u,view,weights=self.state(t)
  im=self.diagram(t,phase,view,weights)
  self.main_notes(im,t,phase,u)
  self.header(im,t,phase,u)
  return im

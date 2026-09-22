"""Minimal motion graphics using recorded footage and explicitly schematic paper art."""
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageOps

def ease(x):
 x=max(0.,min(1.,x));return x*x*(3-2*x)

class MotionDesign:
 def __init__(self,r):
  self.r=r;self.caps={};self.last={}
  import render_indoor_joint as real
  real.S='outputs/realworld_inputs';self.arm=real.Arm('gem')
  self.photos=[r.crop_fig(b) for b in [(650,482,940,626),(1160,482,1448,626),(1698,484,1988,628)]]
  self.archive=r.crop_fig((25,539,578,858))
  self.geometry=r.crop_fig((666,631,1444,811))
  self.bearing=r.crop_fig((1545,640,2020,852))
 def footage(self,name,t,box):
  if name not in self.caps:self.caps[name]=cv2.VideoCapture('outputs/final/'+name+'.mp4')
  cap=self.caps[name];target=round(t*30);pos=int(cap.get(cv2.CAP_PROP_POS_FRAMES))
  if target<pos or target-pos>4:cap.set(cv2.CAP_PROP_POS_FRAMES,target);pos=target
  while pos<=target:
   ok,f=cap.read();assert ok;pos+=1;self.last[name]=f
  return Image.fromarray(cv2.cvtColor(self.last[name],cv2.COLOR_BGR2RGB)).crop(box)
 def opening(self,t):
  r=self.r;im=r.canvas();u=ease((t-1)/2);v=ease((t-2)/1.2)
  # The full-frame robot shot pulls back into an asymmetrical, live three-shot mosaic.
  x=round(64*u);y=round(280*u);w=round(1920+(1112-1920)*u);h=round(1080+(700-1080)*u)
  path,_=self.arm.third(self.arm.at(t));robot=Image.open(path).convert('RGB')
  im.paste(ImageOps.fit(robot,(w,h),Image.Resampling.LANCZOS,centering=(.5,1)),(x,y))
  if u>.01:
   rightx=round(1920+(1192-1920)*u)
   for name,start,yy in [('simulation',12,280),('outdoor',25,638)]:
    pic=self.footage(name,start+t,(28,216,508,486))
    im.paste(ImageOps.fit(pic,(664,342),Image.Resampling.LANCZOS),(rightx,yy))
  layer=Image.new('RGB',(1920,1080),'white')
  r.text(layer,(64,42),'GEM',116,r.INK,True)
  r.text(layer,(390,74),'Remember. Revisit.',55,r.INK,True)
  r.text(layer,(394,149),'Geometric Episodic Memory',29,r.MUTED)
  im.paste(Image.blend(Image.new('RGB',(1920,230),'white'),layer.crop((0,0,1920,230)),v),(0,0)) if u>.95 else None
  if u>.95:
   for xx,yy,s in [(84,938,'INDOOR'),(1212,578,'SIMULATION'),(1212,936,'OUTDOOR')]:
    d=ImageDraw.Draw(im);d.rounded_rectangle((xx-10,yy-7,xx+176,yy+32),radius=6,fill='white');r.text(im,(xx,yy),s,23,r.INK,True)
   r.text(im,(64,1010),'Selected demonstrations',23,r.MUTED)
  if t>9.5:im=Image.blend(im,r.canvas(),ease((t-9.5)/.5))
  return im
 def arrow(self,im,a,b,p):
  r=self.r;p=ease(p);x=a[0]+(b[0]-a[0])*p;y=a[1]+(b[1]-a[1])*p
  d=ImageDraw.Draw(im);d.line((*a,x,y),fill=r.BLUE,width=5)
  if p>.98:d.polygon([(x,y),(x-17,y-10),(x-17,y+10)],fill=r.BLUE)
 def method(self,t):
  r=self.r;im=r.canvas();phase=0 if t<5 else 1 if t<10.5 else 2;local=t-[0,5,10.5][phase]
  labels=['Remember','Verify','Guide'];r.text(im,(96,64),'GEM',34,r.BLUE,True)
  for i,s in enumerate(labels):
   xx=1160+i*230;r.text(im,(xx,76),s,28,r.INK if i==phase else (176,185,194),i==phase)
   if i==phase:ImageDraw.Draw(im).rounded_rectangle((xx,123,xx+110,127),radius=2,fill=r.BLUE)
  r.text(im,(96,186),['Keep experience across goals.','Find the goal in memory.','Guide the frozen controller.'][phase],64,r.INK,True)
  if phase==0:
   r.paste_fit(im,self.archive,(110,355,960,560))
   r.text(im,(1210,460),'RGB + geometry',43,r.INK,True)
   self.arrow(im,(1085,620),(1190,620),(local-.5)/1.5)
   r.text(im,(1210,602),'One persistent memory',32,r.MUTED)
   # An accumulating timeline describes storage, not measured retrieval evidence.
   d=ImageDraw.Draw(im)
   for i in range(8):
    k=ease((local-i*.3)/.5);x=1210+i*61
    d.rounded_rectangle((x,733,x+43,749),radius=4,fill=tuple(round(238+(c-238)*k) for c in r.BLUE))
  else:
   xs=[96,744,1392]
   for i,(pic,label) in enumerate(zip(self.photos,['Goal','Memory','Current view'])):
    r.text(im,(xs[i],360),label,30,r.MUTED,True)
    im.paste(ImageOps.fit(pic,(432,216),Image.Resampling.LANCZOS),(xs[i],415))
   self.arrow(im,(554,523),(717,523),(local-.3)/1.2)
   self.arrow(im,(1202,523),(1365,523),(local-1.2)/1.2 if phase==1 else 1)
   if phase==1:
    r.paste_fit(im,self.geometry,(96,698,1040,255))
    r.text(im,(1230,767),'Geometric verification',34,r.INK,True)
    r.text(im,(1230,824),'Accept only supported recall',27,r.MUTED)
   else:
    r.paste_fit(im,self.bearing,(150,680,620,278))
    self.arrow(im,(844,808),(1030,808),(local-.3)/1.4)
    d=ImageDraw.Draw(im);d.rounded_rectangle((1090,720,1810,907),radius=22,fill=(244,248,252))
    r.text(im,(1140,752),'Goal + bearing',36,r.BLUE,True)
    r.text(im,(1140,819),'Frozen NavDP',32,r.INK,True)
  r.text(im,(96,1010),'Method schematic · adapted from paper Fig. 1',22,r.MUTED)
  if phase==2:r.text(im,(1090,957),'No verified recall → native request',25,r.MUTED)
  if local<.3:im=Image.blend(r.canvas(),im,ease(local/.3))
  return im
 def results(self):
  r=self.r;im=r.canvas();r.text(im,(96,64),'GEM',40,r.BLUE,True)
  r.text(im,(96,187),'Better revisits. Same frozen controllers.',60,r.INK,True)
  r.text(im,(96,398),'+60.7–81.0',112,r.BLUE,True)
  r.text(im,(100,546),'percentage points · Revisit success',30,r.INK)
  r.text(im,(100,614),'NavDP / ViNT / NoMaD',27,r.MUTED)
  r.text(im,(1090,400),'25/30',105,r.BLUE,True);r.text(im,(1520,436),'4/30',69,r.CORAL,True)
  r.text(im,(1097,546),'GEM',30,r.INK,True);r.text(im,(1525,546),'Baseline',30,r.INK)
  r.text(im,(1097,614),'Real-world revisits',27,r.MUTED)
  ImageDraw.Draw(im).line((96,793,1824,793),fill=r.LINE,width=2)
  r.text(im,(96,852),'Remember. Revisit.',58,r.INK,True)
  r.text(im,(96,1010),'Paper evaluation · HM3D + MP3D / 30 real-world trials per method',23,r.MUTED)
  return im

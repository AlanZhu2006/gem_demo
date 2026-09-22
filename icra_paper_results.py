"""Results slides: one claim, the paper table, one takeaway. Video ends on Table II(c)."""
from pathlib import Path
from icra_voice_timing import cue_time
from PIL import Image,ImageDraw
from icra_motion_design import ease
R=Path('outputs/icra_submission/paper_tables')

class PaperResults:
 def __init__(self,r):
  self.r=r;self.pics={n:Image.open(R/(n+'.png')).convert('RGB') for n in ['table_i','table_ii_a','table_ii_c']}

 def ink(self,a,color=None):
  c=self.r.INK if color is None else color
  a=float(max(0,min(1,a)))
  return tuple(round(255+(v-255)*a) for v in c)

 def frame(self,t):
  page=0 if t<20 else 1 if t<32 else 2
  im=self.page(page,t)
  start=[0,20,32][page]
  if page and t-start<.42:im=Image.blend(self.page(page-1,start-.01),im,ease((t-start)/.42))
  return im

 def page(self,page,t):
  r=self.r;im=r.canvas();d=ImageDraw.Draw(im)
  local=t-[0,20,32][page]
  def pic(name,x,y,width):
   p=self.pics[name];h=round(p.height*width/p.width);im.paste(p.resize((width,h),Image.Resampling.LANCZOS),(x,y));return h
  def box(coords,a=1):
   if a<=0:return
   d.rectangle(coords,outline=self.ink(a,r.BLUE),width=4)
  def claim(title,sub):
   a=ease(local/.28)
   r.text(im,(56,32),title,40,self.ink(a),True)

  if page==0:
   claim('Cross-Controller Evaluation','')
   x,y,w=80,168,1760;h=pic('table_i',x,y,w)
   # Snap to booktabs outer rules (y 9–660 of 666) and the spanning header groups.
   if t<cue_time('table_i','by sixty')-135: x0,x1=0.248,0.438
   elif t<cue_time('table_i','while success')-135: x0,x1=0.618,0.805
   else: x0,x1=0.818,0.995
   box((x+round(w*x0),y+round(h*9/666)-3,x+round(w*x1),y+round(h*660/666)+3),ease((t-(cue_time('table_i','Adding GEM')-135))/.3))
   yy=y+h+40;ta=ease((local-0.7)/.35)
   r.text(im,(80,yy+18),'Real-world revisits',28,self.ink(ta),True)
   r.text(im,(560,yy),'25/30',64,self.ink(ta,r.BLUE),True)
   r.text(im,(560,yy+70),'GEM',24,self.ink(ta,r.BLUE),True)
   r.text(im,(900,yy),'4/30',64,self.ink(ta,r.CORAL),True)
   r.text(im,(900,yy+70),'Baseline',24,self.ink(ta,r.CORAL),True)
  elif page==1:
   claim('Continuous Three-Goal Navigation','')
   tw=1180;h=pic('table_ii_a',56,168,tw)
   # Footer row A–B–C completed, between the lower pair of booktabs rules.
   box((56,168+round(h*548/767)-4,56+tw,168+round(h*620/767)+3),ease((local-0.4)/.3))
   ta=ease((local-0.65)/.35)
   r.text(im,(1328,318),'Baseline',26,self.ink(ta),True)
   r.text(im,(1328,352),'12',80,self.ink(ta),True)
   r.text(im,(1328,500),'GEM',26,self.ink(ta,r.BLUE),True)
   r.text(im,(1328,534),'64',120,self.ink(ta,r.BLUE),True)
  else:
   claim('Controlled Third-Goal Recall','')
   tw=1680;h=pic('table_ii_c',120,176,tw)
   if t<cue_time('table_ii_c','while novel')-135: y0,y1=242/388,312/388
   else: y0,y1=312/388,385/388
   box((120,176+round(h*y0)-3,120+tw,176+round(h*y1)+3),ease((local-0.35)/.3))
   ta=ease((local-0.6)/.35)


  return im

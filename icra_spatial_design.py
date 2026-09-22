"""Nine independent incremental scenes, Habitat house gallery, paper method and results."""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw,ImageOps
from icra_motion_design import ease
ROOT=Path('outputs/icra_submission/montage_motion')
GALLERY=Path('outputs/icra_submission/navmesh_gallery')
SCENES=['VFuaQ6m2Qom','1LXtFkjw3qL','759xd9YjKW5','1pXnuDYAj8r','EDJbREhghzL','PX4nDJXEHrG']
ORBIT=90
class SpatialDesign:
 def __init__(self,r):
  self.r=r;self.scenes=json.load(open(ROOT/'selection.json'));self.tiles={}
  order=['courtyard','living','terrace','stage','indoor','garden','gallery','atrium','hall']
  self.scenes=sorted(self.scenes,key=lambda s:order.index(s['name']))
  for s in self.scenes:
   self.tiles[s['name']]=[Image.open(ROOT/s['name']/'tiles'/f'{i:03d}.jpg').convert('RGB') for i in range(s.get('tile_frames',150))]
  from icra_paper_method import PaperMethod
  self.paper_method=PaperMethod(r)
  from icra_paper_results import PaperResults
  self.paper_results=PaperResults(r)
  self._title_overlay=None
  j=json.load(open(ROOT/'indoor/manifest.json'))
  self.hero_rgb=[Image.open(row['path']).convert('RGB') for row in j['frames']]
  self.hero_audit=json.load(open(ROOT/'indoor/tiles.audit.json'))['frames']
  self.houses=[]
  for name in SCENES:
   frames=[]
   for i in range(ORBIT):
    p=GALLERY/name/f'{i:03d}.jpg'
    if p.exists():frames.append(Image.open(p).convert('RGB'))
   if not frames:
    still=GALLERY/f'{name}.jpg'
    frames=[Image.open(still).convert('RGB')] if still.exists() else [Image.new('RGB',(720,480),(236,241,245))]
   self.houses.append(frames)

 def opening(self,t):
  # Centered pull-back; two-line lockup on a solid bar fitted to the glyphs.
  r=self.r;base=r.canvas();hero_frame=0
  for k,s in enumerate(self.scenes):
   start=0 if k==4 else 2.5
   progress=np.clip((t-start)/(11-1/30-start),0,1)
   frame=round(progress*(len(self.tiles[s['name']])-1));x=(k%3)*640;y=(k//3)*360
   base.paste(self.tiles[s['name']][frame],(x,y+20))
   if s['name']=='indoor':hero_frame=frame
  index=max(0,self.hero_audit[hero_frame]['cloud_frames']+6)
  rgb=ImageOps.fit(self.hero_rgb[min(index,len(self.hero_rgb)-1)],(140,79),Image.Resampling.LANCZOS)
  box=(662,386,802,465)
  base.paste(Image.blend(base.crop(box),rgb,1-ease((t-2.5)/1.5)),box[:2])
  zoom=3-2*ease((t-2.5)/2.5)
  enlarged=base.resize((round(1920*zoom),round(1080*zoom)),Image.Resampling.LANCZOS)
  left=(enlarged.width-1920)//2;top=(enlarged.height-1080)//2
  im=enlarged.crop((left,top,left+1920,top+1080)).convert('RGBA')
  if not hasattr(self,'_title_overlay') or self._title_overlay is None:
   gem_font=r.font(124,True);sub_font=r.font(36,True)
   gem_text='GEM';sub_text='A Streaming Geometry Model Is an Episodic Memory'
   gem_xy,sub_xy=(960,488),(960,601)
   probe=Image.new('L',(1920,1080),0);pd=ImageDraw.Draw(probe)
   pd.text(gem_xy,gem_text,font=gem_font,anchor='mm',fill=255)
   pd.text(sub_xy,sub_text,font=sub_font,anchor='mm',fill=255)
   ys=np.where(np.array(probe)>0)[0];gy0,gy1=int(ys.min()),int(ys.max())
   pad_top,pad_bot,fade_px=44,40,10
   y0=max(0,gy0-pad_top);y1=min(1080,gy1+pad_bot+1)
   band=np.zeros((1080,1920),np.float32)
   y_lo,y_hi=max(0,y0-fade_px),min(1080,y1+fade_px)
   yy=np.arange(y_lo,y_hi)
   above=np.clip((yy-(y0-fade_px))/float(fade_px),0,1)
   below=np.clip(((y1+fade_px)-yy)/float(fade_px),0,1)
   band[yy,:]=np.minimum(above,below)[:,None]
   rgba=np.zeros((1080,1920,4),np.uint8)
   rgba[...,0]=8;rgba[...,1]=14;rgba[...,2]=26
   rgba[...,3]=np.round(band*208).astype(np.uint8)
   title=Image.fromarray(rgba,'RGBA');d=ImageDraw.Draw(title)
   def drawn(xy,text,font,fill,stroke=0,sc=(0,0,0,90)):
    if stroke:
     for dx,dy in ((-stroke,0),(stroke,0),(0,-stroke),(0,stroke),(-stroke,-stroke),(stroke,-stroke),(-stroke,stroke),(stroke,stroke)):
      d.text((xy[0]+dx,xy[1]+dy),text,font=font,anchor='mm',fill=sc)
    d.text(xy,text,font=font,anchor='mm',fill=fill)
   drawn((962,491),gem_text,gem_font,(0,0,0,150),0)
   drawn(gem_xy,gem_text,gem_font,(255,255,255,255),2)
   d.rounded_rectangle((900,556,1020,559),radius=2,fill=(255,255,255,220))
   drawn((961,604),sub_text,sub_font,(0,0,0,120),0)
   drawn(sub_xy,sub_text,sub_font,(245,248,252,255),1)
   self._title_overlay=title
  return Image.alpha_composite(im,self._title_overlay).convert('RGB')

 def environments(self,t):
  # LoGoPlanner-style 2x3: flat dollhouse houses, 360° yaw orbit, pale ground.
  r=self.r;im=Image.new('RGB',(1920,1080),(236,241,245))
  ImageDraw.Draw(im).text((960,48),'Example MP3D environments',font=r.font(36,True),anchor='mm',fill=r.INK)
  cw,ch=580,430;gap_x,gap_y=28,22
  ox=int((1920-3*cw-2*gap_x)/2);oy=86
  yaw_i=int(np.floor((t/5.0)*ORBIT))%ORBIT
  for i,frames in enumerate(self.houses):
   col,row=i%3,i//3
   x=ox+col*(cw+gap_x);y=oy+row*(ch+gap_y)
   appear=0.06+i*.12;u=np.clip((t-appear)/.28,0,1)
   if u<=0:continue
   house=frames[yaw_i%len(frames)]
   cell=Image.new('RGB',(cw,ch),(236,241,245))
   src=ImageOps.contain(house,(cw-8,ch-8),Image.Resampling.LANCZOS)
   cell.paste(src,((cw-src.width)//2,(ch-src.height)//2))
   if u<1:cell=Image.blend(Image.new('RGB',(cw,ch),(236,241,245)),cell,float(ease(u)))
   im.paste(cell,(x,y))
  return im

 def method(self,t):
  return self.paper_method.frame(t)

 def results(self,t=2):
  return self.paper_results.frame(t)

 def closing(self,t=0):
  r=self.r;im=r.canvas();d=ImageDraw.Draw(im)
  d.text((960,340),'GEM',font=r.font(120,True),anchor='mm',fill=r.INK)
  d.text((960,500),'Past observations. Verified direction. Frozen control.',font=r.font(36,True),anchor='mm',fill=r.INK)
  d.text((960,620),'No additional training',font=r.font(28),anchor='mm',fill=r.INK)
  return im

"""Fast diagnostic final-layout preview, sampling every sixth cloud observation."""
from pathlib import Path
import argparse,json
import cv2,numpy as np
from outdoor_final import OutdoorArm,FloorFixedMap,draw_outdoor_panels
from render_indoor_joint import ribbon,ring,disc,COL,GOLD
ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
g=json.loads(Path(a.config).read_text());inp=Path('outputs/outdoor_inputs')
m=FloorFixedMap(1344,854,config=a.config,manifest=g.get('manifest',str(inp/'manifest.json')),margin=.90)
arms={k:OutdoorArm(k,inp) for k in ['gem','base']};el=max(r.play for r in arms.values());cut={k:r.at(r.play) for k,r in arms.items()}
m.items=m.items[::6];m.shown=np.zeros(len(m.items),bool);m.reveal(cut)
raster=m.raster.copy();raster[~np.isfinite(m.z)]=255;z=m.z_obs.copy();up=-m.n
for k in ['base','gem']:
 col=np.array(COL[k]);P=m.to_floor(m.track(k,cut[k]),.02)
 m.splat(ribbon(P,up,(.24 if k=='base' else .18)*m.s,m.step_u),col*.92,raster,z,update_z=False)
 m.splat(ribbon(P,up,.085*m.s,m.step_u),np.minimum(col+70,255),raster,z,update_z=False)
 here=m.to_floor(m.pos_at(k,cut[k])[None],.028)[0]
 if arms[k].latch_t is not None:m.splat(ring(here,up,.27*m.s,.035*m.s,m.step_u),GOLD,raster,z,update_z=False)
 m.splat(ring(here,up,.19*m.s,.035*m.s,m.step_u),[255,255,255],raster,z,update_z=False)
 m.splat(disc(here,up,.085*m.s,m.step_u),col,raster,z,update_z=False)
frame=np.full((1080,1920,3),255,np.uint8);frame[198:1052,548:1892]=raster.reshape(854,1344,3)
draw_outdoor_panels(frame,arms,cut,el,lambda k,e:arms[k].latch_t is not None,cv2.imread(str(inp/'goal.png')),2)
cv2.imwrite(a.out,frame);print('Sampled-cloud diagnostic:',a.out)

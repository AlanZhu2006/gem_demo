"""Final real-world video: original joint reconstruction, shared minimal styling."""
import argparse,json,subprocess
from pathlib import Path
import cv2
import numpy as np
import render_indoor_joint as real
from render_indoor_joint import JointMap,Arm,ribbon,ring,disc,COL,GOLD
from final_video_style import draw_real_panels
from real_floor_cloud import FloorSupportedMap

W,H=1920,1080
MX,MY,MW,MH=548,198,1344,854

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--inputs',type=Path)
    ap.add_argument('--scene',choices=['indoor','outdoor'],default='indoor')
    ap.add_argument('--fps',type=int,default=30)
    ap.add_argument('--speed',type=float,default=2.)
    ap.add_argument('--end-hold',type=float,default=1.)
    ap.add_argument('--preview',type=float)
    ap.add_argument('--floor-cloud',choices=['supported','original','floor-fixed'],default=None)
    a=ap.parse_args()
    a.inputs=a.inputs or Path('outputs/outdoor_inputs' if a.scene=='outdoor' else 'outputs/realworld_inputs')
    a.floor_cloud=a.floor_cloud or ('floor-fixed' if a.scene=='outdoor' else 'supported')
    real.S=str(a.inputs.resolve())
    if a.scene=='outdoor':
        from outdoor_final import OutdoorArm,draw_outdoor_panels
        arms={k:OutdoorArm(k,a.inputs) for k in ('gem','base')}
        panels=draw_outdoor_panels
        ground_config=json.loads(Path('outputs/outdoor_frame.json').read_text())
        source_manifest=ground_config.get('manifest',str(a.inputs/'manifest.json'))
        map_kw=dict(config='outputs/outdoor_frame.json',manifest=source_manifest,margin=.90)
    else:
        arms={k:Arm(k) for k in ('gem','base')};panels=draw_real_panels;map_kw={}
    from outdoor_final import FloorFixedMap
    map_class={'supported':FloorSupportedMap,'original':JointMap,'floor-fixed':FloorFixedMap}[a.floor_cloud]
    M=map_class(MW,MH,**map_kw)
    last=max(r.play for r in arms.values())
    main_frames=int(np.ceil(last/a.speed*a.fps))
    nfr=main_frames+round(a.end_hold*a.fps)
    def arrived(k,el):
        r=arms[k]
        return r.latch_t is not None and (el>=r.play or r.at(min(el,r.play))>=r.latch_t)
    ff=None
    if a.preview is None:
        ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}',
            '-r',str(a.fps),'-i','-','-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(a.out)],stdin=subprocess.PIPE)
    up=-M.n;goal=cv2.imread(str(a.inputs/'goal.png'));rows=[]
    for fi in ([round(a.preview/a.speed*a.fps)] if a.preview is not None else range(nfr)):
        el=min(last,fi/a.fps*a.speed) if a.preview is None else a.preview
        cut={k:r.at(min(el,r.play)) for k,r in arms.items()}
        if a.preview is not None:
            for e in np.arange(0,el,.4):M.reveal({k:r.at(min(e,r.play)) for k,r in arms.items()})
        M.reveal(cut)
        raster=M.raster.copy();raster[~np.isfinite(M.z)]=255;z=M.z_obs.copy();tol=0.
        for k in ('base', 'gem'):
            t_s, col = cut[k], np.array(COL[k], np.uint8)
            P = M.to_floor(M.track(k, t_s), 0.020)
            if len(P) > 3:
                M.splat(ribbon(P, up, (.24 if k=='base' else .18) * M.s, M.step_u), col * 0.92, raster, z,
                        ((0, 0), (1, 0), (0, 1), (1, 1)), tol=tol,update_z=False)
                M.splat(ribbon(P, up, .085 * M.s, M.step_u),
                        np.minimum(col.astype(int) + 70, 255), raster, z, tol=tol,update_z=False)
            here = M.to_floor(M.pos_at(k, t_s)[None], 0.028)[0]
            fwd = M.fwd_at(k, t_s)
            side = np.cross(fwd, up)
            p = arms[k].plan(t_s)
            if p is not None and el < arms[k].play and not arrived(k,el):
                q = np.array(p['q'], float) if len(p['q']) else np.zeros(len(p['cand']))
                lo_, hi_ = (np.nanmin(q), np.nanmax(q)) if len(q) else (0., 1.)
                to_w = lambda A: (here + np.asarray(A)[:, :1] * fwd * M.s
                                  + np.asarray(A)[:, 1:2] * side * M.s)
                # the fan changes wholesale every policy step (~2.8 Hz), so a
                # bright wide version pops; keep it a faint short ground marking
                for j, cc in enumerate(p['cand']):
                    if cc is None or len(cc) < 2: continue
                    w = 0.5 if hi_ - lo_ < 1e-6 else (q[j] - lo_) / (hi_ - lo_)
                    M.splat(ribbon(to_w(cc[:int(len(cc) * .6)]), up, 0.045 * M.s, M.step_u),
                            np.full(3, int(58 + 70 * (0.35 + 0.55 * w))),
                            raster, z, ((0, 0),), tol=tol,update_z=False)
                M.splat(ribbon(to_w(p['sel'][:int(len(p['sel']) * .8)]), up,
                               0.085 * M.s, M.step_u),
                        np.minimum(col.astype(int) + 70, 255).astype(np.uint8),
                        raster, z, tol=tol,update_z=False)
            if arrived(k, el):
                lt = min(arms[k].latch_t, arms[k].at(arms[k].play))
                at = M.to_floor(M.pos_at(k, lt)[None], 0.024)[0]
                M.splat(ring(at, up, 0.27 * M.s, 0.035 * M.s, M.step_u),
                        np.array(GOLD, np.uint8), raster, z, tol=tol,update_z=False)
            M.splat(ring(here, up, 0.19 * M.s, 0.035 * M.s, M.step_u),
                    np.array([255, 255, 255], np.uint8), raster, z, tol=tol,update_z=False)
            M.splat(disc(here, up, 0.085 * M.s, M.step_u), col, raster, z, tol=tol,update_z=False)

        frame=np.full((H,W,3),255,np.uint8)
        frame[MY:MY+MH,MX:MX+MW]=raster.reshape(MH,MW,3)
        panels(frame,arms,cut,el,arrived,goal,a.speed)
        assert all(not shown or t<=cut[arm]+1e-6 for shown,(t,arm,_,_) in zip(M.shown,M.items))
        row=dict(video_frame=fi,elapsed_s=el,source_times=cut,shown_frames=int(M.shown.sum()),
            arrived={k:bool(arrived(k,el)) for k in arms},failed={k:bool(el>=r.play and not arrived(k,el)) for k,r in arms.items()})
        rows.append(row)
        if a.preview is not None:
            cv2.imwrite(str(a.out),frame);return
        ff.stdin.write(frame.tobytes())
        if fi%150==0:print(f'{fi}/{nfr}',flush=True)
    ff.stdin.close()
    if ff.wait()!=0:raise RuntimeError('ffmpeg failed')
    if a.scene=='outdoor':
        original=dict(pose_causality=ground_config.get('inference_order','base reversed then gem forward')+' joint inference. Playback visibility is timestamp-causal; model inference is not an online two-stream comparison.',
            clock={k:dict(onset=r.onset,end=r.tend,removed_stall_s=r.cut_s,play_s=r.play,latch_t=r.latch_t) for k,r in arms.items()})
    else:
        original=json.loads((a.inputs/'original_reference.audit.json').read_text())
    audit=dict(video=str(a.out),scene=a.scene,source_manifest=source_manifest if a.scene=='outdoor' else 'outputs/joint_rgb/manifest.json',fps=a.fps,speed=a.speed,end_hold_s=a.end_hold,arrival_hold_s=0,
        reconstruction=str(M.root),input_root=str(a.inputs.resolve()),frames=rows,
        outcome={k:dict(arrived=r.latch_t is not None,playback_source_s=r.play) for k,r in arms.items()},
        pose_causality=original['pose_causality'],clock=original['clock'],
        style='Shared minimal white; bold Lato; blue/coral arrival borders; true grayscale darkened failure panels. '+('Two FPVs.' if a.scene=='outdoor' else 'Third-person with FPV inset.'),
        ground_policy='Original joint real-world floor projection and local-plan convention retained.',
        floor_cloud=dict(mode=a.floor_cloud,stats=getattr(M,'stats',{}),
            policy='Original strict points retained; extra points at -0.30 to +0.20 m, confidence percentile 40, original flatness, two prior same-arm depth matches at 0.18–1.6 s age and >=3 cm camera translation; depth tolerance max(5 cm, 1% range). No coordinate flattening.' if a.floor_cloud=='supported' else ('Original quality; height -0.30 to 1.10 m; raw coordinates retained.' if a.floor_cloud=='floor-fixed' else 'Original JointMap quality and height filters.'),
            support_visibility='Past playback observations only; existing reconstruction inference order unchanged.'),
        causal_visibility_pass=True)
    a.out.with_suffix('.audit.json').write_text(json.dumps(audit,indent=2))
    print('Rendered',a.out)

if __name__=='__main__':main()

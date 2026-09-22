"""Decode both deliverables and check real-world visibility and failure grayscale."""
import hashlib,json
from pathlib import Path
import cv2,numpy as np
import render_indoor_joint as real

ROOT=Path('outputs/final')

def check_real():
    audit=json.loads((ROOT/'realworld.audit.json').read_text());real.S=audit['input_root']
    arms={k:real.Arm(k) for k in ('gem','base')}
    meta=json.loads((Path(audit['reconstruction'])/'reconstruction.json').read_text())
    man=json.loads(Path(meta['source_manifest']).read_text());info={r['key']:r for r in man['frames']}
    ts={k:np.array([r['timestamp_ns']/1e9 for r in meta['frames'] if not r['warming'] and info[r['key']]['arm']==k]) for k in arms}
    for row in audit['frames']:
        expected=0
        for k,r in arms.items():
            t=r.at(min(row['elapsed_s'],r.play));assert abs(t-row['source_times'][k])<1e-6
            reached=r.latch_t is not None and (row['elapsed_s']>=r.play or t>=r.latch_t)
            assert row['arrived'][k]==reached
            assert row['failed'][k]==(row['elapsed_s']>=r.play and not reached)
            expected+=int((ts[k]<=t).sum())
        assert row['shown_frames']==expected
    assert audit['frames'][-1]['arrived']=={'gem':True,'base':False}
    assert audit['frames'][-1]['failed']=={'gem':False,'base':True}
    return audit

def main():
    real_audit=check_real();reports={}
    for name in ['simulation','realworld']:
        p=ROOT/(name+'.mp4');audit=json.loads(p.with_suffix('.audit.json').read_text())
        cap=cv2.VideoCapture(str(p));n=0;sample=[];last=None
        total=len(audit['frames']);events=[]
        if name=='realworld':
            for k in ['gem','base']:
                at=next((r['video_frame'] for r in audit['frames'] if r['arrived'][k] or r['failed'][k]),None)
                if at is not None:events.append(at)
        else:
            events=[r['video_frame'] for r in json.loads((ROOT/'simulation.verified.json').read_text())['visual_arrivals_verified']]
        want=set([0,total//2,total-1]+events);decoded={}
        while True:
            ok,frame=cap.read()
            if not ok:break
            if n in want:decoded[n]=frame.copy()
            last=frame;n+=1
        fps=cap.get(cv2.CAP_PROP_FPS);cap.release();assert n==total and fps==30 and last.shape==(1080,1920,3)
        # Exclude labels, colored borders and inset borders from grayscale ROIs.
        regions=([last[670:910,40:490]] if name=='simulation' else
                 [last[654:900,40:440],last[930:1038,220:430]])
        diffs=[float(np.mean(np.max(r.astype(float),2)-np.min(r.astype(float),2))) for r in regions]
        # YUV420/H.264 round-trip introduces a uniform <=3/255 channel offset
        # even though failed_image() emits exactly equal RGB channels.
        assert max(diffs)<=3.1,(name,diffs)
        assert all(np.percentile(np.ptp(r.astype(float),axis=2),99)<=4 for r in regions)
        assert all(float(r.mean())<125 for r in regions)
        cv2.imwrite(str(p.with_suffix('.last.jpg')),last)
        cv2.imwrite(str(p.with_suffix('.jpg')),np.hstack([cv2.resize(decoded[i],(960,540)) for i in [total//2,total-1]]))
        for i in sorted(set(events)):cv2.imwrite(str(ROOT/f'{name}.event_{i}.jpg'),decoded[i])
        report=dict(frames=n,fps=fps,duration_s=n/fps,full_decode=True,failed_baseline_gray_channel_spread=diffs,
                    failed_baseline_mean_intensity=[float(r.mean()) for r in regions],sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        reports[name]=report
        if name=='realworld':
            report.update(causal_visibility_verified=True,independent_arrival_state_verified=True,outcome=real_audit['outcome'])
            p.with_suffix('.verified.json').write_text(json.dumps(report,indent=2))
    if (ROOT/'outdoor.mp4').exists():
        from verify_outdoor_final import verify
        reports['outdoor']=verify(ROOT/'outdoor.mp4')
    (ROOT/'delivery.verified.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))

if __name__=='__main__':main()

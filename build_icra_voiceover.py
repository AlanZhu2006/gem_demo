"""Align cached speech to the verified visual cut; make external and burned captions.
The visual source stays unchanged. A 16:9 safe area keeps captions below the content.
"""
from pathlib import Path
import array,hashlib,json,subprocess,textwrap,wave
ROOT=Path('outputs/icra_submission');N=ROOT/'narration';SR=24000

def run(args):subprocess.run(args,check=True)
def timestamp(t,ass=False):
    ms=round(t*(100 if ass else 1000));unit=100 if ass else 1000
    h,ms=divmod(ms,3600*unit);m,ms=divmod(ms,60*unit);s,f=divmod(ms,unit)
    return f'{h}:{m:02}:{s:02}.{f:02}' if ass else f'{h:02}:{m:02}:{s:02},{f:03}'
def build():
    spec=json.loads((N/'script.json').read_text());mix=array.array('h',[0])*round(spec['duration']*SR)
    captions=[];audit=[]
    for b in spec['blocks']:
        stem=N/b['id'];words=[json.loads(x) for x in stem.with_suffix('.jsonl').read_text().splitlines()]
        words=[w for w in words if w['type']=='WordBoundary'];assert words
        tokens=b['text'].split()
        assert len(tokens)==len(words),(b['id'],tokens,words)
        for token,w in zip(tokens,words):
            assert token.strip('.,;:!?').lower()==w['text'].lower(),(token,w)
            w['text']=token
        for w in words:
            w['s']=w['offset']/1e7;w['e']=(w['offset']+w['duration'])/1e7
        used=words[-1]['e']+.16;available=b['end']-b['start'];tempo=max(1,used/available)
        assert tempo<=1.17,(b['id'],tempo,'Revise narration instead of rushing it')
        out=stem.with_suffix('.wav')
        run(['ffmpeg','-v','error','-y','-i',str(stem.with_suffix('.mp3')),'-af',f'atrim=end={used},asetpts=PTS-STARTPTS,atempo={tempo:.9f},afade=t=in:d=0.015','-ar',str(SR),'-ac','1','-c:a','pcm_s16le',str(out)])
        with wave.open(str(out)) as f:raw=array.array('h',f.readframes(f.getnframes()))
        at=round(b['start']*SR);assert at+len(raw)<=len(mix)
        mix[at:at+len(raw)]=raw
        # Author-edited short clauses, in the style of the LogoPlanner reference.
        phrases={'Table one':'Table I','sixty point seven':'60.7','eighty-one':'81.0','sixty-four':'64','twelve':'12','twenty-five of thirty':'25/30','four of thirty':'4/30','eight of twenty':'8/20','seventeen of twenty':'17/20','four out of twenty':'4/20'}
        groups=[];at_word=0
        assert ' '.join(b['caption_phrases'])==b['text']
        for phrase in b['caption_phrases']:
            count=len(phrase.split());groups.append(words[at_word:at_word+count]);at_word+=count
        assert at_word==len(words)
        for i,g in enumerate(groups):
            start=b['start']+g[0]['s']/tempo-.035
            end=b['start']+g[-1]['e']/tempo+.25
            if i+1<len(groups):
                next_start=b['start']+groups[i+1][0]['s']/tempo-.035
                # Hold through short speech pauses; no distracting blank flashes.
                if next_start-end<.35:end=next_start
                else:end=min(end,next_start)
            end=min(end,b['end']);txt=' '.join(w['text'] for w in g)
            for spoken,written in phrases.items():txt=txt.replace(spoken,written)
            assert '\n' not in txt and len(txt)<=64,txt
            captions.append(dict(start=start,end=end,text=txt,block=b['id']))
        audit.append(dict(id=b['id'],start=b['start'],end=b['start']+len(raw)/SR,slot_end=b['end'],tempo=tempo,source=b['source'],text=b['text'],words=len(words)))
    rawwav=N/'aligned_raw.wav'
    with wave.open(str(rawwav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR);f.writeframes(mix.tobytes())
    # Two-pass loudness normalization preserves natural dynamics and reproducibility.
    base=['ffmpeg','-hide_banner','-i',str(rawwav)]
    p=subprocess.run(base+['-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    stats=json.loads(p.stderr[p.stderr.rfind('{'):]);(N/'loudness_input.json').write_text(json.dumps(stats,indent=2))
    filt='loudnorm=I=-16:TP=-1.5:LRA=7:linear=true:'+':'.join(f'{a}={stats[b]}' for a,b in [('measured_I','input_i'),('measured_TP','input_tp'),('measured_LRA','input_lra'),('measured_thresh','input_thresh'),('offset','target_offset')])
    run(['ffmpeg','-v','error','-y','-i',str(rawwav),'-af',filt,'-ar',str(SR),'-c:a','pcm_s16le',str(ROOT/'GEM_narration.wav')])
    srt='\n\n'.join(f"{i+1}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}" for i,c in enumerate(captions))+'\n'
    (ROOT/'GEM_English.srt').write_text(srt)
    ass='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,DejaVu Sans,52,&H00141414,&H00141414,&H00FFFFFF,&H60000000,-1,0,0,0,90,100,0,0,1,3,0,2,90,90,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    for c in captions:
        txt=c['text'].replace('\n',r'\N')
        ass+=f"Dialogue: 0,{timestamp(c['start'],True)},{timestamp(c['end'],True)},Narration,,0,0,0,,{{\\pos(960,1052)}}{txt}\n"
    (ROOT/'GEM_English.ass').write_text(ass)
    (N/'alignment.json').write_text(json.dumps(dict(duration=spec['duration'],voice=spec['voice'],blocks=audit,captions=captions,visual_master_sha256=hashlib.sha256((ROOT/'GEM_ICRA_master.mp4').read_bytes()).hexdigest(),caption_layout='16:9; full visual source uniformly fitted to 1792x1008 at x=64,y=0; fixed single-line subtitles at (960,1052), no panel; upload 1440x810.'),indent=2))
    print(json.dumps(audit,indent=2),flush=True)

if __name__=='__main__':build()

"""Encode the narrated delivery; keep the validated silent edit as its visual source."""
from pathlib import Path
import json,shutil,subprocess
ROOT=Path('outputs/icra_submission')
def run(args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y']+args,check=True)
def main():
    spec=json.loads((ROOT/'narration/script.json').read_text());duration=spec['duration']
    archive=ROOT/'visual_cut_v9';archive.mkdir(exist_ok=True)
    for name in ['GEM_ICRA_submission.mp4','encoding.json','submission.verified.json']:
        if (ROOT/name).exists() and not (archive/name).exists():shutil.copy2(ROOT/name,archive/name)
    master=ROOT/'GEM_ICRA_narrated_master.mp4'
    print('Encode captioned master',flush=True)
    vf=f"scale=1792:1008:flags=lanczos,pad=1920:1080:64:0:color=white,ass={ROOT/'GEM_English.ass'},setsar=1,setfield=prog"
    run(['-i',str(ROOT/'GEM_ICRA_master.mp4'),'-i',str(ROOT/'GEM_narration.wav'),'-map','0:v:0','-map','1:a:0','-vf',vf,'-t',str(duration),'-c:v','libx264','-threads','8','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-ac','1','-map_metadata','-1','-metadata','title=GEM | Accompanying Video','-movflags','+faststart',str(master)])
    out=ROOT/'GEM_ICRA_submission.mp4'
    for bitrate in [780,750]:
        base=['-i',str(master),'-map','0:v:0','-vf','scale=1440:810:flags=lanczos,fps=24,setsar=1,setfield=prog','-c:v','libx264','-threads','8','-preset','slow','-b:v',f'{bitrate}k','-pix_fmt','yuv420p','-passlogfile',str(ROOT/'voice_encode_pass'),'-map_metadata','-1']
        for n in [1,2]:
            print('Encode upload',bitrate,'pass',n,flush=True)
            run(base+['-pass',str(n)]+(['-an','-f','null','/dev/null'] if n==1 else ['-map','0:a:0','-c:a','aac','-b:a','64k','-ar','48000','-ac','1','-movflags','+faststart',str(out)]))
        if out.stat().st_size<19_500_000:break
    assert out.stat().st_size<=20_000_000
    for p in ROOT.glob('voice_encode_pass*'):p.unlink()
    for filename,start,length in [('GEM_voice_preview.mp4',0,40),('GEM_results_voiced_preview.mp4',135,43),('GEM_method_voiced_preview.mp4',82,53)]:
        run(['-ss',str(start),'-i',str(out),'-t',str(length),'-c:v','libx264','-threads','8','-preset','fast','-crf','19','-c:a','aac','-b:a','96k','-movflags','+faststart',str(ROOT/filename)])
    (ROOT/'encoding.json').write_text(json.dumps(dict(version=24,video=str(out),master=str(master),visual_source=str(ROOT/'GEM_ICRA_master.mp4'),duration=duration,width=1440,height=810,fps=24,video_bitrate_kbps=bitrate,audio=True,audio_bitrate_kbps=64,audio_codec='AAC mono',subtitles='English burned-in; external SRT and ASS',voice=spec['voice'],passes=2,bytes=out.stat().st_size,last_table_extension_seconds=0,order=['opening','indoor','outdoor','environments','simulation','method','results'],caption_layout='LogoPlanner-inspired: single-line black bold with white outline, 16:9 safe area, no appended caption panel'),indent=2))
    print('Finished',out.stat().st_size,'bytes',flush=True)
if __name__=='__main__':main()

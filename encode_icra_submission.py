"""Size-budgeted two-pass upload encode; retain a separate high-quality master."""
from pathlib import Path
import json,subprocess
root=Path('outputs/icra_submission');src=root/'GEM_ICRA_master.mp4';delivery=root/'visual_cut_v9';delivery.mkdir(exist_ok=True);out=delivery/'GEM_ICRA_submission.mp4'
assert json.loads((root/'assembly.audit.json').read_text())['frames']==5235
for bitrate in [820,790]:
 base=['ffmpeg','-v','error','-y','-i',str(src),'-map','0:v:0','-an','-vf','scale=1280:720:flags=lanczos,fps=24,setsar=1,setfield=prog','-c:v','libx264','-preset','slow','-b:v',f'{bitrate}k','-pix_fmt','yuv420p','-map_metadata','-1','-passlogfile',str(root/'encode_pass')]
 for n in [1,2]:
  print('Encode',bitrate,'kb/s, pass',n,flush=True)
  subprocess.run(base+['-pass',str(n)]+(['-f','null','/dev/null'] if n==1 else ['-movflags','+faststart',str(out)]),check=True)
 if out.stat().st_size<19_000_000:break
assert out.stat().st_size<=20_000_000
for p in root.glob('encode_pass*'):p.unlink()
(delivery/'encoding.json').write_text(json.dumps(dict(video=str(out),video_bitrate_kbps=bitrate,audio=False,passes=2,preset='slow',target_bytes=19_000_000,bytes=out.stat().st_size),indent=2))
print('Upload encode:',out.stat().st_size,'bytes',flush=True)

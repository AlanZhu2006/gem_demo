"""Export website media from the paper and the verified v24 video (no re-reconstruction)."""
from pathlib import Path
from functools import lru_cache
import hashlib
import html
import json
import shutil
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'project_site/assets'
PAPER = Path('/home/asus/Research/Nav-graph-blind/projects/paper')
VIDEO = ROOT / 'outputs/icra_submission'
TILES = VIDEO / 'montage_motion'


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], check=True)


def write_transcript():
    spec = json.loads((VIDEO / 'narration/script.json').read_text())
    names = ['Introduction', 'Indoor revisit', 'Outdoor revisit', 'Simulation environments', 'Successive goals',
             'System overview', 'Episodic memory', 'Goal readout', 'Controller interfaces',
             'Cross-controller evaluation', 'Continuous navigation', 'Shared-history recall']
    parts = []
    for block, name in zip(spec['blocks'], names):
        minutes, seconds = divmod(int(block['start']), 60)
        parts.append(f'<section style="margin:36px 0"><p class="eyebrow">{minutes}:{seconds:02d}</p><h2 style="font-size:24px;margin-bottom:16px">{name}</h2><p>{html.escape(block["text"])}</p></section>')
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GEM — Video transcript</title><link rel="stylesheet" href="styles.css"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"></head><body><header class="site-header"><nav class="nav-shell" aria-label="Main navigation"><a class="wordmark" href="index.html">GEM<span class="brand-dot"></span></a><a href="index.html#film">Back to the film ↗</a></nav></header><main class="section-shell" style="max-width:780px;padding-block:60px"><p class="eyebrow">English narration / 2:58</p><h1 style="font-size:42px;margin-bottom:24px">Video transcript</h1>'''
    (ROOT/'project_site/transcript.html').write_text(page+'\n'.join(parts)+'</main></body></html>\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = Image.open(PAPER / 'figures/gem_architecture_pic_20260915/GEM_architecture_pic_slide2.png').convert('RGB')
    original.save(OUT / 'architecture.webp', quality=95)
    for name, box in [('overview', (0, 0, 2048, 325)), ('memory', (0, 340, 605, 1019)), ('readout', (620, 340, 2048, 1019))]:
        sx, sy = original.width / 2048, original.height / 1019
        crop = original.crop(tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(box)))
        crop.save(OUT / f'{name}.webp', quality=95)
    shutil.copy2(PAPER / 'main.pdf', OUT / 'paper.pdf')
    shutil.copy2(VIDEO / 'GEM_ICRA_submission.mp4', OUT / 'presentation.mp4')
    # VTT timestamps are preserved from the English transcript. The full film
    # already has burned captions; expose this as a download, not a duplicate track.
    srt = (VIDEO / 'GEM_English.srt').read_text()
    (OUT / 'presentation.en.srt').write_text(srt)
    write_transcript()
    for name, start, length, poster in [('indoor', 11, 21, 18), ('outdoor', 32, 24, 16), ('simulation', 61, 21, 15)]:
        ffmpeg('-ss', start, '-i', VIDEO / 'GEM_ICRA_master.mp4', '-t', length,
               '-an', '-vf', 'scale=1280:720:flags=lanczos,fps=24', '-c:v', 'libx264',
               '-threads', 4, '-preset', 'medium', '-crf', 23, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT / f'{name}.mp4')
        ffmpeg('-ss', poster, '-i', OUT / f'{name}.mp4', '-frames:v', 1, '-q:v', 2, OUT / f'{name}.jpg')
    ffmpeg('-ss', 8, '-i', OUT / 'presentation.mp4', '-frames:v', 1, '-q:v', 2, OUT / 'presentation.jpg')
    # Reuse precisely the selected point-cloud/candidate-trajectory frames.
    # The web teaser removes the film's burned title so it does not duplicate H1.
    scenes = {s['name']: s for s in json.loads((TILES / 'selection.json').read_text())}
    order = ['courtyard', 'living', 'terrace', 'stage', 'indoor', 'garden', 'gallery', 'atrium', 'hall']

    @lru_cache(maxsize=27)
    def tile(name, frame):
        with Image.open(TILES / name / 'tiles' / f'{frame:03d}.jpg') as im:
            return im.convert('RGB').copy()

    def ease(x):
        x = min(1, max(0, x))
        return x*x*(3-2*x)

    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '1280x720', '-r', '24', '-i', '-', '-an', '-c:v', 'libx264', '-threads', '4',
           '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT / 'teaser.mp4')]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(264):
            t = i / 24
            grid = Image.new('RGB', (1920, 1080), 'white')
            for k, name in enumerate(order):
                start = 0 if name == 'indoor' else 2.5
                progress = min(1, max(0, (t-start)/(11-1/30-start)))
                frame = round(progress*(scenes[name].get('tile_frames', 150)-1))
                grid.paste(tile(name, frame), ((k % 3)*640, (k // 3)*360+20))
            zoom = 3 - 2*ease((t-2.5)/2.5)
            w, h = 1920/zoom, 1080/zoom
            frame = grid.resize((1280, 720), Image.Resampling.LANCZOS,
                                box=((1920-w)/2, (1080-h)/2, (1920+w)/2, (1080+h)/2))
            if i == 218:
                frame.save(OUT / 'teaser.jpg', quality=90)
            if t > 10.4:
                frame = Image.blend(frame, Image.new('RGB', frame.size, 'white'), ease((t-10.4)/.55))
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        assert proc.wait() == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    paths = [PAPER/'main.tex', PAPER/'main.pdf', PAPER/'tables/main_matrix.tex', PAPER/'tables/continual_meeting.tex',
             PAPER/'figures/gem_architecture_pic_20260915/GEM_architecture_pic_slide2.png', VIDEO/'GEM_ICRA_master.mp4',
             VIDEO/'GEM_ICRA_submission.mp4', TILES/'selection.json']
    manifest = dict(sources=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
                    assets=[dict(name=p.name, bytes=p.stat().st_size) for p in sorted(OUT.iterdir())],
                    note='Teaser is recorded incremental point-cloud visualization, not an online reconstruction timing claim. Demonstration sampling follows the v24 video. Paper PDF is the current anonymous manuscript.')
    (ROOT/'project_site/asset-provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Website assets ready:', sum(p.stat().st_size for p in OUT.iterdir()), 'bytes')


if __name__ == '__main__':
    main()

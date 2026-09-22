"""Generate a cached neural narration take and word timestamps per visual chapter.
Run with /tmp/gem-voice-env/bin/python (pip install edge-tts).
Only the authored narration text is submitted to the TTS service.
"""
import asyncio, hashlib, json
from pathlib import Path
import edge_tts
ROOT=Path('outputs/icra_submission/narration')
async def main():
    spec=json.loads((ROOT/'script.json').read_text())
    for block in spec['blocks']:
        stem=ROOT/block['id']
        rate=block.get('rate',spec['rate'])
        key=hashlib.sha256(json.dumps([spec['voice'],rate,block['text']]).encode()).hexdigest()
        stamp=stem.with_suffix('.sha256')
        if stamp.exists() and stamp.read_text()==key:
            print('Cached',block['id'],flush=True); continue
        for attempt in range(3):
            try:
                c=edge_tts.Communicate(block['text'],voice=spec['voice'],rate=rate,boundary='WordBoundary')
                await c.save(str(stem.with_suffix('.mp3')),str(stem.with_suffix('.jsonl')))
                stamp.write_text(key)
                print('Synthesized',block['id'],flush=True)
                break
            except Exception:
                if attempt==2:raise
                await asyncio.sleep(2)
    (ROOT/'provider.json').write_text(json.dumps({'provider':'Microsoft Edge online neural TTS','client':'edge-tts','version':edge_tts.__version__,'voice':spec['voice'],'rate':spec['rate'],'source':'https://github.com/rany2/edge-tts','uploaded':'Authored narration text only; no source video or manuscript files.'},indent=2))
asyncio.run(main())

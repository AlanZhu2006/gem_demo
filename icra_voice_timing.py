"""Find actual spoken-clause onset times for paper figure/table highlights.
Build voice alignment before rendering; a missing phrase is an error, not a fallback.
"""
import json
from pathlib import Path
from functools import lru_cache
@lru_cache(maxsize=1)
def _load():
    r=Path('outputs/icra_submission/narration')
    spec=json.loads((r/'script.json').read_text())
    aligned=json.loads((r/'alignment.json').read_text())
    assert [b['text'] for b in spec['blocks']]==[b['text'] for b in aligned['blocks']], 'Rebuild narration alignment before rendering.'
    return spec,aligned
@lru_cache(maxsize=None)
def cue_time(block,prefix):
    spec,aligned=_load()
    b=next(b for b in spec['blocks'] if b['id']==block)
    k=[i for i,p in enumerate(b['caption_phrases']) if p.startswith(prefix)]
    assert len(k)==1,(block,prefix,k)
    cues=[c for c in aligned['captions'] if c['block']==block]
    assert len(cues)==len(b['caption_phrases'])
    return cues[k[0]]['start']

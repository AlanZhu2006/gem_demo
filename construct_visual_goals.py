"""Demo goal proposals with unchanged per-arm history-support rules.

Optional proposal budgets, RGB image-quality filters and predefined references
are evaluator-side task construction, never navigation or arrival authority.
The original 60-degree novel route bound is the default. Every accepted goal
is still checked against the surviving arms' actual histories and geometry.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import sys

ROOT=Path('/home/asus/Research/Nav-graph-blind')
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MemNavData'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--request',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    from MemNavData import table2_common_goals as original
    request=json.loads(args.request.read_text())
    angle=float(request.get('novel_max_route_angle_deg',60))
    if not 0<angle<=180:raise ValueError('Invalid novel proposal angle')
    source=inspect.getsource(original.construct_common)
    needle='if role == "novel" and abs(angle) > 60:'
    assert source.count(needle)==1,'Original constructor changed; review required'
    modified=source.replace(needle,'if role == "novel" and abs(angle) > visual_novel_angle_limit:')
    # PNG histories saturate at 65535 / 10000 m. Re-render evaluator-only
    # depth at the recorded poses so distant surfaces remain visible.
    history_anchor='    states = {}'
    assert modified.count(history_anchor)==1
    modified=modified.replace(history_anchor,
        '    for h in histories.values():\n'
        '        h["depths"] = [render(sim, np.asarray([p[k] for k in "xyz"]) + [0, height, 0], p["yaw"])[1] for p in h["poses"]]\n'
        +history_anchor)
    views=int(request.get('novel_views_per_band',original.NOVEL_VIEWS_PER_CELL))
    pool=int(request.get('novel_goals_per_band',1)) if request['role']=='novel' else 1
    min_features=int(request.get('novel_min_goal_keypoints',0))
    max_black=float(request.get('novel_max_black_fraction',1))
    assert views>0 and pool>0 and min_features>=0 and 0<=max_black<=1
    modified=modified.replace('if band in retained:',
        'if sum(c["distance_band"] == band for c in candidates) >= visual_goals_per_band:')
    modified=modified.replace('directory = out / band',
        'directory = out / (band if visual_goals_per_band == 1 else f"{band}_{len(candidates):03d}")')
    modified=modified.replace('        retained.add(band)',
        '        if sum(c["distance_band"] == band for c in candidates) >= visual_goals_per_band:\n            retained.add(band)')
    def quality(rgb):
        import cv2
        import numpy as np
        if float(np.mean(rgb.max(2)<12))>max_black:return False
        return (not min_features or len(cv2.SIFT_create(nfeatures=1200,
            contrastThreshold=.025).detect(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),None))>=min_features)
    render_line='        rgb, depth = render(sim, position + [0, height, 0], yaw)'
    assert modified.count(render_line)==1
    modified=modified.replace(render_line,render_line+'\n        if role == "novel" and not visual_goal_quality(rgb):\n            counts["novel_image_quality_rejected"] += 1\n            return')
    namespace=dict(vars(original),visual_novel_angle_limit=angle,
                   visual_goal_quality=quality,NOVEL_VIEWS_PER_CELL=views,
                   visual_goals_per_band=pool)
    preferred=request.get('preferred_goal')
    start='    try:\n        if role == "novel":'
    assert modified.count(start)==1
    modified=modified.replace(start,'    try:\n        if visual_preferred_goal is not None:\n'
        '            fixed_position = np.asarray(visual_preferred_goal["floor_position"])\n'
        '            fixed_geometry = geometry(fixed_position)\n'
        '            if fixed_geometry is not None:\n'
        '                inspect(fixed_position, visual_preferred_goal["yaw_rad"], fixed_geometry, {"predefined_goal": True})\n'
        '                if candidates and candidates[-1]["goal_rgb_sha256"] != visual_preferred_goal["goal_rgb_sha256"]:\n'
        '                    raise ValueError("Predefined goal render differs from reference RGB")\n'
        '        if role == "novel":')
    namespace['visual_preferred_goal']=preferred
    exec(compile(modified,str(Path(__file__).resolve()),'exec'),namespace)
    result=namespace['construct_common'](request['source'],stage=request['stage'],
        prefixes=request['prefixes'],role=request['role'],out=args.out)
    receipt=dict(formal_population=False,novel_max_route_angle_deg=angle,
        novel_views_per_band=views,novel_min_goal_keypoints=min_features,
        novel_goals_per_band=pool,
        novel_max_black_fraction=max_black,
        predefined_goal=preferred,
        predefined_goal_accepted=bool(preferred and any(c['goal_rgb_sha256']==preferred['goal_rgb_sha256'] for c in result['candidates'])),
        original_novel_max_route_angle_deg=60,history_support_rules_unchanged=True,
        history_depth_source='full_precision_rerender_at_actual_recorded_poses',
        legacy_png_depth_saturation_m=6.5535,
        original_module=str(Path(original.__file__).resolve()),
        original_module_sha256=hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(),
        original_function_sha256=hashlib.sha256(source.encode()).hexdigest(),
        modified_function_sha256=hashlib.sha256(modified.encode()).hexdigest())
    (args.out/'executed_constructor.py').write_text(modified)
    (args.out/'visual_proposal_profile.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(dict(stage=request['stage'],role=request['role'],
        bands=[c['distance_band'] for c in result['candidates']],profile=receipt)),flush=True)


if __name__=='__main__':main()

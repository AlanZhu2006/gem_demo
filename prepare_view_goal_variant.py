"""Predefine an A image goal from an archived view and verify original novel rules.

Only evaluator-side task construction uses poses/depth. The live policies still
receive RGB, and must reach this fixed image through actual continuous motion.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tarfile

import numpy as np

ROOT=Path('/home/asus/Research/Nav-graph-blind')
sys.path[:0]=[str(ROOT),str(ROOT/'MemNavData')]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--rgb-source',type=Path,required=True)
    ap.add_argument('--asset',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--original-goal-yaw-deg',type=float,
                    help='Render a predefined view at the original A goal position instead of using an archived frame.')
    args=ap.parse_args()
    from MemNavData.generate_twoleg import make_sim,render,covis_frac,cam_to_world_hab,first_path_yaw
    from MemNavData.build_shared_online_double_revisit import goal_world_points,jpeg_bytes
    from MemNavData.table2_balanced_sampling import novel_supported_as_task
    from MemNavData.audit_pt1_multinovel_capacity import shortest,distance_bin
    from MemNavData.final14_role_pair_contract import relative_direction_degrees,direction_in_stratum,STRATA,DEPTH_TOLERANCE_M
    pair=json.loads((args.rgb_source/'paired.json').read_text())
    arm=pair['arms']['gem'];leg=arm['legs'][0];frame=arm['frames'][leg['stop']-1]
    with tarfile.open(args.archive) as archive:
        source=json.load(archive.extractfile('task/source.json'))
        query=json.load(archive.extractfile('task/A_query.json'))
    payload=Path(frame['path']).read_bytes()
    assert hashlib.sha256(payload).hexdigest()==frame['sha256']
    assert hashlib.sha256(args.asset.read_bytes()).hexdigest()==source['asset_sha256']
    origin=np.array(source['start_position']);camera=np.array(frame['gt_camera'])
    position=camera-[0,source['camera_height_m'],0];yaw=frame['gt_yaw']
    if args.original_goal_yaw_deg is not None:
        position=np.array(query['floor_position']);camera=position+[0,source['camera_height_m'],0]
        yaw=math.radians(args.original_goal_yaw_deg)
    sim=make_sim(str(args.asset.resolve()),'',agent_radius=.30)
    try:
        rgb,depth=render(sim,camera,yaw)
        if args.original_goal_yaw_deg is not None:payload=jpeg_bytes(rgb)
        _,current_depth=render(sim,origin+[0,source['camera_height_m'],0],source['start_yaw'])
        points=goal_world_points(depth,camera,yaw)
        current=float(covis_frac(points,cam_to_world_hab(origin+[0,source['camera_height_m'],0],source['start_yaw']),current_depth,tol=DEPTH_TOLERANCE_M))
        route=shortest(sim.pathfinder,origin,position);assert route is not None
        angle=relative_direction_degrees(first_path_yaw(route[1],origin),source['start_yaw'])
        assert novel_supported_as_task(len(points),[],current),(len(points),current)
        assert distance_bin(route[0]) is not None and abs(angle)<=60,(route[0],angle)
        assert np.max(np.abs(route[1][:,1]-origin[1]))<=.20
    finally:sim.close()
    args.out.mkdir(parents=True,exist_ok=False)
    image=args.out/'goal_A.jpg';image.write_bytes(payload)
    direction=next(s for s in STRATA if direction_in_stratum(angle,s))
    straight=float(np.linalg.norm((position-origin)[[0,2]]))
    provenance=dict(formal_population=False,original_archive=str(args.archive.resolve()),
        goal_source=('Last saved GEM A RGB in original archive, fixed before the new execution.'
                     if args.original_goal_yaw_deg is None else
                     'Predefined rendered yaw at original A goal position; fixed before new execution.'),
        original_goal_sha256=query['goal_rgb_sha256'],
        selected_frame=frame if args.original_goal_yaw_deg is None else None,
        fixed_goal_position=position.tolist(),fixed_goal_yaw_rad=yaw,
        novel_verified=True,current_view_covis=current,initial_route_angle_deg=angle,
        geodesic_m=route[0],goal_surface_points=len(points))
    query.update(floor_position=position.tolist(),yaw_rad=yaw,geodesic_m=route[0],
        straight_distance_m=straight,route_ratio=route[0]/straight,
        initial_relative_route_angle_deg=angle,direction_stratum=direction,
        cell=f'{distance_bin(route[0])}/{direction}',goal_rgb=str(image.resolve()),
        goal_rgb_sha256=hashlib.sha256(payload).hexdigest(),current_view_covis=current,goal_surface_points=len(points),
        formal_population=False,view_variant_provenance=provenance)
    query.pop('proposal_index',None)
    (args.out/'provenance.json').write_text(json.dumps(provenance,indent=2))
    with tarfile.open(args.out/'source_bundle.tar.gz','w:gz') as bundle:
        for name,data in [('task/source.json',source),('task/A_query.json',query),
                          ('task/pair_summary.json',dict(sequence=pair['sequence'])),
                          ('task/visual_variant_provenance.json',provenance)]:
            blob=json.dumps(data,indent=2).encode();info=tarfile.TarInfo(name);info.size=len(blob)
            bundle.addfile(info,io.BytesIO(blob))
    print(json.dumps(provenance,indent=2))


if __name__=='__main__':main()

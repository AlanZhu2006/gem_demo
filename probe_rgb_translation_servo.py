"""Isolated RGB-only terminal translation experiment; never a paired rollout.

Starts from a recorded failed endpoint. Simulator pose is executor state only;
the estimator receives current/goal RGB and intrinsics, never depth/goal pose.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path[:0]=['/home/asus/Research/Nav-graph-blind',
              '/home/asus/Research/Nav-graph-blind/MemNavData']
from sim_rgb_arrival import RgbGoalArrivalVerifier


def estimate(rgb, goal, intrinsic):
    sift=cv2.SIFT_create(nfeatures=4000)
    k1,d1=sift.detectAndCompute(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),None)
    k2,d2=sift.detectAndCompute(cv2.cvtColor(goal,cv2.COLOR_RGB2GRAY),None)
    result=dict(usable=False)
    if d1 is None or d2 is None:return result
    matches=[a for pair in cv2.BFMatcher().knnMatch(d1,d2,k=2)
             if len(pair)==2 for a,b in [pair] if a.distance<.75*b.distance]
    result['matches']=len(matches)
    if len(matches)<40:return result
    p1=np.float32([k1[m.queryIdx].pt for m in matches])
    p2=np.float32([k2[m.trainIdx].pt for m in matches])
    E,mask=cv2.findEssentialMat(p1,p2,intrinsic,cv2.RANSAC,.999,1.5)
    if E is None:return result
    candidates=[]
    for i in range(0,E.shape[0],3):
        n,R,t,m=cv2.recoverPose(E[i:i+3],p1,p2,intrinsic,mask=mask.copy())
        candidates.append((n,R,t))
    n,R,t=max(candidates,key=lambda x:x[0])
    direction=(-R.T@t).reshape(3)
    yaw=math.atan2(R[0,2],R[2,2])
    tilt=math.degrees(math.acos(np.clip(R[1,1],-1,1)))
    horizontal=float(np.linalg.norm(direction[[0,2]]))
    ratio=n/len(matches)
    usable=(n>=30 and ratio>=.65 and tilt<=5 and abs(math.degrees(yaw))<=20
            and horizontal>.9 and abs(direction[1])<=.25)
    result.update(usable=bool(usable),inliers=n,inlier_ratio=ratio,
        yaw_correction_rad=yaw,off_axis_deg=tilt,
        goal_direction_current_camera=direction.tolist())
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--arm',default='cec')
    ap.add_argument('--stage',default='A')
    args=ap.parse_args()
    from MemNavData.generate_twoleg import make_sim,render
    root=args.run/args.arm/'evaluation';leg=root/f'leg_{args.stage}'
    previous=json.loads((leg/'result.json').read_text())
    source=json.loads((args.run/'source.json').read_text())
    query=json.loads((root/f'selected_{args.stage}.json').read_text())
    intrinsic=np.asarray(source['camera_intrinsic'],float)
    goal=cv2.cvtColor(cv2.imread(str(leg/'goal.jpg')),cv2.COLOR_BGR2RGB)
    options=json.loads((args.run/'protocol.json').read_text())['arrival_options']
    gate=RgbGoalArrivalVerifier(goal,**options)
    pos=np.array(previous['end_pos']);yaw=previous['end_psi']
    sim=make_sim(source['asset'],'',agent_radius=.30)
    args.out.mkdir(parents=True,exist_ok=False)
    rows=[]
    try:
        for step in range(101):
            rgb,_=render(sim,pos+[0,source['camera_height_m'],0],yaw)
            arrival=gate.evaluate(rgb).to_dict()
            est=estimate(rgb,goal,intrinsic)
            row=dict(step=step,position=pos.tolist(),yaw=yaw,arrival=arrival,estimate=est)
            rows.append(row)
            cv2.imwrite(str(args.out/f'{step:03d}.jpg'),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
            if arrival['confirmed'] or step==100:break
            if not est['usable']:break
            # Restrict the experiment to an already overlapping near-scale view.
            if not (.75<=arrival['image_scale']<=1.3
                    and min(arrival['target_coverage'],arrival['current_coverage'])>=.08):break
            turn=est['yaw_correction_rad']
            if abs(math.degrees(turn))>3:
                yaw+=float(np.clip(turn,-math.radians(3),math.radians(3)))
                row['action']=dict(yaw_delta_rad=yaw-row['yaw'])
            else:
                direction=np.asarray(est['goal_direction_current_camera'])[[0,2]]
                direction=.025*direction/np.linalg.norm(direction)
                right,forward=direction
                delta=np.array([math.cos(yaw)*right-math.sin(yaw)*forward,
                                0,-math.sin(yaw)*right-math.cos(yaw)*forward])
                candidate=np.asarray(sim.pathfinder.try_step(pos,pos+delta))
                row['action']=dict(right_m=float(right),forward_m=float(forward),
                    realized_planar_m=float(np.linalg.norm((candidate-pos)[[0,2]])))
                pos=candidate
    finally:sim.close()
    result=dict(not_a_navigation_or_paired_result=True,
        source_failed_run=str(args.run.resolve()),source_stage=args.stage,
        controller_inputs=['current RGB','goal RGB','camera intrinsics'],
        actual_endpoint_used_only_to_initialize_isolated_diagnostic=True,
        confirmed=rows[-1]['arrival']['confirmed'],steps=len(rows)-1,
        final_goal_distance_evaluator_only=float(np.linalg.norm((pos-np.asarray(query['floor_position']))[[0,2]])),
        rows=rows)
    (args.out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)


if __name__=='__main__':main()

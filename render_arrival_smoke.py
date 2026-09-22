"""Side-by-side evidence video for an executed RGB-arrival diagnostic."""
import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    args = ap.parse_args()
    root = args.run / 'evaluation/visual_leg'
    result = json.loads((root / 'result.json').read_text())
    manifest = json.loads((args.run / 'manifest.json').read_text())
    rows = json.loads((root / 'rgb_manifest.json').read_text())['frames']
    events = [json.loads(x) for x in (root / 'arrival.jsonl').read_text().splitlines()]
    poses = result['rollout_trace']
    assert len(rows) == len(events) == len(poses)
    goal = cv2.resize(cv2.imread(str(root / 'goal.jpg')), (720, 405))
    dt = result['rgb_arrival_clock']['step_period_s']
    fps, width, height = 30, 1440, 650
    output = args.run / 'arrival_comparison.mp4'
    writer = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
        '-pix_fmt', 'bgr24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-',
        '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags',
        '+faststart', str(output)], stdin=subprocess.PIPE)
    def text(frame, value, x, y, color=(235,235,235), scale=.75):
        cv2.putText(frame, value, (x,y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
    count = int(round(((len(rows)-1)*dt+3)*fps))
    cached, previous = None, None
    for fi in range(count):
        index = min(int(fi/fps/dt), len(rows)-1)
        if index != previous:
            frame = np.full((height, width, 3), 20, np.uint8)
            event, pose = events[index], poses[index]
            current = cv2.imread(rows[index]['path']); assert current is not None
            if index == len(rows)-1:
                current = cv2.imread(str(root / 'terminal.png'))
            frame[80:485,:720] = cv2.resize(current, (720,405))
            frame[80:485,720:] = goal
            text(frame, 'Live simulation RGB', 18, 55)
            text(frame, 'Frozen target image', 738, 55)
            latched = event['arrival_latched']
            color = (60,200,255) if latched else (200,200,200)
            status = 'ARRIVAL LATCHED - STOPPED' if latched else 'VISUAL ARRIVAL NOT YET CONFIRMED'
            if latched: cv2.rectangle(frame,(1,79),(719,486),color,4)
            text(frame, status, 18, 524, color, .95)
            g = manifest['goal']
            dist = np.linalg.norm(np.asarray([pose['x'],pose['z']])-np.asarray(g['floor_position'])[[0,2]])
            yaw = abs(np.degrees(np.arctan2(np.sin(pose['yaw']-g['yaw_rad']),np.cos(pose['yaw']-g['yaw_rad']))))
            text(frame, f'Action {event["step"]} | GT diagnostics: {dist:.2f} m, {yaw:.1f} deg', 18, 560)
            r = event['result']
            if r:
                text(frame, f'RGB gate: {r["reason"]} | matches {r["good_matches"]} | inliers {r["inliers"]}', 738, 560, color, .65)
            text(frame, 'Archived A endpoint + RGB history; newly executed suffix only.', 18, 602, scale=.7)
            text(frame, 'Playback: 10 simulator actions/s. GT is diagnostic only; RGB matching triggers the stop.',18,633,scale=.64)
            cached, previous = frame.tobytes(), index
        writer.stdin.write(cached)
    writer.stdin.close()
    if writer.wait() != 0: raise RuntimeError('ffmpeg failed')
    cap = cv2.VideoCapture(str(output))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == count
    cap.set(cv2.CAP_PROP_POS_FRAMES, count-1)
    ok, last = cap.read(); cap.release(); assert ok
    cv2.imwrite(str(args.run/'arrival_comparison_last.jpg'), last)
    (args.run/'arrival_video_verified.json').write_text(json.dumps(dict(
        video=str(output), frames=count, fps=fps, duration_s=count/fps,
        final_frame_decoded=True, source_observations=len(rows),
        visual_arrival=result['reached'], scope=manifest['scope']),indent=2))
    print(output)


if __name__ == '__main__':
    main()

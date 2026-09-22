"""Pull everything a demo frame needs out of one revisit bag.

Images go to disk as JPEG (full 848x480); the policy's planned output comes from
/navdp/debug/markers, which carries the selected trajectory, the candidate fan
with its Q values and the lookahead point, all in base_link.
"""
import sys, os, glob, json, math, numpy as np
from PIL import Image
from mcap_ros2.reader import read_ros2_messages

bag, out = sys.argv[1], sys.argv[2]
os.makedirs(out + '/rgb', exist_ok=True)
TOPICS = ['/camera/camera/color/image_raw', '/camera/camera/color/camera_info',
          '/navdp/debug/markers', '/navdp/go2/telemetry/sport_state',
          '/navdp/cmd_vel', '/navdp/rgb_arrival_status']

times, plans, tel, cmd, arr, K = [], [], [], [], [], None
nimg = 0
for mf in sorted(glob.glob(bag + '/*.mcap')):
    for m in read_ros2_messages(mf, topics=TOPICS):
        tp, t = m.channel.topic, m.log_time_ns / 1e9
        g = m.ros_msg
        if tp.endswith('color/image_raw'):
            buf = np.frombuffer(g.data, np.uint8).reshape(g.height, g.width, -1)
            rgb = buf[:, :, ::-1] if g.encoding == 'bgr8' else buf
            Image.fromarray(np.ascontiguousarray(rgb[:, :, :3])).save(
                f'{out}/rgb/{nimg:05d}.jpg', quality=92)
            times.append(t); nimg += 1
        elif tp.endswith('color/camera_info'):
            if K is None: K = np.array(g.k, float).reshape(3, 3)
        elif tp.endswith('debug/markers'):
            sel, cand, qs, look, status = None, [], [], None, ''
            for mk in g.markers:
                if mk.ns == 'selected':
                    sel = np.array([[p.x, p.y, p.z] for p in mk.points], float)
                elif mk.ns == 'candidates':
                    cand.append(np.array([[p.x, p.y, p.z] for p in mk.points], float))
                elif mk.ns == 'candidate_scores':
                    try: qs.append(float(mk.text.split()[-1]))
                    except Exception: qs.append(float('nan'))
                elif mk.ns == 'lookahead':
                    look = [mk.pose.position.x, mk.pose.position.y]
                elif mk.ns == 'status':
                    status = mk.text
            plans.append(dict(t=t, sel=sel, cand=cand, q=qs, look=look, status=status))
        elif tp.endswith('telemetry/sport_state'):
            try: d = json.loads(g.data)
            except Exception: continue
            sf = d.get('sdk_fields') or {}
            p, r = sf.get('position'), (sf.get('imu_state') or {}).get('rpy')
            if not p or not r: continue
            tt = d.get('received_ros_ns')
            tel.append((tt / 1e9 if tt else t, p[0], p[1], p[2], r[0], r[1], r[2]))
        elif tp.endswith('cmd_vel'):
            cmd.append((t, g.linear.x, g.linear.y, g.angular.z))
        elif tp.endswith('rgb_arrival_status'):
            try: arr.append((t, json.loads(g.data)))
            except Exception: pass

np.save(out + '/times.npy', np.array(times, float))
np.save(out + '/tel.npy', np.array(tel, float))
np.save(out + '/cmd.npy', np.array(cmd, float))
if K is not None: np.save(out + '/K.npy', K)
np.save(out + '/plans.npy', np.array(plans, dtype=object), allow_pickle=True)
with open(out + '/arrival.json', 'w') as f: json.dump(arr, f)
A = np.array(cmd, float)
mov = (np.abs(A[:, 1]) > 0.02) | (np.abs(A[:, 3]) > 0.02)
i = int(np.argmax(mov)); j = len(mov) - 1 - int(np.argmax(mov[::-1]))
json.dump(dict(t0=A[i, 0], t1=A[j, 0]), open(out + '/win.json', 'w'))
print(f"{os.path.basename(out)}: rgb {nimg} ({times[-1]-times[0]:.1f}s), plans {len(plans)}, "
      f"tel {len(tel)}, cmd window {A[j,0]-A[i,0]:.1f}s, arrival msgs {len(arr)}")

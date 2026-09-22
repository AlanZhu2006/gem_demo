"""360° orbit stills of MP3D houses: flat dollhouse view, world-up, pale backdrop."""
from pathlib import Path
import numpy as np
from PIL import Image
import magnum as mn
import quaternion as nq
import habitat_sim

MP3D=Path('/home/asus/Research/datasets/mp3d_official_20260814/extracted/mp3d')
OUT=Path('outputs/icra_submission/navmesh_gallery');OUT.mkdir(parents=True,exist_ok=True)
SCENES=['VFuaQ6m2Qom','1LXtFkjw3qL','759xd9YjKW5','1pXnuDYAj8r','EDJbREhghzL','PX4nDJXEHrG']
W,H=720,480
N_YAW=90
ELEV=np.radians(44)
HFOV=44

def look_at_quat(eye, target, up=np.array([0.,1.,0.])):
    f=np.asarray(target,float)-np.asarray(eye,float); f/=np.linalg.norm(f)
    z=-f
    x=np.cross(up,z); x/=np.linalg.norm(x)
    y=np.cross(z,x)
    return nq.from_rotation_matrix(np.stack([x,y,z],1))

def configure(scene_id):
    backend=habitat_sim.SimulatorConfiguration()
    backend.scene_id=str(MP3D/scene_id/f'{scene_id}.glb')
    backend.enable_physics=False
    backend.gpu_device_id=0
    rgb=habitat_sim.CameraSensorSpec()
    rgb.uuid='color';rgb.sensor_type=habitat_sim.SensorType.COLOR
    rgb.sensor_subtype=habitat_sim.SensorSubType.PINHOLE
    rgb.resolution=[H,W];rgb.hfov=HFOV
    rgb.position=mn.Vector3(0.0,0.0,0.0)
    rgb.clear_color=mn.Color4(0.925,0.945,0.96,1.0)
    rgb.near=0.05;rgb.far=300.0
    agent=habitat_sim.agent.AgentConfiguration()
    agent.sensor_specifications=[rgb]
    return habitat_sim.Configuration(backend,[agent])

def orbit_scene(scene_id):
    dest=OUT/scene_id;dest.mkdir(parents=True,exist_ok=True)
    sim=habitat_sim.Simulator(configure(scene_id))
    try:
        bb=sim.get_active_scene_graph().get_root_node().cumulative_bb
        lo=np.array(bb.min);hi=np.array(bb.max);center=(lo+hi)/2.0;ext=hi-lo
        dist=float(np.linalg.norm(ext))*1.02
        for i in range(N_YAW):
            yaw=2*np.pi*i/N_YAW
            eye=center+np.array([dist*np.cos(ELEV)*np.sin(yaw), dist*np.sin(ELEV), -dist*np.cos(ELEV)*np.cos(yaw)])
            st=sim.get_agent(0).get_state();st.position=eye
            st.rotation=look_at_quat(eye,center)
            sim.get_agent(0).set_state(st,infer_sensor_states=True)
            rgb=sim.get_sensor_observations()['color'][...,:3]
            Image.fromarray(rgb).save(dest/f'{i:03d}.jpg',quality=90)
        Image.open(dest/'000.jpg').save(OUT/f'{scene_id}.jpg',quality=92)
        print('orbit',scene_id,N_YAW,'dist',round(dist,2),flush=True)
    finally:
        sim.close()

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--scene',default='');ap.add_argument('--all',action='store_true')
    args=ap.parse_args()
    names=SCENES if args.all else [args.scene or SCENES[0]]
    for name in names:orbit_scene(name)

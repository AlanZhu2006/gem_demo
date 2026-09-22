"""New continuous paired three-leg demo: independent state, common online goals,
real-robot RGB arrival, and explicit visual-demo (not Table II) provenance.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path('/home/asus/Research/Nav-graph-blind')
HERE = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))


def visual_chain(*, goal_provider, after_leg):
    import numpy as np
    import eval_2leg_habitat as base
    from MemNavData.table2_continuous_local import materialize_own_prefix, NoConstructibleGoal
    from MemNavData.table2_continuous_chain import run_chain
    from MemNavData.final14_spl_replay import measurement
    from MemNavData.table2_mixed_local import load, dump
    from run_sim_visual_leg import run_visual_policy_leg
    manifest = load(os.environ['TABLE2_CONTINUOUS_MANIFEST'])
    if base.args.contract_dry_run:
        print('VISUAL_PAIR_PREFLIGHT: continuous own state; shared online sequence-specific goals; RGB stop')
        return
    source = manifest['source']; out = Path(base.args.out)
    planning_seeds=manifest.get('planning_seeds',[source['seed']]*3)
    base.CAM_H = source['camera_height_m']
    sim = base.make_sim(source['asset'], '', agent_radius=.30)
    traces, selected, measured = [], [], []
    try:
        base.srv_reset(camera_height=base.CAM_H, seed=source['seed'],
            episode_len=3*(base.args.max_steps+1),
            camera_intrinsic=np.asarray(source['camera_intrinsic']))

        def execute(index, stage, position, yaw):
            prefix = None if index == 0 else materialize_own_prefix(
                base, sim, source, traces, out/f'history_before_{stage}')
            original = load(manifest['a_query']) if index == 0 else None
            query = goal_provider(index, stage, prefix, original, position, yaw)
            np.testing.assert_allclose(query['start_position'], position, atol=1e-8, rtol=0)
            assert abs(query['start_yaw']-yaw) < 1e-8
            goal = Path(query['goal_rgb']).read_bytes()
            assert hashlib.sha256(goal).hexdigest() == query['goal_rgb_sha256']
            target = np.asarray(query['floor_position'])
            ok, geo, _ = base.geodesic(sim.pathfinder, position, target)
            assert ok and abs(geo-query['geodesic_m']) < .05
            # A visual stop may interrupt an old target's pending turn. Drop
            # that command at the explicit goal boundary, never memory/pose.
            adapter = getattr(base, '_front_goal_adapter', None)
            if index and adapter is not None:
                adapter.events.append(dict(event='visual_goal_switch', old_active=adapter.active))
                adapter.active, adapter.target_yaw = False, None
            selected.append(query); dump(out/f'selected_{stage}.json', query)
            print('START_VISUAL', stage, 'geodesic', geo, flush=True)
            leg = run_visual_policy_leg(base, sim, sim.pathfinder, position, yaw,
                goal, target[[0,2]], geo, out=out/f'leg_{stage}', step_period_s=.1,
                visual_centering=manifest.get('visual_centering',False),
                arrival_options=manifest.get('arrival_options',{}),
                terminal_mode='off', goal_yaw=query['yaw_rad'],
                camera_intrinsic=np.asarray(source['camera_intrinsic']),
                policy_backend='navdp' if manifest['arm']=='native' else 'navdp_auto',
                success_dist=1., episode_seed=planning_seeds[index], leg_index=index)
            return leg

        def observe(index, stage, leg, continuity):
            query = selected[index]
            # This is a geometry-construction carrier, not an action-count
            # benchmark trace. Include the actual terminal observation.
            carrier = dict(leg, steps=len(leg['rollout_trace']))
            trace = base.leg1_trace_payload(episode=source['episode'], episode_seed=planning_seeds[index],
                goal_jpg=Path(query['goal_rgb']).read_bytes(), goal_source_episode=source['episode'],
                source_scene=source['scene'], leg=carrier)
            trace.update(executed_actions=leg['steps'],
                trace_semantics='observations including visual terminal frame; geometry construction only',
                success_definition='rgb_visual_arrival', formal_population=False)
            traces.append(trace)
            row = measurement(leg, np.asarray(query['floor_position'])[[0,2]], query['geodesic_m'])
            row.update(success_definition='rgb_visual_arrival', formal_population=False,
                       rgb_arrival_latched=leg['rgb_arrival_latched'])
            dump(out/f'leg_{stage}/actual_trace.json', trace)
            dump(out/f'leg_{stage}/measurement.json', row)
            dump(out/f'leg_{stage}/continuity.json', continuity)
            measured.append(dict(stage=stage, measurement=row, continuity=continuity))
            print('DONE_VISUAL', stage, leg['reached'], leg['termination_reason'], leg['steps'], flush=True)
            after_leg(index, stage, continuity, row)

        try:
            result = run_chain(source['start_position'], source['start_yaw'], 'ABC', execute, observe)
            result['status'] = 'lifecycle_finished'
        except NoConstructibleGoal as exc:
            result = dict(status='task_construction_blocked', reason=str(exc))
        result.update(formal_population=False, success_definition='rgb_visual_arrival', measurements=measured)
        dump(out/'chain_summary.json', result)
    finally:
        sim.close()


def worker():
    sys.argv.remove('worker')
    import MemNavData.table2_continuous_local as lifecycle
    from MemNavData.table2_continuous_paired import worker as paired_worker
    lifecycle.evaluate_chain = visual_chain
    paired_worker()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--rgb-source', type=Path, required=True)
    ap.add_argument('--asset', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=19880)
    ap.add_argument('--seed', type=int, help='Explicit new-demo seed, preserved separately from archive seed.')
    ap.add_argument('--visual-centering',action='store_true',help='Same RGB centering controller for both arms; new demo profile.')
    ap.add_argument('--park-idle',action='store_true',help='Park idle private servers on CPU, preserving all tensor state.')
    ap.add_argument('--novel-max-route-angle',type=float,default=60,
                    help='Evaluator-only novel proposal angle; >60 is an explicitly different demo task profile.')
    ap.add_argument('--planning-seeds',type=int,nargs=3,metavar=('A','B','C'),
                    help='Fixed per-leg diffusion seed schedule, identical for both methods; no memory reset.')
    ap.add_argument('--arrival-profile',choices=['realworld','aligned','aligned-v2'],default='realworld',
                    help='aligned tightens RGB scale/centering/coverage; no GT stop condition.')
    ap.add_argument('--novel-views-per-band',type=int,default=12)
    ap.add_argument('--novel-min-goal-keypoints',type=int,default=0)
    ap.add_argument('--novel-max-black-fraction',type=float,default=1)
    ap.add_argument('--screen-gem',action='store_true',
                    help='GEM-only continuous candidate screening; never label as a paired result.')
    ap.add_argument('--preferred-b-query',type=Path,
                    help='Predefined B reference, accepted only if actual-history role/geometry checks pass.')
    args = ap.parse_args()
    arrival_options=({} if args.arrival_profile=='realworld' else dict(
        min_image_scale=.90,max_image_scale=1.12,max_center_offset_norm=.10,
        min_coverage=.20,min_inlier_ratio=.65))
    if args.arrival_profile=='aligned-v2':
        arrival_options.update(min_image_scale=.85,min_inlier_ratio=.60)
    proposal_options=dict(novel_max_route_angle_deg=args.novel_max_route_angle,
        novel_views_per_band=args.novel_views_per_band,
        novel_min_goal_keypoints=args.novel_min_goal_keypoints,
        novel_max_black_fraction=args.novel_max_black_fraction)
    preferred_b=json.loads(args.preferred_b_query.read_text()) if args.preferred_b_query else None
    if not 0<args.novel_max_route_angle<=180:ap.error('novel proposal angle must be in (0,180]')
    if args.park_idle:
        os.environ['REPAIRED_MEMORY_CONTROL_LAUNCHER']=str(HERE.with_name('private_residency_server.py'))
    from MemNavData.table2_mixed_local import load, dump, sha
    from MemNavData.table2_continuous_paired import publish, await_record, trim_servers
    from MemNavData.table2_common_goals import choose_common
    from MemNavData.run_repaired_fullmono_local import (private_servers, evaluator_command,
        execution_environment, run_child, HAB_PY, hab_env)
    with tarfile.open(args.archive) as archive:
        source = json.load(archive.extractfile('task/source.json'))
        query = json.load(archive.extractfile('task/A_query.json'))
        sequence = json.load(archive.extractfile('task/pair_summary.json'))['sequence']
        variant=(json.load(archive.extractfile('task/visual_variant_provenance.json'))
                 if 'task/visual_variant_provenance.json' in archive.getnames() else None)
    assert sequence in ('NNN','NNR','NRN','NRR'), sequence
    assert sha(args.asset) == source['asset_sha256']
    archived_seed=source['seed']
    if args.seed is not None:
        source['seed']=args.seed;query['seed']=args.seed
    planning_seeds=args.planning_seeds or [source['seed']]*3
    source['asset'] = str(args.asset.resolve())
    query['asset'] = source['asset']; query['goal_rgb'] = str((args.rgb_source/'goal_A.jpg').resolve())
    assert sha(query['goal_rgb']) == query['goal_rgb_sha256']
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False); (out/'logs').mkdir()
    dump(out/'source.json', source); dump(out/'A_query.json', query)
    dump(out/'protocol.json', dict(formal_population=False, sequence=sequence,
        stop_authority='realworld_rgb_arrival', source_archive=str(args.archive.resolve()),
        archived_seed=archived_seed, execution_seed=source['seed'],
        planning_seeds=planning_seeds,
        goal_view_variant=variant,
        arrival_profile=args.arrival_profile,arrival_options=arrival_options,
        proposal_options=proposal_options,
        history_depth_source='full_precision_rerender_at_actual_recorded_poses',
        screening_only=args.screen_gem,
        predefined_B=preferred_b,
        shared_visual_centering=args.visual_centering,
        novel_max_route_angle_deg=args.novel_max_route_angle,
        idle_server_cpu_parking=args.park_idle,
        common_online_goals=True, own_continuous_state=True, no_prefix_replay=True,
        max_actions_per_leg=600))
    arms = ('cec',) if args.screen_gem else ('cec', 'native')
    ports = {}; commands = {}; environments = {}
    for i, arm in enumerate(arms):
        directory = out/arm; (directory/'logs').mkdir(parents=True)
        ports[arm] = (args.port+2*i,args.port+2*i+1)
        manifest = directory/'manifest.json'
        dump(manifest, dict(source=source, arm=arm, common_root=str(out),
            sequence=sequence, a_query=str(out/'A_query.json'), formal_population=False,
            visual_centering=args.visual_centering,
            planning_seeds=planning_seeds,
            arrival_options=arrival_options,
            common_online_goals=True, a_query_sha256=sha(out/'A_query.json')))
        command = evaluator_command(source,directory/'evaluation',*ports[arm],arm=arm,role='novel',benchmark=out)
        command[2:4] = [str(HERE),'worker']; command[command.index('--leg1_mode')+1] = 'policy'
        env = dict(execution_environment(), TABLE2_CONTINUOUS_MANIFEST=str(manifest),
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        run_child(command+['--contract_dry_run'],directory/'logs/preflight.log',environment=env)
        commands[arm],environments[arm] = command,env
    children,handles,stages = {},[],[]
    def residency(arm,action,stage):
        if not args.park_idle:return
        import requests
        receipts={}
        for port in ports[arm]:
            response=requests.post(f'http://127.0.0.1:{port}/private_{action}',timeout=300)
            response.raise_for_status();receipts[str(port)]=response.json()
        dump(out/f'residency_{stage}_{arm}_{action}.json',receipts)
    try:
        with ExitStack() as stack:
            stacks={}; all_ports=[]; live=list(arms)
            for arm in arms:
                stacks[arm]=stack.enter_context(ExitStack())
                stacks[arm].enter_context(private_servers(out/arm,*ports[arm],memory_control=True))
                all_ports.extend(ports[arm]); trim_servers(all_ports,out,'loaded_'+arm)
            for arm in arms:
                handle=(out/arm/'logs/evaluation.log').open('x');handles.append(handle)
                children[arm]=subprocess.Popen(commands[arm],cwd=ROOT,env=environments[arm],stdout=handle,stderr=subprocess.STDOUT)
            for index,stage in enumerate('ABC'):
                if not live: break
                requests={a:await_record(out/f'request_{stage}_{a}.json',out,[children[a]]) for a in live}
                trim_servers(all_ports,out,'before_'+stage)
                for arm in live:residency(arm,'park',stage)
                if stage=='A': queries={a:str(out/'A_query.json') for a in live}
                else:
                    role='novel' if sequence[index]=='N' else 'revisit'
                    request=out/f'construct_{stage}.json'
                    dump(request,dict(source=source,stage=stage,role=role,**proposal_options,
                                      preferred_goal=preferred_b if stage=='B' else None,
                                      prefixes={a:requests[a]['prefix'] for a in live}))
                    constructor=[HAB_PY,'-u',str(HERE.with_name('construct_visual_goals.py'))]
                    run_child(constructor+['--request',str(request),
                               '--out',str(out/f'common_{stage}')],out/'logs'/f'construct_{stage}.log',environment=hab_env())
                    menu=load(out/f'common_{stage}/construction.json')
                    chosen=choose_common(menu,f'continuous_common/{stage}/{role}',
                        {'6_to_9':0,'4_to_6':1,'2_to_4':2})
                    queries={} if chosen is None else chosen['queries']
                if not queries:
                    for arm in live: publish(out/f'permit_{stage}_{arm}.json',dict(status='construction_empty'))
                    stages.append(dict(stage=stage,status='construction_empty'));break
                digests={load(q)['goal_rgb_sha256'] for q in queries.values()};assert len(digests)==1
                entry=dict(stage=stage,live_arms=list(live),goal_sha256=digests.pop(),queries=queries,outcomes={})
                for arm in list(live):
                    residency(arm,'resume',stage)
                    publish(out/f'permit_{stage}_{arm}.json',dict(status='run',query=queries[arm],query_sha256=sha(queries[arm])))
                    print('RUN',stage,arm,flush=True)
                    done=await_record(out/f'done_{stage}_{arm}.json',out,[children[arm]])
                    entry['outcomes'][arm]=done['measurement']
                    print('DONE',stage,arm,done['measurement']['reached'],flush=True)
                    if not done['measurement']['reached']:
                        assert children[arm].wait(timeout=120)==0
                        stacks[arm].close();all_ports=[p for p in all_ports if p not in ports[arm]]
                    else:residency(arm,'park','after_'+stage)
                    trim_servers(all_ports,out,'after_'+stage+'_'+arm)
                stages.append(entry);dump(out/f'stage_{stage}.json',entry)
                live=[a for a in live if entry['outcomes'][a]['reached']]
            for process in children.values(): assert process.wait(timeout=120)==0
            dump(out/'pair_summary.json',dict(formal_population=False,screening_only=args.screen_gem,
                sequence=sequence,source=source,
                stages=stages,arms={a:load(out/a/'evaluation/chain_summary.json') for a in arms}))
    except BaseException as exc:
        dump(out/'abort.json',dict(error=repr(exc)))
        raise
    finally:
        for process in children.values():
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired: process.kill();process.wait()
        for handle in handles: handle.close()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker': worker()
    else: main()

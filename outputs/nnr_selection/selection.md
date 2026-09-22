# Final selection: formal 003 source, new NNR visual demo

Completed 2026-09-20. [Final video](../sim_visual_arrival_nnr_joint.mp4),
[verification](../sim_visual_arrival_nnr_joint.verified.json),
[main progress document](../../SIM_VIDEO_PROGRESS.md).

Selected scene: **VFuaQ6m2Qom**, original formal task **003**, original seed
**2026091198** and original A image/start. This is a fresh visual-demo execution
with new online B/C targets, shared RGB centering and `aligned-v2` thresholds,
not the archived Table II result. Its original archive GEM distance-based
path was 11.097 m; the new actual GEM visual-arrival path is **18.663 m**.

| Leg | Role | GEM actions | GEM path (m) | Baseline outcome |
| --- | --- | ---: | ---: | --- |
| A | Novel | 67 | 2.339 | Same RGB arrival |
| B | Novel | 175 | 6.274 | Same RGB arrival |
| C | Revisit | 446 | 10.050 | Stuck at 568 actions, 14.241 m traveled |

Starting geodesics total 16.719 m; C includes a detour. Actual GEM endpoint
position errors are 1.267 / 0.883 / 0.348 m and heading errors 15.54 / 7.72 /
2.26 degrees. Rings mark actual visual-latch poses, not surveyed goal positions.
[Target/current views](formal003_ABC_screen_arrivals.jpg) are retained openly.

The output is 56.567 seconds, 1697 frames, 1080p/30 FPS. Baseline's remaining
121 observations after GEM ends occupy 3 seconds at a labeled 2.689× speed;
there is a final 3-second hold. GEM/Baseline ribbon widths are 0.22 / 0.28 m.
Actual failure conditions were not shortened or invented.

## Why the earlier long candidates were rejected

- 138: appealing archived 18.50 m route, but fresh A navigation failed under
  several seeds and a separately predefined goal-view variant.
- 253: A could pass visual arrival, but B navigation failed. Raw-depth history
  also rejected the original long B reference as previously seen (0.3645 max
  covisibility, versus the incorrect zero from clipped depth PNGs). Valid B
  alternatives had poor mesh quality. No invalid Novel goal was forced through.
- 241: new A navigation failed. 385, in the chosen indoor scene but with a
  stairs-facing A target, failed A across original/changed seed and yaw variant.
- 381 / 048 / 397 / 359: prominent missing or black scan geometry in sampled views.
  187's long archive path mainly came from a 17 m A detour with only 3.12 m geodesic.

[Full trial inventory](visual_trial_inventory.json) preserves complete,
interrupted and resource-failed runs separately. [Chronological notes](selection_history.md)
are historical and contain superseded candidate preferences; use this file for
the final selection. The independent RGB translation experiment was NOT enabled
in the successful screen or full pair.

## Final execution and audit trail

`screen_formal003_aligned2` first passed GEM A/B/C. Full paired run
`visual_pair_formal003_aligned2_retry` then started both methods from scratch;
all 691 GEM RGB observations and poses reproduced the screen exactly. Baseline
has 812 actual observations. Each arm had one continuous memory lifecycle,
actual endpoint inheritance, no prefix replay and no GT stop/control.

The first full-pair attempt aborted because concurrent speculative reconstruction
caused CUDA OOM in our own server. It is recorded as a resource failure, excluded
from video, and was followed by a fresh sequential retry. No unrelated GPU job
was stopped. Do not run policy evaluation and official reconstruction together.

The local task constructor re-renders full-precision history depth to avoid the
6.5535 m PNG saturation error. N/R thresholds and 60-degree Novel direction bound
are unchanged. B max-history/current visibility are zero. C max-history support
is 0.8197, current visibility zero, with a 0.22 m / 12-degree earlier-view
perturbation. Original benchmark modules and source archives are unchanged.
Each local construction saves the executed function, original/modified hashes
and a profile receipt. `raw_depth_novel_guard` verifies the formerly false-N
candidate is now rejected.

Two independent official `demo.py` forward reconstructions use identical
FlashInfer / long checkpoint / keyframe interval 3 / max-frame count 1024 settings.
GEM screen reconstruction reuse is backed by exact full-pair input checks.
245 common RGBs produce 238 exactly identical pose/depth predictions. No
cross-arm registration or trajectory warp is used. One display similarity gives
paired fit RMSE 0.175 m / P95 0.323 m. All 1697 video frames and arrival/ending
images passed checks. See `../nnr003_forward_joint/prefix_parity.json` and
`../nnr003_joint_frame.json`.

## Reproduction pipeline

Commands below describe the executed configuration. Use fresh output directories
for reruns; tools intentionally refuse to overwrite navigation/reconstruction runs.
Activate the environments and FlashInfer variables in `lingbot_deployment.md`.
Execute GPU stages sequentially. `run_visual_pair.py` and reconstruction tools
use the lingbot-map Python; the runner starts its own Habitat/policy subprocesses.

```bash
python run_visual_pair.py \
  --archive outputs/table2_inventory/formal_003.tar.gz \
  --rgb-source outputs/table2_formal003_rgb \
  --asset /home/asus/Research/datasets/mp3d/VFuaQ6m2Qom.glb \
  --out outputs/visual_pair_formal003_aligned2_retry \
  --visual-centering --park-idle --arrival-profile aligned-v2 \
  --novel-views-per-band 96 --novel-min-goal-keypoints 350 \
  --novel-max-black-fraction .2
python prepare_visual_pair.py \
  --run outputs/visual_pair_formal003_aligned2_retry --out outputs/nnr003_visual_rgb
python run_lingbot_manifest.py \
  --manifest outputs/nnr003_visual_rgb/manifest_forward_gem.json \
  --out outputs/nnr003_forward_gem --keyframe-interval 3 --max-frame-num 1024
python run_lingbot_manifest.py \
  --manifest outputs/nnr003_visual_rgb/manifest_forward_base.json \
  --out outputs/nnr003_forward_base --keyframe-interval 3 --max-frame-num 1024
python merge_table2_forward.py --source outputs/nnr003_visual_rgb \
  --gem outputs/nnr003_forward_gem --base outputs/nnr003_forward_base \
  --out outputs/nnr003_forward_joint
python fit_table2_joint.py --input outputs/nnr003_forward_joint \
  --out outputs/nnr003_joint_frame.json
python render_table2_joint.py --source outputs/nnr003_visual_rgb \
  --frame outputs/nnr003_joint_frame.json \
  --out outputs/sim_visual_arrival_nnr_joint.mp4 \
  --baseline-tail-seconds 3 --gem-track-width .22 --baseline-track-width .28
python verify_table2_video.py --video outputs/sim_visual_arrival_nnr_joint.mp4 \
  --require-gem-three-visual --require-sequence NNR
```

For the existing artifact the GEM reconstruction's recorded input manifest is
`screen_formal003_aligned2/manifest_forward_gem.json`, whose RGB/pose/timestamp
identity with the full-pair GEM manifest is explicitly verified. Reproducing from
the packaged full-pair manifest above uses the same images and inference settings.

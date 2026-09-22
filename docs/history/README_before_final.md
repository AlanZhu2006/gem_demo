# Historical record — superseded by FINAL_DELIVERY.md

Old exported media links in this record were intentionally removed during final asset cleanup. Source data and experiments remain.

# GEM incremental reconstruction demo

This directory contains the original GEM/Baseline video composition scripts and
a new RGB-only LingBot incremental reconstruction pipeline.

The current simulation video matching `gem_indoor_joint` is the
[complete NNR dual-trajectory video](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.mp4):
**38.567 seconds, 1080p/30 FPS**, scene `VFuaQ6m2Qom`. GEM travels **18.663 m**
and completes three RGB arrivals. Baseline completes A/B and becomes stuck in C;
its remaining tail is explicitly accelerated 2.017× into 3 seconds. Both FPVs,
incremental LingBot cloud and actual RGB-latch rings are retained.

The 2026-09-21 display fix restores floor points incorrectly removed by the
old -0.08 m lower height cut; simulation now uses -0.30 m. See the
[fixed-view comparison](outputs/cloud_display_audit/height_ablation.jpg).

The current minimal presentation keeps the raw floor-fixed cloud, white background,
two FPVs, three small goal images and actual candidate/selected NavDP paths. Titles,
legends and card containers are removed. Goal arrival borders are independently
blue for GEM and coral for Baseline; jointly reached goals show both thin frames. Motion is 2× with no
added arrival pause and a 1-second final hold. Selected local paths remain grounded
and obstacle-occluded (93 GEM / 107 Baseline source plans).
The [previous raw layout](outputs/sim_visual_arrival_nnr_floorfixed.mp4) and
[optional TSDF experiment](outputs/sim_visual_arrival_nnr_fused.mp4) remain intact.

All 1157 frames decoded and passed clock/visibility checks. Both actual official
`demo.py` forward streams have exactly matching pose/depth outputs over their
shared prefix; paired geometry fit RMSE is 0.175 m. This is a new visual-demo
configuration with shared centering and aligned-v2 RGB thresholds, not an
unchanged formal Table II result or exact GT-pose arrival. See
[progress, provenance and remaining errors](SIM_VIDEO_PROGRESS.md),
[arrival checkpoints](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.arrivals.jpg), and
[verification](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.verified.json).
The [previous NRR video](outputs/sim_visual_arrival_joint.mp4) and
[original archive visualization](outputs/sim_table2_nrr_joint.mp4) remain intact.

**Earlier real-world reconstruction handoff (2026-09-20):** Read
[VIDEO_PROGRESS_HANDOFF.md](VIDEO_PROGRESS_HANDOFF.md) for the Claude handoff.
The full official `demo.py` FlashInfer run and diagnostics are complete;
its incremental video still needs rendering. It improves the body-odometry
diagnostic RMSE to 0.187 m (not a GT accuracy score). Earlier wrapper results
below are retained for comparison.

## Current runnable result

- **Use `outputs/gem_lingbot_translation_pose_verified.mp4` for the corrected
  translation segment.** The earlier videos below use the wrong pose direction
  because our integration misinterpreted the exported matrix. The original
  interactive `demo.py` viewer applies another inverse and agrees with the
  corrected projection. See `DEPLOYMENT_AUDIT.md`.
- `outputs/gem_lingbot_pose_verified.mp4` preserves the full run after the same
  convention correction; its remaining trajectory failure is not solved.
- `outputs/gem_lingbot_incremental.mp4`: onboard RGB plus an oblique 3D cloud
  that grows according to original ROS log timestamps; 2x playback, 15 FPS.
- `outputs/gem_lingbot_incremental.jpg`: four playback checkpoints.
- `outputs/gem_lingbot_incremental.audit.json`: each video frame's source time,
  latest included geometry time, chunk count and point count.
- `outputs/cec_090850_lingbot/`: raw per-frame predictions and provenance.
- `outputs/gem_lingbot_translation_probe.mp4`: a fresh 320-frame session
  starting 10 seconds into the same input, with the initial rotation excluded.
- Each reconstruction directory also has `cloud_raw.ply` with frame provenance,
  `trajectory_diagnostic.json` and a trajectory comparison PNG.

The source is `episode_20260919T090850_042322Z`, selected because it is the
episode referenced by the existing indoor renderer's goal image. Its association
with the missing historical `n_cec1` intermediate files has not been established.
962 RGB frames cover 62.30 seconds around the motion-command interval.

Only RGB enters LingBot. Recorded depth, body pose, phone footage and the goal
image do not enter reconstruction. The first 8 frames prime the model; frames
0–6 produce no displayed geometry. Each subsequent output contains `depth`,
`conf`, `K`, OpenCV `c2w`, correctly preprocessed RGB, local points and colors.
Confidence filtering keeps the top 35%, with a 4-pixel sampling stride.

Coordinates remain **model units, not metres**. A plane fitted to the first
output frame is attempted for one rigid display rotation/translation; both
current runs failed this fit and use the camera-up fallback. Raw predictions
are unchanged. No per-frame floor flattening, loop closure or pose correction
is applied. Full-sequence bounds are used for fixed camera framing only. The
temporal audit verifies that displayed geometry never comes from a later frame.
Screen-space occlusion means visible pixels need not increase monotonically;
the accumulated sample count does.

## Reproduce

Use `/home/asus/miniconda3/envs/lingbot-map/bin/python` for all commands below.
The sibling `AnchorScale` backbone and `go2_mono_nav/perception_server` session
are reused. Their locations can be overridden on `reconstruct`.

```bash
python lingbot_incremental.py extract \
  --bag /path/to/episode/rosbag/survey --out outputs/my_rgb
python lingbot_incremental.py reconstruct \
  --input outputs/my_rgb --out outputs/my_lingbot --pose-convention raw-c2w
python validate_lingbot.py --input outputs/my_lingbot
python inspect_lingbot.py --input outputs/my_lingbot
python render_lingbot.py \
  --input outputs/my_lingbot --out outputs/my_incremental.mp4
python -m unittest test_grid_timing -v
```

Choose fresh output paths. Reconstruction uses `lingbot-map-long.pt`, SDPA,
518-pixel crop preprocessing, 8 scale frames, a 64-frame sliding cache and
every-frame updates. The maximum positional index is set beyond the full
input length to avoid an implicit session reset. Saved files permit rerendering
without another GPU inference pass. `validate_lingbot.py` checks saved outputs
against `LingBotBackbone.reconstruct` on a short prefix with identical settings;
that checks implementation parity, not physical map accuracy.

The actual interactive `demo.py` entry point was also run on the 320-frame
translation window using `audit_demo_entrypoint.py`; its original viewer's
sampled projection agrees with the corrected formula to 1.22e-7 model units.
This does not establish full-run parity: the 962-frame demo default chooses
keyframe interval 4, while the current incremental wrapper uses 1. The demo
also casts aggregator weights to bf16. See the audit for measured differences.

## Original 2.5D scripts

`grid_prog.py` consumes RGB-D plus Go2 telemetry and writes floor/obstacle
time buckets. `render_scene5.py` combines the GEM and Baseline buckets with
third-person panels. This differs from the new LingBot reconstruction.

Two defects were fixed:

1. Buckets now carry absolute ROS seconds, timestamped at their **last**
   observation. Previously relative seconds were compared to absolute ROS
   time and the entire map could appear immediately. The renderer rejects old
   bucket files and asks for regeneration.
2. `mount2.npy` roll now follows `calib_mount3.py`'s positive-roll convention;
   legacy `mount.npy` keeps its original convention.

Historical `demo_n_*`, `rgbd_n_*`, `n_grid.npz`, telemetry NPZs and phone-frame
indexes are missing from this directory, so the old composite cannot currently
be regenerated directly. Existing MP4 files are retained. Original MCAP bags
are available in the September 19 experiment archive.

## Remaining integration work

**The following first-pass attribution is superseded by the pose-direction
audit.** The initial 10 seconds contain only about 0.20 m
of body-odometry travel but about 155 degrees of net yaw. The full session has
visible repeated surfaces and a 2.32 m diagnostic position discrepancy after
a best-fit Sim(3) against body odometry. This is not a GT accuracy score.

The controlled restart uses `--start-seconds 10 --max-frames 320`. On **identical
313 output timestamps**, independently fitting one Sim(3) gives 0.450 m RMSE
for the original session and 0.249 m for the fresh session. That supports an
initialization/context problem, but does not establish global map quality:
the first-pass fresh-session cloud still had visible spread, and neither startup frame
yielded a reliable floor for the display transform (camera-up fallback used).
The raw and restart outputs are both retained; no geometry is hidden to claim
a clean result. These numbers describe the old, misinterpreted poses, not the
corrected model geometry. The correction reduces the translation-window
diagnostic RMSE from 0.249 m to 0.091 m and image reprojection error from
33.23 px to 1.45 px. Reproduce the old matched comparison with:

```bash
python inspect_lingbot.py --input outputs/cec_090850_translation_probe \
  --compare-input outputs/cec_090850_lingbot
```

Before overlaying robot paths or adding metre labels, independently establish
the current reconstruction's scale and camera/body alignment. Independent
GEM, Baseline and survey sessions have different coordinate frames and require
validated registration. Their geometry should retain run/frame provenance.

Check accumulated wall/floor agreement and tracking discontinuities before
describing the result as globally consistent. Short-prefix parity is not a
replacement for those checks. See
[`lingbot_deployment.md`](../lingbot_deployment.md), especially
the c2w fix, confidence gating, rotation/parallax failures and the later
correction about session-dependent scale. Do not assume the early scale
transfer statements still apply.

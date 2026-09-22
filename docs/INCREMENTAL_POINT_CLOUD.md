# Incremental point clouds

The 3D in this video is a **timestamped replay of LingBot-Map predictions**. Each RGB frame that the model actually saw produces one depth, one confidence map, one K, and one camera pose. The renderer then *reveals* those chunks in playback order. Nothing in the delivered picture is a globally optimized map.

Three properties were non-negotiable after the first failed attempts:

1. **RGB only.** Recorded depth, body odometry, and Habitat GT pose never enter the network. Odometry is used afterwards for *diagnosis* (Sim(3) RMSE) and, in the opening montage, to *pick which frames to keep*.
2. **Causal streaming.** One persistent KV session, official `demo.py` weights (`lingbot-map-long.pt`), FlashInfer unless a controlled SDPA ablation is running. No per-frame independent inference, no loop closure, no pose graph.
3. **Raw model coordinates.** Points stay in LingBot units. Display code may rotate to a floor frame, apply a height band, and choose a metric *drawing* scale. It must not move points to agree with odometry.

If a cloud looks “smeared,” the first hypothesis is a **pose-convention bug**, not model drift. That bug is documented below and in `docs/history/DEPLOYMENT_AUDIT.md`.

## Units and files

Each accepted observation writes `frames/XXXXXX.npz`:

| Array | Meaning |
|---|---|
| `depth`, `conf`, `K` | Head outputs after official post-process |
| `c2w` | OpenCV camera-to-world, **viewer convention** (see next section) |
| `rgb` | The 518×294 crop the model saw |
| `local_points`, `point_rgb` | Unprojected points in the camera frame, already confidence- and stride-gated |
| `timestamp_ns` | ROS log time (real) or synthetic ns (sim); this is the reveal clock |

`reconstruction.json` lists every source frame, marks the first seven as `warming` (no cloud), and records `pose_adapter`, backend, keyframe interval, and confidence percentile (default 65) plus pixel stride (default 4).

## Two reconstruction entry points

### Official path (what the finals use)

`run_lingbot_manifest.py` is the production entry.

- Reads only an RGB `manifest.json`.
- Imports `/home/asus/Research/lingbot-map/demo.py`.
- Replaces `lingbot_map.vis.PointCloudViewer` with a `CaptureViewer` that writes NPZs instead of opening a web GUI.
- Leaves loading, precision, streaming, and post-process untouched.
- Pose: `closed_form_inverse_se3(data['extrinsic'])[:, :3]`, which is exactly what the official viewer uses after `demo.py` has already inverted the decoded matrix once.

Typical flags for a long real session:

```bash
PY=/home/asus/miniconda3/envs/lingbot-map/bin/python
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export PATH="$CUDA_HOME/bin:$PATH"
export LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib"

$PY run_lingbot_manifest.py \
  --manifest path/to/manifest.json \
  --out path/to/new_empty_directory \
  --backend flashinfer \
  --max-frame-num 2048   # outdoor used 4096
```

`--out` must **not** already exist. Provenance is “new directory per run,” never overwrite.

FlashInfer needs the lingbot-map CUDA toolkit on `PATH` / `LIBRARY_PATH`. Two early full-length jobs died in ninja/`libcudart` discovery; the environment block above is the fix. See [ISSUES.md](ISSUES.md).

Keyframe interval: omit the flag to use `demo.py`’s `ceil(N/320)`. Indoor joint used 6; outdoor joint used 12; opening montage used 1 (short excerpts).

### Wrapper path (kept for audits)

`lingbot_incremental.py reconstruct` talks to `StreamingSession` + `LingBotBackbone` directly. It is how the pose bug was isolated. Production clips do **not** use it.

`--pose-convention` is required:

- `raw-c2w` — invert the wrapper’s exported matrix (matches this long checkpoint + official viewer).
- `wrapper-c2w` — consume the export as-is (the wrong interpretation that smeared translations).

`audit_pose_convention.py` decides which one is right **without** odometry: Lucas–Kanade tracks with forward–backward cycle error &lt; 1 px, then reproject with saved depth and K under both SE(3) interpretations. On the 320-frame indoor translation window, median residual was **33.23 px (saved as c2w)** vs **1.45 px (invert first)**.

## Why the official viewer inverts twice

`demo.py` inverts the decoded pose when exporting. `PointCloudViewer._process_pred_dict` inverts that export again for unprojection and for the camera trajectory. A wrapper that “matches the export file” therefore disagrees with the interactive viewer by one inverse.

Sampling 15 frames: original viewer world points vs the corrected formula differed by at most **1.22×10⁻⁷** model units. That closed the argument. Translation smear on the first videos was a local integration error, not evidence that LingBot cannot track a Go2.

FlashInfer vs the corrected wrapper, same 955 indoor timestamps, body-odometry diagnostic (not GT):

| Session | Traj. RMSE vs odometry | LK residual |
|---|---:|---:|
| Old wrapper, inverted | 2.389 m | 6.594 px |
| Official `demo.py` + SDPA, interval 4 | 0.967 m | 6.264 px |
| Official `demo.py` + FlashInfer, interval 4 | **0.187 m** | **2.873 px** |

SDPA’s attention layer was also observed to **append despite `_skip_append=True`**. FlashInfer is the default backend for every delivered reconstruction.

These RMSE numbers compare to Go2 body odometry with an uncalibrated lever arm. They are not centimetre accuracy claims. They are only allowed as *diagnostics*; they never warp the rendered points.

## Incremental reveal (the picture people call “growing clouds”)

All map classes (`JointMap`, `FloorSupportedMap`, `FloorFixedMap`, the opening tile renderer) share the same idea:

```
for each prediction with timestamp t:
    if t > current_playback_time of that arm: skip
    unproject → rotate into a display floor frame → height-band → z-buffer splat
```

- **No future leak.** A 2.5D time-bucket used to take the bucket’s *last* observation; that showed later points too early. Buckets now use ROS log time and the last observation *inside the current cut*.
- **Two arms, one session.** Indoor and outdoor finals are a *joint* LingBot session. Display still filters by each arm’s own playback time, so GEM cannot show Baseline-only observations and vice versa. Inference itself is **not** two independent online streams. The video must not imply otherwise.
- **Local plans** are recorded NavDP trajectories, projected onto the same floor and tested against the cloud z-buffer (obstacle occlusion), not against each other.

## Joint session order

### Indoor (`outputs/joint_demo_flashinfer`)

One session: **Baseline reversed, then GEM forward**, 1749 frames, interval 6, `max_frame_num` 2048. Shared-scene geometry, seam about 4 cm in the display scale. Trajectories are the reconstructed cameras; no extra ICP.

Renderer: `render_real_final.py --scene indoor` (default `--floor-cloud supported`).

### Outdoor (`outputs/outdoor_joint_reverse`)

Same shared-scene idea: **GEM reversed, then Baseline forward**, 2133+1581 frames, interval 12, `max_frame_num` 4096.

The opposite order (`outputs/outdoor_joint_flashinfer`) was tried first. It had a prettier seam reprojection (2.08 px vs 5.79 px) but **worse whole-route scale** (GEM 0.037 vs 0.103 model units/m). Delivery keeps the reverse-GEM session because trajectory/scale consistency along the route matters more than the seam. Residual holes and drift remain; no per-arm post-alignment.

Renderer: `render_real_final.py --scene outdoor` (default `--floor-cloud floor-fixed`).

### Simulation (`outputs/nnr003_forward_joint`)

Two **independent forward** official sessions (GEM / Baseline) on the packaged RGB `outputs/nnr003_visual_rgb`. Shared-prefix predictions match exactly. One GT similarity sets display scale/up/floor only. Paired position RMSE 0.175 m is a *display* check.

Renderer: `render_table2_joint.py ... --cloud-mode raw`.

## Rebuilding a source clip (lab disk, do not overwrite `outputs/final/`)

Point clouds live in NPZ sessions that are gitignored (~2–5 GB each). The display JSONs *are* in git; they only rotate/scale for drawing.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export PATH="$CUDA_HOME/bin:$PATH"
export LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib"
PY=/home/asus/miniconda3/envs/lingbot-map/bin/python
```

Re-render from **existing** reconstructions (writes a new file):

```bash
$PY render_real_final.py --scene indoor --out /tmp/realworld_rebuild.mp4
$PY render_real_final.py --scene outdoor --out /tmp/outdoor_rebuild.mp4
$PY render_table2_joint.py \
  --source outputs/nnr003_visual_rgb \
  --frame outputs/nnr003_joint_frame.json \
  --out /tmp/simulation_rebuild.mp4 \
  --theme minimal --presentation joint --cloud-mode raw \
  --steps-per-second 20 --arrival-hold 0 --end-hold 1 \
  --baseline-tail-seconds 3 --gem-track-width .18 --baseline-track-width .24
```

Re-infer only if the NPZ directory is gone. `--out` must be a **new** path:

```bash
$PY run_lingbot_manifest.py \
  --manifest outputs/joint_rgb/manifest.json \
  --out outputs/joint_demo_new \
  --backend flashinfer --keyframe-interval 6 --max-frame-num 2048

$PY run_lingbot_manifest.py \
  --manifest outputs/outdoor_inputs/manifest_reverse.json \
  --out outputs/outdoor_joint_new \
  --backend flashinfer --keyframe-interval 12 --max-frame-num 4096
```

Simulation is two independent forward jobs whose shared prefix must match exactly; merge with `merge_table2_forward.py` and fit display with `fit_table2_joint.py`. Do not reuse `sim_frame.json` (that file is the older three-leg demo).

`private_residency_server.py` is a lab GPU-parking helper for a shared workstation. It is not part of the picture.

## Floor, height band, and “supported” points

Simulation originally clipped the floor at −0.08 m in camera-height units and looked empty. The delivered sim/outdoor band is **−0.30 m to +1.10 m** with the original top-35% confidence and 3.5% local depth-spread filter.

Indoor is different. A fixed-view ablation showed that lowering the clip from −0.08 m to −0.30 m only added ~11% occupied pixels; relaxing quality filters added more, and removing both admitted noise. Indoor therefore keeps the strict cloud as the base and **adds** extra points only if:

- they sit in a geometric height band (−0.30 m to +0.20 m about the existing floor reference),
- confidence is at least percentile 40 (not 65),
- the 3.5% spread filter still holds,
- **two** earlier same-arm views, 0.18–1.6 s old and ≥ 3 cm translated, reproject the point within max(5 cm, 1% range).

That is `real_floor_cloud.FloorSupportedMap`. It is not semantic floor segmentation. Baseline files are stored reversed; support votes still follow **playback** time. Occupied pixels on the indoor map rose 4.35% (full prefix), not a visual rewrite of the scene.

TSDF (`cloud_surface_fusion.py`) exists as an experiment. **Delivered videos use raw splats**, never fused surfaces. Filling holes looked smoother and was rejected as dishonest.

## Display floor frame

`render_lingbot.floor_frame` / `fit_ground_frame.py` / `fit_outdoor_frame.py` estimate a gravity-aligned frame from camera centres (and the archived ~0.40 m camera height outdoors). If the estimator falls back to “camera-up”, the cloud sits on a diagonal wall — that showed up in early Habitat stills and in some short real tiles. The opening-tile renderer walks later frames until a supported floor appears; if none does, it uses the 5th percentile of first-frame points as a display-only height reference.

Points are not deformed onto that plane. Only the *drawing* basis changes.

## Opening 3×3 incremental grid

This is the same incremental idea, nine short excerpts, each its own session.

1. `prepare_icra_motion_montage.py`  
   From Habitat eval RGB or real demo RGB, keep a **forward** interval and compress pauses with a motion-keyframe weight: `Δpath + 0.1 |Δyaw|`, dropping near-zero weights. No loops. Telemetry/Habitat trace is editorial only.
2. `run_icra_montage_reconstruction.py`  
   `run_lingbot_manifest.py --backend flashinfer --keyframe-interval 1` per scene into `outputs/icra_submission/montage_motion/<name>/cloud`.
3. Tile renderer (`render_icra_cloud_tiles.py` and the motion-montage equivalent)  
   150 frames, 640×360, white background, z-buffer RGB, a grounded camera ribbon in the same buffer. Height band `−0.3…1.65 × camera_height`. Azimuth chosen to pack the cloud in landscape.

`icra_spatial_design.py` plays those tiles: indoor fills the screen, then a centered pull-back to 3×3 while every cloud keeps growing.

## Confidence and stride (defaults)

| Parameter | Default | Role |
|---|---|---|
| `conf_percentile` | 65 | Keep the top 35% of finite-confidence pixels |
| `pixel_stride` | 4 | Subsample the valid mask |
| warming frames | 7 | KV prime; no NPZ |

Indoor “supported” floor uses percentile 40 **only** for the extra band, and still requires multi-view agreement.

## What reconstruction is not

- Not GEM’s episodic archive. GEM’s memory is the paper’s streaming geometry + readout. The video cloud is a *visualization* of LingBot-Map on the logged RGB.
- Not a metric map. Scale is a display estimate (odometry or GT similarity).
- Not causal two-stream comparison when a joint session is used. The captioning and narration must not say “both robots built this cloud online.”
- Not paper success. Indoor/outdoor arrivals follow recorded RGB latches; simulation RGB arrival is distinct from Habitat distance scoring (GEM GT endpoint errors on A/B/C were still 1.27 / 0.88 / 0.35 m).

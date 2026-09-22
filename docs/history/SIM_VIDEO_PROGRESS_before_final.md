# Historical record — superseded by FINAL_DELIVERY.md

Old exported media links in this record were intentionally removed during final asset cleanup. Source data and experiments remain.

# Table II source simulation video — current NNR result

Updated 2026-09-21. Presentation reference: `outputs/gem_indoor_joint.mp4`.

**Current minimal presentation with candidate paths and per-arm arrival frames:**
[Complete video](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.mp4)
— 38.567 seconds / 1157 frames / 1080p30; decode, arrivals and local-plan timing verified.
[Arrival states](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.arrivals.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_minimal_arrival_2x.verified.json).

**Previous selected-only minimal presentation:** [Minimal white, 2×, continuous playback](outputs/sim_visual_arrival_nnr_minimal_2x.mp4)
— 38.567 seconds / 1157 frames / 1080p30; full decode, arrivals and local-plan timing verified.
[Preview](outputs/sim_visual_arrival_nnr_minimal_2x.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_minimal_2x.verified.json).

**Previous refined presentation:** [White, refined layout, 2×, no arrival pauses](outputs/sim_visual_arrival_nnr_refined_2x.mp4)
— 38.567 seconds / 1157 frames / 1080p30. Full decode, local-plan timing and no-added-arrival-hold checks passed.
[Arrival states](outputs/sim_visual_arrival_nnr_refined_2x.arrivals.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_refined_2x.verified.json).

**Previous white presentation:** [White background, goal cards, 2× motion](outputs/sim_visual_arrival_nnr_white_2x.mp4)
— 45.067 seconds / 1352 frames / 1080p30; full decode, arrivals and local-plan timing verified.
[Arrival cards](outputs/sim_visual_arrival_nnr_white_2x.arrivals.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_white_2x.verified.json).

**Previous dark joint-style video:** [Floor-fixed cloud, joint style and recorded NavDP paths](outputs/sim_visual_arrival_nnr_joint_style.mp4)
— 56.567 seconds, 1697 frames; full decode, arrivals and local-plan timing verified.
[Arrival frames](outputs/sim_visual_arrival_nnr_joint_style.arrivals.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_joint_style.verified.json).

**Alternative TSDF experiment (not user-selected):** [NNR with reduced cloud ghosting](outputs/sim_visual_arrival_nnr_fused.mp4)
— 1697 frames decoded; incremental fusion clock and arrival checks passed.
[Same-view raw/fused comparison](outputs/cloud_fusion_audit/raw_vs_fused.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_fused.verified.json).

**Previous floor correction (raw cloud retained):** [NNR with floor-cloud fix](outputs/sim_visual_arrival_nnr_floorfixed.mp4)
— all 1697 frames decoded; shared clock and five arrival events verified.
[Corrected arrival frames](outputs/sim_visual_arrival_nnr_floorfixed.arrivals.jpg) ·
[Verification](outputs/sim_visual_arrival_nnr_floorfixed.verified.json).

**Previous version (retained for comparison):** [NNR dual-trajectory video](outputs/sim_visual_arrival_nnr_joint.mp4)
— **56.567 seconds, 1697 frames, 1920×1080 / 30 FPS**.
Scene `VFuaQ6m2Qom`, based on formal task 003. GEM completes all three RGB
arrivals and travels **18.663 m**, versus 9.859 m in the previous NRR video.
Baseline completes A/B; C genuinely terminates **stuck at 568 actions**,
4.558 m from its goal. Baseline's total path is 22.854 m.

[Decoded arrival frames](outputs/sim_visual_arrival_nnr_joint.arrivals.jpg) ·
[Decoded checkpoints](outputs/sim_visual_arrival_nnr_joint.jpg) ·
[Accelerated tail frame](outputs/sim_visual_arrival_nnr_joint.tail.jpg) ·
[Full verification](outputs/sim_visual_arrival_nnr_joint.verified.json).

## 2026-09-21: minimal layout + restored candidates + per-arm arrival borders

Latest output: `outputs/sim_visual_arrival_nnr_minimal_arrival_2x.mp4`.
The minimalist layout remains, but the user requested the actual candidate fan
back. Candidate rendering is enabled by default; `--hide-local-candidates`
reproduces selected-only local-path rendering.

Goal images now independently latch **outer blue for GEM** and **inner coral for
Baseline**, using the same method colors as the trajectories. Both reached gives
two thin nested frames; GEM-only arrival gives blue only. A/B correctly show both;
C stays blue even after Baseline terminates unsuccessfully. No border is added
merely because a method stopped. Goal images remain hidden until actually issued.
A direct rendered-pixel check confirms these final A/B/C border states;
`outputs/goal_arrival_border_preview.jpg` shows the arrival sequence.
The previous GEM-only green-goal-border treatment is superseded.

Timing and data are unchanged: 2× normal motion, zero added arrival holds,
1-second final hold, 3-second compressed Baseline tail, raw floor-fixed cloud.

## 2026-09-21: minimal composition (latest preference)

Output: `outputs/sim_visual_arrival_nnr_minimal_2x.mp4`, `--theme minimal`.
Remove title/subtitle, legends, timer card, card containers, repeated status rows,
map-label boxes/leader lines and candidate trajectory fans. Keep two FPVs with
method names, three small target images with role labels, raw floor-fixed cloud,
actual selected NavDP trajectories, and smaller single arrival rings. Only a
small 2× tag remains; the extra Baseline-tail acceleration stays explicitly labeled.

Target-image green borders track **GEM** arrivals; each method's own FPV border
and Arrived/Stopped label communicate its independent outcome. Future targets
remain blank until issued. No false shared success is inferred from target color.
Map viewport (548,198), 1344×854; outer ribbons 18/24 cm, bright center 8.5 cm.
The selected local path retains its original geometry and obstacle occlusion;
only candidate fan display is disabled (audit `local_candidates_visible=false`).
Continuous 2× motion, no added arrival holds, 1-second final hold, 3-second
Baseline tail. Previous themes and videos remain available for comparison.

## 2026-09-21: refined layout and uninterrupted arrivals

Current new output: `outputs/sim_visual_arrival_nnr_refined_2x.mp4`.
Presentation option `--theme refined` keeps the white background with Lato UI
fonts, aligned compact FPV panels, method/status labels outside RGB, subtle card
borders, and per-arm check/active/stop symbols with a compact legend. Target cards
retain issued-only images and independent arrival states. The map is at
(548,278), 1344×774. Trajectory outer widths are GEM 20 cm / Baseline 27 cm with
8.5 cm bright centers; raw point cloud and recorded NavDP geometry are retained.

Latest user preference: **no extra arrival pauses**. Render with
`--steps-per-second 20 --arrival-hold 0 --end-hold 1 --baseline-tail-seconds 3`.
Card checks persist through later legs, so outcomes stay visible during continuous
playback. Last result holds 1 second. Normal per-source-frame sampling duplicates
at 30 fps are not inserted arrival holds. Previous layouts/videos remain intact.
Implementation: `refined_sim_style.py`; `--theme white` retains the earlier cards
and `--theme dark` retains the earlier dark joint presentation.

## 2026-09-21: white background, goal cards, 2× playback

New output: `outputs/sim_visual_arrival_nnr_white_2x.mp4`.
Normal motion advances 20 source observations per video second, i.e. **2×** the
explicit 10 Hz demo clock. The 1.5-second arrival holds, final hold and compressed
3-second Baseline tail remain; this is not a uniform 2× time stretch of the old
render. Tail multiplier is recomputed relative to the new normal speed.

White background replaces empty map pixels using the geometry depth-buffer mask,
not an RGB black-pixel threshold, so reconstructed black surfaces remain black.
The map now occupies (556,246), 1346×816, below a dedicated goal-card band.
Three cards A / Novel, B / Novel, C / Revisit replace the textual stage rows below
the FPVs. Future goal images stay hidden until their leg begins. Active cards
have amber borders; jointly reached cards turn green. Separate GEM/Base result
strips prevent GEM-only arrival from falsely implying Baseline success. At C,
GEM turns green while Baseline remains active and eventually shows stopped.
Left FPVs retain only their method labels and a small current-state badge.
Raw floor-fixed cloud and grounded recorded NavDP paths remain unchanged.

Options: `--presentation joint --theme white --cloud-mode raw
--steps-per-second 20 --baseline-tail-seconds 3 --gem-track-width .26
--baseline-track-width .34`. The old joint look remains available with
`--theme dark`; old outputs are preserved. Goal-card state boundary tests cover
arrival, continued execution, failure and not-yet-issued targets independently.

## 2026-09-21: user-selected floor-fixed cloud + real joint-video styling

Current deliverable: `outputs/sim_visual_arrival_nnr_joint_style.mp4`.
The user prefers the **raw floor-fixed cloud** over TSDF; fusion is retained only
as an alternative experiment. `--presentation joint --cloud-mode raw` combines:

- Real joint map viewport (556,14 / 1346×1062), colors, gold goal thumbnail,
  dark outer ribbons + bright 12 cm center lines, white robot rings, green
  arrival borders and sparse labels. FPV keeps its aspect ratio; no third-person
  imagery is invented. Legacy layout is reproducible with `--presentation legacy`.
- Actual NavDP selected and candidate paths from both arms' saved
  `evaluation/full_plan_outputs.jsonl`. Each plan is joined to its leg/step by
  diffusion seed; selected-path SHA256 and recorded position/yaw are checked.
- NavDP x=forward, y=left in metres; column 3 is yaw, never elevation. Correct
  left basis is `cross(up, forward)` for this OpenCV camera convention.
- Plan geometry is anchored at its **issuance** LingBot position/heading and
  projected to the same reference ground plane +2 cm. Candidate prefixes 60%,
  selected prefix 80%, widths 4.5/8.5 cm, matching the real presentation.
  Existing >25 cm obstacle depth buffer occludes these floor markings.
- Plans are held for at most 30 source steps (3 demo seconds), never cross a leg
  boundary, and disappear at arrival/end. They are recorded predictions, not
  future executed path or fabricated fan geometry. Smoothed LingBot heading,
  like the real renderer, remains an offline display choice.

Full video retains the existing NNR execution, arrival pauses and 3-second
Baseline tail. Outer ribbon widths GEM/Baseline: 26/34 cm to retain the visible
shared prefix. `joint_sim_style.py` implements the layout and recorded plans.
`test_joint_sim_style.py` checks forward/left signs, metric units and floor height;
video audit/verification checks plan age, leg boundaries and displayed counts.
The ground plane is the existing global reference plane, not a dense terrain
surface; raw floor reconstruction residuals are still present.

## 2026-09-21: missing floor cloud diagnosis and display correction

The old NNR video above has a confirmed display defect: the inherited real-video
height interval **(-0.08, 1.10) m** clips away much of the predicted floor.
The reference plane comes from the global GT/pose similarity, not a fit to the
reconstructed floor surface. Good camera-position RMSE does not validate this cut.

A controlled ablation uses every sixth observation (249 samples), the same old
camera/view, confidence/flatness masks and raw predictions. Changing only the
lower height bound to **-0.30 m** restores genuine reconstructed floor points:

| Same-view sampled cloud | Old -0.08 m | Corrected -0.30 m |
| --- | ---: | ---: |
| Accepted points | 840,341 | 1,414,194 |
| Occupied map pixels | 350,955 | 813,901 |
| Occupied pixels in map's left half | 100,569 | 387,911 |

A -0.60 m lower bound yields exactly the same sampled result, so further relaxing
this limit adds nothing in this sample. The height distribution's 10th/25th
percentiles are -0.162/-0.129 m. These are distribution statistics, not a measured
floor accuracy estimate. No GT mesh, artificial floor, pose/depth correction,
confidence relaxation or new navigation run is used for this fix.

[Same-view ablation](outputs/cloud_display_audit/height_ablation.jpg) ·
[Counts](outputs/cloud_display_audit/height_ablation.json).
Reproduce with `audit_cloud_display.py` using the lingbot-map environment.
`render_table2_joint.py` now exposes `--floor-min-height` (default -0.30 m) and
records the actual height interval and final cloud pixel coverage in its audit.
The real-video renderer retains its original settings.

The corrected full video is `outputs/sim_visual_arrival_nnr_floorfixed.mp4`.
Remaining presentation differences: real left panels use external third-person
footage with an onboard inset; simulation uses onboard footage only. The real
reconstruction also uses a baseline-reversed then GEM-forward single session,
whereas this simulation retains independent forward inference. These differences
remain; they are not evidence that inference history caused the missing floor.
Trajectory styling and residual raw reconstruction noise also remain distinct.
Earlier frame-count verification checked temporal visibility, not surface coverage;
it could not detect this defect. The controlled ablation now complements it.

## 2026-09-21: reduce ghosting with causal TSDF display fusion

The raw renderer accumulates depth samples with a nearest-surface z-buffer; noisy
repeated estimates leave layered furniture boundaries and floor streaks. A new
optional `--cloud-mode tsdf` integrates the existing predictions into a surface:

- Open3D TSDF: **2.5 cm voxels**, **10 cm truncation**, depth limit **12 m**.
- Retains the same top-35% confidence, nonblack and local depth smoothness masks;
  integrates their full pixel resolution every third source step.
- Uses only frames reached by each arm's playback clock; shared-prefix prediction
  paths are integrated once. No future observations are used for fusion.
- Camera transforms and depth convert to metres with the existing global scale;
  source predictions, navigation, goal latches and displayed paths are untouched.
- Extracted surfaces use voxel-sized screen footprints, not large hole filling;
  the floor cut remains **(-0.30, 1.10) m**. Surface colors are averaged by TSDF.

A final-view ablation tried 2.5 and 4 cm voxels (417 integrated observations).
The 4 cm option lost too much detail. The 2.5 cm option visibly reduces layered
edges/streaks, at the cost of softer textures and some unsupported-surface holes.
This is display fusion, **not an improvement to measured camera pose accuracy**;
large systematic misalignment can remain. No numeric ghost-removal accuracy is
claimed. `audit_cloud_fusion.py` reproduces the parameter comparison under
`outputs/cloud_fusion_audit/`. The raw-cloud floor-fixed video is preserved.

New output: `outputs/sim_visual_arrival_nnr_fused.mp4`. Its audit records all
fusion parameters, per-frame integrated counts and last integrated source steps;
`verify_table2_video.py` checks those steps never exceed the displayed arm clock.
`test_cloud_surface_fusion.py` verifies metre conversion/extrinsics with translated
cameras observing a known plane, and verifies masked depths add no surface.

Reproduce with the same source/frame/playback options as the floor-fixed video,
adding `--cloud-mode tsdf`. Default remains `raw` for explicit comparison.

## Actual navigation and arrival meaning

This is a **new visual-demo execution**, not the original formal Table II
outcome. It retains task 003's original A image, start and seed **2026091198**.
B/C are constructed online against both surviving methods' actual histories.
Each method has one continuous lifecycle with its own memory and pose;
there is no prefix replay, trajectory splicing or GT-based stop/control.

| GEM leg | Role | Actual path (m) | Arrival action | GT position error (m) | GT yaw error (deg) |
| --- | --- | ---: | ---: | ---: | ---: |
| A | Novel | 2.339 | 67 | 1.267 | 15.54 |
| B | Novel | 6.274 | 175 | 0.883 | 7.72 |
| C | Revisit | 10.050 | 446 | 0.348 | 2.26 |

Starting geodesics are 3.293 / 6.700 / 6.726 m. The 18.663 m total includes
C's detour; it is traveled distance, not map extent. Baseline A/B are identical;
its failed C path is 14.241 m. Source observations: GEM **691**, Baseline **812**.

Gold rings are latched at the **actual RGB arrival observation on the displayed
trajectory**, matching the real-video presentation. They are not surveyed goal
positions. RGB visual agreement does **not** mean exact GT position/heading
agreement; the errors above remain and no poses were warped to conceal them.
[Target/current RGB comparison](outputs/nnr_selection/formal003_ABC_screen_arrivals.jpg)
shows the successful screen; every one of those 691 RGBs and poses was reproduced
exactly in the full paired run.

Both methods use the same RGB centering and `aligned-v2` verifier profile:
image scale 0.85–1.12, center offset <=0.10, coverage >=0.20, inlier ratio >=0.60.
Other verifier settings and the arrival latch implementation are preserved.
This is **not the unchanged real-world threshold profile**. The experimental
RGB translation probe is not enabled. All six actual terminal PNGs were
independently checked against the configured gate: GEM A/B/C and Baseline A/B
pass; Baseline C fails. See
[terminal check](outputs/visual_pair_formal003_aligned2_retry/independent_arrival_check.json).

## Pacing and reconstruction checks

Main playback uses a shared clock at 15 observations/s, with an added 1.5-second
pause at each distinct arrival. A/B/C first appear at video frames
**134 / 531 / 1470** (4.467 / 17.700 / 49.000 s), each held for 47 frames including
normal playback samples. After GEM ends, the remaining 121 Baseline observations
are shown over **3 seconds at 2.689×**, explicitly labeled in the video, followed
by a 3-second final hold. The actual Baseline termination was executed and recorded.
Displayed ribbon widths are GEM 0.22 m and Baseline 0.28 m, preserving visible
shared-prefix edges without giving Baseline the previous 0.34 m width.

Both streams use the actual official `demo.py`, FlashInfer, long checkpoint,
keyframe interval 3 and max-frame count 1024. The shared **245 RGB observations**
produce **238 exactly matching pose/depth predictions** after warming: maximum
absolute differences are zero. No cross-method registration is applied.
[Prefix and input checks](outputs/nnr003_forward_joint/prefix_parity.json).

One GT-to-LingBot similarity supplies display scale, gravity and floor only;
raw camera matrices and depths remain unchanged. Full paired fit RMSE is
**0.175 m**, P95 **0.323 m**; GEM RMSE 0.182 m and Baseline 0.169 m.
[Frame/geometry audit](outputs/nnr003_joint_frame.json). This is an offline
incremental replay: fixed bounds, scale and 13-frame ribbon smoothing use the
full run, while cloud visibility follows each current source observation.
Remaining scan holes, sparse floor points and pose residuals are visible.

All **1697 encoded frames** decoded, their source clocks and visible-cloud
counts were verified, and the three arrival frames, ending and acceleration
banner were inspected. The final frame correctly shows GEM A/B/C OK and
Baseline A/B OK, C FAIL / stuck.

## Inputs, selection and reproduction

- Full pair: `outputs/visual_pair_formal003_aligned2_retry`.
- Recovered original input: `outputs/table2_inventory/formal_003.tar.gz`,
  `outputs/table2_formal003_rgb`.
- Packaged actual observations: `outputs/nnr003_visual_rgb`.
- Reconstructions: `outputs/nnr003_forward_gem`, `outputs/nnr003_forward_base`,
  `outputs/nnr003_forward_joint`.
- Final frame: `outputs/nnr003_joint_frame.json`.
- [Final selection and pipeline commands](outputs/nnr_selection/selection.md).
- [All local NNR trials](outputs/nnr_selection/visual_trial_inventory.json).

The GEM reconstruction was computed from the successful screen. Reuse is
validated by exact equality of all 691 full-pair RGBs, poses and timestamps,
recorded in `gem_screen_reproduction.json` and the merge input checks. An earlier
full pair aborted due to concurrent reconstruction causing CUDA OOM; it is
preserved as a resource failure and excluded from the video. The successful
retry and subsequent reconstruction were run sequentially.

**Task-construction correction:** depth-history PNGs saturate at 6.5535 m and
can hide distant surfaces already seen. A proposed 253 B goal scored zero with
these PNGs but 0.3645 with raw depth, so it was rejected as Novel. The local demo
constructor now re-renders full-precision depth at actual recorded poses for
both N/R support checks; thresholds and the 60-degree Novel route bound remain.
For this final pair, B's max history/current visibility are both zero; C's
max history visibility is 0.8197 and current visibility zero, with a 0.22 m /
12-degree source-view perturbation. Original external benchmark code and archives
are unchanged. The raw-depth guard regression and executed constructor receipts
are retained under `outputs/nnr_selection` and the paired run.

## Previous NRR revision and historical implementation notes

**Previous completed NRR video:** [sim_visual_arrival_joint.mp4](outputs/sim_visual_arrival_joint.mp4)
— 1920×1080 H.264, 30 FPS, **55.567 s / 1667 frames**. Blue GEM / red Baseline,
shared incremental LingBot cloud, N–R–R goals, real RGB-latch rings and shared
1.5 s arrival holds. GEM completes A/B/C; Baseline completes A and exhausts
600 actions in B, so C is not attempted. Both methods use the same additional
RGB centering controller; this is explicitly labeled a new demo configuration,
not the original Table II result.

All 1667 frames decoded successfully; every frame's cloud visibility and source
clock were checked. Actual arrival frames are A **238 (7.933 s)**, B **555
(18.500 s)**, C **762 (25.400 s)**. Each appears for 47 frames, including the
45-frame added hold. Visual checks include all arrival frames and the ending.
[Arrival frames](outputs/sim_visual_arrival_joint.arrivals.jpg) ·
[Four decoded checkpoints](outputs/sim_visual_arrival_joint.jpg) ·
[Verification](outputs/sim_visual_arrival_joint.verified.json).
The full-run section below records source provenance and remaining pose/drift
errors; a visual latch does not imply identical target and arrival world pose.

**Earlier diagnostic: A terminal-continuation visual arrival succeeded.**
[12.5 s RGB comparison video](outputs/visual_arrival_suffix_113_a_v1/arrival_comparison.mp4)
and [decoded final frame](outputs/visual_arrival_suffix_113_a_v1/arrival_comparison_last.jpg).
This is a separately initialized suffix diagnostic, not full paired NRR success.

**Rendered, but arrival presentation does not yet satisfy the requested demo:** [sim_table2_nrr_joint.mp4](outputs/sim_table2_nrr_joint.mp4).
1920×1080 H.264, 30 FPS, 1802 frames, 60.067 seconds (15 simulator steps/s plus
3-second final hold). [Four decoded frames](outputs/sim_table2_nrr_joint.jpg).
Timing, all per-frame visible-chunk counts and final arm steps were verified;
the decoded ending correctly shows GEM A/B/C success and Baseline B stuck,
C not attempted. Checks: `outputs/sim_table2_nrr_joint.verified.json` and
`outputs/sim_table2_nrr_joint.audit.json`.

## Input selection and verified source

### Full paired visual-demo rebuild (2026-09-20; completed and verified)

New entry point: `run_visual_pair.py`. Each arm starts from the original pose
with empty runtime history, performs one reset for the whole lifecycle, and
inherits its own actual endpoint and memory at each goal switch. B/C goals are
generated online by the existing common-goal constructor against surviving
arms' actual observations. RGB visual arrival, not the old 1 m threshold,
decides leg completion. Geometry-construction traces explicitly count terminal
observations separately from executed actions; they are not benchmark traces.

Unmodified-policy attempts retained locally:

- `visual_pair_011_v1`: both A runs hit 600 actions without visual arrival.
- `visual_pair_113_seed1`: both A runs ended stuck at 351 actions.
- `visual_pair_113_seed2`: both A runs ended stuck at 383 actions.

Original/new first-frame hashes match; trajectories then diverge from the HPC
archive as tiny inference differences feed back through rendering/control.
Two arms within each new local attempt have identical A RGB. Changed demo
seeds are recorded explicitly and never substituted into original results.

An explicitly different demo profile adds **the same RGB terminal centering
controller to both methods** (`--visual-centering`). `visual_terminal_centering.py`
uses matched-ray bearing, low bearing dispersion, essential-pose inlier/tilt
checks and two consecutive supported views. Each turn is bounded to 5 degrees.
It reads only current/goal RGB and camera intrinsics, never goal GT/depth. The
original real-world arrival verifier and all its thresholds are unchanged.
This is Baseline **plus shared centering**, not untouched Table II Baseline;
the new video's footer must disclose it. No formal success-rate claim applies.

`visual_pair_113_centered1` (seed 2026120441) reached A in 119 actions and B
in 135 actions for GEM; both arms reached A. Baseline B then suffered CUDA OOM,
which is an infrastructure error, not navigation failure. This attempt is
retained and is not the final video source.

`--park-idle` uses `private_residency_server.py` only for these private servers.
Idle CUDA tensor storages move to CPU and back without policy reset/replay,
preserving tensor identities, shared-storage aliases, offsets, strides, dtype
and RNG. CPU/CUDA round-trip checks preserve exact values and model outputs.
New attempt `visual_pair_113_centered2` reproduces GEM A and B image hashes
through the compared prefix and avoids simultaneous GPU residency. Existing
unrelated GPU services are preserved. Residency receipts record bytes and live
CUDA allocation (zero while parked).

`prepare_visual_pair.py` has packaged verified actual frames,
endpoint continuity and latch events; forward `demo.py` reconstructions are
merged only after checking identical-prefix outputs. `render_table2_joint.py`
now displays gold double rings at the actual visual-arrival observation,
shared 1.5 s arrival holds, target images, and dimmed failed runs. It does not
move target GT or warp trajectories to force a match. Original video files
remain available.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_visual_pair.py \
  --archive outputs/table2_inventory/expansion_113.tar.gz \
  --rgb-source outputs/table2_expansion113_rgb \
  --asset /home/asus/Research/datasets/mp3d/VVfe2KiqLaN.glb \
  --out outputs/new_visual_pair --seed 2026120441 \
  --visual-centering --park-idle
```

### Full-run result and reconstruction checks

Final source: `outputs/visual_pair_113_centered2`, scene `VVfe2KiqLaN`, new
seed **2026120441**, shared RGB centering enabled for both arms. This is a new
continuous NRR execution derived from expansion task 113, not a replay of its
original benchmark run. It uses 337 GEM and 721 Baseline observations.

| Arm / stage | Actions | Path (m) | Visual arrival | Final GT distance (m) | Heading error |
| --- | ---: | ---: | --- | ---: | ---: |
| GEM A | 119 | 4.081 | yes | 0.391 | 24.08° |
| GEM B | 135 | 3.073 | yes | 0.201 | 11.20° |
| GEM C | 80 | 2.704 | yes | 0.052 | 12.31° |
| Baseline A | 119 | 4.081 | yes | 0.391 | 24.08° |
| Baseline B | 600 | 18.453 | no; action budget exhausted | 4.383 | 46.44° |
| Baseline C | — | — | not attempted | — | — |

GEM travels **9.859 m** in total. The unchanged real-world verifier measures
RGB correspondence, not exact equality of world pose: in particular A still
has 0.391 m / 24.08° pose error. Rings mean a recorded visual latch at the
corresponding point on the drawn path, not surveyed target coordinates.
No archived suffix is spliced into this run. Per-frame hashes, terminal-frame
inclusion, and position/heading continuity were checked by the packager.
Independent re-evaluation of all five lossless terminal images agrees with
the recorded outcomes. See `outputs/visual_pair_113_rgb/terminal_verification.json`
and [target/terminal comparison](outputs/visual_pair_113_rgb/terminal_comparison.jpg).

Both actual `demo.py` forward reconstructions use long weights, FlashInfer,
bfloat16 aggregator, keyframe interval 3, max frame number 1024. Their 121
identical input-prefix frames yield 114 exported prediction pairs with **zero
camera/depth difference**. Branch translations are 0.0249 m for GEM (GT 0)
and 0.0257 m for Baseline (GT 0.0364 m). No cross-arm alignment is applied.

Remaining reconstruction limitation: after one global similarity, GT position
RMSE is **0.733 m** overall, **0.315 m GEM / 0.861 m Baseline**, p95 **1.632 m**.
This run's later Baseline reconstruction drifts more than the old archive's;
the common prefix and branch boundary checks do not establish low full-run
drift. Raw LingBot poses/depth remain unchanged. The display uses GT only for
one global scale/up/floor, and full-run bounds/path smoothing for presentation.
Checks: `outputs/visual_pair_113_forward_merged/prefix_parity.json` and
`outputs/visual_pair_113_frame.json`.

Reconstruct and render the completed source with fresh reconstruction output
paths if rerunning (the existing directories intentionally reject overwrites):

```bash
python prepare_visual_pair.py --run outputs/visual_pair_113_centered2 \
  --out outputs/visual_pair_113_rgb
python run_lingbot_manifest.py \
  --manifest outputs/visual_pair_113_rgb/manifest_forward_gem.json \
  --out outputs/visual_pair_113_forward_gem --keyframe-interval 3
python run_lingbot_manifest.py \
  --manifest outputs/visual_pair_113_rgb/manifest_forward_base.json \
  --out outputs/visual_pair_113_forward_base --keyframe-interval 3
python merge_table2_forward.py --source outputs/visual_pair_113_rgb \
  --gem outputs/visual_pair_113_forward_gem \
  --base outputs/visual_pair_113_forward_base \
  --out outputs/visual_pair_113_forward_merged
python fit_table2_joint.py --input outputs/visual_pair_113_forward_merged \
  --out outputs/visual_pair_113_frame.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python render_table2_joint.py \
  --source outputs/visual_pair_113_rgb --frame outputs/visual_pair_113_frame.json \
  --out outputs/sim_visual_arrival_joint.mp4
python verify_table2_video.py --video outputs/sim_visual_arrival_joint.mp4 \
  --require-gem-three-visual
```

### First actual closed-loop validation (2026-09-20)

**Suffix result:** `outputs/visual_arrival_suffix_113_a_v1` executed 95 new
actions after initialization at the archived A endpoint (0.979 m from target).
At observation 95 the unchanged real-world RGB verifier latched, terminating
before action 96. Terminal distance is **0.202 m**, heading error **13.02°**;
166 good matches / 104 inliers, coverage .287/.354, center offset .2077,
scale 1.1769, reprojection error 1.0808 px. Re-evaluating the saved lossless
terminal RGB independently produces the same metrics and a positive latch.

This was a useful separation of translation and viewing direction: action 28
passed within 0.092 m but had 74.31° heading error and did not trigger arrival.
The policy subsequently changed its viewpoint and the real RGB gate, not GT,
decided when to stop. No terminal steering controller or relaxed thresholds
were added. The verification binds 95 executor actions to 96 observations.

`report_arrival_smoke.py` creates the numeric verification and comparison
image; `render_arrival_smoke.py` creates the side-by-side target/current video.
The successful video has 375 decoded-count-verified frames, 30 FPS, 12.5 s,
including a 3 s final hold. Its captions explicitly identify the archived-endpoint
initialization and distinguish GT diagnostics from RGB stop authority.

`outputs/arrival_render_controls_113_a/results.json` contains separate GT-pose
rendering controls, not navigation: the true target pose passes (611 inliers),
the archived stop fails (16 good matches), and the same stop position with
target yaw still fails (26 good matches). This supports checking both position
and viewpoint rather than simply rotating the goal marker.

**Historical limitation, resolved by the full run above:** successful A continuation alone does not establish a successful fresh
start or B/C performance. The fresh-start trial below failed before reaching
the target region. Before producing a full paired demo, run a continuous
lifecycle with visual stop authority and construct successor goals from its
actual new history. Do not splice archived A with this continuation and label
it a newly executed full episode. The original Table II video remains intact.

`run_arrival_smoke.py` now initializes the real Habitat executor and two private
model servers, using the original scene hash, target-image hash, starting pose,
seed and 600-action budget. It calls `run_visual_policy_leg` under the same
bounded RGB executor/front-heading adapter used by Table II. Existing GPU
services are preserved; the launcher tears down only its own child servers.

`outputs/visual_arrival_smoke_113_a_v1`: source-A trial ended **stuck after 299
actions**, with no visual arrival and no distance-success crossing. Minimum
target distance was 2.116 m; terminal distance 4.435 m and heading error 8.1°.
The first rendered JPEG exactly matches the archive, but only the first two
JPEGs of the new trajectory match its archived prefix. This is a new execution,
not reproduction of the old successful A or continuation of its video. The
trial therefore does not answer convergence after entering the 1 m region.
See `verified.json`, `comparison.jpg`, per-frame arrival JSONL, actual executor
actions, `visual_leg/terminal.png`, and the exported `executed_loop.py`.

A separate `--from-archived-endpoint` diagnostic initializes at archived A's
post-action endpoint and supplies its original 537 RGB history frames. This
rebuilds visual history through memory endpoints; it does **not** restore an
exact serialized policy state, count replayed motion as newly executed, or
constitute a full A/B/C result. NavDP decision images are replayed every eight
frames without diffusion sampling. Its purpose is to test the last-meter
behavior directly. Use a fresh output directory for each invocation.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_arrival_smoke.py \
  --archive outputs/table2_inventory/expansion_113.tar.gz \
  --rgb-source outputs/table2_expansion113_rgb \
  --asset /home/asus/Research/datasets/mp3d/VVfe2KiqLaN.glb \
  --out outputs/new_visual_arrival_smoke
# Add --from-archived-endpoint only for a separately labeled suffix diagnostic.
python report_arrival_smoke.py --run outputs/new_visual_arrival_smoke
```

The real episode's archived `formal_config.json` was checked as well: its
arrival settings are the same RGB-homography defaults, and terminal approach
is `bearing_only`, not the experimental local-approach controller. Backup
formal task 011 also has no visual latches in any archived leg under these
unchanged thresholds (`outputs/table2_formal011_visual_arrival/summary.json`).

### Real-world RGB arrival port (2026-09-20)

Implemented a ROS-free adapter in `sim_rgb_arrival.py`, using byte-for-byte
copies of the actual 20260919 deployment snapshot's `rgb_goal_arrival.py` and
`image_goal_io.py` under `vendor/realworld_arrival/`. `provenance.json` records
source paths and SHA256 hashes. No matcher thresholds were tuned on this case.
The archived defaults use SIFT, ratio matching and homography geometry;
required consecutive matches = 1, min good matches = 45, min inliers = 30,
inlier ratio >= .45, coverage >= .07, center offset <= .22, image scale
.60–1.45, image-plane rotation <= 16 degrees, median reprojection <= 4 px.
The 16-degree check is **not a camera yaw tolerance**. This verifier does not
certify metric position or exact target-pose equality.

The adapter preserves sticky latch and per-goal state, rejects duplicate or
out-of-order observations and applies the .75 s arming grace. Synchronous
simulation observations replace ROS freshness/estop/status transport; each arm
and each new goal gets a new gate. A demo step clock must be explicitly given;
Table II archives contain no measured timing, so replay uses an explicitly
labeled .1 s/step convention rather than claiming exact real-time equivalence.

Full shadow replay of expansion 113: GEM A/B/C and Baseline A/B all have
**no visual latch** across 1690 archived RGB observations (including arming
grace observations). All three target-to-self positive controls pass. See
`outputs/table2_expansion113_visual_arrival/summary.json` and per-leg JSONL.
This is not a new closed-loop result; original benchmark labels remain intact.

The actual Habitat evaluator now accepts an optional `rgb_arrival_observer`
in `MemNavData/eval_2leg_habitat.py:run_policy_leg`. In this explicit demo mode:

- Fresh RGB is checked before planning or executing the next action.
- The latch stops immediately with `termination_reason=rgb_visual_arrival`.
- Entering the original distance-success region records its diagnostics but
  does not stop the policy. Stuck/budget termination still applies.
- The budget allows the final post-action observation without another action.
- Visual and benchmark distance results are distinct. Default callers retain
  the original stop behavior and output schema.

`run_sim_visual_leg.run_visual_policy_leg(...)` connects the gate to that
evaluator, records all observed RGB and JSONL events, and saves actual terminal
RGB even for failure. Its returned `reached` means visual arrival, with
`benchmark_distance_reached` retained separately and `formal_population=false`.
Use this **separate demo entry point**, not the formal Table II coordinator or
its original trace validator (the demo can have an extra terminal observation).
It expects an already initialized evaluator, simulator and policy servers:

```python
from run_sim_visual_leg import run_visual_policy_leg
leg = run_visual_policy_leg(
    base, sim, sim.pathfinder, pos, yaw, goal_jpg, goal_xz, geodesic_m,
    out=unique_leg_output, step_period_s=0.1,
    terminal_mode="off", goal_yaw=goal_yaw, camera_intrinsic=K,
    policy_backend=backend, success_dist=1., episode_seed=seed, leg_index=index,
)
```

CPU validation (`validate_sim_arrival.py`) passes latch/reset/grace/freshness,
actual evaluator stop-before-action, diagnostic separation, budget boundary,
and distance-termination behavior with and without the new hook. Syntax checks
pass. At the time of the port, no closed-loop trial had been run; the actual
trial results and successful suffix video are recorded above. The gate itself
supplies no approaching/turning actions. Full paired A/B/C convergence remains
to be established.

```bash
python replay_sim_arrival.py --source outputs/table2_expansion113_rgb \
  --out outputs/a_new_visual_arrival_replay
python validate_sim_arrival.py
```

### Arrival mismatch diagnosed on 2026-09-20

The user requires arrival to agree with the target, as in the real-video
presentation. The current selected task does not provide target-pose convergence:
GEM stops A/B/C at approximately 0.979/0.972/0.997 m from the target.
Heading errors are approximately 34.4/74.7/150.8 degrees. These are original
simulator endpoint errors, before LingBot reconstruction or display alignment.
See [endpoint RGB versus target RGB](outputs/table2_arrival_comparison.jpg) and
[numeric audit](outputs/table2_arrival_audit.json). Saved RGB is pre-action;
the numeric endpoint is post-action, and no final post-action RGB is archived.

`MemNavData/table2_continuous_local.py:140` explicitly calls `run_policy_leg`
with `terminal_mode="off"` and `success_dist=1.`. All 27 scanned NRR candidates
with GEM 3/3 success end each leg between 0.964 and 1.000 m from the target.
Changing candidates cannot remove this protocol-induced gap.

The real renderer `render_indoor_joint.py` draws its ring at the trajectory
pose where the visual arrival module latched, not at an independently surveyed
target coordinate. The simulation renderer currently draws the target-image
capture coordinate transformed from GT. These rings have different semantics.
Moving the simulation target ring onto the stopping point would not establish
actual target convergence, and has not been done.

Next implementation should be a separate simulation demo with terminal visual
alignment, recording post-action terminal RGB and validating both location and
heading/image agreement. A smaller distance threshold alone is insufficient.
Preserve Table II results and distinguish any new rollout from the archived
benchmark. Start with one leg to validate actual convergence before repeating
the full paired NRR lifecycle; changing a stop also changes successor histories
and can change the online-selected B/C goals. Do not append synthetic motion or
goal RGB to the existing video and call it policy execution.

Read-only remote scan of
`/scratch/yz11502/Research/Nav-axis-uturn-results/` on `alantorch`:

| Population | Tasks/summaries | GEM completes 3 | Baseline completes 3 |
|---|---:|---:|---:|
| table2_continuous_formal_20260912_v1 | 97 | 11 | 2 |
| table2_continuous_expansion_20260912_v2 | 411 | 64 | 12 |

All 508 summaries were readable. There are 27 NRR tasks where GEM completes
three legs. See `outputs/table2_inventory/all_tasks.json` and `candidates.md`.
This is qualitative-video selection, not replacement of evaluation cases.

Selected expansion **113**, scene `VVfe2KiqLaN/episode_0032`, has the longest
GEM path among those 27: **25.462 m** (17.714 + 4.376 + 3.371).
Baseline completes A, moves 4.842 m on B, then stops with `stuck`; C is not
attempted. Baseline total is 22.557 m. GEM has 834 recorded RGB frames and
Baseline 856. Their first 538 frames have identical JPEG hashes, positions
and headings. The shared A leg has 537 actions; the first B observation also
matches.

Backup formal **011**, scene `PX4nDJXEHrG/episode_0000`: GEM 19.258 m, 551
frames; Baseline 17.461 m, 614 frames, fails B with `stuck`. All RGB/poses/goals
were recovered for both cases. The missing `/rgb` search result was not missing
data: recorded frames also live in `buffer/ep_0001/*.jpg` inside the archive.
`prepare_table2_video.py` matches images to each pose by SHA256, not filename
ordering. All selected frame hashes match; successive leg initial states
match the previous executed endpoint. Final saved RGB is before the final
action, so no artificial endpoint frame is added.

Original archives:

- `outputs/table2_011_source/artifacts.tar.gz`
- `outputs/table2_inventory/expansion_113.tar.gz`

Prepared data:

- `outputs/table2_formal011_rgb/paired.json`, `manifest.json`, `source_contact.jpg`
- `outputs/table2_expansion113_rgb/paired.json`, `manifest*.json`, `source_contact.jpg`

Both sources contain black regions from incomplete simulator scene meshes.
These are present in archived RGB. Display point sampling rejects near-black
pixels, but the images fed to LingBot are the original recorded images.

## Reconstruction experiments

1. Direct Baseline reverse + GEM forward was stopped after finding that its
   first 8 frames had zero translation (the stopped Baseline tail).
   `outputs/table2_expansion113_joint` is incomplete; do not use it.
2. A recorded 150-frame moving Baseline suffix was prepended for initialization,
   followed continuously by reverse Baseline and forward GEM. All 1840 input
   frames completed. Output: `outputs/table2_expansion113_joint_warm`.
   One global GT-to-model similarity yields camera position RMSE **0.582 m**;
   the 538 identical-image pairs disagree by **0.667 m RMSE**, p95 **1.171 m**.
   Thus a joint session alone is insufficient to align this long repeated route.
   The diagnostic preview `table2_expansion113_first_preview.jpg` is not final.
3. Current candidate: reconstruct the verified identical prefix **once**, then
   Baseline branch forward, reverse that branch as context, then GEM branch
   forward. This is 1470 inputs (538 shared + 318 Baseline + 318 reverse context
   + 296 GEM). Output: `outputs/table2_expansion113_shared`.
   Metadata `also_arm=base` reuses each shared-prefix prediction for both tracks.
   Shared-prefix agreement is therefore by construction, not an independent
   accuracy result. Validate the branch geometry and the global GT residual.

   Completed result: global GT-fit position RMSE **0.341 m**, p95 **0.696 m**;
   GEM **0.452 m**, Baseline **0.173 m**. This is after one fitted similarity,
   not raw metric accuracy, and remaining branch drift is not hidden. LK
   reprojection median is **4.945 px** over 75 sampled pairs in the inference
   sequence (inverse interpretation: 28.590 px). The first 7 initialization
   frames are not exported; 531 exported shared-prefix pairs are exactly equal
   because the prediction is reused. See `table2_expansion113_shared_frame.json`
   and the reconstruction's `pose_convention_audit.json`.

   **Rejected as final:** the explicit branch-boundary check found a 1.369 m
   jump in GEM between steps 537 and 538 while GT translation was zero. The
   global RMSE alone hid this discontinuity. Rendering was stopped; the partial
   `outputs/sim_table2_nrr_reverse_context_rejected.mp4` is diagnostic only.
4. **Final verified approach:** original GEM and Baseline forward streams
   independently, with exactly the same long checkpoint, anchor frames, image
   preprocessing, keyframe interval 3 and max frame number 1024. Because the
   first 538 inputs are identical, their prefix camera/depth outputs must match
   before merging. `merge_table2_forward.py` enforces numeric parity and then
   reuses shared geometry. No fitting between arms, no reverse context and no
   individual pose correction are applied. This differs from two arbitrary
   real-robot runs, whose initial anchor images were not identical.

   Forward outputs: `outputs/table2_expansion113_forward_gem` and
   `outputs/table2_expansion113_forward_base`; intended merged output:
   `outputs/table2_expansion113_forward_merged`.

   Both streams completed. Before merging, all **531 exported shared-prefix
   predictions** were independently compared: maximum absolute camera matrix
   difference **0**, maximum absolute depth difference **0**. No registration
   is applied between methods. Global GT-fit RMSE is **0.162 m**, p95 **0.267 m**;
   GEM **0.161 m**, Baseline **0.163 m**. At step 538, GEM's inferred translation
   is **0.037 m** (GT 0), Baseline **0.053 m** (GT 0.037 m), eliminating the
   reverse-context experiment's artificial 1.369 m branch jump.
   LK median residual: GEM **5.081 px**, Baseline **4.430 px**, 44 pairs each.
   Remaining error is not zero. GT position errors are after one global
   similarity, not evidence of absolute metric scale from RGB alone.

   Machine-readable checks: `outputs/table2_expansion113_validation.json`,
   `outputs/table2_expansion113_forward_merged/prefix_parity.json`,
   `outputs/table2_expansion113_forward_frame.json`.

All inference uses actual local `demo.py`, FlashInfer, long checkpoint and
bf16 aggregator. Reverse experiments use automatic keyframe interval and max
frame number 2048; the final forward pair uses fixed interval 3 and max 1024.
RGB alone enters inference. Reverse experiments are **offline joint
visualizations**, not online causal mapping. The forward pair keeps separate
causal observation histories after the identical scale-anchor prefix.
The final display still uses offline bounds, GT scale/up and smoothed ribbons.

## Original archived-run presentation (superseded by the visual-arrival video above)

Original completed output: `outputs/sim_table2_nrr_joint.mp4`. Final forward-pair preview:
`outputs/sim_table2_nrr_joint_preview.jpg`.
`table2_expansion113_shared_preview.jpg` belongs to the rejected reverse-context
experiment, not the final forward pair.

`render_table2_joint.py` reuses the projection, ground ribbons and obstacle
occlusion logic of `render_indoor_joint.py`. The latter gained optional config
and manifest parameters; its existing defaults are retained.

- Left: GEM and Baseline FPV, current goal image and per-method N/R/R stage.
- Right: shared incremental point cloud; blue GEM, red Baseline. Wider red
  under narrower blue keeps the identical common prefix visibly shared.
- Both methods use the same source-step clock, with no independent stall cuts.
  Baseline freezes only at its recorded termination. No C frames are invented.
- Playback is labeled simulator steps/s, not measured execution seconds.
- Goals are transformed from evaluator GT through one global similarity.
  This transform also supplies scale, up and ground for display; individual
  LingBot poses/depths are not warped to GT.
- Original model poses are preserved. Only drawn paths receive 13-frame
  smoothing. Framing uses full-sequence bounds. Visible cloud chunks are
  restricted to the current step of their own arm.

## Reproduce

Use `/home/asus/miniconda3/envs/lingbot-map/bin/python`; select fresh output
directories for extraction and reconstruction.

```bash
python prepare_table2_video.py \
  --archive outputs/table2_inventory/expansion_113.tar.gz \
  --out outputs/another_113_rgb

export PATH=/home/asus/miniconda3/envs/lingbot-map/bin:$PATH
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export LIBRARY_PATH=/home/asus/miniconda3/envs/lingbot-map/targets/x86_64-linux/lib${LIBRARY_PATH:+:$LIBRARY_PATH}
python run_lingbot_manifest.py \
  --manifest outputs/another_113_rgb/manifest_forward_gem.json \
  --out outputs/another_113_gem --keyframe-interval 3
python run_lingbot_manifest.py \
  --manifest outputs/another_113_rgb/manifest_forward_base.json \
  --out outputs/another_113_base --keyframe-interval 3
python merge_table2_forward.py --source outputs/another_113_rgb \
  --gem outputs/another_113_gem --base outputs/another_113_base \
  --out outputs/another_113_merged

python fit_table2_joint.py --input outputs/another_113_merged \
  --out outputs/another_113_frame.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python render_table2_joint.py \
  --source outputs/another_113_rgb --frame outputs/another_113_frame.json \
  --out outputs/another_sim_table2_nrr_joint.mp4
python verify_table2_video.py --video outputs/another_sim_table2_nrr_joint.mp4
```

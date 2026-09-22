# Final delivery — 2026-09-21

| Video | Duration | Frames | Resolution |
| --- | ---: | ---: | --- |
| [Simulation](outputs/final/simulation.mp4) | 38.567 s | 1157 | 1920×1080, 30 fps |
| [Real robot — indoor](outputs/final/realworld.mp4) | 31.333 s | 940 | 1920×1080, 30 fps |
| [Real robot — outdoor](outputs/final/outdoor.mp4) | 71.767 s | 2153 | 1920×1080, 30 fps |

## Visual and outcome contract

Minimal white composition with Lato Semibold: method names 30 px, target roles
22 px, arrival/stop labels 21 px. GEM blue and Baseline coral match trajectories.
Goal images get independent nested arrival frames; stopping unsuccessfully never
adds an arrival frame. Simulation A/B have both colors; C has blue only. The real
revisit goal has blue only. Successful FPVs retain green arrival outlines.

Baseline only becomes gray **after actual unsuccessful termination**, not while
still navigating. `final_video_style.failed_image()` converts to grayscale and
scales luminance by 0.48. The real third-person panel AND onboard inset are treated
consistently. Encoded grayscale channel offsets are at most ~3/255 from YUV420
round-trip conversion; unencoded source grayscale channels are exactly equal.

Recorded NavDP candidates and selected paths are retained and grounded. Real
paths use the original joint projection conventions; markings test against scene
obstacles, not each other, avoiding depth fighting. Local plans disappear after
arrival/end. Both runs play at 2× with zero inserted arrival pauses and a 1-second
final hold. Simulation's 3-second extra Baseline tail retains its explicit speed label.

The real reconstruction remains the original baseline-reversed then GEM-forward
single session: display visibility follows playback time, but reconstruction
inference itself is not a causal online two-stream comparison. Simulation uses
two independent forward sessions. Original model predictions are not changed.

## Reproduce from the project root

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/home/asus/miniconda3/envs/lingbot-map/bin/python
$PY render_table2_joint.py --source outputs/nnr003_visual_rgb --frame outputs/nnr003_joint_frame.json --out outputs/final/simulation.mp4 --theme minimal --presentation joint --cloud-mode raw --steps-per-second 20 --arrival-hold 0 --end-hold 1 --baseline-tail-seconds 3 --gem-track-width .18 --baseline-track-width .24
$PY render_real_final.py --out outputs/final/realworld.mp4
$PY verify_table2_video.py --video outputs/final/simulation.mp4 --require-gem-three-visual --require-sequence NNR
$PY verify_final_delivery.py
```

Real-world playback inputs formerly under `/tmp/claude-1000/...` are preserved at
`outputs/realworld_inputs` (telemetry, local plans, arrival records, goal and third-person
frames). Real onboard RGB remains in `outputs/cec_090850_rgb` / `base_091940_rgb`;
reconstruction remains `outputs/joint_demo_flashinfer` with `joint_frame.json`.
The new real renderer no longer relies on the temporary scratch directory.

## Verification and cleanup

Both full videos decode; real and simulation source clocks/visibility are checked.
Simulation local-plan age/leg and no-added-arrival-pause checks pass. Real arrival
and failure are independently checked against its recorded latch/clock inputs.
Failed Baseline grayscale is checked in the encoded final FPV and both real views.
[Delivery hashes and checks](outputs/final/delivery.verified.json).

Removed **114** obsolete exported videos, previews, render audits and
render logs, freeing **284.45 MB**. The exact paths, sizes and
SHA256 values are in [cleanup_manifest.json](outputs/final/cleanup_manifest.json).
Raw RGB, original experiments, reconstructed points/poses, source trajectories and
scripts are retained. `clean_final_video_assets.py` inventories by default;
`--apply` requires matching verified final-video hashes before deletion.
Historical progress is archived in `docs/history/`; its old media links are intentionally obsolete.


## Follow-up: real-world floor coverage audit

Before the floor-support update, a fixed-view ablation on every sixth eligible
observation (291 samples) shows that the old -0.08 m floor cut is only part of its
sparse floor display. Lowering it to -0.30 m raises occupied map pixels from
189,001 to 209,139 (+10.7%); -0.60 m adds no visible pixels in this sample.
Keeping the -0.30 m floor cut while relaxing confidence retention from top 35%
to top 60%, with flatness preserved, yields 248,552 pixels (+31.5% vs current).
Removing both quality masks yields 416,854 pixels, but admits visibly noisy
geometry. Removing only flatness gives 279,175; removing only confidence gives
292,656. These are sampled screen-coverage counts, not geometric accuracy.

Thus real-world coverage has a modest floor-clipping component and a larger
quality-filter contribution; it does not reproduce the simulation's primarily
floor-clipping failure. The subsequent ground-specific, past-view support experiment is recorded below.
[Controlled comparison](outputs/real_floor_audit/comparison.jpg) ·
[Measurements](outputs/real_floor_audit/report.json).
Reproduce with `audit_real_floor.py` in the lingbot-map environment.


## Real-world floor support update

`render_real_final.py` now defaults to `--floor-cloud supported`; use
`--floor-cloud original` to reproduce the preceding floor appearance.
`real_floor_cloud.py` preserves the original camera fit and strict-filtered cloud.
Only additional points between -0.30 and +0.20 m relative to the existing floor
reference use the relaxed confidence threshold (percentile 40); the original
3.5% local depth-spread filter still applies. Each additional point needs two
past same-arm observations, 0.18–1.6 seconds old and at least 3 cm translated,
whose projected depth agrees within max(5 cm, 1% range). Points keep their
predicted coordinates. This is a geometric height band, not semantic floor segmentation.

All 1,741 eligible observations were replayed. Of 615,547 supplemental candidates,
114,200 passed. Final occupied map pixels increased from 280,114 to 292,290
(+4.35%). At frame 600 the increase was 6.37%. These full-prefix measurements
are distinct from the earlier every-sixth-observation ablation. Large holes and
existing reconstruction ghosts remain; depth self-consistency is not ground-truth accuracy.
Baseline frames are processed in ascending playback time for support, despite
reversed inference storage. Existing reconstruction causality limitations remain.

[Before/after, left/right](outputs/real_floor_audit/supported_comparison_939.jpg) ·
[Measurements](outputs/real_floor_audit/supported_report.json).
Reproduce with `audit_supported_floor.py`; support logic regression:
`python test_real_floor_cloud.py` in the lingbot-map environment.

The supported version replaced `outputs/final/realworld.mp4` after full decoding
and equality checks of all 940 source-time/outcome/visibility rows against the
preceding final. `verify_final_delivery.py` passes, including both failed real
panels. Simulation hash is unchanged. Temporary candidate video was removed;
at that stage only the two deliverable MP4s remained under outputs; the outdoor
delivery below adds a third.


## Outdoor final from gem_outdoor / p035

The outdoor delivery uses the same final typography, colors, goal-arrival frame,
grounded NavDP candidates/selected plans, and Baseline failure grayscale. It has
two FPVs, since matching third-person footage was not identified. GEM arrives;
Baseline stops unsuccessfully. Both play at 2×, no arrival pause, one-second final hold.

Assets are preserved in `outputs/outdoor_inputs`. `outputs/outdoor_joint_reverse`
is the selected official demo.py/FlashInfer joint reconstruction, with GEM reversed
then Baseline forward. `outputs/outdoor_frame.json` holds the display calibration.
Raw cloud uses the -0.30 m floor-fixed cutoff and original quality filtering.
The initial opposite-order reconstruction is retained as diagnostic evidence;
its poorer whole-route scale consistency was not used for the delivery. Both
orders have residual geometry errors; the selected seam reprojection is worse
while GEM trajectory/scale consistency improves. This is an offline joint
reconstruction with timestamped visibility, not a causal online comparison.

[Outdoor sources, measurements and reproduction](OUTDOOR_VIDEO_PROGRESS.md).
Render with `$PY render_real_final.py --scene outdoor --out outputs/final/outdoor.mp4`.
`verify_final_delivery.py` also verifies outdoor when present, including all failed
Baseline frames, goal-blue-frame timing and source RGB/plan causality.
The existing indoor and simulation video files are unchanged.


Outdoor verification completed: all 2,153 frames decode, arrival-blue-frame timing
and every failed Baseline frame pass. Failure begins at frame 1465; GEM arrival
at frame 2123. `outputs/final/delivery.verified.json` now covers all three videos.


## Complete ICRA accompanying video

[Upload MP4](outputs/icra_submission/GEM_ICRA_submission.mp4) ·
[1080p master](outputs/icra_submission/GEM_ICRA_master.mp4) ·
[Storyboard](outputs/icra_submission/GEM_ICRA_storyboard.jpg).
The v24 edit adds connected narration transitions between the opening, demonstrations, method, and results, with resynthesized speech and synchronized subtitles/highlights. It retains v23 figure motion, core explanatory groups, numbered steps, and indoor-only glass-wall annotation. Duration 178 s; upload 19,009,643 bytes (19.01 MB), 1440×810, 24 fps. Verification and previews: ICRA_VIDEO_DELIVERY.md. Original three final demonstrations remain unchanged. Not uploaded.

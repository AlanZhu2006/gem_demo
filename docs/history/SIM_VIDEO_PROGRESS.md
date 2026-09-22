# Simulation video — final version

Current: [simulation.mp4](outputs/final/simulation.mp4), **38.567 s / 1157 frames / 1080p30**.
The final render uses raw floor-fixed LingBot cloud, minimal white layout and bold
labels; all recorded selected/candidate NavDP paths use ground projection and
obstacle occlusion. Arrival frames on goal images are blue for GEM, coral for
Baseline, independently latched. Failed Baseline ends in dark grayscale.
2× normal playback, no added arrival pauses, 1 s final hold, 3 s compressed tail.

Scene `VFuaQ6m2Qom`, based on Table II task 003, seed 2026091198. This is a new
visual-demo execution with shared RGB centering and aligned-v2 arrival checks,
not an unchanged formal Table II benchmark result. GEM travels 18.663 m and
reaches A/B/C visually; Baseline reaches A/B and terminates stuck in C (568 actions,
4.558 m from the goal). GT endpoint errors for GEM A/B/C remain 1.267 / 0.883 /
0.348 m: RGB arrival is not exact metric pose arrival. No pose warping is applied.

Actual paired execution: `outputs/visual_pair_formal003_aligned2_retry`.
Packaged RGB: `outputs/nnr003_visual_rgb`. Reconstruction: `outputs/nnr003_forward_joint`.
Frame calibration: `outputs/nnr003_joint_frame.json`. Both independent streams
used official LingBot `demo.py`; their shared-prefix predictions match exactly.
One GT similarity sets display scale/up/floor; paired position RMSE is 0.175 m.
The lower floor cut is -0.30 m (upper 1.10 m), preserving previously clipped floor.
NavDP source plans: 93 GEM / 107 Baseline, joined by seed and verified hash/pose.

[Verification](outputs/final/simulation.verified.json) · [Decoded arrivals](outputs/final/simulation.arrivals.jpg).
Commands and cleanup details: [FINAL_DELIVERY.md](FINAL_DELIVERY.md).
[Full historical investigation](docs/history/SIM_VIDEO_PROGRESS_before_final.md) retains
previous decisions and failure evidence; historical exported media were intentionally cleaned.

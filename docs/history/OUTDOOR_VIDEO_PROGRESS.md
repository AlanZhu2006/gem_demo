# Outdoor final — p035 / original gem_outdoor assets

The original `gem_outdoor.mp4` matches `demo_p035_gem` and `demo_p035_base`,
not p037 or the earlier o1 outdoor recordings. Original RGB, timestamps, plans,
arrival messages, command windows, telemetry and mount calibration are preserved
in `outputs/outdoor_inputs`. `provenance.json` names the original paths. The
original goal is the p035 GEM episode's `media/revisit_goal.png`.

GEM has a recorded arrival latch at 1789375627.8733265; Baseline has none.
Movement onset uses the same telemetry-based clock as the indoor final. There
are no stationary intervals removed in this pair. GEM plays 141.5 source seconds;
Baseline 97.65 seconds. At 2× plus a one-second final hold: 71.767 s / 2153 frames.
The terminal source timestamp includes the exact arrival/end event beyond the
50 ms playback clock grid.

Presentation: current final minimal white layout, two 480×270 FPVs (no matching
third-person footage identified), original image goal, blue/coral arrival frames,
recorded candidate and selected local trajectories on the ground, no added arrival
pause, unsuccessful Baseline darkened grayscale after its own termination.

Reconstruction uses the official `demo.py`, FlashInfer, original dense RGB,
CPU output offload and max_frame_num 4096. The selected session uses 2,133 GEM frames reversed then
1,581 Baseline frames forward: 3,714 frames, automatic keyframe interval 12. This matches indoor joint's shared-scene method. The display reveals
only observations already played for each arm, but inference itself is not an
online two-stream comparison. Old static survey-map pixels are not used as new
observations. Recorded depth is not used for LingBot inference.

Commands (lingbot-map environment; see lingbot_deployment.md for CUDA paths):

```bash
python prepare_outdoor_final.py
python run_lingbot_manifest.py --manifest outputs/outdoor_inputs/manifest_reverse.json --out outputs/outdoor_joint_reverse --max-frame-num 4096
python fit_outdoor_frame.py --root outputs/outdoor_joint_reverse --manifest outputs/outdoor_inputs/manifest_reverse.json
python render_real_final.py --scene outdoor --out outputs/final/outdoor.mp4
python verify_final_delivery.py
```

Preparation must precede inference; the inference output path must not already
exist. Preparation copies input assets from their original scratch directory;
subsequent reconstruction and rendering use the preserved project inputs.


## Geometry selection and limitations

The initial baseline-reverse/GEM-forward trial remains in
`outputs/outdoor_joint_flashinfer` for diagnosis. Its per-arm scale estimates
were 0.03668 / 0.05587 model units per metre (GEM / Baseline), with odometry-fit
RMSE 0.678 / 0.279 m and camera-plane p95 thickness 0.180 m.

Selected `outputs/outdoor_joint_reverse`: scale estimates 0.10250 / 0.09691,
RMSE 0.288 / 0.366 m and plane p95 0.076 m. Thus GEM and scale consistency improve;
Baseline's individual fit worsens slightly. These are comparisons with odometry,
not ground-truth accuracy. No point/pose deformation or per-arm post-alignment
was applied. Original source imagery is unchanged.

The release poses are not assumed identical. Initial seam SIFT/PnP-inlier
reprojection median was 2.08 px; selected order is 5.79 px. The selected model's
seam translation is 0.93 m using the display scale; feature-based PnP estimates
1.22 m with model depth. These are estimates, not a surveyed physical separation.
The selected order prioritizes whole-route scale/shape, not seam reprojection.
Cloud holes and residual drift remain. Measurements and sampled-view comparisons
are in `outputs/outdoor_inputs/frame_*.json`, `frame_reverse.seam.json`,
`geometry_initial.jpg` and `geometry_reverse.jpg`.

Outdoor uses `--floor-cloud floor-fixed`: original top35% confidence, 3.5% local
spread and stride4, with height band -0.30 to +1.10 m. Ground is estimated from
camera centres and archived ~0.418 m camera mounting height; metric display scale
is estimated from GEM camera/odometry correspondence. Map margin is 0.90. Local
plans use the inherited real-world coordinate convention. The model points remain
raw; no TSDF, synthetic floor fill or confidence relaxation is applied.


## Delivery verification

`outputs/final/outdoor.mp4`: 2,153 frames, 1920×1080, 30 fps, 71.7667 seconds.
All frames decoded. Source-time visibility and original arrival records agree;
Baseline turns grayscale at frame 1465 (48.833 s), GEM receives its blue goal
frame at 2123 (70.767 s). Every failed Baseline frame was checked for grayscale.
FPV and local-plan timestamps never exceed their arm's playback cut. Indoor and
simulation hashes remain unchanged. Shared `delivery.verified.json` includes all
three videos. Outdoor SHA256:
`94e6460781b237168efeaae030fca98f910c70ce2a9851729bfa299d01966543`.

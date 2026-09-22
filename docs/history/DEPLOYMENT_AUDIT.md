# Current-checkpoint pose convention audit

**2026-09-20 follow-up:** The full actual `demo.py` run is now complete for both
SDPA and FlashInfer with automatic keyframe interval 4. On 955 matched output
timestamps, body-odometry diagnostic RMSE is 0.967 m (SDPA) / 0.187 m
(FlashInfer), versus 2.389 m for the corrected old wrapper. LK median residual
is 6.264 / 2.873 px respectively. The current SDPA attention layer was also
shown to append despite `_skip_append=True`. Thus the earlier text below
saying full demo parity was not yet tested is historical. FlashInfer video
rendering and visual acceptance remain pending. See
[VIDEO_PROGRESS_HANDOFF.md](VIDEO_PROGRESS_HANDOFF.md) for current artifacts,
commands and the Claude handoff, and the dated update at the top of the shared
[deployment note](../AnchorScale/docs/lingbot_deployment.md).

The first implementation followed the deployment note's model, preprocessing,
attention, cache and confidence settings, but accepted its c2w/w2c conclusion
without independently verifying the current checkpoint. That was insufficient.
The claim that the displayed translation smearing was mainly motion-induced
drift is withdrawn.

## What was verified

- Checkpoint: `/home/asus/Research/lingbot-map/weights/lingbot-map-long.pt`.
- Repository HEAD: `63fddb3`. Working-tree changes in the attention, camera-head
  and streaming model files inspected during this audit were comments/debug
  logging. Existing changes were preserved.
- `crop`, width 518, patch 14, output 518x294; 8 scale frames, 64-frame KV
  window, keyframe interval 1; SDPA with bf16 autocast and fp32 model weights.
- Direct execution of the deployment note's `demo_render/batch_demo.py`, on
  source frame indices 130:450, produced 320 frame NPZs. Its 313 post-startup
  outputs match our saved predictions: maximum absolute depth error 0,
  extrinsic error 5.96e-8, intrinsic error 6.10e-5.
- No missing/unexpected checkpoint keys were reported by that entry point.
  The constructor's earlier empty `pretrained_path` message precedes the full
  checkpoint load; it does not mean the full checkpoint was missing.

Official outputs are retained in `outputs/deployment_audit_official/rgb/`.
This establishes agreement with that local official entry point, **not physical
correctness of its convention**. Both it and the wrapper invert the decoded pose.

## Independent direction test

Use forward/backward Lucas–Kanade correspondences, keeping tracks with cycle
error <1 px, and compare predicted pixels in the next frame using saved depth,
intrinsics and the relative pose under both interpretations. No robot pose,
scale fitting, smoothing, map optimization or image-derived pose estimate
enters this test.

For the 320-frame translation window:

| Interpretation | Median per-pair reprojection residual |
|---|---:|
| Treat previous saved `c2w` as c2w | 33.23 px |
| Invert previous saved `c2w` first | 1.45 px |

20 pairs were tested with frame gap 5 and sampling stride 15. A second sampling
with gap 10 and stride 19 yielded 13 usable pairs: corrected 1.53 px versus
41.18 px for the old direction. These strongly support the inverse of the
legacy export as the physical c2w for this code/checkpoint combination.
The global claim that all LingBot checkpoints use this convention is not made.

## Actual interactive `demo.py` check

The standard interactive entry point is `demo.py`. Comparing only the offline
export above missed an important second half of its pipeline: `demo.py:286`
inverts the decoded matrix, and `PointCloudViewer._process_pred_dict` then
inverts that exported matrix again, both for depth unprojection and for the
camera trajectory (`point_cloud_viewer.py:167,217`). Thus the original
interactive viewer agrees with our corrected direction. This was a local
integration error interpreting an export, not evidence that the official
interactive demo displays poses backwards.

`audit_demo_entrypoint.py` executed actual `demo.main` on the same 320 input
frames with SDPA and CPU output offloading. Only the server-launching viewer
constructor was replaced; geometry was evaluated with the original viewer
method on 15 sampled frames. Results are saved in
`outputs/demo_entrypoint_audit/report.json`:

- Maximum sampled world-point difference between original viewer geometry and
  our corrected projection formula, with identical inputs: 1.22e-7 model units.
- Across 313 post-startup frames, the median of per-frame median depth relative
  differences versus our existing wrapper outputs is 0.133%; the largest
  per-frame median is 0.937%.
- Maximum absolute camera matrix element difference: 0.001915 (mixed rotation
  and model-unit translation elements, not a metric trajectory error).

The remaining numerical difference includes a real precision-policy mismatch:
`demo.py` casts aggregator weights to bf16 and leaves heads fp32, while our
wrapper and the offline batch entry point retain fp32 weights with bf16
autocast. Both paths in this check used SDPA, so this does not test the default
FlashInfer backend.

For the full 962 inputs, `demo.py` automatically selects keyframe interval 4;
our existing full run used 1. Both use 64 cached frames, but the keyframe policy
changes temporal context. The full run has **not** been compared against that
actual demo default, so its failure cannot yet be attributed solely to input
motion or to the model. The 320-frame check above uses interval 1 in both paths.

`audit_pose_convention.py` saves pair-level residuals and optionally exports
fresh corrected predictions. Original predictions remain unchanged. Only the
interpretation of SE(3) changes; depth, colors, confidence selection and pixel
sampling are identical. `wrapper_c2w` preserves the old matrix.

## Result and limitations

The corrected translation video shows substantially more coherent repeated
walls. On the same 313 timestamps, diagnostic Sim(3) comparison with recorded
Go2 body odometry improves from 0.249 m to 0.091 m position RMSE. Body odometry
is not GT and the body/camera lever arm is not calibrated; this is not a
claimed 9 cm reconstruction accuracy.

The full 962-frame run still fails globally: the reprojection median improves
48.35 -> 6.59 px, but body-reference trajectory discrepancy remains large
(2.32 -> 2.39 m after separate best-fit similarities). Pose direction therefore
explains the exaggerated short-translation smearing but not all full-run error.
The opening low-translation rotation is a remaining hypothesis, not a proven
complete diagnosis. The full run must not be presented as a clean map.

Metric scaling, gravity calibration, exposure/frame-gap analysis and global
consistency checks remain separate from this convention fix. No independent
metre calibration has been applied to the rendered cloud.

## Reproduce the audit

Use the `lingbot-map` environment:

```bash
PYTHONPATH=/home/asus/Research/lingbot-map python \
  /home/asus/Research/lingbot-map/demo_render/batch_demo.py \
  --input_folder outputs/cec_090850_rgb/rgb --image_range 130:450 \
  --image_stride 1 \
  --model_path /home/asus/Research/lingbot-map/weights/lingbot-map-long.pt \
  --output_folder outputs/another_official_audit \
  --use_sdpa --no_render --save_predictions
python audit_pose_convention.py --input outputs/cec_090850_translation_probe \
  --official outputs/deployment_audit_official/rgb
```

Future local reconstructions require an explicit `--pose-convention` choice;
`raw-c2w` is the verified setting for the current long checkpoint. Other
projects' wrappers and the shared deployment notes were not modified.

# Problems found while making the video, and what actually fixed them

This is a selected list of issues that changed a command, a matrix, or a frame. Cosmetic editor taste is omitted unless it shipped. Dated notes with numbers live in `docs/history/`.

---

## 1. Translation smear was a pose inverse, not model drift

**Symptom.** Incremental clouds streaked along the travel direction. Early write-ups blamed LingBot drift.

**Cause.** The long checkpoint’s wrapper export is not viewer `c2w`. Official `demo.py` inverts the decoded pose; the official `PointCloudViewer` inverts that export again. Consuming the file as `c2w` is one inverse away from the interactive demo.

**Fix.** Independent LK cycle-consistent tracks + depth reprojection (`audit_pose_convention.py`). Invert-first: 1.45 px vs 33.23 px. `run_lingbot_manifest.py` now uses the viewer formula `closed_form_inverse_se3(extrinsic)`. Do not “correct” clouds with ICP to hide this.

**Still true.** Residual drift exists. Diagnostics vs odometry are allowed; warping points to odometry is not.

---

## 2. Matching `batch_demo.py` exports was not enough

**Symptom.** Offline NPZs matched `demo_render/batch_demo.py` to numerical noise, yet the interactive demo looked different.

**Cause.** That batch exporter stops after the first invert. The GUI path inverts again.

**Fix.** `audit_demo_entrypoint.py` ran real `demo.main` (SDPA, CPU offload), replaced only the viewer constructor, and compared world points with the official unprojection on 15 frames (max error 1.22e-7). Production jobs always go through `demo.py`.

---

## 3. FlashInfer vs SDPA, and `_skip_append`

**Symptom.** Corrected wrapper and official SDPA still had metre-scale odometry RMSE on the full indoor bag. FlashInfer on the same RGB was much tighter (0.187 m vs 0.967 m / 2.389 m).

**Cause.** The SDPA attention path was observed to append keys even when `_skip_append=True`, so the streaming cache did not match the intended policy. FlashInfer is the deployment default.

**Fix.** All delivered reconstructions use `--backend flashinfer`. SDPA remains an ablation only.

---

## 4. CUDA / ninja / `libcudart` on full-length FlashInfer

**Symptom.** Two full indoor FlashInfer jobs died during compile or runtime library discovery (`demo_full_flashinfer.log`, `*_retry.log`).

**Fix.** Point the process at the lingbot-map toolkit:

```bash
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export PATH="$CUDA_HOME/bin:$PATH"
export LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib"
```

`run_icra_montage_reconstruction.py` sets the same variables. Do not treat the failed logs as the latest result.

---

## 5. Joint order: indoor vs outdoor

**Symptom.** Outdoor reverse-Baseline / forward-GEM (the indoor recipe) gave a nicer seam (2.08 px) but GEM scale 0.037 vs Baseline 0.056 model units/m and a thick ground plane.

**Fix.** Outdoor delivery is **GEM reversed, then Baseline forward** (`outputs/outdoor_joint_reverse`): scales 0.103 / 0.097, GEM RMSE 0.288 m, plane p95 0.076 m. Seam reprojection got worse (5.79 px); that was accepted. Indoor keeps Baseline-reversed / GEM-forward.

Never blend the two orders in one render. Never run ICP between arms.

---

## 6. Floor too empty, two different causes

**Symptom.** Simulation floors vanished. Indoor floors looked sparse too; the same −0.08 m clip was applied everywhere.

**Fix.**

- Sim and outdoor: height band **−0.30…+1.10 m**, original confidence/spread. That was mostly a clip problem.
- Indoor: clip was only ~11% of the missing pixels. `FloorSupportedMap` adds a conservative multi-view supplement (see [INCREMENTAL_POINT_CLOUD.md](INCREMENTAL_POINT_CLOUD.md)). Occupied pixels +4.35% on the full prefix. Large holes remain on purpose.

TSDF hole-filling was implemented and **not** used in the finals.

---

## 7. Future points leaking into earlier frames

**Symptom.** Clouds popped in before the robot had looked.

**Cause.** Absolute ROS time was bucketed, but the bucket timestamp was the *last* observation in the bucket.

**Fix.** Bucket time is the last observation already revealed by the playback cut. `assert pt < t` in indoor floor support. Opening tiles advance `done` strictly with the 150-frame index.

---

## 8. Habitat gallery: API, roll, and a wrong dataset caption

**Symptoms.**

- `navmesh_file_path` missing on Habitat-sim 0.3.3.
- `SensorSpec.position` needed `mn.Vector3`, not a tuple.
- `bb.center` is a method; Magnum `Range3D.min/max` are properties.
- `quat_from_two_vectors` rolled the camera; houses sat on a diagonal.
- Orthographic probe rendered gray; pinhole + high elevation was kept.
- On-screen title said “HM3D and MP3D” while all six `.glb` files are MP3D.

**Fix.** `render_icra_navmesh_gallery.py` uses a Y-up look-at (`numpy-quaternion` `from_rotation_matrix`, camera −Z). Title: **Example MP3D environments**. Speech: “We also evaluate in Habitat on HM3D and MP3D.” Do not mix evaluation scope with mesh provenance.

---

## 9. Opening title bar ate the letters

**Symptom.** A 36 px vertical gradient on a 428–658 band put the top of `GEM` (124 pt, y=488, glyph top ≈ 436) in the fade. Letters sat on the moving cloud.

**Fix.** Measure the glyph mask at runtime; build a **solid** bar with 44/40 px pad; 10 px fade only outside that pad; alpha 208; lockup stays at (960,488) / (960,601) so `verify_icra_opening_title.py` still passes. No third-line footnote.

---

## 10. Method highlight boxes were inset and the wrong shape

**Symptom.** First boxes were axis-aligned with radius 12 (“crooked” on capsules). Then fill + `0.30 * min(w,h)` radius sat **inside** `Fφ`, clipped Sparse `⊥` / Dense `d_t`, and left photo frames visible around a smaller rounded rect.

**Fix.** Detect the paper PNG’s outer stroke in 2048-space (crop profiles, not a loose ink bbox). Stadiums use `radius = min(w,h)//2`. Expand 6 artboard units and stroke width 5 so the outline sits outside the original ink. Photos use a small radius; the adapter uses a card radius.

---

## 11. Table boxes missed booktabs rules

**Symptom.** `y+4 … y+h-4` left Table I’s bottom rule outside the blue box; column fractions clipped spanning headers.

**Fix.** Snap to the PNG’s dark rules (Table I y 9–660 of 666; II(a) completed row between 548–620 of 767; II(c) 242–312 / 312–385 of 388) and slightly generous column fractions. II(a) highlights **only** `A–B–C completed`.

---

## 12. Outdoor jump-cut vs speed-up

**Symptom.** A version dropped source frames 1480–1883 to save time. That deleted real travel.

**Fix.** Keep **all** 2153 frames. Compress the middle with `1658/390 ≈ 4.25` source-frames per output frame, badge **8×**. Start and end stay 3×. No editorial hole.

---

## 13. Closing card stole Table II(c)

**Symptom.** A final “GEM” page plus closing VO crushed the last table slot (tempo would exceed 1.17 or the block would be cut).

**Fix.** No closing page, no `VoiceClosing`. The video ends on Table II(c). Last empty-caption check moved from t=10.7 to **11.1** after opening speech was extended to 10.85 s.

---

## 14. Caption length and tempo

**Symptoms.** “from Matterport3D.” failed the 1.1 s minimum. A long Habitat sentence needed tempo 1.30. Phrase “and reaches it,” was 1.09 s.

**Fix.** Hard caps: caption ≤ 64 characters, ≥ 1.1 s; `atempo` ≤ 1.17. Shorten or merge phrases and resynthesize. Indoor Ava rate is `−8%` so that block can stay under the cap. Opening is the tightest block (≈ 1.12).

---

## 15. Gray footnote chrome vs one claim per beat

**Symptom.** Method/results pages accumulated small gray lists (the paper’s parenthetical style).

**Fix.** Delete that chrome. One large claim sentence, the figure or table, at most one takeaway number. Mechanism lives in speech. Do not put it back.

---

## 16. Environment gallery too long; middle-dot title

**Symptom.** First 3D-house insert ran well over 5 s; title used “HM3D · MP3D”.

**Fix.** Exactly 5 s, 90-frame yaw, title without `·`.

---

## 17. Simulation RGB arrival ≠ paper success

**Symptom.** GEM “arrives” on the sim clip while GT endpoint error is still 0.35–1.27 m. Viewers (and we) could read that as Table II.

**Fix.** Overlay and narration: qualitative visual-goal replay. Paper numbers appear only on the results pages and as spoken 25/30, 64 vs 12, 8/20→17/20. `validate_sim_arrival.py` / `sim_rgb_arrival.py` keep the latch honest to RGB, not to distance.

---

## 18. Baseline gray while still driving

**Symptom.** Early composites grayed Baseline as soon as GEM looked better.

**Fix.** Gray **after unsuccessful termination only**. Indoor FPV actually grays at source frame 480 (not 467). Outdoor at 1465. `final_video_style.failed_image()` is grayscale × 0.48 luminance. Encoded YUV420 channel offsets stay ≤ ~3/255. Verifier checks every failed Baseline frame.

---

## 19. Indoor glass wall

**Symptom.** Baseline stop needed a concrete description without claiming an internal failure mode.

**Fix.** Author-confirmed: it stops **before a glass wall**. That phrase is in the indoor block. Do not infer why the policy failed.

---

## 20. Upload 20 MB and 16:9 captions

**Symptom.** 1080p master with a white caption panel blew the size cap and looked unlike the LoGoPlanner reference.

**Fix.** Fit picture to 1792×1008, pad 1920×1080 with 64 px white sides, burn ASS at (960, 1052), then two-pass 1440×810 / 24 fps at 780 kbps (750 if needed). No appended panel. Metadata stripped.

---

## 21. Thread oversubscription

**Symptom.** Renders stalled or thrashed.

**Fix.** `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` on every compositing job.

---

## 22. Reconstruction directory reuse

**Symptom.** A second inference into an existing folder mixed two sessions.

**Fix.** `run_lingbot_manifest.py` and `lingbot_incremental.py` refuse an existing `--out`. Always mint a new directory. `encode_icra_voiceover.py` copies the previous upload into `visual_cut_v9/` once; that folder is a local rollback, not a source of truth.

---

## 23. Absolute paper path

**Symptom.** Fig. 1 is loaded from `/home/asus/Research/Nav-graph-blind/projects/paper/...`. A clone of this GitHub repo will not find it.

**Fix.** Documented, not vendored (the PNG is manuscript art). Point `FIG` in `render_icra_submission.py` at a local copy if you rebuild elsewhere. The table PNGs **are** in `outputs/icra_submission/paper_tables/`.

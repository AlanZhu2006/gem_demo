# ICRA accompanying video — production

Current delivery: `outputs/icra_submission/GEM_ICRA_submission.mp4`

| Spec | Value |
|---|---|
| Duration | 178.006 s (limit 180 s) |
| Upload | 19,009,643 bytes (limit 20 MB), 1440×810, 24 fps, 4272 frames |
| Silent master | 1920×1080, 30 fps, 5340 frames (`GEM_ICRA_master.mp4`, local only) |
| Audio | AAC mono, Ava `en-US-AvaMultilingualNeural`, ≈ −16 LUFS |
| Anonymity | no author/institution on screen |
| Locked inputs | `outputs/final/{realworld,outdoor,simulation}.mp4` are never rewritten |

Encoding record: `outputs/icra_submission/encoding.json` (version 24). Verification: `outputs/icra_submission/submission.verified.json`. Spoken text: `outputs/icra_submission/ENGLISH_SCRIPT.md`.

## Timeline (v24)

| Time | Frames (30 fps master) | Section | Picture |
|---|---:|---|---|
| 00:00–00:11 | 330 | opening | 3×3 incremental clouds, indoor hero pull-back, two-line title |
| 00:11–00:32 | 630 | indoor | `realworld.mp4` at 3× |
| 00:32–00:56 | 720 | outdoor | all 2153 source frames; middle travel at 8×, start/end at 3× |
| 00:56–01:01 | 150 | environments | 2×3 MP3D Habitat orbits, 5 s |
| 01:01–01:22 | 630 | simulation | `simulation.mp4` retimed N–N then Revisit |
| 01:22–02:15 | 1590 | method | camera tour of paper Fig. 1, 53 s |
| 02:15–02:58 | 1290 | results | Table I 20 s, II(a) 12 s, II(c) 11 s; **no closing card** |

330+630+720+150+630+1590+1290 = 5340.

Order is demonstration-first: indoor → outdoor → environment gallery → simulation → method → tables. There is no end title.

## Local machines and environments

| Role | Path / env |
|---|---|
| This repo | `/home/asus/Research/pengyue/gem_demo` |
| LingBot-Map (official `demo.py`, long checkpoint) | `/home/asus/Research/lingbot-map` |
| Render / verify Python | `/home/asus/miniconda3/envs/lingbot-map/bin/python` |
| Habitat gallery | `/home/asus/miniconda3/envs/habitat/bin/python` |
| TTS | `/tmp/gem-voice-env/bin/python` + `edge-tts` |
| Paper Fig. 1 | `/home/asus/Research/Nav-graph-blind/projects/paper/figures/gem_architecture_pic_20260915/GEM_architecture_pic_slide2.png` |
| MP3D meshes | `/home/asus/Research/datasets/mp3d_official_20260814/extracted/mp3d` |

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` is required around NumPy/OpenCV compositing. Without it, thread oversubscription makes renders slower and can hang.

## Two layers of work

1. **Source clips** (`outputs/final/*.mp4`). Built from incremental LingBot reconstructions plus recorded RGB/plans. Documented in [INCREMENTAL_POINT_CLOUD.md](INCREMENTAL_POINT_CLOUD.md). These three files are frozen. Indoor drawing uses `joint_frame.json`; outdoor uses `outputs/outdoor_frame.json`; simulation uses `outputs/nnr003_joint_frame.json` (not the historical root `sim_frame.json`).
2. **ICRA cut**. `render_icra_submission.py` samples those clips, composites the opening / gallery / method / tables, then `build_icra_voiceover.py` + `encode_icra_voiceover.py` add Ava and captions.

Do not mix the layers. Re-running LingBot does not update the submission until someone *intentionally* replaces a file in `outputs/final/` and re-verifies it.

## ICRA cut pipeline

```
outputs/final/{realworld,outdoor,simulation}.mp4
outputs/icra_submission/montage_motion/*/tiles/*.jpg     # opening clouds
outputs/icra_submission/navmesh_gallery/<scene>/*.jpg    # 90 yaw frames each
paper Fig. 1 PNG + paper_tables/{table_i,table_ii_a,table_ii_c}.png
        │
        ▼
render_icra_submission.py
        │
        ├─ GEM_ICRA_master.mp4          1920×1080 / 30 / silent
        └─ assembly.audit.json          hashes of paper + source clips
        │
        ▼
build_icra_voiceover.py                 atempo-fits cached MP3s, writes WAV + SRT/ASS
        │                               records visual_master_sha256
        ▼
encode_icra_voiceover.py
        │  scale 1792×1008, pad 1920×1080 (64 px sides, captions at y=1052)
        │  two-pass 1440×810 / 24 fps, 780 then 750 kbps if needed
        ▼
GEM_ICRA_submission.mp4
        │
        ▼
verify_icra_voiceover.py
verify_icra_opening_title.py
```

### Opening (11 s)

Implemented in `icra_spatial_design.SpatialDesign.opening`.

- Nine independently reconstructed scenes, tiles 640×360, 150 frames of growing clouds each.
- Grid order: courtyard, living, terrace, stage, indoor, garden, gallery, atrium, hall.
- Indoor is the hero: it starts at 1×1, zooms 3×→1× from t=2.5–5.0 s while the other eight start streaming at t=2.5 s.
- A small live RGB inset on the indoor tile fades out 2.5–4.0 s; the rest of the grid is cloud-only.
- Title is a **full-width solid bar** fitted to the glyph bounding box of `GEM` (124 pt) and the subtitle, with a 10 px fade *outside* the bar only. Persistent, centered, two lines. No third-line footnote.
- Overlay is cached; it does not depend on `t`.

Opening tiles come from `prepare_icra_motion_montage.py` → `run_icra_montage_reconstruction.py` → `render_icra_cloud_tiles.py` (or the motion-montage variant). Telemetry is used only to *pick* moving frames. It is never an input to LingBot.

### Indoor / outdoor / simulation

`sample_segments` in `render_icra_submission.py` maps source frames onto the master clock.

- Indoor: 940 source frames → 630 output frames (uniform, labeled 3×).
- Outdoor: **keep every source frame** 0–2152. Segments `(0,225)@1.5` labeled 3×, `(225,1883)@4.25` labeled 8×, `(1883,2153)@1.5` labeled 3×. Do not jump-cut the long travel.
- Simulation: A 0–364, C 365–1034, arrival tail 1035–1156, mixed 3×/4×/3×.

Overlays are lean: a title (`Indoor revisit` / `Outdoor revisit` / `Memory across goals`) and a speed badge. When Baseline can no longer reach the active goal, `stop_card` draws “Baseline does not reach the goal” on the map (indoor FPV gray at source 480; outdoor at 1465; simulation once GEM has arrived at 1035).

### Environment gallery (5 s)

`render_icra_navmesh_gallery.py` in the Habitat 0.3.3 env renders 90 yaw frames per house with a Y-up look-at so floors stay horizontal. On-screen title is **Example MP3D environments**. Spoken line is “We also evaluate in Habitat on HM3D and MP3D.” The six glbs are all MP3D; HM3D is evaluation scope, not the mesh source. See [ISSUES.md](ISSUES.md).

### Method (53 s)

`icra_paper_method.py`: one claim sentence per beat, camera tour of the *actual* Fig. 1 PNG (2048×1019 artboard coordinates). Phases 0/10/20/37 s:

1. Frozen model relates every RGB frame — highlight `Fφ`, then Dense/Sparse readouts.
2. History is written by motion — panel (b) claims only, no gray footnotes.
3. A past view is useful only if it connects to now — photos, loc/ver pills, cache, bearing.
4. The controller stays frozen — readouts + adapter.

Highlight rectangles are the **outer stroke** of each paper element, drawn as stadiums (`radius = min(w,h)//2`) for pills and a milder radius for photos/cards, expanded 6 artboard units so a 5 px outline sits outside the original ink.

`icra_voice_timing.py` can bind a highlight to a spoken clause; v24 still uses the phase clock plus a few hard starts (5.0 s, 39.4 s). If you change `caption_phrases`, rebuild alignment *before* rendering.

### Results (43 s)

`icra_paper_results.py` pastes the paper PNG crops and boxes booktabs rules:

- Table I: Revisit SR → ΔSR → Novel SR, y snapped to rules at 9 and 660 of the 666 px crop.
- Table II(a): footer row `A–B–C completed` only (64 vs 12).
- Table II(c): Revisit row, then Novel row. Video **ends here**.

Side numbers 25/30 vs 4/30 are paper-wide real-world totals, also spoken during outdoor.

## Narration and captions

- Voice: `en-US-AvaMultilingualNeural`, rate `+0%` (indoor block `−8%`).
- Script: `outputs/icra_submission/narration/script.json`.
- Cached MP3 + Edge word timestamps (`*.jsonl`) live next to the script.
- `build_icra_voiceover.py` fits each block into its slot with `atempo` **≤ 1.17**. If a block would exceed that, shorten the text and resynthesize; do not raise the cap.
- Captions: single line, Lato-like DejaVu Sans 52, black fill, white outline, `\\pos(960,1052)` on the padded 1920×1080 frame. Max 64 characters, min 1.1 s. No extra white caption panel.
- Empty-caption probe is at **t = 11.1 s** (after opening speech ends at 10.85 s).

## Verification that must stay green

`verify_icra_voiceover.py` checks: duration 178 s, ≤ 20 MB, 1440×810 / 24, progressive, AAC mono, source-clip hashes vs `assembly.audit.json`, visual MAE between master and padded narrated master, caption ink, Baseline gray ROIs, loudness ≈ −16 LUFS, every speech block has RMS.

`verify_icra_opening_title.py` checks 300 opening frames: `GEM` and the subtitle stay white, and a left-edge band of the title bar stays dark (`mean < 160`). If you move the lockup, update that mask.

## What not to do when polishing

- Do not change `outputs/final/*.mp4`.
- Do not put author names, logos, or a closing “GEM” card back in.
- Do not restore gray footnote chrome on method/results pages.
- Do not skip outdoor frames 1480–1883; speed the middle instead.
- Do not feed odometry, depth, or Habitat GT pose into LingBot.
- Do not “fix” clouds by TSDF, ICP, or loop closure for the delivered picture. Display filters only.

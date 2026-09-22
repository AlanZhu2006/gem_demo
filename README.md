# GEM accompanying video

This repository is the production record for the **ICRA 2027 accompanying video** of GEM (Geometric Episodic Memory). It keeps the method, the locked source clips, the 178-second submission encode, and a written account of the incremental point-cloud pipeline — including mistakes that actually changed the picture.

The **LingBot operations handbook** is [`docs/lingbot_deployment.md`](docs/lingbot_deployment.md). Read that before running reconstruction. NPZ sessions stay on the lab disk (~45 GB); GitHub holds the handbook, scripts, display calibrations, audit JSON, locked clips, and the project-site media.

| File | Role |
|---|---|
| [`outputs/icra_submission/GEM_ICRA_submission.mp4`](outputs/icra_submission/GEM_ICRA_submission.mp4) | Submission encode (v24): 178 s, 19.01 MB, 1440×810 / 24 fps |
| [`outputs/final/realworld.mp4`](outputs/final/realworld.mp4) | Indoor Go2 revisit, 31.333 s, 1080p30 |
| [`outputs/final/outdoor.mp4`](outputs/final/outdoor.mp4) | Outdoor Go2 revisit, 71.767 s, 1080p30 |
| [`outputs/final/simulation.mp4`](outputs/final/simulation.mp4) | Habitat N–N–R pair, 38.567 s, 1080p30 |

**Do not regenerate or replace** the three files under `outputs/final/`. The ICRA edit retimes them; it does not re-infer them.

## Documents

1. [LingBot-Map operations handbook](docs/lingbot_deployment.md) — environment, pose convention, FlashInfer, joint sessions, verification. **Read this first for reconstruction.**
2. [Historical issue log](docs/lingbot_deployment_history.md) — archive only; do not copy commands from it
3. [How the 178 s video is assembled](docs/PRODUCTION.md)
4. [Incremental point clouds](docs/INCREMENTAL_POINT_CLOUD.md) — RGB-only streaming, display filters, opening 3×3 grid
5. [Problems and how they were fixed](docs/ISSUES.md)
6. [Local vs published files](docs/DATA_LAYOUT.md)
7. Dated lab notes: [`docs/history/`](docs/history/)

## Rebuild the ICRA encode (from locked clips)

Requires the local LingBot / Habitat / paper-figure paths described in `docs/PRODUCTION.md`. From the repo root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/home/asus/miniconda3/envs/lingbot-map/bin/python

# 1) 1920×1080 / 30 fps silent master (5340 frames)
$PY render_icra_submission.py

# 2) Align cached Ava speech to the new master hash (no new TTS)
$PY build_icra_voiceover.py

# 3) Burn captions, pad to 16:9, encode ≤20 MB upload
$PY encode_icra_voiceover.py

# 4) Spec + hash + loudness checks
$PY verify_icra_voiceover.py
$PY verify_icra_opening_title.py
```

Changing narration text additionally needs `/tmp/gem-voice-env/bin/python synthesize_icra_narration.py` before step 2.

## Rebuild a source clip (does not replace `outputs/final/`)

Incremental reconstruction is a **separate** job from the ICRA edit. Re-render from the existing NPZ session; write somewhere other than `outputs/final/`:

```bash
PY=/home/asus/miniconda3/envs/lingbot-map/bin/python
$PY render_real_final.py --scene indoor --out /tmp/realworld_rebuild.mp4
$PY render_real_final.py --scene outdoor --out /tmp/outdoor_rebuild.mp4
```

Full geometry rules, pose convention, joint-session order, and the re-infer commands: [docs/INCREMENTAL_POINT_CLOUD.md](docs/INCREMENTAL_POINT_CLOUD.md).

## What this video claims, and what it does not

The demonstrations are **paired visual replays** with a frozen NavDP (or Habitat policy) plus GEM recall. Point clouds are **offline timestamped visualizations** of LingBot-Map predictions. They are not online GEM memory, not metric maps, and not the paper’s distance-based success test (simulation uses an RGB arrival latch). Paper-wide numbers in the narration (25/30 vs 4/30, Table I/II) come from the manuscript, not from counting the two selected robot clips.

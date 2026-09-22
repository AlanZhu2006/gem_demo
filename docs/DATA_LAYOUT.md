# What is in git, what stays on the lab disk

The GitHub repo is a **method + deliverable** package. The machine that made the video still has ~45 GB under `outputs/` that must not be pushed.

## Tracked (this repository)

| Path | Why |
|---|---|
| `*.py`, `vendor/` | Reconstruction, render, verify, ICRA assembly |
| `docs/` | Production method, incremental clouds, issues, dated history |
| `joint_frame.json` | Indoor joint display scale / floor (`outputs/joint_demo_flashinfer`) |
| `ground_frame.json`, `ground_frames.json` | Earlier *separate-arm* indoor diagnostics (not the delivered joint session) |
| `sim_frame.json` | Historical `outputs/sim_3leg_demo` frame; **not** the delivered NNR clip |
| `outputs/outdoor_frame.json` | Outdoor display calibration (GEM-reversed joint session) |
| `outputs/nnr003_joint_frame.json` | Delivered simulation display calibration (two forward sessions) |
| `outputs/final/realworld.mp4` | Locked indoor clip (7.4 MB) |
| `outputs/final/outdoor.mp4` | Locked outdoor clip (15 MB) |
| `outputs/final/simulation.mp4` | Locked sim clip (18 MB) |
| `outputs/final/*.verified.json` | Frame counts, hashes, arrival checks |
| `outputs/icra_submission/GEM_ICRA_submission.mp4` | ICRA upload encode (19.01 MB) |
| `outputs/icra_submission/encoding.json` | v24 encode record |
| `outputs/icra_submission/submission.verified.json` | Last PASS |
| `outputs/icra_submission/ENGLISH_SCRIPT.md` | Spoken text as shipped |
| `outputs/icra_submission/GEM_English.srt`, `GEM_English.ass` | Captions |
| `outputs/icra_submission/narration/script.json` | Slots, phrases, Ava settings |
| `outputs/icra_submission/narration/*.mp3`, `*.jsonl` | Cached TTS + word timestamps |
| `outputs/icra_submission/paper_tables/table_{i,ii_a,ii_c}.png` | Paper crops used on screen |

## Local only (gitignored)

Do not delete these on the lab machine unless you are sure you will never re-render. They are just too large for GitHub.

| Path | Approx. | Role |
|---|---|---|
| `outputs/joint_demo_flashinfer` | ~2.1 GB | Indoor joint LingBot session |
| `outputs/outdoor_joint_reverse` | ~4.7 GB | Outdoor joint session (delivered) |
| `outputs/outdoor_joint_flashinfer` | ~4.8 GB | Outdoor order ablation |
| `outputs/nnr003_forward_*` | ~2 GB | Sim reconstructions |
| `outputs/icra_submission/montage_motion` | 3.1 GB | Opening 3×3 clouds + tiles |
| `outputs/icra_submission/montage`, `montage_plans` | ~3.1 GB | Earlier opening attempts |
| `outputs/icra_submission/navmesh_gallery` | 49 MB | 90 yaw stills × 6 MP3D houses |
| `outputs/icra_submission/GEM_ICRA_master.mp4` | 51 MB | Silent 1080p30 master |
| `outputs/icra_submission/GEM_ICRA_narrated_master.mp4` | 47 MB | Captioned 1080p master |
| `outputs/cec_090850_*`, `base_091940_*` | several GB | Indoor RGB + pose-convention audits |
| `outputs/visual_pair_*`, `outputs/screen_*` | many GB | Habitat paired runs feeding the opening selection |
| `outputs/realworld_inputs`, `outputs/outdoor_inputs` | ~0.6 GB | Plans, RGB manifests, calibration |
| `outputs/final/ICRA26.mp4` | 23 MB | **Third-party** LoGoPlanner reference; not published here |
| `gem_indoor.mp4`, `gem_outdoor.mp4` | 31 MB | Pre-LingBot historical cuts |
| `IMG_*.MOV` | ~0.7 GB | Phone dumps, unused by the pipeline |

## Intentionally removed from the workspace (2026-09-22)

Duplicate ICRA encodes and QC stills that were only rollback copies:

- `outputs/icra_submission/before_{method_expansion_v21,refinement_v22,transitions_v23}/`
- `outputs/icra_submission/narrated_v10/`, `narrated_v11/`, `narrated_v11_gray/`
- `outputs/icra_submission/visual_cut_v9/`
- `outputs/icra_submission/qc_v14/`, `qc_v15/`
- `outputs/icra_submission/check_*.jpg`
- `__pycache__/`

Reconstruction sessions and locked `outputs/final/` clips were **not** deleted.

## Third-party / private paths

Paper Fig. 1, LingBot weights, MP3D meshes, and ROS bags are **not** in this repo. Commands in the docs use absolute paths on the lab workstation. A public clone can play the MP4s and read the method; it cannot re-run inference without those dependencies.

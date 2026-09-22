# Longer NNR scene selection — 2026-09-20

Requested change: better-looking indoor scene, longer GEM route, and less
screen time dominated by Baseline failure. Previous visual-demo GEM path was
9.859 m; the previously selected archive's 25.46 m does not describe the new
visual-arrival execution.

Scanned all 508 inventory tasks: 23 NNR tasks have archived GEM 3/3.
Read original RGB and complete pose traces for expansion 381, 138 and 253
from the remote archives, without reconstructing or modifying source results.
Sparse RGB samples include each goal and nine observations per leg; review
sheets show goal, start, quarter, midpoint and last saved frame.

## Preferred candidate: expansion 138

Scene `759xd9YjKW5`, episode 0015. Archived GEM paths A/B/C:
**7.172 / 6.742 / 4.586 m**, total **18.500 m**, 552 actions.
Route x/z extent **8.824 × 3.904 m**. Sum of per-leg starting geodesics
**15.903 m**. Baseline A/B match GEM's action counts, then C ends **stuck at
395 actions**, versus GEM C 147. Baseline's C path is 8.447 m.

Visual inspection favors its furnished interior, recognizable doorway/stair
landmarks and mostly continuous visible surfaces over 381's extensive black
mesh gaps. This is a qualitative sparse-frame assessment, not a guarantee of
low LingBot drift. View [RGB sheet](138_rgb.jpg) and [route plot](138_route.png).

| Candidate | GEM total / A+B+C (m) | Archived Baseline | Assessment |
| --- | --- | --- | --- |
| 138 | 18.50 / 7.17+6.74+4.59 | C stuck, 395 actions | Preferred: interior quality and shorter failure tail |
| 381 | 23.90 / 10.04+8.35+5.51 | C max_steps, 600 actions | Longer spatial spread; extensive missing mesh in RGB; B detours |
| 253 | 20.59 / 5.51+7.78+7.30 | C succeeds, 424 vs GEM 239 actions | Attractive long route if successful-but-slower Baseline is acceptable |
| 187 | 25.76 / 17.13+4.74+3.89 | C max_steps, 600 actions | Not shortlisted: A geodesic only 3.12 m versus 17.13 m traveled |

All figures above are **archived distance-threshold results**, not validated
visual-latch runs. Archived success cannot substitute for the real RGB gate.
New online goal construction and visual terminal alignment can change both
the trajectory length and outcome, as they did in the previous NRR scene.

## Execution and presentation requirements for the next video

1. Generalize `run_visual_pair.py`: it currently hardcodes NRR and uses
   `role='revisit'` for both B/C. NNR requires actual novel goal construction
   at B and revisit construction at C. Preserve continuous own state and the
   same centering/arrival logic for both methods.
2. Generalize `prepare_visual_pair.py` and `render_table2_joint.py`: sequence,
   per-leg Novel/Revisit labels, and N/R badges are currently hardcoded NRR.
   Merely relabeling an NRR trajectory as NNR is invalid.
3. Check new A/B/C geodesics and total executed route before expensive final
   reconstruction. Prefer an 18–25 m executed route with useful spatial spread,
   not a long clip due to terminal turning or repeated loops. The 18.50 m
   archive value is a selection signal, not a promised rerun result.
4. Make GEM's A/B/C the main narrative. Keep both methods synchronized through
   GEM's completion. Then explicitly fast-forward the remaining Baseline tail
   in about 3 seconds to its actual termination, followed by a short ending.
   Fast-forward the entire display clock and both geometry streams together;
   expose acceleration in the image and audit. Do not change failure criteria,
   pretend it failed at GEM's completion, or reveal future cloud during normal
   playback. This pacing policy also applies if Baseline eventually succeeds.
5. For archived 138 as a timing example: GEM ends after 552 observations;
   Baseline after 800. At 15 observations/s, the 248-observation tail occupies
   16.53 s; compressing only that tail to 3 s means about 5.51× acceleration.
   With 4.5 s arrival holds and a 3 s ending, approximate total is 47.3 s.
   Recompute timings from the actual new visual execution.

NNR's two novel legs share the same underlying novel controller in these
archived comparisons; their tracks coincide through A/B. The meaningful
separation appears in C (revisit). Keep the wider red under narrower blue
shared-prefix presentation; do not manufacture an earlier divergence.

Raw inspection metrics: [inspected.json](inspected.json).
All 23 candidates: [all_successful_nnr.json](all_successful_nnr.json).
Reproduce sampling: execute `sample_table2_archives.py 381 138 253` with Python
on the archive host, redirect stdout to `samples.tar`, then run local
`inspect_nnr_candidates.py`. No new full navigation run or video is claimed.

## Visual rerun progress

`visual_pair_138_centered1`, seed 2026120199: GEM A failed at 600 actions,
20.268 m path, terminal goal distance 5.786 m, zero RGB centering turns.
This is navigation failure before usable terminal alignment. It must not be
substituted for the archive's A success. The matching Baseline run is finishing;
next trial will record a new seed explicitly. Sequence generalization and
optional shared-clock tail acceleration are implemented; the old NRR video's
1667-frame timing is unchanged when acceleration is disabled.

Further 138 trials: seed 2026120200 (centered2) ended stuck at 178 actions for both arms. Seed 2026120201 (centered3) GEM A exhausted 600 actions; Baseline is finishing. The original-seed first action matches archive position exactly; maximum first-plan coordinate difference is 2.12e-6 m. Closed-loop trajectories nevertheless diverge. Preparing archived NNR 253 as a fallback with the same visual-arrival profile; original outcomes will not be assumed.

## 253 successor-construction finding

`visual_pair_253_centered1`, original seed 2026120035: both A runs latched
at 165 actions (5.477 m traveled, 1.015 m GT goal distance, 22.35 degrees
heading error). B had no admissible novel goal under the original 60-degree
forward proposal limit. This is construction failure, not B navigation failure.
The unchanged RGB gate is not an exact-pose certificate.

The original long B target lies 8.116 m away at -68.38 degrees after actual
visual stopping. A read-only construction probe with a **90-degree novel
proposal limit** recovers exactly that archived target: max history and current
view covisibility are both zero. All novelty/revisit support rules, renderer,
navmesh, runtime policy and RGB arrival thresholds are unchanged. The new
`construct_visual_goals.py` records original/modified constructor hashes and
its executed source; the external benchmark constructor is untouched.

`visual_pair_253_wide1` is a fresh complete paired run with
`--novel-max-route-angle 90 --visual-centering --park-idle`. This explicitly
changes the demo task proposal profile, not the formal Table II experiment.
The video footer will disclose wider novel goals as well as shared centering.
There is no A suffix splicing or restored/replayed policy history.

## Goal-view variant, restoring original NNR proposal rules

The original A image faces a side room (yaw pi/2). Visual alignment therefore
leaves the next long corridor outside the original forward proposal band.
253 wide1 B became stuck at 279 actions; changing the B planning seed to
2026120036 in schedule1 still exhausted 600 actions. Wide2 changed the global
seed to 2026120036 and failed A at 326 actions. Wide2 and schedule1 were
explicitly interrupted after GEM failure; incomplete Baseline runs are not
claimed as results. Their `selection_stop.json` and `abort.json` preserve this.

A separate, predefined task variant uses **archived GEM A observation 157** as
the A goal image, at its recorded pose/yaw, fixed before new navigation.
`prepare_view_goal_variant.py` independently verifies the original task rules:
5.122 m geodesic, initial route angle -52.865 degrees, 3585 surface points,
zero initial-view covisibility (no prior history). The goal's heading is
0.54866 rad, facing along the corridor rather than into the side room.
This is an explicitly changed A image goal, not a reproduction of original
Table II targets or a target moved after observing the new run's endpoint.

`visual_pair_253_view1` starts a fresh lifecycle from the original start with
this task bundle, original seed 2026120035 for all legs, original 60-degree
novel construction rule, unchanged real-world RGB verifier thresholds and
shared centering. B/C remain actual-history common online goals. No GT enters
policy control. Full pose/depth is used only for task validation and later
display scale/up/floor. The footer discloses the archived A view.
Provenance: `253_view_goal/provenance.json`; source bundle contains the original
source and updated A query/sequence, not a claim to contain the full archive.

## Simulation alignment profile

The predefined archived A view exposed a real arrival-quality issue: the
unchanged real-world defaults latched at 2.461 m with image scale 0.6054.
`visual_pair_253_view1` is retained but rejected for presentation and explicitly
interrupted; this stop is not a B navigation failure.

`visual_pair_253_aligned1` uses the same verifier implementation with stricter
RGB-only settings, **identical for both methods**: image scale 0.90–1.12,
center offset <=0.10, minimum coverage 0.20, minimum inlier ratio 0.65. Other
thresholds and single-frame latch confirmation are unchanged. No GT distance
is added to stop authority. All settings appear in protocol, arm manifests,
leg results and packaged metadata; the video footer identifies aligned RGB
arrival. A/B/C use the original seed 2026120035, original 60-degree novel
proposal bound, continuous own state, shared centering and CPU parking.

First GEM A result: 189 actions, 4.965 m traveled, goal distance 0.456 m,
heading error 6.03 degrees; 163 good matches / 116 inliers, coverage
0.5385/0.4479, center offset 0.0537, image scale 0.9009. B/C remain pending.
This is a stricter simulation configuration, **not the unchanged real-world
threshold profile** and not a formal Table II result.


## Latest superseding status: raw-depth audit and A40 calibration

The early preferred-candidate notes above are historical selection reasoning,
not successful new executions. See `visual_trial_inventory.json` for measured
results. `visual_pair_253_aligned1` B failed 600 actions for both methods.
`screen_241_aligned1` A stuck at 474; `screen_253_A40_aligned1` A stuck at 323,
although the latter reached a stable pose by step 176, 0.478 m and 3.91 degrees
from its predefined A reference. Strict aligned thresholds rejected its scale
0.8521 and inlier ratio 0.6080. `aligned-v2` was calibrated against this positive,
the previous 0.456 m positive and the rejected 2.461 m negative; saved checks
are in `aligned_v2_gate_validation.json`. A fresh run is required afterward.

The A40 task preserves original A position and sets target yaw to 40 degrees
before execution (`253_A40_goal/provenance.json`). It is a changed demo target.
The original B reference will NOT be forced into this run: the raw-depth audit
`253_A40_stop176_B_check.json` finds max historical visibility 0.3645, whereas
legacy saturated depth PNGs incorrectly give zero. The local constructor now
re-renders raw depth at all actual history poses for BOTH Novel and Revisit
support. Existing support thresholds and original 60-degree Novel route bound
remain. The original external Table II code and results are untouched.

Current fresh GEM-only screen: `screen_253_A40_aligned2`. It uses no preferred
B target, the corrected history depth, 96 Novel proposals per distance band,
minimum 350 goal keypoints and at most 20% near-black goal pixels. Such a screen
is explicitly not a paired comparison and cannot be packaged as one.


### 253 A40 outcome and 385 scene fallback

`screen_253_A40_aligned2` completed as a failed GEM-only screen. A latched at
176 actions, 6.109 m traveled, 0.478 m endpoint error. Corrected full-depth
Novel sampling selected a 4.001 m B goal; B exhausted 600 actions, traveled
18.797 m and ended 8.773 m away. No C was attempted. `raw_depth_novel_guard`
independently confirms rejection of the previously seen original long B goal.
The expanded B pool (`A40_B_pool/gallery.jpg`) contains only 2–4 m and ~4 m
views with pronounced mesh artifacts. This scene is no longer preferred.

Sparse archives 385 and 048 were inspected next. 048 is rejected for extensive
black/missing geometry. 385 (`VFuaQ6m2Qom`) has clearer indoor structure;
archive GEM path is only 10.912 m, geodesic sum 12.973 m, so it is a scene-quality
fallback, not yet evidence of meeting the preferred longer route. Its archived
Baseline C is stuck at 510 actions. See `385_rgb.jpg` and `385_route.png`.

Fresh `screen_385_aligned2`, original seed 2026120398: A stuck at 299 actions,
3.567 m traveled, endpoint 0.826 m from goal; raw RGB verifier has only 16
homography inliers, so no arrival. A source-image variant from the archive's
last A observation was rejected BEFORE execution because its initial route
angle 67.81 degrees exceeds 60. No invalid variant was created or used.

Current independent screens: `screen_385_seed399` retains the original A goal
and explicitly changes the seed to 2026120399. `screen_385_A60` retains original
seed and A position, but predefines A yaw -60 degrees before new execution;
its task-construction receipt is `385_A60_goal/provenance.json`. Both retain
aligned-v2 RGB thresholds, original Novel route bound, raw-depth history checks,
actual continuous state and the same shared centering. Neither is a paired result.


### Successful fresh screen: formal 003, NNR, 18.663 m

`screen_formal003_aligned2` finished GEM A/B/C with visual arrival at actions
67 / 175 / 446. Actual lengths: 2.339042 / 6.273917 / 10.050012 m. Starting
geodesics: 3.292774 / 6.699565 / 6.726310 m. Endpoint errors: 1.266675 / 0.883202 /
0.347875 m. The total 18.662971 m includes a C detour and should not be described
as 18.66 m of spatial extent. A/B visual goal/current comparisons are saved in
`formal003_AB_arrivals.jpg`; view alignment does not certify an identical pose.

Original A image, start and seed are retained. B/C are newly constructed from
actual histories, with full-precision depth support, original role thresholds
and 60-degree Novel direction rule. C support maximum is 0.819732, current
visibility 0, source perturbation 0.22 m / 12 degrees. B maximum history and
current visibility are both zero. Both subsequent geodesics exceed 6.6 m.
The full paired rerun `visual_pair_formal003_aligned2` now uses exactly these
settings. No successful screen is being relabeled as a completed comparison.

385's original-goal second seed and A60 variant both failed A. The isolated
RGB-only translation probe reduced one failed endpoint's goal error from
0.826 to 0.402 m but did NOT reach the gate; it is not integrated into navigation
or any final-video source. `probe_rgb_translation_servo.py` is diagnostic only.
NRR 359 was inspected but rejected for severe outdoor missing geometry.


The first full pair `visual_pair_formal003_aligned2` reproduced A for both arms
but aborted during GEM B due to CUDA OOM caused by concurrent speculative
GEM reconstruction. This is an execution-resource error, NOT navigation failure.
`resource_abort.json` records it; the incomplete pair is excluded from video.
Finish the official reconstruction and then restart both navigation lifecycles
from scratch, sequential with all further GPU reconstruction. No unrelated GPU
process was stopped. Reuse of a screen reconstruction requires identical full
RGB hashes/timestamps verified by `merge_table2_forward.py` before merging.

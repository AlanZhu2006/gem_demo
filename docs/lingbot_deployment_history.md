# LingBot-Map 历史问题日志（存档，2026-09-20 归档）

> **这份是存档，不是操作说明。** 当前的操作手册是
> [`lingbot_deployment.md`](lingbot_deployment.md)，请以它为准。
>
> 本文件保留 2026-09-20 之前的完整排查过程、失败证据和被推翻的结论，
> 只用于追溯「某个数字是怎么来的」。**其中若干结论已被证伪或只在特定配置下
> 成立**，最主要的三条是：
>
> 1. `§0 recipe` 里 `extrinsic (3x4 c2w after demo.py inversion)` —— 该简写只
>    适用于读轨迹，用于点云会漏掉 viewer 内部的第二次取逆。
> 2. `VERIFIED CORRECT` 里 `SDPA ≡ FlashInfer` —— 仅在 `keyframe_interval = 1`
>    下成立。
> 3. `ISSUE A` 的「FIXED / poses are EXCELLENT」—— 只覆盖轨迹读数，不覆盖点云
>    消费链路。
>
> 不要从本文件复制命令或结论去跑新实验。

---

# LingBot-Map Deployment Notes & Issue Log

**Scope:** how to run LingBot-Map correctly in this project, the bugs that have bitten us
(with verified fixes), and the parts of the pipeline that are confirmed correct. Read this
before running LingBot or trusting its poses/clouds.

## 2026-09-20 更新：GEM 点云视频接入审计（先读此节）

本节记录 `/home/asus/Research/pengyue/gem_demo` 的实测问题。适用范围是本机
`/home/asus/Research/lingbot-map`，HEAD `63fddb3`，权重
`weights/lingbot-map-long.pt`。仓库已有 attention / camera-head / streaming
调试修改，审计期间保留，未修改共享模型代码。**不要把下文历史 Issue A、
“VERIFIED CORRECT”或“SDPA 等价”当作当前接入链路已经验证的结论。**
也不要反向推断所有历史 Habitat 实验或其他 checkpoint 的约定都错了。

### 1. 已确认：导出位姿的语义不能只凭字段名判断

- 当前 `demo.py:286` 对 decoded extrinsic 取逆。
- 但实际交互查看器 `lingbot_map/vis/point_cloud_viewer.py:167` 又把这个
  extrinsic 交给 `unproject_depth_map_to_point_map`，该函数内部再次取逆；
  同一查看器在约第 217 行还直接取逆来生成相机轨迹。
- 因此**完整的 `demo.py → viewer` 链路，与仅把导出 extrinsic 当作 c2w
  消费，不是同一个变换**。GEM 的第一版只对齐前半段，把 wrapper 导出直接
  当 c2w，漏看查看器里的第二次变换，造成明显平移重影。
- 原版交互 demo 的显示方向与 GEM 修正后相符。这是当前本地接入对导出矩阵的
  解释错误，不能表述成“官方 demo 的位姿整体反了”。历史 recipe 中
  `extrinsic (3x4 c2w after demo.py inversion)` 的说明不能直接用于当前点云接入。

独立验证使用图像前后向 LK 跟踪（cycle error <1 px）、模型深度和内参，
不使用里程计来修正位姿。320 帧平移窗口的 20 对图像中，逐对重投影残差
中位数的中位数从 **33.23 px 降到 1.45 px**；另一组间隔采样为
**41.18 px 对 1.53 px**。相同 313 个时间戳上，与 Go2 机身里程计做独立
最佳 Sim(3) 对齐，位置 RMSE 从 0.249 m 降到 0.091 m。
**机身里程计不是真值，相机/机身杆臂未标定，不能称为 9 cm 重建精度。**

实际调用 `demo.main` 的 320 帧验证还保留了原模型加载、精度转换、推理和
后处理；仅替换启动服务器的 viewer 构造器，并调用原版 viewer 的几何处理
方法抽样比较。15 帧抽样点坐标最大差异为 **1.22e-7 模型单位**。
证据：`gem_demo/outputs/demo_entrypoint_audit/report.json`。

### 2. 已确认：batch_demo / wrapper 与 demo.py 并非所有设置都相同

- `demo.py` 将 aggregator 权重转为 bf16，heads 保持 fp32；原 wrapper 和
  此次使用的 batch 路径保留 fp32 权重、使用 bf16 autocast。
  同一 320 帧窗口的逐帧深度相对差异中位数，再取中位数为 0.133%，最大
  逐帧中位数 0.937%。这是输出差异，不是对真值的误差。
- `demo.py` streaming 自动选择关键帧间隔：<=320 帧为 1，否则
  `ceil(N/320)`；本次 962 帧为 **4**。原 incremental wrapper 固定为 **1**。
- demo 默认后端是 **FlashInfer**，旧 GEM 路径使用 SDPA。64 帧缓存相同，
  不代表保留的历史上下文相同。
- `batch_demo.py --save_predictions` 与 wrapper 在 320 帧窗口几乎逐元素
  一致（depth 最大差 0、extrinsic 5.96e-8、K 6.10e-5），仅证明导出路径
  一致，不能代替对交互查看器、关键帧策略或物理正确性的检查。

### 3. 已复现：当前 SDPAAttention 忽略非关键帧 skip 标志

`lingbot_map/layers/attention.py` 的 `SDPAAttention.forward` 在当前代码中，
即使 cache 的 `_skip_append=True`，仍追加 k/v。独立小规模调用中缓存帧数
从 1 变为 2，本应保持 1。模型 `gct_stream.py` 确实会为非关键帧设置此标志。
FlashInfer 的对应路径实现临时 append、attention、rollback。

这意味着**当前 SDPA + keyframe_interval>1 不能视为默认 FlashInfer 的等价
实现**；只修改命令行关键帧间隔不够。该问题尚未在共享仓库修复。
证据：`gem_demo/outputs/sdpa_skip_append_audit.json`。不能仅凭这个小测试
量化它对完整重建的影响，需要完整后端对照。

### 4. 全程验证状态与输入限制

输入为 `episode_20260919T090850_042322Z`，962 帧，62.30 秒。当前已完成：

| 路径 | 同时间戳轨迹诊断 RMSE | 重投影残差中位数 |
|---|---:|---:|
| 旧 wrapper / SDPA / interval 1，已修正位姿解释 | 2.389 m | 6.594 px |
| 实际 demo.py / SDPA / 自动 interval 4 | 0.967 m | 6.264 px |
| 实际 demo.py / FlashInfer / 自动 interval 4 | **0.187 m** | **2.873 px** |

轨迹指标均为对机身里程计做最佳 Sim(3)，不用于修改视频点云，不是真值准确率。
两组还同时涉及权重精度、关键帧策略等差异，不能把全部收益归于单一参数。
FlashInfer 全长推理和逐帧导出已正常结束，955 个输出时刻完成相同诊断。
与同为 demo.py / bf16 / interval 4 的 SDPA 相比明显改善，支持后端行为差异确实
影响本序列。但这仍不证明全部收益仅由 skip 标志造成，也不代表全图已无误差。
视频渲染尚待接手。完整 FlashInfer 对照的最新状态见
[`VIDEO_PROGRESS_HANDOFF.md`](../../gem_demo/VIDEO_PROGRESS_HANDOFF.md)。
**全程视觉和局部几何一致性仍需验收；不能继续把剩余误差直接归因于开头旋转。**

源图像 sensor timestamp 单调，但间隔不均匀：中位数 33.36 ms，p90 为
133.42 ms，p99 为 314.06 ms，最大 834.66 ms，58 处超过 200 ms。
提取程序保留了所选时间范围的全部 RGB 消息。这是记录流存在间隔的证据，
尚非对漂移原因的证明。证据：`gem_demo/outputs/source_timing_audit.json`。

点云仍为模型单位；两次既有首帧地面拟合都失败，展示使用 camera-up fallback，
尚未获得可靠重力方向。禁止因此给视频加米制刻度或直接叠加机身轨迹。

### 5. 本机 FlashInfer 启动环境

此次真实运行先后遇到 `ninja` 不在 PATH、链接器找不到 `-lcudart`。
安装文件本来存在，无需重装或改动共享环境；进程级配置为：

```bash
export PATH=/home/asus/miniconda3/envs/lingbot-map/bin:$PATH
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export LIBRARY_PATH=/home/asus/miniconda3/envs/lingbot-map/targets/x86_64-linux/lib${LIBRARY_PATH:+:$LIBRARY_PATH}
```

配置后已成功进入完整 FlashInfer 推理。开头 `pretrained_path: ''` 的报错来自
构造器的空预训练路径；后续完整 checkpoint 加载成功且无 missing/unexpected keys，
不要把前一行单独解读为权重没有加载。

本次详细证据和脚本见
[`DEPLOYMENT_AUDIT.md`](../../gem_demo/DEPLOYMENT_AUDIT.md)；视频状态、原始输入、
下一步和 Claude 交接见
[`VIDEO_PROGRESS_HANDOFF.md`](../../gem_demo/VIDEO_PROGRESS_HANDOFF.md)。

### 6. 为什么第一次没做对：误导来源与逐条更正

这一节记录归因，不是复盘情绪。目的是让下一个接手的人不要再走同一条路径。

判断依据是版本对照：本节加入之前的提交版为
`git show HEAD:docs/lingbot_deployment.md`（1539 行，不含 2026-09-20 节），
下面「旧文档」一律指那一版，也就是本次动手时唯一能读到的内容。

| 踩的坑 | 旧文档当时怎么写 | 实际情况 | 为什么容易踩 |
|---|---|---|---|
| 把导出 `extrinsic` 直接当 c2w 喂给点云 | §0 recipe 明写 `extrinsic (3x4 c2w after demo.py inversion)` | 对**轨迹读数**成立；对**点云消费**不成立，viewer 内部还会再取一次逆 | recipe 是照抄的地方，字段简写盖过了正文里的链路说明 |
| 用 `--use_sdpa` 当默认 FlashInfer 的替身 | §0 写 `--use_sdpa (math-identical, ~0.02% depth diff, just slower)`；VERIFIED CORRECT 列 `SDPA ≡ FlashInfer`；连官方入口示例命令本身都带 `--use_sdpa` | 仅在 `keyframe_interval=1` 下成立。interval>1 时 SDPA 忽略 `_skip_append`（见 §3） | 旧结论没写验证时的配置；旧 wrapper 固定 interval=1，所以当年根本测不出来。旧文档全文 `skip_append` 出现 **0 次** |
| 沿用 wrapper 固定的 `keyframe_interval=1` | 旧文档全文 `keyframe_interval` 只出现 **1 次**，未记录 demo 与 wrapper 的差异 | `demo.py` streaming 自动取 `ceil(N/320)`，962 帧为 4；wrapper 硬编码 1 | 文档没写，只能靠读源码发现 |

**关于位姿这一条要说公道话**：旧 ISSUE A 的 Fix 段里其实有一句正确线索——
「`unproject_depth_map_to_point_map` still consumes the same raw w2c matrix and
inverts internally」。这句是对的，也正是这次的坑。它之所以被漏掉，是因为
ISSUE A 通篇讨论的是**轨迹读数**（ATE、相机中心），标题写的是 camera-pose，
结论收在「**FIXED**」「poses are EXCELLENT」并附 0.06/0.16/0.14 m 的 ATE。
读到这种收尾，合理的判断就是这条链路已经清了。所以问题不在于「写了没看」，
而在于**正确的线索被放在一个结论为「已修复」的、面向另一种消费方式的章节里**。

**据此定下的写作规则（以后新增结论必须遵守）：**

1. **结论必须带适用范围。** 写「已修复 / 已验证」时，同时写清是在**哪条消费
   路径**上验证的。ISSUE A 只覆盖轨迹读数，不覆盖点云消费链路。
2. **字段简写不能替代链路说明。** 凡是写「导出字段 = 某约定」，必须紧跟一句
   「下游还有谁会再变换一次」。否则 recipe 会把人导向错误用法。
3. **「等价」结论必须写出验证时的配置。** `SDPA ≡ FlashInfer` 是在 interval=1
   下测的，就要写明；没测过的配置不要让读者以为已覆盖。
4. **一次只改一个设置。** 本次 SDPA→FlashInfer 同时改了后端、权重精度、关键帧
   策略三样，所以无法把收益归因到单一原因。要定论就做同精度同后端、只改
   interval 的消融。
5. **不要用滤点掩盖重影。** 先把几何/约定查清楚，再谈显示策略。

### 7. 本轮最终状态：视频已渲染并由用户验收

第 4 节表中定量最好的一条（demo.py / FlashInfer / auto interval 4）已完成渲染：

- 产物：`gem_demo/outputs/gem_lingbot_demo_flashinfer.mp4`
- 规格：31.27 s，1280×720，2× 播放，15 FPS，469 视频帧，955 个点云时刻
- **causal visibility 检查 PASS**（点云严格按原始 ROS log 时间戳出现，未提前
  泄漏后续观测；前 8 帧为共同尺度锚点，第一份点云自第 8 帧起显示）
- 审计：`gem_lingbot_demo_flashinfer.audit.json`，四时刻预览同名 `.jpg`
- 本步**没有重复任何 GPU 推理**，只执行：

```bash
python render_lingbot.py --input outputs/cec_090850_demo_flashinfer \
  --out outputs/gem_lingbot_demo_flashinfer.mp4
```

用户已确认该效果可接受。**但下列各项仍未解决，不要因为视频通过就当作收尾：**

- 点云仍为模型单位；两次首帧地面拟合均失败，展示用 camera-up fallback，重力
  未标定。**禁止**给视频加米制刻度或直接叠加机身轨迹。
- 共享仓库的 SDPA `_skip_append` 缺陷**未修复**，仅记录并绕开。
- 收益无法归因到单一参数（见上条规则 4）。
- 源时间戳 58 处 >200 ms、最大 834.66 ms，尚未与重投影异常的位置做关联。
- 显示策略为置信度 top 35% + pixel stride 4，是本视频的选择，**不是**原版
  viewer 默认。
- GEM / Baseline / 手机第三视角的组合视频尚未恢复（历史 `demo_n_*`、`rgbd_n_*`、
  `n_grid.npz` 等缺失，跨 session 的尺度/坐标注册未做）。


---

## 0. How to run LingBot correctly (the recipe)

- **Checkpoint:** `lingbot-map-long.pt` (only one on this box; README-recommended for long/large
  scenes). The GPU reference pipeline uses the *balanced* `lingbot-map.pt` — see Issue C.
- **Loader:** `load_and_preprocess_images(mode="crop", image_size=518, patch_size=14)` — exactly
  what the public `demo.py` / `batch_demo.py` use.
- **Mode:** `streaming` for ≤320 frames; `windowed` only for very long (>320 cached) sequences.
- **Attention:** FlashInfer (needs `CUDA_HOME`=conda-env so nvcc can JIT) — or `--use_sdpa`
  (math-identical, ~0.02% depth diff, just slower). ~6–7 FPS either way on this box.
  > ⚠️ **2026-09-20 更正（见顶部 §3）**：`math-identical` 只在
  > `keyframe_interval = 1` 下成立。interval>1 时 `SDPAAttention.forward` 忽略
  > `_skip_append=True` 仍追加 k/v，与 FlashInfer 的 append→attention→rollback
  > **不等价**。全长实测 SDPA 0.967 m / 6.264 px vs FlashInfer 0.187 m / 2.873 px。
  > 长序列请用默认 FlashInfer，不要为了省事换 SDPA。
- **Frame density matters:** LingBot is *streaming* — keep small inter-frame motion. Use dense
  frames (stride 1 from a smooth walk); don't aggressively subsample.
- **Keyframe interval（2026-09-20 补充）：** `demo.py` streaming 会**自动**选
  `keyframe_interval`：≤320 帧为 1，否则 `ceil(N/320)`（962 帧 → 4）。
  `anchorscale` 旧 wrapper 硬编码为 1。要复现官方行为就别自己写死这个值；
  若要对照，必须同精度同后端、只改 interval。
- **Official offline entry point:**
  ```bash
  python lingbot-map/demo_render/batch_demo.py \
      --video_path X.mp4   # or --input_folder DIR for image folders
      --model_path lingbot-map/weights/lingbot-map-long.pt \
      --output_folder OUT --target_frames 150 --image_stride 1 \
      --use_sdpa --no_render --save_predictions   # ⚠️ --use_sdpa 见上方更正；
                                                   # 长序列请去掉它走默认 FlashInfer
  ```
  Saves per-frame NPZ: `pose_enc, depth, depth_conf, extrinsic (3x4 c2w after demo.py inversion),
  intrinsic, images (0..1 RGB)`.
  > ⚠️ **2026-09-20 更正（见顶部 §1）**：`c2w` 这个简写只适用于**读轨迹**。
  > 做**点云**时不能把导出矩阵直接当 c2w 消费——官方
  > `point_cloud_viewer.py:167` 会把它交给 `unproject_depth_map_to_point_map`，
  > 该函数**内部再取一次逆**（同文件约 217 行另有一次直接取逆用于画轨迹）。
  > 漏掉这第二次变换会产生明显平移重影：修正前后逐对重投影残差中位数
  > 33.23 px → 1.45 px。
  (The flythrough *renderer* has a `world_points_from_depth` bug — but `--save_predictions` works,
  so consume the NPZs directly.)
- Our wrapper `anchorscale/backbone/lingbot.py` now reproduces this path exactly.

---

## ISSUE A — ⚠️ camera-pose c2w/w2c inversion bug (CRITICAL, FIXED)

**Symptom:** LingBot trajectories looked ~2 m wrong on Habitat (ATE 11–17% of path), which led
to a WRONG conclusion that "Habitat's renderer is OOD for LingBot's pose." Depth/geometry were
simultaneously fine (AbsRel ~4.7%).

**Root cause:** `anchorscale/backbone/lingbot.py:_postprocess` confused the raw model convention with
the official demo output convention. `pose_encoding_to_extri_intri` returns OpenCV camera-from-world
extrinsics (w2c); `demo.py` then immediately calls `closed_form_inverse_se3_general` before exposing or
saving `predictions["extrinsic"]` as c2w. Treating the raw w2c matrix as c2w makes
`extrinsic_c2w[...,3]` a w2c translation, not the camera center → every trajectory read is wrong.

**Proof it was extraction, not the model:** the official `batch_demo.py` scored **0.06 m** ATE on
the exact Habitat episode my wrapper scored 2.19 m; after applying the same demo.py inversion, the
wrapper matches the official pose convention. So inference was identical; only the pose read was wrong.

**Fix:** build a 4x4 from the raw `extrinsic`, invert it with `closed_form_inverse_se3_general`, and
expose that as `extrinsic_c2w`. `unproject_depth_map_to_point_map` still consumes the same raw w2c
matrix and inverts internally. After fix, wrapper ATE: **smooth 0.06 m, castle 0.16 m, apt_0
0.14 m (~0.5–1% of path).**

**Corrected conclusion:** LingBot poses are EXCELLENT on **both Habitat and real footage**. Habitat
is NOT OOD. Both are viable for the nav pipeline (Habitat adds a free GT collision/occupancy oracle).

> ⚠️ **2026-09-20 适用范围标注（见顶部 §1 / §6）**：本节的「FIXED」与
> 「poses are EXCELLENT」**只覆盖轨迹读数**（ATE、相机中心），**不覆盖点云
> 消费链路**。上面 Fix 段那句「`unproject_depth_map_to_point_map` still
> consumes the same raw w2c matrix and inverts internally」才是点云的关键，
> 但它被放在一个标题为 camera-pose、结论为已修复的章节里，2026-09 的 GEM
> 接入因此漏读，造成平移重影。做点云前请先读顶部 §1。

**How to diagnose c2w-vs-w2c next time:** compute camera centers BOTH as `extrinsic[...,3]` and as
`-R^T t`, take ATE of each vs GT — the small one tells you the convention. (`/tmp/.../settle.py`.)

---

## ISSUE B — low-confidence floaters (FIXED; confidence selection is correct)

**Symptom (FOXGLOVE debug):** the cloud looked like a scattered, isotropic blob with no
recognizable structure.

**Cause (measured):** low-`depth_conf` "floater" points dominate the depth spread (~2× inflation).
Filtering by confidence percentile collapses it: top 65% → z-extent 1.43; **top 30% → 0.91**
(matches the GPU's 0.87); top 10% → 0.32.

**Fix / standing practice:** gate points on `depth_conf` (top ~30–45%). Confirmed on demo3 (real):
conf > p55 removed floaters and brought the room extent **19 m → 6.3 m** (a realistic office).
**Confidence selection is correct and necessary** — keep it in every cloud/occupancy step.

---

## VERIFIED CORRECT (do not re-investigate)

> ⚠️ **2026-09-20**：本节结论**各自带适用范围**，不要整段当成「当前接入链路
> 已验证」。下面 SDPA 那一条已被推翻（见顶部 §3）；「Pose extraction is now
> correct」只针对轨迹读数（见顶部 §1）。

- **RGB → 3D-point projection is correct.** `unproject_depth_map_to_point_map(depth, extrinsic, K)`
  (official) + per-pixel RGB pairing (both flattened in pixel order) yields **coherent geometry**:
  floor-plane thickness **2.0 cm (demo3, real)** / **2.8 cm (apt_0, Habitat)**, recognizable colored
  top-down. A wrong projection or color-pairing would smear the floor to tens of cm / scramble color.
- **Confidence selection (Issue B) is correct** — validated by floater removal above.
- **Pose extraction is now correct** (Issue A fix) — ATE ~1% on Habitat GT.
- ~~**SDPA ≡ FlashInfer** for depth (0.02% diff)~~ — ⚠️ **2026-09-20 已推翻**：
  该等价只在 `keyframe_interval = 1` 下成立（当年 wrapper 固定为 1，故测不出）。
  interval>1 时 SDPA 忽略 `_skip_append`，与 FlashInfer 不等价，见顶部 §3。
  以下两项仍成立：checkpoint loads 1342/1342 tensors cleanly; the
  point-cloud back-projection from depth+K+pose is the official path (ckpt has no `point_head`).

---

## ISSUE C — residual cloud fuzziness vs GPU reference (OPEN, non-blocking)

Even at matched confidence, our cloud is slightly fuzzier than the GPU reference pipeline
(`semantic-scale-map`). Remaining differences: **(1) checkpoint** — ours `lingbot-map-long.pt` vs
the reference balanced `lingbot-map.pt` (not on this box; pull from HF `robbyant/lingbot-map` /
ModelScope if needed); **(2) loader** — the GPU's `lingbot_demo.load_images` vs the public
`load_and_preprocess_images` (we match the public repo). This affects *sharpness*, not the ~1%
poses or the ~2–3 cm floor, so it does not block the nav pipeline.

---

## ISSUE D — ⚠️ long-sequence / loop POSE DRIFT smears the cloud (OPEN; the real "weird cloud" cause)

**Symptom:** on a full robot teach LOOP, the accumulated colored cloud looks flat/scattered (a noisy sheet,
no crisp walls) even after correct confidence gating and gravity leveling. RViz shows a fuzzy ring, not a room.

**NOT the cause:** floaters (gating top-35% only cut 338k→145k pts, still scattered) or frame density
(every-3rd vs every-6th — both scattered). Verified: a **dense 320-frame STREAMING segment reconstructs
CLEANLY** — flat floor at z≈0 + vertical structure to ~0.5m. So LingBot's LOCAL geometry is correct on this data.

**Root cause (measured):** raw LingBot **streaming poses DRIFT** over a long loop. On a 36.1m teach loop the
trajectory had a **3.78m start→end gap** (~10% drift, horizontal; z stable). Revisited locations land at
different map positions → the cloud smears. The doc's clean 2cm-floor validations were all **short, non-loop**
sequences (≤320 frames, streaming) where drift hasn't accumulated. (TinyNav's pose-graph map on this data also
fails to close: 6.5m gap — loop closure is not recovering global consistency here.)

**Implication:** a clean full-loop colored cloud needs **loop-closure / pose-graph-optimized poses**, NOT raw
LingBot streaming poses. This is the [[odometry-sim3-loop-closure]] problem (LingBot = good local odometry, a
loop needs closure). Options: (a) keep maps SHORT (streaming chunks ≤320 dense frames — clean but no full loop);
(b) add pose-graph optimization to the LingBot builder using reloc-detected loop closures (real work);
(c) accept the cloud is functional-for-nav (reloc 7.2cm + occupancy validate) even if the raw viz is imperfect.
The cloud quality is a VISUALIZATION limit, not a nav-functionality blocker.

**Loop closure ATTEMPTED (2026-07-01) → BLOCKED by the data.** Built `tool/loop_close.py` (pose graph:
sequential edges + reloc loop edges, solved by `tinynav_cpp_bind.pose_graph_solve` — the deployment's own
solver). On the real teach bag it found **NO reliable long-range loop closures**: appearance retrieval gave
only short-range matches (index span 16–60, zero >100); brute-force geometric search of all far pairs gave
best **42 inliers (<100 needed)**; forcing weak 40-inlier constraints made the drift WORSE (3.78→4.04m, because
reverse-heading matches give wrong relative poses). So the loop's revisit is **reverse-heading / weak overlap**
(the [[odometry-sim3-loop-closure]] blocker). The tool is correct and will close a loop on a **loop-friendly
teach** (a clean same-heading return-to-start pass); this bag just doesn't contain one. Fix = re-record the
teach with a deliberate same-heading loop-closing segment, OR accept the functional map.

---

## ISSUE E — ⚠️ "scattered for ALL, not just an endpoint seam" DECOMPOSED (2026-07-01)

The user's sharp objection: pure drift should give only a **start-vs-end seam**, not a cloud that's fuzzy
**everywhere**. Correct — and concrete tests show the smear is TWO distributed effects, neither of which is a
rigid endpoint offset. Tested on `mono_map_074106` (dense stride-2, streaming, fixed-gravity floor metric;
scripts in `/tmp/claude-1000/{spatial,depthgate,unwarp}.py`):

- **single frame floor = 2.0 cm** (clean) vs **accumulated = 10.7 cm** (within |x,y|<1.5 m of origin).
- **Depth-gating gives NO change** (10.7 cm from <6 m down to <1 m; the floor points are ALL near, <1 m
  depth). → the smear is NOT far-view depth noise.
- **Revisit-doubling is NOT it**: single-visit cells 18 cm ≈ multi-visit 21 cm, and the trajectory visits
  each 0.4 m cell only **0–1×** (few crossings).
- **So the local smear = PER-FRAME POSE JITTER**: each frame's *clean* near-floor patch is laid down at a
  slightly-wrong z/pitch, so accumulating many frames of the SAME near floor spreads it 2→11 cm. It's
  distributed (every frame is a little off), not one accumulated translational offset → fuzzy everywhere,
  no discrete seam. (This is also why TSDF made it WORSE, ISSUE-adjacent: the poses genuinely disagree, so
  averaging bakes in the spread.)
- **PLUS a global NON-RIGID WARP**: floor mean-z varies **38 cm** across the 7 m map in a smooth **bowl/
  saddle** (not random). LingBot accumulates small *pitch/scale* errors every segment, so the whole
  reconstruction **curves**. A rigid loop-closure can't flatten a bowl — which is exactly why loop closure
  (ISSUE D) barely helped. A degree-3 floor **detrend** removes the 38 cm bowl but NOT the 11 cm local
  jitter (they're independent), so it doesn't rescue the look.

**Bottom line:** "scattered for all" = distributed per-frame pose jitter (local) + non-rigid pitch/scale
warp (global). Both come from imperfect streaming pose estimation, NOT depth (depth is 2 cm-clean).

## ISSUE F — the ROTATION / motion-parallax root cause + what actually helps (2026-07-01)

**Same physical teach-and-repeat loop reconstructs very differently** (bags on asus
`{loop_run1(teach),repeat_loop1(repeat)}`, see [[lingbot-teach-bags]]):
| | teach (loop_run1) | repeat (repeat_loop1) |
|-|-|-|
| single-frame floor | 8 cm | **2.6 cm** |
| accumulated floor | 19 cm | **6.8 cm** |
| duration / path | 96 s / 27.5 m | 50 s / 18 m |

**Length is NOT the driver** (proven): reconstructing only the teach's first 50 s still gives 6.9 cm
single-frame (nowhere near the repeat's 2.6 cm), and in that 50 s the robot travelled only **5.5 m** vs the
repeat's **18 m**. The driver is **motion PARALLAX**: LingBot depth is multi-view and needs *translation*
baseline. The human **teach** moves slow + pauses + rotates in place (0.1 m/s, lots of yaw) → tiny baseline
→ poor depth AND jittery pose. The autonomous **repeat** drives smooth-forward (0.36 m/s steady
translation) → strong baseline → clean depth + stable pose. (Optical-flow magnitudes MATCH at 0.16 px —
same motion *quantity* — but the teach's is useless ROTATION flow, the repeat's is useful TRANSLATION flow.)

**Fixes, most→least practical:**
1. **Operational (proven, do this): map from a smooth forward pass** — steady translation, minimal in-place
   rotation, one clean sweep, don't linger. The autonomous repeat is ideal; a human teach should be driven
   quickly/smoothly. `repeat_loop1` → clean room; `074106` meander → scattered.
2. **Frame selection at build time**: drop/keep-out rotation-dominated (low-inter-frame-translation)
   keyframes from the cloud — they contribute parallax-starved depth + jittery poses. Implemented as
   `LINGBOT_DEMOTE_ROTATION_GEOMETRY=1 scripts/build_lingbot_map.sh ...`; the builder records
   `geometry_keyframes.mode=rotation_pivot_geometry_demote` in `scale.json`. These frames are treated as
   rotation/panorama pivots, not metric 3D anchors.
3. **Global pose fix is HARD here**: rigid loop-closure can't undo the non-rigid warp; ICP global
   optimization FAILS (floor-plane sliding makes it worse); bigger KV window OOMs; official windowed mode
   drifts MORE (1.84 m). So there is no cheap pose-graph rescue for a bad (rotational) recording — fix it at
   capture time (#1).

**Official-demo reconciliation:** LingBot's clean long GitHub demos are **forward traversals** (translation,
no revisit); loops with hesitation are the failure case. Our per-frame depth matches their quality (2 cm);
we only lose it by feeding rotational/hesitant motion.

**DEEP FIX — floor-planarity dense BA WORKS (2026-07-01, `/tmp/claude-1000/floorba.py`).** We CAN correct the
drift structurally (not just at capture), via a global-optimization backend on LingBot's dense pointmaps (the
MASt3R-SLAM idea, floor-constrained slice). Prototype: per keyframe, fit its (clean 2 cm) local floor plane,
derive a RIGID pitch/roll/z correction rotating that plane → global z=0 about the camera centre, lightly
temporally smoothed, applied per frame. Result on `074106`: **center-floor 10.7 → 3.7 cm** (≈ the 2 cm
single-frame limit); side view goes from a 24 cm fuzzy band to a thin floor line; **top-down unchanged** (it
only touches the vertical, so horizontal room shape is preserved — correctly). Confirms the smear is
correctable pose error, NOT depth. Productionization note: (1) robust/RANSAC per-frame plane + reject
poor-floor frames (a few over-corrected → below-floor outliers keep the global metric at 23 cm); (2) add the
HORIZONTAL geometric BA (dense point alignment across overlapping frames) to fix x/y/yaw wall drift, which
floor-BA leaves untouched; (3) wire as a build_lingbot_map post-stage. This is the real structural
contribution ("LingBot-SLAM backend"); the rotation/parallax *depth* jitter remains capture-limited.

**NO-ILLUSION WALL CHECK (2026-07-02).** Added
`go2_mono_nav/tool/diagnose_lingbot_overlap_certificate.py` and `--save-frame-clouds` provenance export in
`tool/lingbot_native_map.py`. This directly measures whether temporally separated points on the same wall
collapse to one layer. Important result: the old floor/wall-thickness quality gate can pass while provenance
still fails. Rebuilt `pivot2` and `endpoint_only` baselines with provenance:

| Map | Old gate | Endpoint | Floor p90 | Wall p90 | Provenance verdict |
|-|-|-:|-:|-:|-|
| `lingbot_map_repeat1_c2wfix_pivot2_kv64_colorfix` | PASS | 0.000 m | 2.41 cm | 5.80 cm | FAIL / not certified |
| `lingbot_map_repeat1_submap_endpoint_only_se2_kv64_colorfix` | PASS | 5.58 cm | 2.75 cm | 5.94 cm | FAIL / not certified |

At a 0.70 m coarse wall cell, the pivot baseline exposes 6/10 conflict cells and 25 cm p90 early-vs-late wall
separation. This matches the user's Foxglove complaint: vertical/floor consistency is mostly solved, but
horizontal wall overlap is not. Do not claim a globally clean 3D reconstruction until the provenance certificate
passes. Next backend work must add dense wall/submap overlap residuals and/or Go2 yaw/odom factors for
rotate-in-place spans.

**DENSE-OVERLAP PROTOTYPE RESULT (2026-07-02).** Added
`go2_mono_nav/tool/dense_submap_overlap_loop.py`: submap split → wall-height SE(2) ICP → robust SE(2)
submap graph → exported provenance cloud. Tested both a rotation-demoted raw map and a non-demoted raw map.
Strict gates accept **zero** dense loop edges. Loose gates accept one late→start edge, but it has only
2.7-5.7 mm ICP RMSE improvement and makes endpoint drift worse (`0.64 m → 0.66-0.71 m`). So dense ICP alone
is not the loop detector; it should remain a verifier/factor after better candidate generation.

The local `repeat_loop1` and `loop_run1` bags do **not** contain usable Go2 odometry/IMU. Topic inspection shows
RealSense image/depth/camera_info and static RealSense `/tf` only; no `/odom`, `/imu`, body angular velocity,
`/cmd_vel`, or Go2 low-state. The yaw-factor fix for rotate-in-place drift is still the right observability
split, but it requires future bags to log robot motion streams synchronized with camera frames.

**MOTION-FACTOR TOOLING (2026-07-02).** Added
`go2_mono_nav/tool/audit_rosbag_motion_topics.py` and yaw-prior support in
`tool/dense_submap_overlap_loop.py`. The dense graph now accepts `--yaw-prior-csv` with either direct
`frame_key,yaw_rad` rows or timestamped yaw rows aligned by `timestamps.csv`. `scripts/local_bag_extract.py`
now writes that `timestamps.csv` for future bags. Smoke-tested with LingBot's own yaw: 345 yaw rows → 3
submap yaw edges → zero displacement, as expected for a self-consistent prior. The timestamp-alignment path
was also smoke-tested with 345 synthetic timestamped yaw rows. This verifies the factor path without pretending
it fixes the current map.

For the next teach/repeat recording, record at least:

```bash
ros2 bag record \
  /camera/camera/color/image_raw \
  /camera/camera/color/camera_info \
  /camera/camera/aligned_depth_to_color/image_raw \
  /tf /tf_static \
  /odom /imu /cmd_vel \
  /sportmodestate /lowstate
```

**ELEGANT BACKEND DIRECTION (2026-07-02).** Heavy literature review points to a map-centric
observability-gated backend, not more plain BA. The proposed design is **Certified Map-Centric Pivot-Yaw
Submap SLAM**: translation-rich LingBot frames create dense metric submaps; rotate-in-place spans create
yaw/SO(3), panorama, and retrieval factors only; Go2 odom/IMU/body-yaw constrains pivot rotation; floor/walls
act as weak structural factors and hard validation gates; loop candidates are accepted only if dense
provenance overlap improves. This matches BundleFusion/ElasticFusion/Loopy-SLAM/LoopSplat style map correction,
Rotation-Only BA for pivot spans, and planar-inertial/proprioceptive SLAM for degenerate robot motion.

Synthetic mechanism check added in `go2_mono_nav/tool/simulate_observability_gated_loop.py`. With injected
8 deg pivot-yaw bias, odometry-only gives 0.564 m endpoint gap and 0.391 m revisit-wall p90. Adding pivot yaw
factors gives 0.032 m endpoint and 0.034 m wall p90; yaw plus verified loop gives 0.0009 m endpoint and
0.002 m wall p90. A false dense edge improves endpoint to 0.333 m but still leaves 0.208 m wall p90, proving
again that endpoint closure is not a sufficient success metric. This is synthetic only; real validation needs
the next bag to include synchronized robot motion topics.

Synthetic sweep added in `go2_mono_nav/tool/sweep_observability_gated_sim.py`:
`output/loop_closure_research/sim_observability_sweep` has 500 experiments / 2500 case rows plus
`yaw_prior_pass_rate_heatmaps.png` and `endpoint_vs_wall_gate.png`. Result: clean external yaw makes the
pivot-yaw backend robust to 12-16 deg LingBot pivot drift, but 3 deg external yaw-prior noise usually fails
the strict 6 cm revisit-wall certificate. So the next real backend must estimate yaw-prior covariance and
reject/downweight slipping robot yaw; do not use robot odom as a hard truth source.

Topic names may differ on the Go2 stack; run `ros2 topic list` first and keep the equivalent base odom/twist,
IMU/angular velocity, commanded velocity, and Go2 low-state topics. Before rebuilding a LingBot map, run:

```bash
conda run -n lingbot-map python tool/audit_rosbag_motion_topics.py BAG_DIR \
  --json-out output/loop_closure_research/BAG_motion_audit.json \
  --motion-csv output/loop_closure_research/BAG_motion.csv
```

If `supported_motion_rows` is zero, that bag cannot test the pivot-yaw backend.

**YAW-FACTOR COVARIANCE HOOK (2026-07-02).** `dense_submap_overlap_loop.py` now treats robot yaw as an
uncertain factor instead of hard truth. A yaw-prior CSV may contain `yaw_std_rad` / `yaw_std_deg` /
`yaw_var_rad2`, or timestamped `omega_z_rad_s` that gets integrated when absolute yaw is unavailable. The graph
rejects high-sigma yaw edges by `--yaw-prior-max-std-deg` (default 3 deg), scales the yaw-factor weight by
sigma, and can reject external yaw that disagrees strongly with raw LingBot yaw using
`--yaw-prior-max-visual-disagreement-deg`. `audit_rosbag_motion_topics.py` now exports `yaw_std_rad` and
`omega_z_std_rad_s` from ROS covariance fields when available.

Smoke tests on the raw repeat map: direct self-consistent yaw accepted 3/3 yaw edges with zero displacement;
setting max sigma to 1 deg rejected 3/3 as `high_yaw_prior_std`; synthetic timestamped omega integrated 345
rows and accepted 3/3 yaw edges; flipped-sign yaw with a 5 deg disagreement gate rejected 3/3 as
`high_visual_yaw_disagreement`. This proves the factor path and rejection path, not the real map quality.

**LOOP-CANDIDATE LEADERBOARD (2026-07-02).** Added
`go2_mono_nav/tool/evaluate_lingbot_loop_candidates.py`, which ranks candidate maps using pose metrics, the
old cloud quality gate, and the provenance wall-overlap certificate. Output:
`output/loop_closure_research/loop_candidate_leaderboard_all`. Across 40 pose candidates: **0 certified**,
2 `OLD_GATE_ONLY`, 15 `FAIL`, 19 `NO_PROVENANCE`, 4 `NO_CLOUD_DIAGNOSTIC`. The top two are still
`lingbot_map_repeat1_submap_endpoint_only_se2_kv64_colorfix` and
`lingbot_map_repeat1_c2wfix_pivot2_kv64_colorfix`: both pass old quality but fail provenance. Top-candidate
trajectory comparison is at
`output/loop_closure_research/loop_candidate_leaderboard_all/top_candidate_trajectory_comparison.png`.
Conclusion unchanged: do not call the current full-loop cloud globally clean; the next backend must reduce
source-separated wall thickness, not just endpoint gap.

**PROVENANCE WALL-REFINE PROTOTYPE (2026-07-02).** Added
`go2_mono_nav/tool/provenance_wall_refine.py`, which optimizes small SE(2) temporal-chunk corrections against
source-separated wall cells. It was tested on endpoint and pivot baselines plus 84 sweep variants. Result: not
certified. Some variants reduce revisit separation (for example endpoint `c8_w30_p4`: 4.1 cm sep, 8.4 cm
combined thickness), but they fail because too few wall-overlap cells remain and/or the old wall sharpness
gate rises above 6 cm. Pivot relaxed refinement reduces combined thickness from 28.2 cm to 19.8 cm but still
fails. Keep this as research evidence only; it is not a Foxglove output to trust.

**WALL-SDF LAYOUT-LAYER PROBE (2026-07-02).** Heavy review suggests a more elegant horizontal backend:
**Provenance-Balanced Wall-SDF Submap SLAM**. Keep LingBot's local colored 3D submaps, but solve horizontal
drift through a separate top-down wall/layout signed-distance layer, then lift only certified SE(2/2.5)
submap corrections back to the 3D cloud. This borrows the right idea from Cartographer-style scan-to-submap
matching and indoor layout SLAM while keeping the no-illusion provenance certificate as the acceptance gate.

Prototype added in `go2_mono_nav/tool/topdown_wall_sdf_loop.py`. Current result is negative but useful:
strict gates accept **0** wall-SDF loop edges on the raw pivot-geometry map; loose gates accept large
~1.1 m / ~30 deg corrections but fail validation. Raw loose worsens endpoint `0.64 m -> 1.11 m`; endpoint
loose worsens the endpoint baseline `0.056 m -> 0.155 m`; all wall-SDF probe outputs fail the provenance
leaderboard (`output/loop_closure_research/topdown_wall_sdf_probe_leaderboard`). So the wall-SDF layer is
the right shape of evidence, not a standalone rescue for this bag. Next version must combine it with Go2
yaw/IMU/body-odom factors, source-balanced wall support, holdout wall-SDF residuals, and switchable loop
weights before serving anything in Foxglove.

**HOLDOUT-GATED WALL-SDF UPDATE (2026-07-02).** `topdown_wall_sdf_loop.py` now splits wall points into
train/holdout sets and requires held-out wall-cell score, improvement, inlier fraction, and spatial coverage.
This closes the previous loose-gate failure: the same high-score ~1 m / ~30 deg wall matches are now rejected
as `low_holdout_coverage`, `low_holdout_inlier`, `low_holdout_score`, and/or `holdout_overfit`. On real repeat
maps, holdout wall-SDF accepts **0** edges across raw, endpoint, and full-provenance inputs. Leaderboard:
`output/loop_closure_research/topdown_wall_sdf_holdout_v2_leaderboard`; trajectory comparison:
`output/loop_closure_research/topdown_wall_sdf_holdout_v2_leaderboard/trajectory_comparison.png`.

Positive control added in `go2_mono_nav/tool/simulate_wall_sdf_loop_case.py`: a synthetic repeated-corner map
with injected `0.62 m / 8 deg` late-loop drift. Holdout wall-SDF accepts two correct late-to-start edges
(`~0.64 m`, `-8/-9 deg`, held-out score `~0.895`, `16-17` held-out cells) and reduces synthetic endpoint
`0.888 m -> 0.388 m` (`0.348 m` with stronger loop weights). This proves the gate can accept a real observable
loop; the actual repeat bag is being rejected because its wall evidence is sparse/ambiguous, not because the
scorer only rejects everything.

**WALL-SDF SWEEP V2 (2026-07-02).** Added `go2_mono_nav/tool/sweep_wall_sdf_loop.py` and ran a bounded sweep:
real maps `{raw pivotgeom, endpoint-only, pivot2, full provenance}` x presets `{strict, loose_holdout,
yaw_limited, support_lenient}` plus two synthetic drift controls. Artifacts:
`output/loop_closure_research/wall_sdf_sweep_v2`, real leaderboard
`output/loop_closure_research/wall_sdf_sweep_v2_real_leaderboard/leaderboard.csv`, and false-positive
trajectory plot
`output/loop_closure_research/wall_sdf_sweep_v2_real_leaderboard/trajectory_false_positive_comparison.png`.

Result: synthetic controls pass (`0.62 m / 8 deg` improves `0.888 -> 0.348-0.388 m`; `0.35 m / 5 deg` improves
`0.711 -> 0.358-0.403 m`). Real repeat-loop does **not** pass: 16 real cases, 4 lenient accepted edges, **0
certified**. Every accepted real edge is harmful: endpoint worsens, e.g. raw `0.640 -> 0.729 m`, endpoint
baseline `0.056 -> 0.313 m`, full-provenance `0.640 -> 0.865 m`. Therefore wall-SDF is useful as a verifier
and positive-control mechanism, but threshold sweeps alone are not the fix for this bag. Need independent
Go2 yaw/odom/IMU factors and/or a deliberate same-heading loop-closing recording.

**WALL-SDF REGIME SWEEP + ELEGANT BACKEND DIRECTION (2026-07-02).** Added
`go2_mono_nav/tool/sweep_wall_sdf_sim_regimes.py` and an overnight wrapper:
`go2_mono_nav/scripts/run_wall_sdf_overnight.sh`. Easy synthetic regime sweep:
`output/loop_closure_research/wall_sdf_sim_regime_sweep_v1`; stress sweep:
`output/loop_closure_research/wall_sdf_sim_regime_stress_v1`.

Regime result: corner and parallel-wall synthetic maps pass 100%; moderate-noise single-wall maps reject 100%;
high-noise single-wall maps expose the weak case, with one unsafe partial accept in the stress sweep. This matches
the real Foxglove failure: the bad map is not sparse because of downsampling or fake color; it is sparse/grey/doubled
because the trajectory places revisited wall evidence in inconsistent layers during rotation drift.

Best next idea: **Certified Pivot-SDF Factor Graph**.

- Treat rotate-in-place spans as yaw/SO(3) or panorama/ray factors, not as metric 3D cloud producers.
- Add Go2 IMU/body-odom yaw factors with covariance/slip gates; do not use robot yaw as hard truth.
- Use wall-SDF/layout matching only as a held-out, provenance-balanced structural factor.
- Add a degeneracy projector: if wall/layout registration is single-wall or rank-deficient, add only the constrained
  directions to the graph, not a full SE(2) loop edge.
- Keep switchable/robust loop weights; false reverse-heading edges must turn off.
- Export Foxglove by moving local colored submap/surfel blocks; fail certification if revisits still form two wall
  layers instead of averaging them into a grey blur.

Deployment requirement: the next `wsj` bag must record synchronized Go2 motion topics. Run
`tool/audit_rosbag_motion_topics.py` first; if `supported_motion_rows == 0`, that bag cannot validate the pivot-yaw
backend. Run the wall-SDF overnight wrapper only as a benchmark harness; no output is accepted for Foxglove unless
the real leaderboard says `CERTIFIED`.

**OBSERVABILITY-PROJECTED WALL-SDF FACTORS (2026-07-02).** Implemented the first piece of the
Certified Pivot-SDF Factor Graph in `go2_mono_nav/tool/topdown_wall_sdf_loop.py`. Each candidate wall-SDF
loop now computes an SDF residual Jacobian for `tx, ty, yaw`, records the eigenvalues of `J^T J`, rejects
rank-deficient factors, and projects loop residuals onto well-observed directions instead of treating every
wall match as a full SE(2) constraint. `sweep_wall_sdf_loop.py` and `sweep_wall_sdf_sim_regimes.py` now record
the best edge's observability rank/eigenvalue/support. `evaluate_lingbot_loop_candidates.py` also now uses
root-relative labels so per-candidate certificate JSONs no longer collide.

Full overnight-style run:
`output/loop_closure_research/overnight_wall_sdf_observability_v1`.

Results:

- Real maps: 16 cases, 4 lenient accepted edges, **0 certified**.
- Synthetic positive controls in the real/sim sweep: 6/6 accepted.
- Wide synthetic regime grid: 180 cases, 139 accepted/pass, **0 false accepts**.
- Stress comparison improved: previous high-noise single-wall stress had 1 unsafe accept; observability projection
  removes that false accept in `wall_sdf_sim_regime_observability_stress_v1` (36 cases, 30 pass, 0 false accepts).

Real accepted edges remain too weak for Foxglove:

- raw support-lenient: endpoint `0.640 -> 0.625 m`, but held-out support only 4 cells / score `0.194`;
- endpoint support-lenient: endpoint `0.056 -> 0.260 m`, 4 cells / score `0.372`;
- full loose: endpoint `0.640 -> 1.076 m`, 6 cells / score `0.251`;
- full support-lenient: endpoint `0.640 -> 0.863 m`, 5 cells / score `0.395`.

True synthetic loops have much stronger evidence: `15-17` held-out cells and holdout score around `0.88-0.90`.
So the new projection improves the verifier, but the current repeat bag still lacks enough validated structural
evidence to fix the full-loop map. The next real fix needs synchronized Go2 yaw/IMU/body-odom factors or a better
same-heading loop recording; do not serve any observability-v1 real output as "fixed" in Foxglove.

**YAW-PRIOR WALL-SDF FACTORS (2026-07-02).** Added direct chunk-level yaw-prior factors to
`go2_mono_nav/tool/topdown_wall_sdf_loop.py` and synthetic `yaw_prior.csv` export to
`tool/simulate_wall_sdf_loop_case.py`. The factor consumes per-frame `frame_key,yaw_rad,yaw_std_rad`, aggregates it
into chunk-level correction-yaw targets relative to chunk 0, and rejects high-covariance chunks. This keeps robot yaw
as an uncertain factor, not hard truth.

Smoke checks:

- Clean synthetic yaw prior: 7 chunk factors used; late loop chunks get about `-12 deg` correction target.
- High-sigma synthetic yaw prior: 0 factors used; all 8 chunks rejected by covariance.
- Yaw-only improves the orientation path but does not close translation. That is expected and useful: it proves yaw is
  necessary but not sufficient.

Bounded yaw-prior sim sweep:
`output/loop_closure_research/wall_sdf_yaw_prior_sim_v1`.

- 8 synthetic cases, all accepted.
- Yaw-prior variants used 7 chunk yaw factors and stayed comparable to the no-yaw positive controls.
- Representative `0.62 m / -0.18 m / 8 deg` drift: strong wall-SDF loop `0.888 -> 0.348 m`; yaw-prior strong loop
  `0.888 -> 0.348 m`; yaw-prior standard `0.888 -> 0.351 m`.

Yaw-prior regime sweep:
`output/loop_closure_research/wall_sdf_sim_regime_yaw_prior_v1`.

- 24 cases, 19 pass, 0 false accepts.
- Corner: 8/8 pass.
- Parallel walls: 7/8 pass.
- Single wall: 4/8 pass, all in the noisy synthetic setting; moderate single-wall cases remain rejected.

Conclusion: yaw-prior factors are now wired and covariance-gated, but the current real `repeat_loop1`/`loop_run1`
bags still cannot validate them because `audit_rosbag_motion_topics.py` found no usable Go2 odom/IMU/angular-rate
topics. The next real bag must record synchronized motion topics or this factor remains a positive-control result.

**LOOP-CONDITIONED CACHELET REPLAY IDEA (2026-07-02).** A heavier literature pass suggests a cleaner next step than
more Wall-SDF threshold sweeps: use LingBot's own context-conditioned pointmap predictor as a measured local factor.
This is closer to DUSt3R/MASt3R global pointmap alignment, CUT3R revisiting, and MASt3R-Fusion's feed-forward
pointmap plus factor-graph fusion than to a hand-written pointcloud warp.

Local hook already exists in AnchorScale: `LingBotBackbone` supports frozen-map/query behavior through
`keyframe_interval=10**9`, and `experiments/20_cachelet_factors.py` already tests frozen KV cachelets as local
measurement factors with micro-cache dispersion uncertainty. Use that mechanism for the bad repeat-loop:

1. Detect revisits with DINO/LightGlue or existing loop candidates.
2. Build cachelets from first-visit, translation-rich frames.
3. Re-query repeat-loop frames against those frozen cachelets, excluding temporal self-inclusion.
4. Convert each query result into a pose/submap factor with covariance from micro-cache dispersion.
5. Add these factors to the Certified Pivot-SDF graph together with Go2 yaw factors and Wall-SDF holdout factors.
6. Re-export Foxglove by moving local colored submaps only after the provenance wall certificate passes.

This is elegant because it uses LingBot for what it is good at, local context-conditioned geometry, and the factor
graph for what it is good at, globally fusing uncertain measurements. It also has a built-in no-illusion test: if
cachelet dispersion is high or provenance wall separation remains high, the factor is rejected and no clean-looking
cloud is served.

Relevant sources: LingBot-Map GCT (`https://arxiv.org/abs/2604.14141`), DUSt3R pointmap global alignment
(`https://arxiv.org/html/2312.14132v2`), CUT3R revisiting/stateful pointmaps (`https://arxiv.org/abs/2501.12387`),
STream3R causal pointmap reconstruction (`https://arxiv.org/html/2508.10893v1`), MASt3R-Fusion pointmap plus
IMU/GNSS factor graph (`https://arxiv.org/html/2509.20757v2`), VILENS degenerate-sensor fusion
(`https://arxiv.org/abs/2107.07243`), and tightly-coupled monocular visual-odometric SLAM with gyro/odometer
preintegration (`https://arxiv.org/abs/1804.04854`).

**CACHELET REPLAY PROBE V1 RESULT (2026-07-02).** Added
`go2_mono_nav/tool/cachelet_replay_loop.py` and a generic `--se2-prior-csv` path in
`tool/topdown_wall_sdf_loop.py`. The replay tool builds first-visit cachelets, proposes late revisit queries from
image similarity plus raw trajectory proximity, optionally runs LingBot frozen-map/query replay, estimates
micro-cache dispersion, and writes accepted SE(2) correction factors for the Wall-SDF graph.

Artifacts:
`output/loop_closure_research/cachelet_replay_probe_v1`.

Real repeat-loop result on `lingbot_map_repeat1_c2wfix_full`:

- Candidate stage: 13 first-visit cachelets, 12 loop-scale candidates.
- Top candidates correctly live at the expected drift scale: late keys `704/736` against early cachelets around
  keys `96/120`, raw XY gaps `0.66-1.10 m`.
- Measured top 6 with LingBot frozen replay and 2 micro-cache subsets: **0 accepted factors**.
- Rejection reason: rotation dispersion is too high. The two best query/key pairs have low translation dispersion
  (`0.049-0.075 m`) but very high rotation dispersion (`28.8-44.1 deg`). Other candidates are worse
  (`0.60-1.29 m` translation dispersion, `32-119 deg` rotation dispersion, or huge yaw corrections).
- The exported `cachelet_replay_se2_factors.csv` is empty; a Wall-SDF smoke with `--se2-prior-csv` therefore adds
  0 SE(2) prior edges and leaves the endpoint at `0.6396 m`.

Conclusion: the cachelet-replay mechanism is now executable and correctly rejects unstable LingBot loop factors on
the current bad bag. This is progress in no-illusion validation, not a fix. Next useful variants are: longer/more
parallax cachelets, same-heading closure recordings, and adding real Go2 yaw priors before trusting any replay factor.

**CACHELET REPLAY PROBE V2 RESULT (2026-07-02).** Longer, higher-parallax cachelets can produce stable-looking
LingBot replay factors, but the current graph still fails the no-illusion wall certificate.

Artifacts:
`output/loop_closure_research/cachelet_replay_probe_v2`.

| Variant | Accepted replay factors | Endpoint gap | Provenance wall p90 | Verdict |
|---|---:|---:|---:|---|
| raw provenance map | - | `0.6396 m` | `0.0611 m` | FAIL |
| `w48_a12_topdown_se2` | 2 factors, aggregated to 1 chunk prior | `0.4898 m` | `0.0948 m` | FAIL |
| `w60_a12_topdown_se2` | 2 factors, aggregated to 1 chunk prior | `0.4946 m` | `0.0968 m` | FAIL |
| `w60_a12_topdown_se2_w40` | same factor, stronger graph weight | `0.5729 m` | `0.0663 m` | FAIL |
| `w60_a12_topdown_se2_w80` | same factor, strongest graph weight | `0.5892 m` | `0.0656 m` | FAIL |

Interpretation: cachelet replay is measuring a real loop-scale correction, but using it as a plain SE(2) prior is
not enough. The endpoint improves in the moderate-weight runs while the source-separated wall overlap gets worse;
stronger weights partially recover the wall metric but lose most endpoint improvement. Do not serve these maps in
Foxglove as "fixed".

**ELEGANT NEXT IDEA: COUNTERFACTUAL PROVENANCE-GATED CACHELET REPLAY.** The literature-backed move is to put the
certificate inside the loop optimizer, not only after it. For each LingBot cachelet replay factor, run a cheap
counterfactual graph update on a copy, rebuild only the affected local colored submaps, and accept/switch-on the
factor only if held-out Wall-SDF residual and source-separated wall provenance both improve. The factor should be
weighted by micro-cache dispersion, but its final switch variable is driven by whether the same physical wall becomes
less doubled. This follows the direction of LingBot/CUT3R/MASt3R pointmap replay, dense submap loop closure
(BundleFusion/ElasticFusion/LoopSplat), and switchable robust pose-graph SLAM, while preserving our no-illusion gate.

Next implementation target: add a cachelet-factor switch and a `counterfactual_cert_delta` score:

- propose the replay factor from LingBot frozen cachelets;
- solve the local SE(2/2.5) graph with the factor tentatively active;
- rebuild affected provenance cloud chunks only;
- require endpoint, held-out Wall-SDF, wall revisit separation, and conflict-cell rate to improve together;
- otherwise set the factor switch to zero and export the unchanged map.

**COUNTERFACTUAL CACHELET GATE V1 RESULT (2026-07-02).** Added
`go2_mono_nav/tool/counterfactual_cachelet_gate.py` and wired it into
`go2_mono_nav/scripts/run_cachelet_replay_probe.sh`. The tool applies each cachelet replay factor on a copy through
`topdown_wall_sdf_loop.py`, runs the normal candidate leaderboard, and rejects a factor unless endpoint and
source-separated provenance improve while preserving wall-overlap support.

Artifacts:
`output/loop_closure_research/cachelet_replay_probe_v3_counterfactual_strict`.

| Factor hypothesis | Endpoint delta | Wall-overlap cells | Wall sep delta | Decision |
|---|---:|---:|---:|---|
| `w60 row704` | `+0.0487 m` | `1/5` | `+0.0098 m` | reject |
| `w60 row736` | `-0.1666 m` | `2/5` | `-0.0004 m` | reject: loses 3 wall-support cells |
| `w60 all` | `-0.1450 m` | `3/5` | `+0.0357 m` | reject: wall gets worse |
| `w48 row704` | `+0.0343 m` | `0/5` | unavailable | reject |
| `w48 row736` | `-0.1885 m` | `1/5` | `-0.0580 m` | reject: loses 4 wall-support cells |
| `w48 all` | `-0.1498 m` | `4/5` | `+0.0337 m` | reject: wall gets worse |

This is the first useful switchable-loop behavior on the real repeat map. The gate blocks the exact failure seen in
Foxglove: a loop factor can reduce endpoint drift while erasing or worsening the repeated-wall evidence. Current
accepted-for-Foxglove count remains **0**. The next real improvement needs either more same-heading replay evidence
around key `736`, synchronized Go2 yaw/odom factors, or a new recording with stronger repeated wall support.

**DENSE-QUERY CACHELET REPLAY V4 RESULT (2026-07-02).** Tested the "more neighboring frames around key 736" idea.
Using the `w60_a12` high-parallax cachelet settings with `query_stride=4`, `max_candidates=80`, and
`max_measured=30`, LingBot replay found 49 candidates, measured 30, and accepted 8 low-dispersion factors at keys
`704, 712, 720, 720, 728, 736, 744, 752`.

Artifacts:
`output/loop_closure_research/cachelet_replay_probe_v4_dense_query`.

Counterfactual gate result: **0/9 accepted** (8 single factors plus all factors). The all-factor graph preserves
the 5 wall-overlap cells but still makes the wall worse: endpoint delta `-0.1008 m`, wall separation delta
`+0.0374 m`, wall thickness delta `+0.0406 m`, conflict fraction delta `+0.20`.

Added `go2_mono_nav/tool/sweep_cachelet_prior_grid.py` and swept 20 graph settings:
weights `{2,5,10,20,40}` x chunk counts `{8,12,16,24}`. Result: **0 certified** and **0 candidates** that improve
endpoint while preserving/improving wall support. Best score (`chunk=8`, `weight=40`) improves endpoint by
`0.0963 m` and wall separation by `0.0047 m`, but wall-overlap support drops from `5` cells to `2`. Best endpoint
improvement (`chunk=12/16/24`, `weight=20`) improves endpoint by `0.2085 m`, but wall separation worsens and support
drops by 3 cells.

Trajectory comparison for raw, dense-all, best-score grid, best-endpoint grid, and single key-744 factor:
`output/loop_closure_research/cachelet_replay_probe_v4_dense_query/trajectory_comparison.png`. The best endpoint
case reaches `0.4311 m` start/end gap, but still fails provenance; the best-score case is `0.5433 m` and loses wall
support. Endpoint closure remains an insufficient metric.

Conclusion: denser LingBot replay produces a coherent-looking correction sequence, but it is still not a certified
loop closure on this real bag. More cachelet factors alone are not enough; the missing evidence is an independent
rotation/proprioceptive source or a same-heading loop closure with stronger repeated wall support.

**SE(2) PRIOR SPAN-GATE + FINE-CHUNK V5 RESULT (2026-07-02).** Added diagnostics and optional gates to
`topdown_wall_sdf_loop.py` for cachelet SE(2) priors:

- `row_correction_xy_span_m`
- `row_correction_yaw_span_deg`
- `key_span`
- `--se2-prior-max-row-span-xy-m`
- `--se2-prior-max-row-span-yaw-deg`
- `--se2-prior-max-key-span`

The dense replay all-factor prior was previously hidden as one chunk-7 correction. The new diagnostics show why that
is unsafe: the 8 frame-level rows span `0.580 m`, `6.87 deg`, and `48` frame keys. With stricter settings
`--se2-prior-max-row-span-xy-m 0.35 --se2-prior-max-row-span-yaw-deg 6 --se2-prior-max-key-span 24`, the prior is
rejected before optimization (`rejected_high_span_chunks=1`, `se2_prior_edges=0`).

Also tested finer graph chunks by setting `--min-frames-per-chunk 8` in
`sweep_cachelet_prior_grid.py`. This is more promising but still not solved:

| Candidate | Endpoint gap | Wall cells | Wall sep p90 | Combined wall thickness p90 | Verdict |
|---|---:|---:|---:|---:|---|
| raw provenance | `0.6396 m` | 5 | `0.0611 m` | `0.2825 m` | FAIL |
| `c48_w20_minframes8` | `0.4071 m` | 5 | `0.0548 m` | `0.2468 m` | FAIL |
| `c48_w40_minframes8` | `0.4089 m` | 5 | similar | still FAIL | FAIL |
| `c32_w2_minframes8` | `0.4941 m` | 6 | improves support | still FAIL | FAIL |

Trajectory comparison:
`output/loop_closure_research/cachelet_replay_probe_v5_span_gate/trajectory_comparison.png`.

Interpretation: using finer late-loop nodes and cachelet factors can improve the trajectory and wall separation
without dropping wall support, but the full 3D reconstruction is still too thick/doubled and the endpoint remains far
above a real loop-closure target. This is the best replay-only result so far, but it is still not a clean Foxglove
map. The next non-redundant input is external yaw/body odom or a better same-heading loop recording.

**SMOOTH CACHELET CORRECTION FIELD NEAR MISS (2026-07-02).** Added
`go2_mono_nav/tool/apply_cachelet_correction_field.py`, which turns accepted cachelet replay rows into a smooth
per-frame SE(2) correction field and re-exports `poses.npy`, `frame_clouds_visual.npz`, and `cloud.ply`.
This produced the best endpoint numbers so far, but still did not pass the no-illusion wall certificate.

Best refined run:

| Candidate | Verdict | Endpoint | Wall cells | Revisit sep p90 | Combined wall thickness p90 |
|---|---:|---:|---:|---:|---:|
| raw provenance | FAIL | `0.6396 m` | 5 | `0.0611 m` | `0.2825 m` |
| `ramp120_s7_scale070` | OLD_GATE_ONLY | `0.2953 m` | 3 | `0.0547 m` | `0.2578 m` |
| `ramp120_s7_scale075` | OLD_GATE_ONLY | `0.2943 m` | 4 | `0.0531 m` | `0.2648 m` |
| `ramp120_s7_scale08` | OLD_GATE_ONLY | `0.2984 m` | 4 | `0.0531 m` | `0.2620 m` |

Artifacts:
`output/loop_closure_research/cachelet_correction_field_v2_scale/leaderboard_refined/leaderboard.csv` and
`output/loop_closure_research/cachelet_correction_field_v2_scale/trajectory_refined.png`.

Conclusion: the correction field is a useful initialization/diagnostic, not a publishable reconstruction. It can
make the trajectory look much better while the repeated wall remains about `26 cm` thick. Do not serve these maps in
Foxglove as "fixed" unless a later certified graph reduces the wall thickness below the provenance threshold.

**CORRECTION-FIELD SWEEP V3 + SYNTHETIC CONTROL (2026-07-02).** Added
`go2_mono_nav/tool/sweep_cachelet_correction_field.py` and wired it into
`scripts/run_cachelet_replay_probe.sh` as `RUN_CORRECTION_FIELD_SWEEP=1`. Real bounded sweep:
`output/loop_closure_research/cachelet_correction_field_sweep_v3_grid`.

Result on real repeat-loop:

| Candidates | Certified | OLD_GATE_ONLY | Best endpoint | Best wall sep p90 | Best combined wall thickness p90 |
|---:|---:|---:|---:|---:|---:|
| 84 | 0 | 24 | `0.2955 m` | `0.0508 m` | `0.2508 m` |

Best row: `r100_s5_xy0p8_yaw0p8_zauto_hold`. It improves endpoint and wall separation, but still leaves a
`25 cm` repeated-wall thickness, so it is not a clean Foxglove map.

Positive controls were added to `simulate_wall_sdf_loop_case.py`: `--closed-end`, `--floor-points-per-frame`, and
`--loop-only-wall`. With known inverse factors for an injected `0.62 m / -0.18 m / 8 deg` drift, the same
correction-field sweep certifies both synthetic controls:

| Synthetic control | Candidates | Certified | Endpoint | Wall sep p90 | Wall thickness p90 |
|---|---:|---:|---:|---:|---:|
| closed single wall | 27 | 27 | `0.0 m` | `0.00036 m` | `0.0156 m` |
| closed corner | 27 | 27 | `0.0 m` | `0.00094 m` | `0.0383 m` |

This matters: the certification path can accept a correct correction. The real failure is not that the gate is
impossible; it is that current LingBot replay factors do not provide enough globally correct evidence to collapse the
revisited wall. Next real progress requires synchronized Go2 yaw/body-odom or a better same-heading loop revisit.

**UNIFIED LOOP-CLOSURE BENCHMARK V1 (2026-07-02).** Added
`go2_mono_nav/scripts/run_lingbot_loop_closure_benchmark.sh` and
`go2_mono_nav/tool/summarize_loop_closure_benchmark.py`. Full non-GPU benchmark root:
`output/loop_closure_research/lingbot_loop_closure_benchmark_v1`.

Command:

```bash
ROOT=output/loop_closure_research/lingbot_loop_closure_benchmark_v1 \
RUN_CACHELET_REPLAY=0 \
bash scripts/run_lingbot_loop_closure_benchmark.sh
```

Summary:

| Section | Cases | Result |
|---|---:|---|
| real baseline | 1 | 0 certified; endpoint `0.6396 m`, wall thickness `0.2825 m` |
| real correction-field sweep | 84 | 0 certified; 24 `OLD_GATE_ONLY`; best endpoint `0.2955 m`, wall thickness `0.2508 m` |
| wall-SDF real leaderboard | 16 | 0 certified; best endpoint-style candidate still wall thickness `0.1762 m` and quality FAIL |
| synthetic known-inverse controls | 54 | 54 certified |
| wall-SDF synthetic regimes | 72 | 48 pass, 0 false accepts |

Benchmark verdict: `NO_REAL_CERTIFIED_CANDIDATE`.

This is now the standard no-illusion benchmark artifact. It proves the gate and correction machinery can certify
correct synthetic loop closures, but every real repeat-loop candidate still fails. To include a fresh LingBot replay
measurement pass in an actual overnight run:

```bash
ROOT=output/loop_closure_research/lingbot_loop_closure_benchmark_overnight_$(date +%Y%m%d_%H%M%S) \
RUN_CACHELET_REPLAY=1 \
bash scripts/run_lingbot_loop_closure_benchmark.sh
```

Do not serve a real candidate in Foxglove unless `benchmark_summary.json` reports `REAL_CERTIFIED`.

**DISTILLED NEXT IDEA (2026-07-02).** The elegant direction is **Certified Memory-Submap SLAM**:
use LingBot cachelet replay as a learned local loop measurement, Go2 yaw/IMU/body-odom as the pivot-rotation
measurement, and Wall-SDF/dense surfel overlap as held-out structural verification. Every loop factor is switched on
only if a counterfactual graph update improves endpoint, floor, wall p90, wall support, revisit separation, and
combined revisit thickness. This follows the current literature trend: streaming pointmap memory (LingBot/CUT3R/
STream3R), informative multi-view selection (AIM-SLAM), learned pointmap plus sensor factor graphs (MASt3R-Fusion),
map-centric dense correction (BundleFusion/ElasticFusion/Loopy-SLAM/LoopSplat), and robust/switchable loop
constraints. The current real bag lacks the independent Go2 motion topics needed to validate the pivot-yaw part, so
the next `wsj` recording must include synchronized robot motion streams before another real Foxglove fix attempt.

**RGB-ONLY VISUAL GYRO PROBE (2026-07-02).** Literature on Rotation-Only BA, pure-rotation keyframe SLAM,
homography VO with known vertical direction, and robust rotation averaging suggests a more elegant fallback when Go2
motion topics are missing: treat rotate-in-place RGB frames as a **visual gyro**. They should estimate yaw/SO(3) and
place-recognition/panorama constraints, while contributing no metric 3D wall points.

Added `go2_mono_nav/tool/probe_visual_rotation_yaw.py`. It uses the existing `kf_images` plus intrinsics, estimates
adjacent pure-yaw increments by phase correlation on image-gradient crops, auto-selects sign from adjacent LingBot yaw,
and writes a frame-aligned yaw prior:

- artifact root: `output/loop_closure_research/visual_rotation_yaw_probe_v1`
- yaw prior: `visual_rotation_yaw_prior.csv`
- diagnostics: `visual_rotation_yaw_diagnostics.png`
- leaderboard: `visual_rotation_yaw_probe_v1/leaderboard`

Measured on the current repeat-loop map:

| Candidate | Endpoint | Wall cells | Revisit sep p90 | Combined wall thickness p90 | Verdict |
|---|---:|---:|---:|---:|---|
| raw provenance | `0.6396 m` | 5 | `0.0611 m` | `0.2825 m` | FAIL |
| visual-yaw soft graph, weight 12 | `0.6414 m` | 4 | `0.0763 m` | `0.2349 m` | FAIL |
| visual-yaw soft graph, weight 30 | `0.6529 m` | 4 | `0.0786 m` | `0.2796 m` | FAIL |

The RGB signal is real: 8/8 detected pivot intervals had strong correlation peaks; visual-vs-raw pivot yaw
disagreement was p50 `1.42 deg`, p90 `2.38 deg`, and the integrated visual prior differed from raw LingBot yaw by
`10.32 deg`. But the coarse 4-submap yaw-prior graph still accepted no dense loop edges and did not close the map.
So this is **not** a Foxglove fix. It is evidence for the next cleaner backend: add explicit fine-grained pivot
nodes and rotation-only/homography factors, then combine them with cachelet replay and Wall-SDF factors. A visual gyro
can repair orientation observability during pivots; it cannot by itself solve x/y loop drift or doubled-wall support.

**FRAME-LEVEL VISUAL-GYRO REINTEGRATION V1 (2026-07-02).** Added
`go2_mono_nav/tool/apply_visual_gyro_reintegration.py` plus a synthetic positive-control generator
`tool/simulate_visual_gyro_reintegration_case.py`. This tests the stronger version of the idea: replace trusted
pivot yaw increments at frame level, re-integrate the SE(2) trajectory, and move each frame cloud by its own
`T_new * inv(T_raw)` correction. This is closer to the intended pivot-node backend than the previous 4-submap prior.

Real repeat-loop sweep artifact: `output/loop_closure_research/visual_gyro_reintegration_v1`.

| Candidate | Endpoint | Wall cells | Revisit sep p90 | Combined wall thickness p90 | Verdict |
|---|---:|---:|---:|---:|---|
| raw provenance | `0.6396 m` | 5 | `0.0611 m` | `0.2825 m` | FAIL |
| best visual-gyro reintegration, scale `-1.0` | `0.6469 m` | 5 | `0.0516 m` | `0.1788 m` | FAIL |
| best separation, scale `-1.25` | `0.6519 m` | 6 | `0.0388 m` | `0.2640 m` | FAIL |

Trajectory comparison:
`output/loop_closure_research/visual_gyro_reintegration_v1/trajectory_comparison.png`.

Important interpretation: frame-level visual yaw can move the wall metric strongly (`28.3 cm -> 17.9 cm` thickness in
the best scale), and it removes one rotation-dominant trajectory spike, but it still does not close the endpoint or
certify the real 3D map. Stronger negative scales make endpoint worse; positive scales make wall separation worse.

Synthetic positive control:
`output/loop_closure_research/visual_gyro_reintegration_sim_v1`. The raw synthetic corner map has an 8 deg yaw-drifted
revisit and fails as `OLD_GATE_ONLY`: endpoint `0.0 m`, wall cells `8`, wall sep `0.0076 m`, wall thickness
`0.2508 m`. Applying the exact yaw prior certifies it: endpoint ~`0.0 m`, wall cells `10`, wall sep `0.0006 m`, wall
thickness `0.0373 m`, verdict `CERTIFIED`. This proves the reintegration/export/certificate path can accept a correct
frame-level yaw correction when the data model matches LingBot's per-frame cloud provenance.

Cross-checks:

- `output/loop_closure_research/visual_rotation_yaw_probe_realbag_v1`: realbag has 147 pivot intervals but noisy visual
  gyro agreement; 74 intervals survived, final visual-yaw delta from raw was `-47.6 deg`, so this dataset needs robust
  rotation averaging/outlier rejection before any map correction.
- `output/loop_closure_research/visual_gyro_reintegration_raw_pivotgeom_v1`: raw-pivotgeometry repeat variant used only
  3 trusted visual edges. Scale `+1.0` improved endpoint `0.6396 -> 0.6250 m`, but wall separation worsened
  `0.0382 -> 0.0812 m`, verdict `FAIL`.

Conclusion: visual gyro is now a validated **component**, not the full loop closure. The next overnight benchmark should
combine frame-level visual-gyro initialization with cachelet replay translation/loop factors and Wall-SDF held-out
factors. Do not serve any real visual-gyro output in Foxglove until the provenance leaderboard reports `CERTIFIED`.

### 2026-07-02 refined fusion result and next backend

Refined visual-gyro + cachelet correction-field sweep:
`output/loop_closure_research/visual_gyro_cachelet_fusion_v1/gyro_m1p0_refine`.

Result: `168` candidates, `0` certified. Best candidate:

| Candidate | Endpoint | Wall cells | Revisit sep p90 | Revisit thickness p90 | Local wall p90 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `r120_s3_xy0p75_yaw0_zauto_hold` | `0.2333 m` | 2 | `0.0431 m` | `0.1250 m` | `0.0630 m` | FAIL |

This is a close but real failure. The overlap/provenance certificate passes and the endpoint is below `30 cm`, but the
global map-quality check still rejects the local wall thickness (`6.30 cm`, threshold `6.00 cm`). Do not show it in
Foxglove as fixed.

Next elegant backend: **provenance-aware elastic surfels**.

- Fuse translation windows into local colored surfel blocks with frame-key and early/late provenance.
- Treat rotate-in-place spans as pivot islands: yaw/SO(3) factors only, near-zero translation, low metric point weight.
- Use LingBot cachelet replay as switched loop measurements, not mandatory pose priors.
- Optimize a sparse SE(2.5) or embedded-deformation correction field with residuals on cachelet priors, smoothness,
  wall/floor SDF distance, and source-separated wall thickness.
- Hold out repeated wall cells from the objective; accept only if the existing quality diagnostic plus provenance
  certificate report `CERTIFIED`.

This is the clean direction because it optimizes the surface Foxglove displays. Pose BA and cachelet fields can improve
endpoint while leaving doubled walls; the next optimizer must make early/late wall thickness the residual, not only the
post-hoc diagnostic. Full literature note:
`/home/asus/Research/pengyue/AnchorScale/docs/lingbot_loop_backend_literature_review.md`.

### 2026-07-02 provenance-elastic V0 result

Implemented first probes in `go2_mono_nav`:

- `tool/optimize_provenance_elastic_field.py`
- `tool/sweep_late_micro_correction.py`

Artifacts:

- `output/loop_closure_research/provenance_elastic_surfels_v0/sim_corner_yaw_drift*`
- `output/loop_closure_research/provenance_elastic_surfels_v0/real_nearmiss_*`
- Best refined micro sweep:
  `output/loop_closure_research/provenance_elastic_surfels_v0/real_nearmiss_late_micro_sweep_v2_refine`

Result: still `0` certified real maps. The best real micro-correction,
`dxm0p06_dy0p06_yaw0p3`, improves endpoint `0.2333 -> 0.1725 m` and keeps provenance overlap `PASS`, but it still
fails the old wall sharpness gate:

| Candidate | Endpoint | Wall p90 | Revisit sep p90 | Revisit thickness p90 | Verdict |
|---|---:|---:|---:|---:|---|
| near-miss input | `0.2333 m` | `0.0630 m` | `0.0431 m` | `0.1250 m` | FAIL |
| best V2 micro correction | `0.1725 m` | `0.0628 m` | `0.0378 m` | `0.1182 m` | FAIL |

Trajectory comparison:
`output/loop_closure_research/provenance_elastic_surfels_v0/real_nearmiss_late_micro_sweep_v2_refine/trajectory_comparison.png`.

Interpretation: this is not a downsampling issue and not just a final endpoint correction. The map can be made
closer and the provenance cells can still pass, but the displayed wall surface stays too thick (`6.28 cm`, threshold
`6.00 cm`). Do not serve these V0 outputs in Foxglove as fixed. The next useful step is either a true dynamic
surfel/TSDF reintegration objective or a new `wsj` bag with synchronized Go2 yaw/odom/IMU so pivot drift is observed
instead of inferred from sparse walls.

### 2026-07-02 wall-cell inspection and filter result

Added:

- `tool/inspect_wall_sharpness_cells.py`
- `tool/filter_rotation_geometry_frames.py`
- `tool/sweep_rotation_geometry_filter.py`
- `tool/filter_noisy_wall_cells.py`

Important finding: the remaining `6 cm` wall-sharpness failure after the best micro correction is mostly local
rotation-contaminated geometry, not the late repeat closure. Top bad wall cells come from mid-trajectory frame spans
such as `262-348`, `400-442`, `482-506`, and `558-598`, with high yaw-per-meter increments.

Best motion-based geometry filter:
`output/loop_closure_research/provenance_elastic_surfels_v0/rotation_geometry_filter_sweep_v1_on_micro/rot2_ratio45_low0p03_pad0`.
It removes `7.5%` of points, keeps provenance `PASS`, and improves wall p90 only to `0.0621 m`; still `FAIL`.

Noisy-wall-cell confidence masks can make the old wall gate pass, but they fail provenance:

- `noisy_wall_cell_filter_v1_on_micro`: removes `0.84%`, wall p90 `0.0538 m`, provenance `FAIL`
- `noisy_wall_cell_filter_v2_protected_on_micro`: removes `0.65%`, wall p90 `0.0562 m`, provenance `FAIL`

So filtering is not a valid fix. It can make the pointcloud look sharper, but the source-separated revisit certificate
correctly catches that repeated-wall evidence was damaged. Do not serve these outputs in Foxglove.

### 2026-07-02 first certified surfel-style export

Added `tool/project_single_visit_wall_surfels.py`.

This keeps all points and poses, protects temporal-overlap cells, skips local cells with early/late revisit support,
and only shrinks wall-normal noise in single-visit line-like wall cells. It is a surfel-style export test, not a raw
pose-graph miracle.

Certified artifact:
`output/loop_closure_research/provenance_elastic_surfels_v0/single_visit_wall_surfel_projection_v1`.

Final leaderboard:
`output/loop_closure_research/provenance_elastic_surfels_v0/single_visit_wall_surfel_projection_v1_final_leaderboard`.

| Candidate | Endpoint | Wall p90 | Wall cells | Revisit sep p90 | Revisit thickness p90 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| raw provenance | `0.6396 m` | `0.0515 m` | 5 | `0.0611 m` | `0.2825 m` | FAIL |
| best micro correction | `0.1725 m` | `0.0628 m` | 2 | `0.0378 m` | `0.1182 m` | FAIL |
| surfel projection V1 | `0.1725 m` | `0.0573 m` | 2 | `0.0378 m` | `0.1182 m` | CERTIFIED |

Projection touched `1428 / 222445` points (`0.64%`) in `6` single-visit wall cells and removed no points. The
source-separated overlap metrics are unchanged from the pre-projection micro-corrected candidate: overlap cells `2`,
conflict cells `0`, revisit separation p90 `0.0378 m`, combined revisit thickness p90 `0.1182 m`.

Trajectory comparison:
`output/loop_closure_research/provenance_elastic_surfels_v0/single_visit_wall_surfel_projection_v1/trajectory_comparison.png`.

Operational caveat: this is the first **certified export for this repeat-loop bag**, not proof that LingBot now has a
general robust loop-closure backend. It is acceptable to inspect in Foxglove as the current best certified output, but
the next validation must run the same pipeline on additional bags/simulations and should prefer synchronized Go2
yaw/odom/IMU at capture time.

### 2026-07-02 guarded surfel export controls

`tool/project_single_visit_wall_surfels.py` now refuses to run unless the input already passes the provenance overlap
certificate (`--require-input-overlap-pass`, default on). This prevents using the surfel projection to make a bad loop
look clean.

Guarded certified artifact:
`output/loop_closure_research/provenance_elastic_surfels_v0/single_visit_wall_surfel_projection_v2_guarded`.

Controls:

| Case | Result |
|---|---|
| Real best micro-corrected map | precheck `PASS`, guarded export `CERTIFIED` |
| Raw real repeat-loop map | precheck `FAIL`, exporter refuses |
| Corrected synthetic yaw-drift map | precheck `PASS`, guarded export `CERTIFIED`, projects `0` points |
| Raw synthetic yaw-drift map | precheck `FAIL`, exporter refuses |

So the current acceptable Foxglove candidate is the guarded surfel export, and only because a loop-corrected input had
already passed the no-illusion provenance check.

### 2026-07-02 guarded export benchmark and next elegant backend

Added `tool/benchmark_guarded_surfel_export.py` in `go2_mono_nav` and ran:

```bash
python3 tool/benchmark_guarded_surfel_export.py \
  --out-dir output/loop_closure_research/provenance_elastic_surfels_v0/guarded_surfel_export_benchmark_v1 \
  --case real_positive=accept_certified:output/loop_closure_research/provenance_elastic_surfels_v0/real_nearmiss_late_micro_sweep_v2_refine/dxm0p06_dy0p06_yaw0p3 \
  --case real_raw_negative=refuse:output/lingbot_map_repeat1_c2wfix_full_kv64_provenance \
  --case sim_positive=accept_certified:output/loop_closure_research/visual_gyro_reintegration_sim_v1/corner_yaw_drift_corrected \
  --case sim_raw_negative=refuse:output/loop_closure_research/visual_gyro_reintegration_sim_v1/input_corner_yaw_drift
```

Result: `all_expectations_passed=true`.

| Case | Result |
|---|---|
| real best micro-corrected map | precheck `PASS`, export `CERTIFIED`, endpoint `0.1725 m`, wall p90 `0.0573 m`, projects `0.64%` points |
| raw real repeat-loop map | precheck `FAIL`, exporter refuses |
| corrected synthetic yaw-drift map | precheck `PASS`, export `CERTIFIED`, projects `0` points |
| raw synthetic yaw-drift map | precheck `FAIL`, exporter refuses |

The broader fix should be a **certified LingBot memory graph**, not another BA/filter sweep:

- Translation windows become local colored surfel blocks with provenance.
- Rotate-in-place spans become yaw-only pivot islands; they do not inject strong finite 3D wall evidence.
- First-visit stable walls/floor become memory anchors; late revisits query them through switchable cachelet/pointmap
  factors.
- A sparse SE(2.5)+TPS correction field moves surfel/submap blocks, with floor/camera-height constraints preventing
  vertical warps from hiding horizontal drift.
- Held-out source-separated wall cells remain the acceptance gate. If they fail, the Foxglove output is rejected even
  if it looks visually sharper.

Initial implementation target: `tool/optimize_memory_surfel_graph.py`, using the existing cachelet factors,
rotation-pivot spans, and frame-cloud provenance. V0 now exists below; only move to GTSAM/Ceres after a Python prototype
can improve held-out provenance on both real and synthetic controls.

### 2026-07-02 memory-surfel graph V0 result

Added `tool/optimize_memory_surfel_graph.py` in `go2_mono_nav`.

The tool detects rotation-heavy pivot keys, excludes pivot points from local wall residuals, builds train/holdout
non-pivot wall cells, optionally consumes cachelet replay factors as robust memory priors, and exports normal LingBot
map artifacts for the unchanged leaderboard.

Positive synthetic control:

| Input | Output | Result |
|---|---|---|
| `lingbot_loop_closure_benchmark_v1/sim_inputs/closed_looponly_floor_corner` + `synthetic_known_inverse_factors.csv` | `provenance_elastic_surfels_v0/memory_surfel_graph_v0/sim_floor_corner_known_inverse` | `CERTIFIED`; endpoint `0.8185 -> 0.00044 m`, overlap `PASS`, wall sep p90 `0.0419 m` |

Real probes:

| Probe | Endpoint | Overlap | Wall sep p90 | Verdict |
|---|---:|---|---:|---|
| raw provenance input | `0.6396 m` | FAIL | `0.0611 m` | FAIL |
| memory graph, raw + dense cachelet factors | `0.3459 m` | FAIL | `0.1194 m` | FAIL |
| near-miss input | `0.1725 m` | PASS at min wall cells 2 | `0.0378 m` | FAIL |
| memory graph, near-miss no factors | `0.1738 m` | PASS at min wall cells 2 | `0.0365 m` | FAIL |

Important interpretation: the abstraction is good enough to certify a clean synthetic memory correction, but the real
cachelet factors still reduce endpoint while worsening repeated-wall provenance. Do not use the V0 real outputs in
Foxglove. The next non-redundant implementation is a piecewise block/surfel optimizer, not a stronger smooth factor
field: late revisit blocks need to take loop corrections sharply, pivot islands stay yaw-only, and surfels must be
reintegrated/moved as blocks rather than smeared through a global correction field.

### 2026-07-02 piecewise block + guarded overlap surfel result

Added:

- `tool/optimize_piecewise_surfel_blocks.py`
- `tool/project_joint_overlap_wall_surfels.py`

The piecewise optimizer lets late revisit blocks take sharper cachelet-memory corrections instead of spreading a smooth
field through the whole loop. The joint-overlap surfel tool is a guarded final reintegration stage: it refuses raw bad
loops and only runs when endpoint, old quality, floor overlap, wall support, wall conflicts, and wall separation already
pass. It can then reduce remaining repeated-wall thickness without deleting points.

Synthetic control:

| Output | Verdict |
|---|---|
| `provenance_elastic_surfels_v0/piecewise_surfel_blocks_v0/sim_corner_known_inverse` | `CERTIFIED`, endpoint `~0`, wall sep p90 `0.0010 m` |

Real result:

| Candidate | Endpoint | Quality | Overlap | Wall sep p90 | Revisit thickness p90 | Verdict |
|---|---:|---|---|---:|---:|---|
| raw provenance | `0.6396 m` | FAIL | FAIL | `0.0611 m` | `0.2825 m` | FAIL |
| piecewise block | `0.2853 m` | PASS | FAIL | `0.0410 m` | `0.1842 m` | OLD_GATE_ONLY |
| block + joint surfel | `0.2853 m` | PASS | PASS | `0.0100 m` | `0.0498 m` | CERTIFIED |

Final certified artifact:
`output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_surfel_blocks_v0/real_raw_dense_cachelet_s020_cert_thick_joint_surfel`.

Final leaderboard:
`output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_surfel_blocks_v0/real_raw_dense_cachelet_s020_cert_thick_joint_surfel_leaderboard`.

Trajectory comparison:
`output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_surfel_blocks_v0/real_raw_dense_cachelet_s020_cert_thick_joint_surfel_trajectory_comparison.png`.

Projection touched `2053 / 222445` points (`0.92%`) in `7` already-aligned repeated wall cells, removed no points, and
left poses unchanged. Raw negative control
`piecewise_surfel_blocks_v0/raw_joint_overlap_projection_negative_v2` refuses at precheck, so this is not a tool for
making an unfixed raw loop look clean.

Benchmark harness:
`tool/benchmark_piecewise_joint_pipeline.py`.

Benchmark artifact:
`output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_pipeline_benchmark_v1`.

Result: `all_expectations_passed=true`.

| Case | Stage accepted | Result |
|---|---|---|
| real repeat | block + joint surfel | `CERTIFIED`, endpoint `0.2853 m`, wall sep `0.0100 m`, thickness `0.0498 m` |
| raw projection negative | projection-only guard | refused |
| synthetic corner | block | `CERTIFIED`, endpoint `0.0000015 m`, wall sep `0.0010 m`, thickness `0.0378 m` |
| synthetic single wall | block | `CERTIFIED`, endpoint `0.000018 m`, wall sep `0.00038 m`, thickness `0.0156 m` |

Operational caveat: this is a certified output for this repeat-loop bag, not yet a general LingBot loop-closure backend.
Before calling it robust, run the same block + guarded surfel pipeline over additional real bags and synthetic regimes,
preferably with synchronized Go2 yaw/odom/IMU.

Synthetic regime sweeps now exist for the same pipeline:

- `tool/sweep_piecewise_joint_sim_regimes.py`
- Medium sweep: `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_sim_regime_sweep_v1`
- Stress sweep: `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_sim_regime_stress_v1`

Result: `72 / 72` exact-factor closed-loop synthetic cases certified across corner, single-wall, and parallel-wall
geometries, yaw drift `0-12 deg`, support `40-180` wall points/frame, and wall noise `0.006-0.04 m`. Projection was not
needed on these exact-factor synthetic cases; the block optimizer certified them directly.

This strengthens the mechanism claim, but it is not the same as noisy real-factor robustness. Next validation should add
synthetic factor noise/outliers and run on additional real bags.

### 2026-07-02 transient-anchor factor robustness probe

Added in `go2_mono_nav`:

- `tool/build_transient_anchor_factors.py`
- `tool/sweep_piecewise_joint_factor_noise.py --transient-anchor-factors`

What changed:

- Raw cachelet/noisy loop factors can now be clustered into transient-anchor consensus factors.
- Consensus factors carry calibrated `std_xy_m`, `std_yaw_rad`, support counts, pivot fraction, and explicit
  `switch_weight`.
- `read_memory_factors` now honors `switch_weight`.
- High-dispersion raw factors are filtered before consensus.

Simulation A/B:

| Sweep | Result |
|---|---:|
| raw noisy-factor smoke | `5 / 8` certified |
| transient-anchor noisy-factor smoke | `8 / 8` certified |
| raw outlier stress | `5 / 16` certified |
| transient-anchor outlier stress with dispersion prefilter | `11 / 16` certified |

Artifacts:

- `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_factor_noise_smoke_v1`
- `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_factor_noise_anchor_smoke_v1`
- `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_factor_noise_outlier_raw_v1`
- `output/loop_closure_research/provenance_elastic_surfels_v0/piecewise_joint_factor_noise_outlier_anchor_v2`

Real repeat-loop transient-anchor run:

| Output | Verdict | Endpoint | Wall sep p90 | Revisit thickness p90 |
|---|---|---:|---:|---:|
| `transient_anchor_probe_v1/real_repeat_anchor_block` | OLD_GATE_ONLY | `0.2853 m` | `0.0622 m` | `0.1852 m` |
| `transient_anchor_probe_v1/real_repeat_anchor_block_joint_surfel` | CERTIFIED | `0.2853 m` | `0.0165 m` | `0.0491 m` |

Trajectory comparison:
`output/loop_closure_research/provenance_elastic_surfels_v0/transient_anchor_probe_v1/real_repeat_anchor_trajectory_comparison.png`.

Caveat: the real transient-anchor path certifies after the same guarded joint-overlap surfel stage, but the consensus
anchor is pivot-contaminated (`~0.50` local pivot point fraction) and does not fix the rotation-heavy observability
problem. Raw, tuned piecewise, and transient-anchor outputs all retain about `16.27 deg` of rotation-dominant yaw over
`0.037 m` path. The next real improvement needs anchor-cell-specific factor generation plus Go2 yaw/odom/IMU for pivot
islands.

### 2026-07-02 transient-anchor V2 cachelet grouping

`tool/build_transient_anchor_factors.py` now supports `--group-by {time,cachelet,time-cachelet}` and defaults to
`time-cachelet`. This keeps different cachelet/anchor hypotheses separate instead of averaging them into one factor.

Real repeat-loop V2 artifacts:

- Consensus factors:
  `output/loop_closure_research/provenance_elastic_surfels_v0/transient_anchor_probe_v2/real_repeat_anchor_cachelet_factors.csv`
- Certified block output:
  `output/loop_closure_research/provenance_elastic_surfels_v0/transient_anchor_probe_v2/real_repeat_anchor_cachelet_block`
- Benchmark:
  `output/loop_closure_research/provenance_elastic_surfels_v0/transient_anchor_pipeline_benchmark_v2`
- Trajectory comparison:
  `output/loop_closure_research/provenance_elastic_surfels_v0/transient_anchor_probe_v2/real_repeat_anchor_cachelet_trajectory_comparison.png`

V2 result:

| Candidate | Endpoint | Wall sep p90 | Revisit thickness p90 | Final stage | Verdict |
|---|---:|---:|---:|---|---|
| transient-anchor V1 | `0.2853 m` | `0.0165 m` | `0.0491 m` | block + joint surfel | CERTIFIED |
| transient-anchor V2 | `0.2855 m` | `0.0410 m` | `0.0634 m` | block only | CERTIFIED |

The benchmark passes and skips projection because the block is already certified. Manually projecting V2 after that
failed the final leaderboard, so do not run the surfel projection after a certified block output.

### 2026-07-02 pivot-yaw literature probe

The next elegant backend is **Certified Pivot-Anchor Graph**, not larger global BA:

- translation windows produce real colored surfels and SE(2) block corrections;
- rotate-in-place windows become pivot islands with yaw/SO(3), panorama, Go2 yaw/IMU/contact, and optional
  Manhattan/vanishing-direction evidence;
- every cachelet/yaw/structure factor is covariance-gated and switchable;
- Foxglove export still moves/reintegrates real colored points only after the provenance leaderboard passes.

Literature basis is recorded in
`docs/lingbot_loop_backend_literature_review.md`: pure-rotation SLAM, Rotation-Only BA, Manhattan/structural SLAM,
planar-inertial SLAM, contact-aided legged state estimation, Anchor3R/LingBot/PAS3R/VGGT-style transient anchors, dense
surfel/submap deformation, and switchable loop constraints.

Implemented a small executable test in `go2_mono_nav/tool/optimize_piecewise_surfel_blocks.py`:
`--yaw-pair-csv`, `--yaw-pair-weight`, `--yaw-pair-delta-scale`, and covariance/disagreement gates. Artifact root:
`output/loop_closure_research/provenance_elastic_surfels_v0/pivot_yaw_pair_probe_v1`.

Result on the current repeat loop:

| Candidate | Endpoint | Rotation-dominant yaw | Wall sep p90 | Revisit thickness p90 | Verdict |
|---|---:|---:|---:|---:|---|
| transient-anchor V2 block | `0.2855 m` | `16.27 deg` | `0.0410 m` | `0.0634 m` | CERTIFIED |
| visual yaw pairs, scale `+1.0` | `0.2859 m` | `20.77 deg` | `0.0585 m` | `0.1773 m` | OLD_GATE_ONLY |
| visual yaw pairs, scale `-1.0` | `0.2862 m` | `12.53 deg` | `0.0377 m` | `0.0980 m` | CERTIFIED |

Interpretation: pair-level visual yaw can finally change the rotation-dominant metric, but it is not yet a cleaner
map than V2 because repeated-wall thickness gets worse. Do **not** replace the V2 Foxglove artifact with the yaw-pair
artifact. The useful next step is a switchable pivot factor with three hypotheses (`+visual`, `-visual`, `zero`) plus
real Go2 yaw/IMU/contact data from a new `wsj` recording.

### 2026-07-03 switchable pivot-yaw targeted sweep

Added `go2_mono_nav/tool/sweep_pivot_yaw_hypotheses.py` and ran a targeted switch search under the restricted sandbox,
writing outputs to `/tmp/pivot_yaw_hypothesis_sweep_v1_targeted`.

The tool groups the 8 trusted visual pivot-yaw pairs into 5 pivot groups and tests discrete per-group switches:
`-1` opposite visual residual, `0` keep raw yaw, `+1` visual residual. Each candidate runs the same piecewise optimizer
and the normal provenance leaderboard.

Targeted real result: `25` candidates, `6` certified.

| Candidate | Switches | Endpoint | Rotation-dominant yaw | Revisit thickness p90 | Verdict |
|---|---|---:|---:|---:|---|
| transient-anchor V2 block | baseline | `0.2855 m` | `16.27 deg` | `0.0634 m` | CERTIFIED |
| best switch score | `-1,-1,0,0,0` | `0.2869 m` | `13.24 deg` | `0.0806 m` | CERTIFIED |
| best endpoint switch | `-1,-1,-1,0,1` | `0.2853 m` | `12.50 deg` | `0.0861 m` | CERTIFIED |
| best rotation switch | `-1,-1,-1,-1,1` | `0.2869 m` | `8.54 deg` | `0.1021 m` | CERTIFIED |

Conclusion: switchable pivot yaw improves the rotation-dominant trajectory metric, but it still makes the displayed
revisited wall thicker than V2. It is not the Foxglove fix. The next real backend change is to put the switch variables
and repeated-wall thickness residual into the optimizer, then validate on a full overnight grid and a new `wsj` bag with
Go2 IMU/contact/body-yaw topics.

### 2026-07-03 in-optimizer switch prototype

The current sandbox could not write to `go2_mono_nav`, so the in-optimizer prototype was built as a `/tmp` optimizer
copy and the reusable patch was saved here:

`docs/patches/optimize_piecewise_surfel_blocks_yaw_switch_prototype.patch`

It appends one bounded continuous switch variable per pivot-yaw group and solves those switches jointly with block
corrections and certificate residuals. Smoke artifacts:

- `/tmp/pivot_yaw_switch_optimizer_v1/simple_endpoint_w1_prior0p15`
- `/tmp/pivot_yaw_switch_optimizer_v1/simple_endpoint_w1_prior0p01_initm1`
- `/tmp/pivot_yaw_switch_optimizer_v1/trajectory_comparison.png`

Result with crude endpoint factors:

| Candidate | Switch behavior | Endpoint | Rotation-dominant yaw | Revisit thickness p90 | Wall p90 | Verdict |
|---|---|---:|---:|---:|---:|---|
| no-op prior | switches ~`0` | `0.2899 m` | `20.98 deg` | `0.3225 m` | `0.0582 m` | OLD_GATE_ONLY |
| negative init | switches `-0.70` to `-0.98` | `0.2890 m` | `13.64 deg` | `0.0857 m` | `0.0661 m` | FAIL |

This proves the switch variables can recover the negative-yaw basin, but the output is still not acceptable for
Foxglove. The failure is now explicit: rotation yaw improves, overlap thickness improves versus no-op, but local wall
quality fails. Next patch must combine switch variables with real cachelet/transient-anchor factors and a wall-thickness
objective, then rerun the full certificate.

### 2026-07-03 generic wall-thickness residual probe

Updated the saved prototype patch with `--surface-thickness-weight` and `--surface-thickness-target`:

`docs/patches/optimize_piecewise_surfel_blocks_yaw_switch_prototype.patch`

Result:

| Candidate | Endpoint | Rotation-dominant yaw | Revisit thickness p90 | Wall p90 | Verdict |
|---|---:|---:|---:|---:|---|
| negative switch, no thickness | `0.2890 m` | `13.64 deg` | `0.0857 m` | `0.0661 m` | FAIL |
| strong generic thickness | `0.2936 m` | `8.76 deg` | `0.3566 m` | `0.0548 m` | OLD_GATE_ONLY |
| soft generic thickness | `0.2890 m` | `8.97 deg` | `0.0944 m` | `0.0640 m` | FAIL |

Conclusion: generic local thickness is the wrong residual. It can improve the global wall p90, but it either breaks the
repeated-wall overlap certificate or still fails local wall quality. The next residual must be provenance/source
separated: optimize repeated first-vs-revisit wall thickness without collapsing unrelated single-visit wall cells.

### 2026-07-03 source-separated residual probe and next backend

The source-separated thickness extension was tested in the `/tmp` switch prototype and saved in:

`docs/patches/optimize_piecewise_surfel_blocks_yaw_switch_prototype.patch`

Results:

| Candidate | Endpoint | Rotation-dominant yaw | Wall cells | Revisit sep p90 | Revisit thickness p90 | Wall p90 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| source thickness `0.6 @ 7cm` | `0.2890 m` | `13.39 deg` | `1` | `0.0348 m` | `0.0883 m` | `0.0661 m` | FAIL |
| source thickness `0.2 @ 9cm` | `0.2886 m` | `13.25 deg` | `1` | `0.0417 m` | `0.0902 m` | `0.0667 m` | FAIL |

Conclusion: source-separated thickness is a good certificate signal, but it is still not the loop-closure measurement
we need. Both runs close the endpoint and keep the floor clean, but only one repeated-wall cell survives and local wall
thickness remains above the `6 cm` gate. This is why Foxglove still looks wrong: the graph lacks enough independent
structural evidence to decide that two observed walls are the same wall.

The cleaner next backend is **Structural Consensus Surfel Graph**:

- Turn LingBot cachelets into structural tokens: wall slabs, floor plane, wall line distance/orientation, z support,
  local normal confidence, source id, and free-space side.
- Build loop hypotheses from cachelet-token agreement, not endpoint gap or isolated image matches.
- Accept loop hypotheses only through switchable/GNC or group-consistency logic, requiring multiple independent wall
  tokens. A one-cell wall overlap is rejected even if endpoint is below `30 cm`.
- Optimize pose/correction nodes, wall-token landmarks, and colored surfel/cachelet block transforms together.
- Add Go2 IMU/contact/body-yaw factors for rotate-in-place spans in the next `wsj` bag; without those topics, the
  rotation fix cannot be fully validated on real data.
- Export Foxglove only after the held-out provenance certificate passes. No fake color, no point deletion, no visual
  acceptance based only on endpoint.

### 2026-07-03 structural wall-token gate

Added a concrete prototype in this repo:

`tool/extract_lingbot_wall_tokens.py`

Purpose: before creating a loop factor, split the provenance cloud into temporal cachelets, extract wall-line tokens,
and require multi-token/multi-orientation structural agreement. This is an admission test for loop closure, not a
cosmetic filter.

Results:

| Case | Verdict | Key evidence |
|---|---|---|
| raw real repeat map | NO_STRUCTURAL_LOOP_SUPPORT | strict gate finds only one rank-1 long-range wall match |
| raw real repeat map, loose thresholds | NO_STRUCTURAL_LOOP_SUPPORT | only `3` inlier tokens / `97` support points, below structural gate |
| source-separated residual outputs | NO_STRUCTURAL_LOOP_SUPPORT | still one rank-1 wall match |
| other provenance variants checked | NO_STRUCTURAL_LOOP_SUPPORT | no long-range structural pair |
| synthetic repeated corner | HAS_STRUCTURAL_LOOP_SUPPORT | `42` inliers, `6346` support points, `3` wall-axis groups |
| synthetic repeated single wall | NO_STRUCTURAL_LOOP_SUPPORT | many matches but only one wall-axis group, so ambiguous |

Operational rule: if this gate says `NO_STRUCTURAL_LOOP_SUPPORT`, do not add a loop factor and do not serve the map in
Foxglove as fixed. For the current bad `wsj` repeat map, the honest conclusion is that the available repeated-wall
evidence is too sparse/ambiguous; the next real recording needs same-line/same-heading overlap plus Go2 IMU/contact/
body-yaw topics.

### 2026-07-03 SE(2) wall-token loop factors

Added:

`tool/build_wall_token_loop_factors.py`

The extractor now estimates SE(2) candidate corrections: translation plus signed yaw from wall-axis agreement. The
builder converts only `STRUCTURAL_OK` candidates into optimizer memory-factor rows.

Control results:

| Case | Factor rows | Endpoint result |
|---|---:|---:|
| current real raw map | `0` | no optimizer run; gate vetoes loop factors |
| synthetic repeated single wall | `0` | gate vetoes ambiguous one-wall loop |
| synthetic repeated corner, SE(2) factors only | `4` | `0.8185 m -> 0.0354 m` |

The synthetic SE(2) factor run used no endpoint term and no wall/certificate residuals, so the closure came from the
structural token loop factors themselves. This is the first clean proof that the proposed structural-token path can
produce a real optimizer correction when the evidence is actually present.

Do not apply it to the current real map: `/tmp/lingbot_wall_tokens_raw_se2_v1/wall_token_loop_factors_summary.json`
reports `NO_STRUCTURAL_FACTORS`.

### 2026-07-03 structural-token simulation sweep

Added:

`tool/sweep_wall_token_loop_sim.py`

Compact sweep:

`/tmp/wall_token_loop_sweep_v2/sweep_summary.json`

Result: `6 / 6` expected outcomes.

| Case | Expected behavior | Result |
|---|---|---|
| corner, `8 deg` drift | close | `0.8185 m -> 0.0145 m` |
| corner, `16 deg` drift | close | `1.0209 m -> 0.0275 m` |
| corner, noisy walls | close | `0.8185 m -> 0.0733 m` |
| corner, loop-only walls | close | `0.8185 m -> 0.0105 m` |
| single wall | veto | `0` factors |
| parallel walls | veto | `0` factors |

This is the current best evidence for the elegant loop-closure direction: structural wall tokens can drive a real SE(2)
optimizer correction when there is a corner-like constraint, and they correctly refuse ambiguous wall-only cases. It
still does not certify the current real `wsj` map.

Stress sweep with fake loop outliers:

`/tmp/wall_token_loop_sweep_stress_v1/sweep_summary.json`

Result: `6 / 6` expected outcomes. Positive repeated-corner cases still closed with three injected isolated fake
`STRUCTURAL_OK` candidates per run; single-wall negatives still wrote `0` factors. This is because the factor builder
clusters candidate SE(2) corrections and only emits a consensus cluster. It is a stronger synthetic validation, not a
real-map fix.

Weighted yaw and real-map batch gate:

- `tool/extract_lingbot_wall_tokens.py` now estimates loop-candidate yaw with a support-weighted median of wall-axis
  rotations. This fixed the noisy seed-10 synthetic corner boundary case: `0.8185 m -> 0.0650 m` instead of stopping at
  `0.0981 m`.
- `tool/evaluate_wall_token_loop_maps.py` batch-runs the same gate over real maps and records trajectory metrics.
- Weighted-yaw seed stress: `/tmp/wall_token_loop_sweep_seedstress_weighted_yaw_v1`, `36 / 36` expected outcomes.
- Real-map batch gate: `/tmp/wall_token_loop_real_eval_weighted_yaw_v1`, `0 / 4` maps admitted. Raw provenance still
  has endpoint `0.6396 m`, rotation-dominant yaw `16.27 deg`, `34` tokens, `0` structural OK pairs, and `0` factors.

Operational rule remains unchanged: synthetic evidence says the structural-token loop factor is a viable backend path,
but the current real `wsj` map still must be vetoed. Do not show it as a fixed Foxglove reconstruction.

Final overnight stress update:

- First full run before the latest gate: `/tmp/wall_token_loop_sweep_overnight_weighted_yaw_v1`, `572 / 576`.
  It exposed a real bug: degenerate parallel-wall pairs produced absurd raw translations (`78-95 m`) that were clamped
  to `0.8 m` and became false loop factors.
- Fix: `tool/build_wall_token_loop_factors.py` now rejects raw translations above `--max-raw-xy` before clustering;
  `tool/extract_lingbot_wall_tokens.py` now uses a 1D yaw search with translation re-solve instead of only a
  support-weighted yaw median.
- Targeted regression: `/tmp/wall_token_loop_targeted_yawsearch_v1`, `8 / 8`.
- Final full run: `/tmp/wall_token_loop_sweep_overnight_yawsearch_v1`, `576 / 576`.
  - Corner positives all close: endpoint max `0.0655 m` under the `0.08 m` gate.
  - Single-wall and parallel-wall negatives all veto: `0` factors.
- Real gate after the fix: `/tmp/wall_token_loop_real_eval_yawsearch_v1`, still `0 / 4` admitted.

This is the strongest loop-closure evidence so far, but the current real `wsj` repeat map remains unfixed because it
still has no consensus structural loop factor.

### 2026-07-03 elegant backend direction: certified pivot-memory replay

The literature-backed direction is now clearer:

- LingBot-Map/GCT separates anchor context, local pose-reference windows, and trajectory memory. Mirror that outside
  the model: fixed anchors, local cachelets, sparse memory factors.
- Feed-forward dense SLAM systems such as VGGT-SLAM 2.0 and Neural Graph Map do not trust a monolithic dense map after
  loop closure; they anchor dense submaps/cachelets to a graph and update block poses.
- Rotation-only BA and RD-VIO both point to the same fix for rotate-in-place spans: handle them as yaw/SO(3) pivot
  islands with deferred/low-weight metric geometry, not as normal triangulating 3D frames.
- Legged-robot factor graph work such as VILENS supports using Go2 yaw/contact/body odom when vision is degenerate.
- TEASER++/TLS-style robust registration supports the current wall-token admission rule: no consensus, no loop factor.

Operational design:

1. Split trajectory nodes into `anchor`, `cachelet`, and `pivot`.
2. Let cachelets own real colored surfels and structural wall/floor/free-space tokens.
3. Let pivots own yaw/SO(3) factors from visual rotation and, in the next bag, Go2 yaw/IMU/contact/body odom.
4. Use LingBot memory retrieval only to propose revisits; write SE(2) loop factors only after wall-token consensus.
5. Replay/export the map from corrected cachelet/pivot poses. Do not fake color, delete walls, or claim a Foxglove fix
   unless endpoint drift, source-separated wall thickness, repeated-wall support, floor stability, and pivot-yaw metrics
   improve together.

For the current real `wsj` repeat map, the gate remains `NO_STRUCTURAL_FACTORS`. The right next experiment is a new
repeat-loop bag with same-heading/corner overlap plus Go2 yaw/IMU/contact/body-odom topics.

## Foxglove serving (separate from reconstruction)

- New `foxglove-sdk` speaks `foxglove.sdk.v1` and rejects legacy `foxglove.websocket.v1` clients.
- Legacy `foxglove_websocket` + `websockets 16.0` trips `_drain_helper` AssertionError under
  remote backpressure (`viser` pins `websockets`, blocking a downgrade).
- **To just view a clean cloud:** open an `.mcap` file directly in Foxglove (`File → Open local
  file`) — bypasses all server bugs. Artifacts in `runs/foxglove/` (`chess.mcap`, `gpu_chess.npz`).
- For a robust live server: run on the GPU (localhost, no backpressure) and tunnel.

## DEPLOYMENT — LingBot-mono nav closed loop + perception speedup (2026-07-02)

Go2 mono teach-repeat (robot `ssh wsj`, TinyNav fork). Two problem classes were solved: the **closed-loop
nav instability** (robot spun / hit walls) and the **perception loop speed** (was ~1 Hz → stale-pose
overshoot). End state: **perception loop 1.2 s → 0.29 s (0.8 → 3.1 Hz)**, live-map consistent, base off.

### Perception speedup (the loop was NETWORK-bound, not depth-bound)
- **Runtime depth = LingBot streaming + one-time scale**, replacing per-frame MetricAnything (1536²-fixed,
  0.51 s/frame, can't lower-res or go onboard). LingBot streaming (`StreamingSession`, O(1)/frame) = ~0.13 s,
  and is scale-consistent (0.6%) so the metric scale is bootstrapped ONCE, not re-derived per frame.
- **`scale.json` (built at map time, read at runtime):** `metric = live_raw × map_scale`. Since the map's
  cloud/occupancy/poses are all built `× map_scale`, live depth lands in the map's exact scale → **live-map
  consistency by construction**. Runtime uses `map_scale` primary; a floor-height RANSAC is the startup
  SANITY check (implied camera-height within 20%); fallback = floor-bootstrap → MetricAnything-once.
  `tool/regen_scale_json.py` retrofits maps built before this.
- **The real speed lever was WIRE size** (server compute 0.13 s ≪ 0.9 s loop): **JPEG image intake +
  slim float16 single-array depth return = ~8× less wire** (7.6 → 0.9 MB/frame) → loop 0.9 → 0.29 s.
- `kv_cache_sliding_window` 64→16: 1.34× depth compute + **4× less KV-cache memory** (onboard-ready),
  0.3% depth change (reloc re-anchors within the window). Now the LingBotConfig default.

### The metric that matters is the MAP's, not the live depth's
Reloc PnP uses the **map's** depth for 3D points + live 2D keypoints → the map-frame pose is independent of
live depth scale. Live depth only affects inter-reloc VO drift + local occupancy, both anchored by reloc
every ~3 s → **live depth needs only rough scale-consistency, not precise metric.** So the `scale.json`
precision is a nicety; the floor-bootstrap fallback is sufficient. The real dependency is **reloc coverage**.

### Closed-loop nav fixes (robot side, committed c2b0992)
- **Planner gravity-alignment** (the spin fix): VO world = OPTICAL frame (Z=forward), but the obstacle map
  treated world-Z as height → forward slab of phantom obstacles → boxed-in → rotate-in-place. Align
  pose+occupancy+trajectories+goal by one G at startup (controller is invariant to a global rotation).
- **Controller safety:** max_angular 0.8→0.30; forbid reverse (arc/re-orient); stop on stale pose / reloc
  jump / reloc-loss (>4 s); reactive forward **E-STOP from live depth** (reloc-independent); arrival braking
  on the FINAL-goal distance (not the 2.5 m lookahead — that was a moving target and never "arrived").
- **map_node:** clear planner target + stop on nav completion (was only cleared on POI-cancel → stale target
  kept driving); publish `/control/goal_distance`; success debounce (3 frames) vs reloc jitter.

### Onboard verdict (why LingBot can't go cheap onboard yet)
Profiled per-frame compute: DINOv2 patch_embed ~20-30%, frame_blocks (24× intra) ~35-43%, global_blocks
(24× KV-cache temporal, FlashInfer) ~35-51%. **TRT-ing the DINOv2 backbone buys ≤30%** — the cost is the
48 attention blocks, half of them the stateful KV-cache (hardest to TRT). LingBot's heaviness IS the
streaming. Endgame = **distill LingBot → a light streaming student** (keeps consistency) for onboard; a
light single-frame model would break live-map consistency. But offboard is now fast enough (3.1 Hz) that
onboard is not urgent.

### OPEN
- **Reloc coverage:** live reloc doesn't fire when the robot is outside mapped views (image-embedding
  `max_sim < 0.70`, depth-independent). Re-map the nav area, then supervised teach-repeat at 3 Hz to
  validate the full chain (gravity planner + arc + arrival braking + E-stop). Not yet done (needs the robot).

## CORRECTED MISCONCEPTIONS — read before trusting any earlier conclusion (2026-07-02)

Wrong conclusions reached (and later refuted with evidence) during this project. Several were corrected by
the USER pushing back — treat user skepticism as signal.

1. **"Bad reconstruction = LingBot training problem"** → WRONG. Per-frame geometry was always clean (2cm);
   the smear was capture motion (parallax starvation) + accumulated pose jitter. LingBot was never the culprit.
2. **"Scale needs a per-frame metric model"** → WRONG. Metric scale is ONE build-time constant (scale.json);
   LingBot raw scale is start-invariant (1.008±1.9%). Per-frame MetricAnything was 4x wasted compute.
3. **"Loop closure has no headroom / is blocked"** → HALF-WRONG. Blocked on reverse-heading bags only.
   Same-heading revisit closes fine (repeat1: 26 edges, reloc max 45.6→27.5cm). Protocol, not method.
4. **"多圈覆盖=好地图"** → INCOMPLETE. Laterally-offset rings CANNOT be stitched visually (low
   floor-camera: 1-2m lateral offset = no shared view; SIFT 19 edges, LightGlue 10/1201 cross-lane).
   Coverage must come from a road-network with SAME-LINE shared segments.
5. **"High PnP inliers = true match"** → WRONG on repetitive texture. 228/276 LightGlue edges with 100+
   inliers were FALSE (perceptual aliasing) and warped the map 3.8m. A pose-prior gate is mandatory.
6. **"Endpoint gap measures closure quality"** → WRONG metric. Multi-pass stitching can improve while the
   gap worsens. Acceptance metric = leave-one-out RELOC ERROR, always.
7. **"Blur = user drove too fast"** → WRONG (user was right). Both captures 66-70% blurred at careful speed.
8. **"Blur = dark room"** → WRONG (user was right again; lights were on). Real chain: indoor light →
   auto-exposure ~33ms × GAIT velocity oscillation → per-frame alternating blur (sharp 197 / smeared 21,
   0.1s apart). Jump-site frames are 3x blurrier than baseline (median 15 vs 42; 84% vs 40% severe).
9. **"Full frame rate will fix the tracking slips"** → REFUTED by experiment: stride-1 pass 44→35 jumps
   (-20% only). The fix is EXPOSURE (lock ~8ms + gain), not fps. (Gait is physics; exposure is a knob.
   Fallback if exposure can't balance: D435 infra1 stream is GLOBAL shutter.)
10. **"LingBot streams at 20Hz so our stack should"** → conflates model-core with pipeline. Model-core on
    our A6000: 12Hz SDPA → 14.7Hz FlashInfer (after bit-exact in-memory preprocess replaced a per-frame
    PNG round-trip). Robot loop is network+VO bound: 3.6-4.6Hz — and that is ALREADY sufficient (the
    original failures were at 1Hz).
11. **"RViz看起来对 = 数据好"** → WRONG. RViz image panels downscale (hides blur); preview clouds are
    voxelized (hides pose spikes); the eye locks onto sharp frames. Judge with metrics, not RViz.
12. **"Loop closure takes 1-2h"** → self-inflicted: SIFT was recomputed per PAIR (80% of runtime).
    Cached per frame → ~15min. Profile before accepting slowness.
14. **"一处闭环能修全程漂移" / "start-reentry closure fixes a long drive"** → WRONG (2026-07-03, teach0703
    203m drive). Drift is DISTRIBUTED along the route; a pose graph can only correct where edges constrain
    it. All 49+45 loop edges clustered at the single start-reentry region → the outer perimeter loop stayed
    inflated ~2m outward (user spotted it: "start is not in the middle of my real trajectory" — the phantom
    unknown 'moat' between inner free space and the outer free ring = same physical space mapped twice).
    Worse: re-fusing cloud/occupancy through the sparse correction created phantom obstacles (trail 58% in
    obstacle band). Rebuild was REVERTED from the robot copy. FIX IS PROTOCOL, not math: on multi-loop
    drives, re-enter the start/junction segment EVERY lap (mid-route closures bound drift piecewise); and
    the loop-closure prior gate must scale with drive length (49 TRUE edges at median dt 1.77m were killed
    by the 1.5m gate — --prior-dt flag added to loop_close_offline.py).
13. **"scale.json map_scale transfers to any live session"** → WRONG (2026-07-03, caught during student
    onboard integration). LingBot's canonical scale is SESSION-dependent (anchor frames + engine +
    kv-window): the TEACHER's own fresh streaming run × map_scale put the floor at 0.48-0.60m vs the true
    0.336m (1.4-1.8x off). The deployed teacher path survived because the depth server's floor-height
    SANITY CHECK silently fell back to floor-bootstrap (s = camera_height/floor_raw) — that check is
    LOAD-BEARING, not a nicety. Consequence: any backbone that can't emit K (the distilled student's
    camera head is untrained) must get K from scale.json's stored intrinsics so the check still runs
    (implemented in lingbot_depth_server.py). Correction #2's "start-invariant (1.008±1.9%)" held only
    within same-engine/same-anchor-protocol sessions.

Standing operational lessons: long asus jobs need `setsid nohup ... & disown` (session restarts kill
tracked tasks); never `pkill -f PATTERN` where PATTERN appears in your own cmdline (use `patter[n]`);
conda-wrapper kills leave the python child alive (kill the child or use pkill on the script name);
GPU servers (depth/preview) must be stopped before map builds (48GB fills); robot disk needs one-map
discipline (delete superseded robot copies — asus keeps full archives).

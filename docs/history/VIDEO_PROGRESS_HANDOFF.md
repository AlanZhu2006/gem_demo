# GEM 视频进度与 Claude 交接

更新日期：2026-09-20（Asia/Shanghai）。工作目录：
`/home/asus/Research/pengyue/gem_demo`。

## 用户目标与本次交接范围

用户想用 LingBot-Map 做 RGB 三维重建，并在视频中按时间增量展示点云；参照
`../AnchorScale/docs/lingbot_deployment.md`，尤其强调应对齐通常使用的 `demo.py`，
不认可把明显平移重影直接归因于模型漂移。最新要求是先更新 deployment 问题记录，
再单独记录视频进度，交给 Claude 继续。不要把下面的诊断版本当作最终完成的视频。

deployment 文档已于 2026-09-20 重写为**操作手册**（`lingbot_deployment.md`），
错误结论已删除，历史日志移到 `lingbot_deployment_history.md` 存档。动手前读手册
§2 约定与 §5 验证方法；不要从存档里复制命令或结论。另见本目录 `DEPLOYMENT_AUDIT.md`。

## 已经完成的工作

1. 从 MCAP 提取 RGB 和整数纳秒时间戳，LingBot 仅使用 RGB。机身里程计仅用于
   独立诊断，录制深度不进入 LingBot 重建。
2. 实现持续 KV 的重建输出、逐帧深度/置信度/内参/位姿保存，以及 FPV + 固定
   斜视点云视频。视频按原始 ROS log 时间戳增加点云，2x 播放、15 FPS、1280×720。
3. 修正本地对导出位姿的解释：原版 demo 后处理取逆后，viewer 又取逆一次。
   旧封装只对齐前半段，直接消费导出矩阵，造成平移重影。当前修正与原 viewer
   的点云投影已抽样验证一致。没有给点云做平滑、闭环或里程计拟合修正。
4. 对 320 帧平移窗口实际运行 demo.main；完整模型加载/推理/后处理保持原版，
   仅替换启动网络服务器的 viewer 构造器。抽样使用原 viewer 几何函数验证。
5. 完成全长 `demo.py + SDPA + auto interval 4` 对照，输出数据、诊断和视频。
6. 完成全长 `demo.py + FlashInfer + auto interval 4` 推理、955 帧导出、PLY、
   轨迹诊断和 LK 重投影检查；视频尚待 Claude 渲染。
7. 原 2.5D 路径修正时间桶：绝对 ROS 时间，桶时间取最后观测，避免提前泄漏后续
   点云；`mount2.npy` roll 符号与标定脚本一致。已有历史 MP4 没有覆盖。

## 当前视频和数据（注意版本）

所有路径相对于本目录。MP4 通常有同名 `.jpg` 四时刻预览及 `.audit.json`。

| 产物 | 状态 / 用途 |
|---|---|
| `outputs/gem_lingbot_translation_pose_verified.mp4` | 已修正的短平移段，当前最明确验证的局部结果；320 输入、313 点云帧，来源从 +10 秒重新初始化 |
| `outputs/gem_lingbot_pose_verified.mp4` | 全长修正位姿后的旧 wrapper 结果；955 点云帧，全程仍有大误差 |
| `outputs/gem_lingbot_demo_sdpa.mp4` | 本次实际 demo.py / SDPA / 自动关键帧间隔 4；已生成 469 视频帧，955 点云帧，时间因果检查通过，仍有散开 |
| `outputs/gem_lingbot_demo_flashinfer.mp4` | **已生成并由用户验收（2026-09-20）**；31.27 s、1280×720、2×、469 视频帧、955 点云时刻，causal visibility PASS。定量最好的一条（RMSE 0.187 m / 2.873 px） |
| `outputs/gem_lingbot_incremental.mp4`、`outputs/gem_lingbot_translation_probe.mp4` | 早期错误位姿版本，仅保留对照，不要作为最新结果展示 |
| **`outputs/gem_indoor_joint.mp4`** | **最终成片（2026-09-20）**；31.9 s。一张联合重建、两条路径；Baseline 倒放接 GEM 顺放喂成一次 session，接缝 4.2 cm；轨迹直接取重建相机位姿，无需配准。含目标图、GEM 到达金环与绿框。联合重建 LK 重投影 **2.810 px** |
| `outputs/joint_demo_flashinfer` / `outputs/joint_rgb` | 联合 session 的重建与输入清单（1749 帧，interval 6，max_frame_num 2048） |
| `outputs/gem_indoor_lingbot_final.mp4` | 两行各自独立重建的版本，保留作对照；1920×1080、30.4 s、×2，轨迹贴地绘制并与点云共用 z-buffer；两行以实际起动对齐、剪除卡顿；causal visibility PASS |
| `outputs/base_091940_demo_flashinfer` | Baseline 的 LingBot 重建（780 帧，FlashInfer，用新入口 `run_lingbot_manifest.py` 跑出） |
| `gem_indoor.mp4`、`gem_indoor_map.mp4`、`gem_outdoor.mp4` | 原项目历史成片，与新增 LingBot 流程不同，原样保留 |

数据目录对应关系：

- `outputs/cec_090850_rgb`：962 原始 RGB PNG + `manifest.json` + `telemetry_reference.npy`。
- `outputs/cec_090850_lingbot`：早期全长错误解释版本。
- `outputs/cec_090850_translation_probe`：早期 320 帧错误解释版本。
- `outputs/cec_090850_translation_pose_verified`：修正后的短段。
- `outputs/cec_090850_pose_verified`：修正后的全长旧 wrapper 版本。
- `outputs/cec_090850_demo_auto`：全长实际 demo.py / SDPA / interval 4。
- `outputs/demo_entrypoint_audit/report.json`：320 帧实际 demo 与 viewer 对照。
- `outputs/deployment_audit_official/rgb`：320 帧 batch_demo 原始导出。
- `outputs/cec_090850_demo_flashinfer`：本次默认后端全长运行目标目录，状态见下一节。

重建目录的 `reconstruction.json` 是完整导出完成标志之一；完整日志成功退出仍需确认。
诊断程序生成 `cloud_raw.ply`（保留 frame_key）、`trajectory_diagnostic.json/.png`。

## 最后一次运行状态：已完成，无需重复推理

完整 FlashInfer 已成功结束（进程 exit 0），参数为原版 demo 默认 streaming、auto interval 4、
64 帧缓存、8 初始帧、long checkpoint；仅启用 CPU 输出 offload，并用导出器替代
服务器启动。输入为同一完整 962 帧，没有跳过初始旋转。

- 日志：`outputs/demo_full_flashinfer_final.log`
- 原 Python PID：`2259872`，已退出，不再有待接管的推理进程。
- 输出：`outputs/cec_090850_demo_flashinfer`
- 原 Codex 工具会话 `31554` 已完成，Claude 无需使用此会话。
- 前两次失败日志 `demo_full_flashinfer.log` / `demo_full_flashinfer_retry.log` 是
  ninja / libcudart 搜索路径问题，已用进程环境修正；不要把旧日志当最新结果。
- `reconstruction.json`、`report.json`、955 份逐帧 NPZ、`cloud_raw.ply`、
  `trajectory_diagnostic.json/.png`、`pose_convention_audit.json` 已存在。
- 当前没有待完成的模型推理任务。下一步是渲染和视觉检查。下方重跑命令仅供复现，
  如需重跑必须使用新的输出目录；不要删除原始数据。

## 已有验证数字与尚未解决的问题

| 对照 | 结果 |
|---|---|
| 短平移段，错误/修正位姿解释 | 重投影 33.23 → 1.45 px；相同 313 时刻的轨迹诊断 RMSE 0.249 → 0.091 m |
| 原版 viewer 与修正公式、相同输入 | 320 帧运行抽样 15 帧，最大点坐标差 1.22e-7 模型单位 |
| 全长旧 wrapper，修正位姿 | 轨迹诊断 RMSE 2.389 m；重投影 6.594 px |
| 全长实际 demo.py / SDPA / interval 4 | 轨迹诊断 RMSE 0.967 m；重投影 6.264 px（60 对） |
| 全长实际 demo.py / FlashInfer / interval 4 | **轨迹诊断 RMSE 0.187 m；重投影 2.873 px（60 对）** |

轨迹数字均为对 Go2 **机身里程计**独立最佳 Sim(3) 拟合，非 GT，杆臂未标定，
不代表厘米级重建精度。只用于诊断，不改变渲染几何。

关键未决项：

1. 默认 FlashInfer 的全程定量结果明显改善；视频已渲染并通过用户主观验收，
   但**逐段局部几何一致性仍未逐一核查**。
   当前 SDPA 层忽略 `_skip_append=True`，
   小测试缓存从 1 帧变 2 帧，不能认为 SDPA 的关键帧模式等价。共享模型代码未改。
2. 全程一致性尚未最终验收；不能把剩余误差断言为旋转、低视差或模型能力问题。
   原始 sensor 时间戳有 58 处 >200 ms 间隔，最大 835 ms，尚未与误差位置关联。
3. 当前模型坐标不是米；既有地面拟合失败并使用 camera-up fallback，重力未标定。
   视频的固定视角使用全序列 bounds，仅用于构图；点云可见性按时间限制。
4. 目前是完成推理后的增量回放，尚未做实时前端。初始 8 帧共同初始化，仅从第 8
   帧显示第一份点云，避免把初始化使用的未来观测提前显示。
5. ~~尚未恢复 GEM/Baseline/手机第三视角的原组合视频~~ —— **已完成**。
   跨 session 注册**做了但结论是不可合并**：里程计链式初值重叠中位 29.7 cm，
   带剔除相似 ICP 后门限内 5.4 cm，但整个重叠区仍为中位 25.8 cm、p90 53.2 cm，
   非刚性漂移。最终成片改为两行各用自己的重建。详见 deployment 手册 §2.7。
6. **`n_cec1` ≡ `cec_090850` 已确认**：重建时间戳 100% 落在该场次遥测区间内。
7. 新增可用于新场次的入口 `run_lingbot_manifest.py`（只读 RGB manifest）。
8. 地面平面与米制尺度改由**相机轨迹**求得（轨迹平面厚度 p95 3.6/1.7 cm），
   替代失败的点云地面拟合；详见手册 §2.6。仅用于绘图，未回写重建。
9. 联合重建已完成 LK 重投影核查：**中位 2.810 px**（113 对），反向约定对照
   34.69 px，与 GEM 单独 session 的 2.873 px 持平。Baseline **单独**那条重建仍未做
   该核查（但成片不用它）。
10. 成片已标出成败依据：目标图缩略图、GEM 在 +61.4 s 自动锁定到达（82 条消息）、
    地面金色双环、第三人称绿框；Baseline 0 次锁定。**金环是该 run 自己宣布到达的
    位姿，不是独立测绘的目标位置。**
11. 仍未解决：联合重建两腿间约 5% 相对尺度漂移（不要拿视频量距离）；成片无单位提示；
    室外场景未走该管线；`render_indoor_final.py`（两行各自重建的旧版）已被取代但保留。

## 代码入口与复现命令

- `lingbot_incremental.py`：extract + 旧 wrapper reconstruct，位姿选项必须显式提供。
- `audit_demo_entrypoint.py`：直接执行真实 demo.main 并导出与 viewer 一致的相机位姿；
  可选择后端/关键帧间隔，`--export` 输出增量渲染需要的逐帧数组。
  当前仍要求 `--reference` 指向既有 reconstruction 作为时间戳/比较来源，尚未改成
  只读原始 manifest 的通用入口。默认后端仍为 SDPA，FlashInfer 必须显式指定。
- `audit_pose_convention.py`：LK 独立重投影验证；默认 gap 5 / stride 15。
- `inspect_lingbot.py`：PLY 和机身里程计诊断，可在共同时间戳比较两组结果。
- `render_lingbot.py`：视频、四时刻预览、时间可见性审计。
- `validate_lingbot.py`：仅与相同 wrapper 短前缀对齐，不是独立物理正确性验证。
- `test_grid_timing.py`：原 2.5D 时间桶回归检查，已通过。

在本目录运行，选择新的输出目录：

```bash
export PATH=/home/asus/miniconda3/envs/lingbot-map/bin:$PATH
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export LIBRARY_PATH=/home/asus/miniconda3/envs/lingbot-map/targets/x86_64-linux/lib${LIBRARY_PATH:+:$LIBRARY_PATH}
python audit_demo_entrypoint.py \
  --reference outputs/cec_090850_pose_verified \
  --out outputs/another_demo_flashinfer --backend flashinfer --export

# 以下针对已完成的输出；不要在导出未完成时运行。
python inspect_lingbot.py --input outputs/cec_090850_demo_flashinfer \
  --compare-input outputs/cec_090850_pose_verified
python audit_pose_convention.py --input outputs/cec_090850_demo_flashinfer
python render_lingbot.py --input outputs/cec_090850_demo_flashinfer \
  --out outputs/gem_lingbot_demo_flashinfer.mp4
```

## Claude 接下来按这个顺序继续

1. ~~**直接渲染已经完成的 FlashInfer 输出**~~ —— **已完成（2026-09-20）**。未重复
   GPU 推理，只执行 `render_lingbot.py`；用户已确认效果可接受。归因分析与写作
   规则见 deployment 文档新增 §6，最终状态见 §7。
2. 在相同 955 个输出时间戳比较全长旧 wrapper、demo SDPA、demo FlashInfer：轨迹
   诊断、LK 重投影、预览。当前两组同时改变多个设置，不能直接归因于某一个参数。
3. 根据结果确定标准接入。优先保留官方 demo 推理行为，只适配时间戳导出和增量展示。
   若需要消融，再做同精度/同后端/仅改变 interval 的实验。不要先用滤点掩盖重影。
4. 如默认 demo 明显改善，将其整理成可直接从 RGB manifest 运行的本地入口；明确
   置信度保留 top 35%、pixel stride 4 是当前视频显示策略，并非原版 viewer 默认。
5. 若仍有局部失败，定位具体时间段，结合图像运动、时间间隔和重投影异常判断。
   尺度/重力和最终视频合成是后续独立工作，不要用未经验证的米制轨迹覆盖点云。
6. 更新本文件及 deployment 新增节的最终结果，保留旧产物与失败证据。

## 环境与原始输入

- Python：`/home/asus/miniconda3/envs/lingbot-map/bin/python`。
- LingBot repo：`/home/asus/Research/lingbot-map`，checkpoint `weights/lingbot-map-long.pt`。
- 旧封装：`../AnchorScale/anchorscale/backbone/lingbot.py` 和
  `../go2_mono_nav/perception_server/streaming_session.py`。
- MCAP 根目录：
  `/home/asus/Research/Nav-graph-blind/projects/realworld/runtime/experiment_archives/jetson_20260919/jetson/runtime/go2/experiment_capture/episode_20260919T090850_042322Z/rosbag/survey`。
- 该 episode 是旧渲染脚本目标图引用的场次，与历史 `n_cec1` 别名的对应尚未确认。
- 本目录没有 Git 仓库。共享 LingBot repo 有用户既有修改，勿重置、覆盖或为了
  方便修复擅自改共享 attention 实现；本次工作只新增本地脚本/产物及更新文档。
- GPU 可能有其他任务，不要广泛 kill。原 MP4、原 MCAP、旧诊断结果全部保留。

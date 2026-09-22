# GEM actual English narration — v24

本稿已用于实际成片配音与字幕。依据作者指定的 `Nav-graph-blind/projects/paper/main.tex` 及其方法、仿真、真机实验正文和表格。室内玻璃墙标注由作者确认。

本次补全三处主要逻辑转场：记忆概念→室内示例、导航行为→共享几何机制、控制器接口→跨控制器评测。真机→仿真及 Table I→连续导航也加入简短承接。说明保持完整长句，字幕按语义短语切分，不把字幕换行当作语音停顿。

| 实际语音时间（秒） | 段落 | 英文 |
|---|---|---|
| 0.30–10.86 | opening | We introduce GEM, a geometric episodic memory that uses a streaming geometry model to help existing navigation policies return to previously observed places without retraining. |
| 11.40–30.36 | indoor | We first show how this memory supports an indoor revisit, where the robot must return to a place shown in a goal image. Both runs share the same starting pose, goal image, and survey history, but the baseline stops before a glass wall, while GEM uses that history to reach the destination. |
| 32.40–51.32 | outdoor | In the outdoor trial, GEM turns toward the remembered goal and updates its direction as the robot moves, while the unchanged NavDP controller plans the local motion. Across ten real-world settings, GEM reaches the goal in twenty-five of thirty trials, compared with four of thirty for the baseline. |
| 56.25–60.85 | environments | We also evaluate in Habitat on HM3D and MP3D. |
| 61.40–80.10 | simulation | In this episode, both methods first reach two novel goals, collecting observations that remain available when the third goal asks them to revisit an earlier location. GEM uses this accumulated history to locate the goal relative to the current camera, allowing it to complete the sequence while the baseline fails. |
| 82.25–92.00 | overview | These revisits rely on shared geometry, which a frozen model builds by estimating pose and depth from RGB images, without external pose measurements. |
| 92.40–102.11 | memory | This memory combines a working state for streaming geometry with an archive that links past images to their geometry, and both are retained as the robot moves between goals. |
| 102.45–117.35 | readout | When a new goal image is given, GEM matches it to a supporting historical view and uses archived depth to estimate and verify the goal pose. The shared geometry then connects that pose to the current camera, even without direct image overlap. |
| 119.35–134.71 | interfaces | Once the goal pose is cached, GEM updates its bearing as the robot moves. NavDP receives this cue alongside the original goal image, while ViNT and NoMaD use the verified historical view; if verification fails, the original inputs are retained. |
| 135.30–154.71 | table_i | To test these benefits across controllers, we compare three frozen policies on HM3D and MP3D under matched histories and evaluation conditions. Adding GEM improves revisit success by sixty point seven to eighty-one percentage points, while success on novel goals is maintained or improved across all six comparisons. |
| 155.25–166.70 | table_ii_a | When we extend the evaluation to continuous navigation, where each method builds its own history across goals, GEM completes sixty-four three-goal sequences, compared with twelve for the baseline. |
| 167.20–177.55 | table_ii_c | When both methods receive the same two-goal histories, third-goal revisit success rises from eight to seventeen out of twenty, while novel success remains four out of twenty for both. |

## 范围与来源

- 几何模型与控制器权重冻结；工作状态和历史归档在运行中更新。冻结不表示没有记忆更新。
- 真机 25/30 vs 4/30 是论文十个设置的总计，不是视频中两个片段的统计。室内玻璃墙是停止位置描述，没有推断失败的内部机制。
- 环境示例为 MP3D；评测范围为 HM3D 和 MP3D。
- Table I 的 60.7–81.0 为百分点。Table II(a) 64 vs 12 为完整三目标序列数；Table II(c) 8→17/20 与 Novel 4/20 是共享两腿历史实验。
- 真机点云是离线联合重建的可视化；仿真 RGB arrival latch 与论文的严格距离评分不同。精选演示不代替论文定量结果。
- 原片不改；双臂共用抽帧时间映射。实际字幕见 GEM_English.srt，图上高亮时间由 icra_voice_timing.py 读取 narration/alignment.json。

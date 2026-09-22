# GEM 视频精修方案 — v23 计划稿

状态：已落实为 v23。用户后续确认保留主要图外说明栏、bullet points 和 1/2/3 步骤，仅删除后续追加的补充句；最终布局见 ICRA_METHOD_EXPLANATIONS.md，最终已合成旁白见 outputs/icra_submission/ENGLISH_SCRIPT.md。下文为原计划记录，早期删除全部说明栏的建议已被用户的上述澄清取代。
当前基线：v22，178 秒；视觉参考为 `outputs/icra_submission/before_method_expansion_v21/` 中的 v21 脚本及视频。

## 设计决策

恢复 v21 的大图、缩放和平移路径，顺序仍为 Fig. 1(a) → (b) → (c) → 完整架构。特别是 (c)，取消 v22 右侧三步说明栏，恢复原图的主画面尺寸。保持现有章节顺序与 178 秒目标时长。

删除后续淡入的解释性小字，包括 `Observations write to the stream.`、`Goal images only query history.`、`No external pose input. All model weights stay frozen.`，以及 v22 的三栏正文、右侧说明清单和额外阈值文字。论文原图内的文字、框图和公式保留。详细解释由旁白和底部单行字幕承担。

图上只对当前讲述的结构做高亮。取消小字上移、逐条弹出和文字累积效果。镜头使用约 0.7 秒平滑过渡，随后稳定停留；高亮随语音出现，完成后恢复原图，避免把多个模块持续圈满。

## 标题

采用专业名词标题，统一字号、位置和字重；不额外增加一句总结型副标题。标题随页面转场出现，不单独晚进场。

| 页 | 计划标题 |
|---|---|
| Fig. 1(a) | System Overview |
| Fig. 1(b) | Episodic Memory |
| Fig. 1(c) | Goal Localization from History |
| 完整架构 | Frozen Controller Interfaces |
| Table I | Cross-Controller Evaluation |
| Table II(a) | Continuous Three-Goal Navigation |
| Table II(c) | Controlled Third-Goal Recall |

结果页保留原表、现有数值和语音对应的高亮。去掉 `Same past. New query. Frozen controller.` 等副标题。数值不在标题、正文和字幕里重复堆叠。

## 真机 Baseline 标注

拟使用用户指定的原文：`Baseline stopped before a glass wall`。

保留两行结构：第一行 `Baseline`，第二行 `stopped before a glass wall`，合起来就是上述完整表述。使用原停止时刻、指示线和灰屏，不移动停止事件。检查长句在原框内的实际字宽；优先微调框宽，保持字号可读。

用户已确认：仅用于室内真机。户外和仿真的 Baseline 标注保持现有含义。这里陈述的是观测到的停止位置，不引申为已证实的失败机制。

## 英文改稿原则

- 用自然的学术视频讲述，句子明确说明主体、动作和结果。
- 统一使用 goal image、historical view、goal pose、goal bearing、controller 等术语。
- 删除 `Here is how that recall works`、`This also holds for longer sequences` 等占时的引导句，以及 `preserves native execution` 等生硬表达。
- 实验用语与论文保持一致；定量结果不用口号强化。
- 保留 Ava 音色。先合成、测时，再调整文字；不为塞入脚本而明显加快语速。

## 逐段英文旁白草稿

以下是待合成的改稿；暂按原画面窗口分配，不是已经通过实测的最终语音时间。

| 画面时间 | 旁白草稿 |
|---|---|
| 0–11 s · Opening | We introduce GEM, a geometric episodic memory for monocular image-goal navigation. GEM reuses past observations to guide existing navigation policies without additional training. |
| 11–32 s · Indoor | Here, the robot returns to a location observed during a prior survey. Both runs use the same starting pose, goal image, and survey history. The baseline stops in front of a glass wall. GEM uses the stored geometry to estimate the goal direction and reaches the destination. |
| 32–56 s · Outdoor | In the outdoor trial, GEM initially turns toward the previously observed goal. It then updates the goal direction as the robot moves, while NavDP plans the local motion. Across ten real-world settings, GEM succeeds in twenty-five of thirty trials, compared with four of thirty for the baseline. |
| 56–61 s · Environments | We evaluate in Habitat on HM3D and MP3D. |
| 61–82 s · Simulation | This episode tests navigation across three successive goals. Both methods reach the first two goals, which are novel, while retaining the observations collected along the way. The third goal revisits a previously observed location. GEM uses the accumulated history to reach it; the baseline does not complete the sequence. |
| 82–92 s · Fig. 1(a) | A frozen streaming model estimates camera pose and depth from incoming RGB images. Its shared coordinate frame supports historical recall without external pose measurements. |
| 92–102 s · Fig. 1(b) | The memory combines a persistent working state with an archive of images and geometry. Both are retained across goals and reset between episodes. |
| 102–119 s · Fig. 1(c) | For each new goal image, GEM retrieves a supporting historical view. Feature matches and archived depth provide correspondences for estimating and verifying the goal pose. The shared geometry then relates that pose to the current camera, even without direct image overlap. |
| 119–135 s · Interfaces | GEM caches the goal pose and updates its bearing as the robot moves. NavDP combines this cue with the original goal image. ViNT and NoMaD use the verified historical image. Unverified recall leaves the original inputs unchanged. |
| 135–155 s · Table I | We compare three frozen controllers on HM3D and MP3D using matched histories and evaluation conditions. Adding GEM improves revisit success by sixty point seven to eighty-one percentage points. Success on novel goals is maintained or improved across all six comparisons. |
| 155–167 s · Table II(a) | In continuous navigation, each method builds its own history across successive goals. GEM completes sixty-four three-goal sequences, compared with twelve for the baseline. |
| 167–178 s · Table II(c) | With identical two-goal histories, third-goal revisit success increases from eight to seventeen out of twenty. Novel-goal success remains four out of twenty for both methods. |

方法与实验依据：作者指定的 `Nav-graph-blind/projects/paper`，重点为 `sec/4_method.tex`、`sec_lg/5_experiments.tex`、`sec/5_realworld.tex` 及 Table I/II。玻璃墙位置来自用户对该真机片段的补充说明。

## 动画与旁白的对应

- (a)：先显示 RGB 和 geometry model；讲到 pose/depth 与 shared frame 后强调几何状态和读出，不加图外清单。
- (b)：先强调工作状态，再强调带几何的归档，最后指向跨目标时间轴。观察写入/目标查询的完整技术定义保留在论文和脚本文档，不在图上另弹一句。
- (c)：依次强调历史视图、匹配/历史深度、定位/验证、历史到当前的几何关系。每一步以新语音词边界重新校准，不复用旧脚本的固定秒数。
- 完整架构：缓存/bearing → NavDP → ViNT/NoMaD → 验证失败时保留原输入。原图占主要空间，不再放两行接口补充小字。
- 结果：评测条件 → Revisit/增益 → Novel；连续任务完成数；共享历史下 Revisit → Novel。高亮必须跟随对应数字的实际语音。

## 执行顺序与验收

1. 保存 v22 完整回退副本；仅恢复 v21 的方法镜头/大图布局，保留已经纠正的数据集来源、结果高亮逻辑和当前章节顺序。
2. 实施专业标题、删除额外小字、更新指定真机标注。
3. 合成英文改稿、测量各段时长；必要时缩短冗余文字。画面总长以 178 秒为目标，绝不超过 180 秒。
4. 根据新词边界重新切分单行字幕，并同步图上高亮。保持字幕字号，避免拆断名词短语或频繁闪空。
5. 先输出方法段和结果段预览，检查运镜与阅读节奏，再导出整片。
6. 核对数字、数据集来源、原演示事件与双臂时间映射；检查完整解码、声音响度、字幕安全区和文件大小 ≤20 MB。更新实际脚本与交付文档。

不添加章节、不增加新的结果主张，也不加入与旁白重复的额外文字动画。

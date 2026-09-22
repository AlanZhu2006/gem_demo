# Fig. 1 布局与动画 — v24

按用户最新澄清，**保留主要图外说明栏、bullet groups 和 1/2/3 步骤，删除后续额外出现的补充句**。说明和专业标题随页面一起进入，随后稳定显示；高亮根据实际语音切换。既不把文字全删掉，也不再累积解释性小字。

## 页面内容

- **System Overview**：原架构图下保留 Streaming geometry / Sparse readout / Dense readout 三组；每组一行，分别为 RGB observations → pose and depth、Verified view + goal direction、Current depth for local control。
- **Episodic Memory**：图右侧保留 Working state / Indexed archive / Across goals 三组；说明当前几何上下文、逐帧 RGB/descriptor/pose/depth/confidence、跨目标保存至 episode reset。
- **Goal Localization from History**：放大原 c 图；1 Retrieve / 2 Localize and verify / 3 Read the bearing 改放图下三栏，每栏一行关键关系，不再用右侧长清单挤压主图。
- **Frozen Controller Interfaces**：回到完整架构，用相应模块高亮配合旁白；不增加额外接口解释小字。

删除原来的 `Observations write to the stream.`、`Goal images only query history.`、`No external pose input…`、晚出现的阈值说明和页面口号式副标题。论文原图内文字与公式保留。

## 运镜

全部面板共享原图坐标系，使用约 0.7 秒 easing 连续平移/缩放，顺序 a→b→c→完整架构。b 页面使用同一坐标变换进入左侧大图，避免图与文字布局切换时跳动。c 的图宽约 1535 px，比 v22 左侧图更大，图下保留两行高度的简短 1/2/3 步骤。

高亮不再使用旧稿的固定秒数，而由 `icra_voice_timing.py` 从本次实际词边界读取：历史视图→PnP→共同坐标关系→bearing；完整架构缓存→NavDP→ViNT/NoMaD→验证失败回退。结果表同样按新语音中的 Revisit、百分点、Novel 等短语同步。

## 旁白

采用完整、自然的英文长句交代逻辑关系；保持学术准确性，减少碎片化引导句和术语堆叠。室内片段先交代巡视及图像目标，再讲共同条件与两种结果；只有室内的标注改为 `Baseline stopped before a glass wall`。完整实际语音文稿在 `outputs/icra_submission/ENGLISH_SCRIPT.md`。

方法仍为 82–135 秒，总视频 178 秒。图下单行字幕保持原来字号与白描边。原始演示视频不变。

## v24 旁白衔接

演示转入 a 图时，先以 These revisits rely on shared geometry 承接前段行为；完整架构转 Table I 时，以 To test these benefits across controllers 交代评测目的。画面布局沿用 v23，高亮重新随实际词时间戳对齐。

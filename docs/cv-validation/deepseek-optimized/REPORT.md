# DeepSeek：最终优化版 CV 规则实测

本次使用刚才的最终版规则与抽取校验逻辑，规则指纹 `e7d33875d4c306652dda0061db5c3ce6690a432655973c9faf7bebde20a88f89`。仅调用已配置的 DeepSeek（deepseek-flash），没有调用其他 API。

## 结果

| 论文 | 原始候选 | 数值与基本归属有依据 | 需修正 | 排除 |
|---|---:|---:|---:|---:|
| Fast R-CNN | 14 | 7 | 2 | 5 |
| Faster R-CNN | 16 | 11 | 1 | 4 |
| YOLO | 4 | 3 | 0 | 1 |
| 合计 | 34 | 21 | 3 | 10 |

排除的10条中，9条是摘要/正文/表格重复或约数概述，1条是RPN组件耗时。排除不等于全部是捏造。supported仅指数值和基本实验归属有依据，并不代表所有条件齐全或适合跨论文排名。未知条件仍需复核。

三项修正：Fast R-CNN 320ms、220ms都排除候选框生成，原输出错误标为端到端；Faster R-CNN 59.2实验的检测器骨干为ZF，VGG16属于候选网络。修正建议单独保存在逐条review文件，数据库原始候选未被改写。

27条预选参考中，直接支持15条，按明确建议修正后覆盖17条。另有范围内的消融结果不在预选清单中。这不是全文召回率或独立人工测得的准确率。仍漏掉Fast的多项S/M速度、Faster的68.5/67.0/68ms等参考，不能称作完整提取。

## 流程与接口适配

首次尝试的Fast R-CNN五批中三批在4096额度内只输出思考，finish_reason=length，零条有效候选，保护逻辑正确拒绝导入。失败预览归档在忽略版本控制的data/cv-validation/deepseek-optimized/fast_rcnn-partial-*.json；首次诊断另存initial-failed-run.json。

随后依据[DeepSeek官方说明](https://api-docs.deepseek.com/guides/thinking_mode/)为DeepSeek的flexible_output抽取请求设置thinking.type=disabled。规则、PDF、输出额度4096、超时120秒未改变，也没有修改用户保存的API配置。该提供商适配是本次唯一新增的后端行为。

重跑Fast五批、Faster四批、YOLO三批均stop，无失败/跳过批次。解析与请求分别约25.843、26.156、13.234秒；用时不是受控性能基准。导入、证据链接、PDF下载回读与SHA-256比对均通过。

## 保留位置

工作区：**CV目标检测 · DeepSeek优化版验证（保留）**

ID：`workspace_cv目标检测___deepseek优化版验证_保留_94a76234`

三篇原始PDF和34条原始候选已保留，全部pending且有证据链接。原有cv工作区未删除。刷新工作区列表即可查看。

- `run-summary.json`：真实批次诊断、用时、提交结果、覆盖分析。
- `*-model-results.json`：原始模型候选与证据页码。
- `*-review.json`、`all-judgements.json`：逐条AI辅助原文判别，明确修正建议。
- `persistence-check.json`：从正常接口回读的持久化核对。
- `assessment-summary.json`：汇总与本次提供商适配文件指纹。
- `reference-checklist.json`、`cv-detection-rules.json`：固定参考与规则快照。

## 与此前智谱结果的关系

此前智谱首轮31条：6条有依据、12条需修正、13条排除；强化后单跑Faster七条：4条有依据、2条需修正、1条排除。本次常见的类别AP、融合模型、测试集总耗时混淆明显减少，但不能据此宣称DeepSeek在受控条件下优于智谱：此前结果混合不同优化阶段，且这些论文参与过规则调试。三篇主要验证经典VOC目标检测，不能外推到整个CV或现代COCO论文。

全部判别属于AI辅助本地v1原文复核，未标记为独立人工核验。数据库保留原始输出；正式科研结论仍需确认实验条件。

验证：LLM基础测试20项通过；DeepSeek请求参数回归测试3项通过（覆盖抽取关闭思考、非抽取请求不受影响、自定义提供商不受影响）。

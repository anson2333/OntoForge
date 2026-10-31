# CV 实验事实标注指南

## 标注单位

每条记录对应一个来源明确的“实验 + 测量”。标注人必须查看固定 PDF 版本，记录页码、表/行/列或连续正文引句；无法定位时标 `unresolved`，不得凭模型常识补全。

必填字段：`paper/version/hash`、`model_variant`、`training_split`、`test_split`、`metric`、原报告值与单位、`denominator`、`aggregation`、`measurement_scope`、字段证据、标注人、时间和歧义说明。

## 判定规则

- `VGG-16`/`VGG16` 可标同一 Backbone；Backbone 的 detector/RPN 角色分别记录。
- Fast/Faster R-CNN、整机/RPN、默认/SVD 变体不得因词面相似合并。
- `07+12` 不含 VOC07 test；`07++12` 包含，二者训练集不同。
- 类别 AP、整体 mAP、相对提升、百分点分别标注。
- 秒到毫秒只改变单位，不改变 `image/dataset/batch` 分母。
- 摘要约数和表格精确值保留为不同来源；没有足够实验身份依据时不强制合并。
- YOLO 无独立 RPN 时 proposal 字段标 `not_applicable`，没有读清楚则标 `unresolved`。

## 人工流程

1. AI 可产生草稿，但草稿目录不得命名为 gold。
2. 第一名标注人逐字段核对原文并署名。
3. 建议第二名成员复核高风险负例，记录分歧和最终理由。
4. 只有真实操作者产生的审核事件才能设置 `human_verified`。
5. 开发集和留出集分开；看过留出答案并改规则后，该样本转为开发集。

## 评价

分别报告正确合并/错误合并/未决数、完整实验元组 precision/recall、证据可达率与语义支持率、正确拒答与覆盖率、空白候选人工判定。必须给出分母、版本和失败样例；全部返回 unknown 不能通过验收。

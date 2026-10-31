# CV 历史文献与后续验证集

使用目标检测，冻结日期为 **2016-06-30**。下面的日期均核对自 arXiv 首次公开记录；会议年份只用于引用。所有下载固定 `v1`，避免老论文后来修订引入未来成果。机器清单见 `corpus.json`。

## 历史输入：12 篇

| 论文 | 会议 | 首次公开 | 原始来源 |
|---|---|---|---|
| R-CNN | CVPR 2014 | 2013-11-11 | [论文](https://arxiv.org/abs/1311.2524) |
| Scalable Object Detection / MultiBox | CVPR 2014 | 2013-12-08 | [论文](https://arxiv.org/abs/1312.2249) |
| SPP-net | ECCV 2014 | 2014-06-18 | [论文](https://arxiv.org/abs/1406.4729) |
| Fast R-CNN | ICCV 2015 | 2015-04-30 | [论文](https://arxiv.org/abs/1504.08083) |
| Multi-region & segmentation-aware CNN | ICCV 2015 | 2015-05-07 | [论文](https://arxiv.org/abs/1505.01749) |
| Faster R-CNN | NeurIPS 2015 | 2015-06-04 | [论文](https://arxiv.org/abs/1506.01497) |
| YOLO | CVPR 2016 | 2015-06-08 | [论文](https://arxiv.org/abs/1506.02640) |
| SSD | ECCV 2016 | 2015-12-08 | [论文](https://arxiv.org/abs/1512.02325) |
| Inside-Outside Net / ION | CVPR 2016 | 2015-12-14 | [论文](https://arxiv.org/abs/1512.04143) |
| HyperNet | CVPR 2016 | 2016-04-03 | [论文](https://arxiv.org/abs/1604.00600) |
| Online Hard Example Mining / OHEM | CVPR 2016 | 2016-04-12 | [论文](https://arxiv.org/abs/1604.03540) |
| R-FCN | NeurIPS 2016 | 2016-05-20 | [论文](https://arxiv.org/abs/1605.06409) |

这组论文包括区域方法、密集回归、速度瓶颈、多尺度特征和困难样本问题。它不是历史文献全集，未覆盖的组合只能称为“该输入集合中的候选证据空白”。

## 后期留出集：7 篇

| 论文 | 首次公开 | 可用于复核的方向（人工研究线索，不是系统预测结果） |
|---|---|---|
| [FPN](https://arxiv.org/abs/1612.03144) | 2016-12-09 | 跨尺度语义特征、小目标评估；不能把“多尺度”本身说成此前无人研究，SSD、ION、HyperNet 已涉及 |
| [YOLO9000](https://arxiv.org/abs/1612.08242) | 2016-12-25 | 检测与分类联合训练、类别覆盖及速度精度权衡；核查相同数据和训练条件 |
| [RetinaNet / Focal Loss](https://arxiv.org/abs/1708.02002) | 2017-08-07 | 密集单阶段检测的前景背景失衡；OHEM 已处理困难样本，不能宣称此前没有样本选择研究 |
| [Cascade R-CNN](https://arxiv.org/abs/1712.00726) | 2017-12-03 | 高 IoU 定位质量、多阶段训练与质量匹配 |
| [CornerNet](https://arxiv.org/abs/1808.01244) | 2018-08-03 | 角点表示替代预定义 anchor；不能把所有非 anchor 检测归为同一创新 |
| [FCOS](https://arxiv.org/abs/1904.01355) | 2019-04-02 | 逐像素、无 anchor 的单阶段检测 |
| [DETR](https://arxiv.org/abs/2005.12872) | 2020-05-26 | 集合预测、匹配损失、去除手工 NMS；不代表所有检测问题已解决 |

上表只用于预测冻结后的复核。FPN 与 YOLO9000 虽常引用为 2017 年论文，但首次公开都在 2016 年；因此没有采用简单的会议年份切分。

## 下载与使用

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.prepare_cv_corpus --check-only
.\backend\.venv\Scripts\python.exe -m backend.scripts.prepare_cv_corpus --split historical
# 预测冻结后再单独下载后期文献
.\backend\.venv\Scripts\python.exe -m backend.scripts.prepare_cv_corpus --split holdout
```

PDF 分别存入 `data/cv-validation/historical` 和 `holdout`，下载报告保存 SHA-256、页数、文件规模和耗时。PDF 不加入 Git；论文许可仍以原始来源为准。

在新工作区选择 `cv_detection` 领域包，只上传 historical 的 PDF。需要显式配置真实 LLM；规则抽取结果不能当成真实模型调用证据。每篇先预览，核对断言与来源后提交。保留完整响应和模型名称，隐藏密钥。

## 公平的历史回测

1. 冻结配置与输入清单，记录 Git 提交号、截止日期、模型、提示词、PDF 哈希。领域词汇以历史任务与数据集为准，不把后期方法名称塞进历史领域包。
2. 在历史集运行抽取，人工修订证据错误并记录修订；抽取错误导致的缺覆盖应单独统计。
3. 导出覆盖报告并保存时间戳和 SHA-256。固定 Top-K（建议 K=10），不能看到后期结果再改候选排序。
4. 逐项标注：方法、场景/数据集、指标、历史支撑证据、缺失内容、是否可检验。仅为数字缺报的候选，与机制性的研究问题分开评价。当前 Coverage 是覆盖统计排序，不能独立发明一种新网络结构。
5. 再解封 holdout，两个独立评审分别给出：直接覆盖、部分相关、未找到覆盖、历史已覆盖、无效候选，并提供论文页码/节/表。分歧讨论后保留原始判断。
6. Top-K 直接覆盖率 = 直接覆盖数/K；相关率 =（直接覆盖+部分相关）/K。无效候选仍留在分母；不能删除不命中的条目。历史已覆盖率另报，用来量化系统误报。留出集不完整，所以“未找到”不等于事实上没有研究。
7. 同时报告均匀随机候选、未排序零覆盖单元等基线。该系统的启发式分数不是概率，不能解释为未来命中概率。

历史论文已经研究多尺度和困难样本，上述反例是必须保留的反误报检查。YOLO 本身也不能简单按“无 anchor”认定等同 FCOS。即使后期论文方向相近，也需证明它与冻结候选的限定范围一致，才算命中。

现代 LLM 可能在训练中见过后续论文。限制检索和提示词不能消除模型记忆，所以实验应称为**有潜在训练泄漏的文献覆盖回溯验证**，不能宣称证明了模型当年能预测未来。

## 抽取质量与性能验收

从至少 3 篇历史论文各选摘要、实验文字和表格段落，人工标注不少于 30 条断言。每条记录规范指标、值、单位、数据集/split、IoU 协议、模型变体、backbone、分辨率、GPU、来源页码和原文。两人复核；不把自动输出当人工金标准。

计算字段匹配 precision/recall/F1、有效证据引用率、数值和单位正确率，公开样本量和排除规则。VOC AP50、COCO AP@[.5:.95]、AP75、AP_small 不可直接互换；不同硬件 FPS 不用于直接优劣结论。缺失上下文保留 unknown，不编造。

记录每篇 PDF 大小、页数、解析/模型/总耗时、批次数、失败批次和 provider 可返回的 token 用量。记录图谱写入/查询/分析的样本量和重复次数。当前预览 `diagnostics` 已提供解析和模型相关基础数据，但真实质量与性能结果必须实际运行后填写。

截至本次实施：本文提供可执行协议与文献清单；不将人工拟定的研究线索或模拟输出冒充已经测得的预测命中结果。

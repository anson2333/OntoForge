# CV 目标检测规则检查与原文核验报告

## 结论

已把 `cv_detection` 配置为“目标检测：准确率与推理速度”，并使规则中的指标定义、实验条件、分类、排除范围、数值界限与单位换算实际参与抽取。规则适合作为文献整理与人工复核的起点，当前智谱免费模型的输出仍不能自动当作正确科研结论。

首轮三篇共有 **31 条候选：6 条数值与基本归属有依据、12 条需修正、13 条排除**。这是最终逐条复核结果，包含后续发现的07+12与07++12训练集混淆，替代早期进度中的初判。排除含重复概述、他人基线、融合模型及读错表格，不全是数值幻觉。强化规则后单独复跑 Faster R-CNN：7 条保留候选中 **4 条有依据、2 条需修正、1 条排除**。四批 finish_reason 都为 stop，无失败批次；语义错误仍未清零。

本轮没有把这些原始候选当成已核验成果入库。逐条原始输出、判别理由和修订建议都保留；研究者仍需最终确认。

## 样本与方法

- 采用本地已下载的 arXiv v1 PDF，固定 SHA-256；不拿后来的修订版数值补齐旧版本。
- Fast R-CNN：9 页；Faster R-CNN：10 页；YOLO：9 页。表格和相关正文经 Poppler 渲染检查，并与提取文本交叉核对。
- 在真实调用之前冻结了 27 条代表性参考记录。它们不是全文穷举，也不是两名独立人工评审制作的金标准。
- 使用用户既有智谱 glm-4.7-flash 配置；每个模型请求串行，试验额外采用 65 秒冷却。用时包含等待、解析和接口请求，不是纯模型计算耗时。
- 本轮边检查边改规则，属于开发集调试；不能把这三篇的表现外推成未知论文上的准确率。

| 阶段 | 论文 | 候选数 | 有依据 | 需修正 | 排除 | 运行秒数（含等待） |
|---|---|---:|---:|---:|---:|---:|
| round1 | fast_rcnn | 12 | 4 | 6 | 2 | 93.625 |
| round1 | faster_rcnn | 7 | 0 | 5 | 2 | 211.188 |
| round1 | yolo | 12 | 2 | 1 | 9 | 184.89 |
| round2 | faster_rcnn | 7 | 4 | 2 | 1 | 270.906 |

## 旧规则与程序中发现的问题

1. 旧提示词没有完整传入必需上下文字段和分类定义，模型常把条件放进模糊字符串，覆盖分析无法稳定识别方法和场景。现已把结构化要求、指标定义和领域准则传入每批。
2. 旧规则把 percentage_points 当成 percent 的同义单位。现已分开，并把相对提升、逐类别 AP 与总体 mAP 区分。
3. 旧规则只接受毫秒，原文以秒报告的延迟会被过滤。现按配置执行 s→ms 的显式乘法换算，保留 reported_value、reported_unit 与换算因子；不推导 FPS 倒数。
4. 旧 JSON 输出只检查数值格式，未检查原文是否含该数值。CV 规则现要求被引用的证据中出现原始数值，并检查准确率范围。数值存在仍无法证明读对了表格行列。
5. 首轮 Faster R-CNN 第二批恰好用满 4096 tokens，初版适配器可能从不完整文本中捞到少数条目。现记录 finish_reason；length/max_tokens 会判为失败批次，禁止把它当成完整成功。
6. 最终规则限制每批 14000 字符，要求简短输出；每批带论文身份，并执行方法一致性、基线角色与融合结果排除。方法标错也可能使真实结果被过滤，这是精确性与漏检的权衡，不能把所有被过滤条目都宣称为错误。
   最终收尾把宽泛的fusion排除词改成model fusion/detector fusion等，避免误删单检测器内部的特征融合；该措辞调整未另发真实请求，用回归测试与冻结候选策略重放验证。
7. 年份原先可能误取 VOC 2012 等基准年份。对带现代 arXiv 编号的文档，现优先读取编号中的发表年份；本地这三篇均回到 2015。作者或会议的 PDF 元数据缺失没有被模型补猜。

多条语义错误的模型置信度仍高达0.9～1.0。该字段未经校准，不能解释为结果正确的概率，也不能替代原文复核。

## 有代表性的逐条判别

| 问题 | 原文核对结论 |
|---|---|
| 旧 Fast R-CNN 把 74.5、77.0、80.1 当作总体 mAP | 第5页表1～3对应的是逐类别 AP。旧文档中抽样的这些结果不能信任；新版主结果不再这样列。 |
| Fast R-CNN 的 S、M 都被写成 VGG16 | 第5页4.1节：S=CaffeNet，M=VGG_CNN_M_1024，L=VGG16。100ms、150ms数值正确，但骨干归属须修正。 |
| Fast R-CNN SVD 的 220ms 与 223ms | 第6页表4是0.22s；图2是223ms。不能用图2的223ms去解释表4的精确220ms。 |
| Faster R-CNN 被写成 Fast R-CNN | 论文完整系统是 RPN + detector；Fast R-CNN 是检测头或基线，不能直接混为同一方法。每批传标题和方法约束后，复跑结果的完整方法归属改善。 |
| 5 FPS 被标成排除 proposal | 第1页明确 including all steps，第7页表4进一步说明总时间；应改为完整流程。复跑后仍有此错，不能只信模型解释。 |
| 10ms 被当作完整检测器延迟 | 第2页说的是额外计算 proposals 的边际成本，第7页表4可交叉核对；应排除。 |
| YOLO 的 62.5% 被写成融合模型总体 mAP | 第6页表1：融合模型总体是70.4%；62.5在YOLO的person类别列。该候选同时违反单检测器范围和总体指标定义。 |
| YOLO 的74.7% | 第8页表3是Fast R-CNN+YOLO融合结果，不是单独YOLO。 |
| YOLO 的45 FPS | 第7页4.2节与表2支持，GPU为Titan X；不能与K40上的其他模型速度无条件排名。摘要和正文重复出现，不应算两次独立实验。 |
| 把155 FPS当成本地YOLO结果 | 本地v1此次核验的主速度为45 FPS。155 FPS见后续版本的信息，不能借模型记忆填入此v1实验。本轮没有把它计入。 |

## 可以支持的研究判断

- 同一论文内部、相同评测条件下的比较更可靠。Faster R-CNN第7页表2提供了VGG16、相同VOC2007训练范围下SS基线与RPN方法的比较，不能用不同训练集的行混算提升。
- Fast R-CNN第6页的检测器时间排除了候选框生成；Faster R-CNN第7页表4报告完整系统，且列出K40上的候选生成瓶颈。直接拿320ms、196ms和YOLO的45 FPS做不加条件的速度排行榜不成立。
- YOLO v1 的VOC2012总体mAP为54.5%，VOC2007表2为58.8%；这些结果体现其速度与定位精度的取舍。不同测试集、硬件与变体仍不能直接混比。
- 三篇没有覆盖某个COCO指标，不等于该方向无人研究。Coverage空白同时受到输入论文范围、模型漏提和上下文缺失影响，不能据此宣称发现科研空白。

## 代表性参考覆盖与复核集

最终复核候选集共 19 条（使用首轮Fast R-CNN、首轮YOLO及复跑Faster R-CNN）。其中明确保留原始模型上下文和AI修订字段，human_verified始终为false。它不是已人工批准的数据库成果。

预先选定的 27 条参考中，模型候选在不作上下文修正时匹配 8 条；加入有原文依据的AI修订后匹配 16 条。缺失参考：R03, R10, R11, R13, R14, R16, R17, R19, R21, R23, R24。这些是所选参考的覆盖数，不是全文召回率；也不据此报告precision/F1。

最终策略对保存的首轮YOLO候选作无API重放，可排除7条融合/基线候选，仍留下重复和时间口径问题。首轮Faster候选因方法标错会全部被一致性策略挡住；复跑即用于验证模型能否改正这种归属。重放不能代替对错真值评估，细节见 policy-replay.json。

## 复现与文件

- [规则说明](RULES.md)、[可导入JSON规则](cv-detection-rules.json)。源码配置为 `backend/configs/domain-pack-cv-detection.yaml`。
- [首轮原始记录](round1/run-summary.json)、[复跑记录](round2/run-summary.json)、[汇总判别](assessment-summary.json)。
- [全部38条判别](all-judgements.json)、[附修订建议的复核集](reviewed-candidates.json)、[冻结参考](reference-checklist.json)。
- 原始完整预览位于被Git忽略的 `data/cv-validation/rule-review*`，不包含密钥。逐条数值与上下文的脱敏模型输出保存在本目录。
- 配置校验与121项相关后端测试通过；类型检查、lint、生产构建和24个页面/弹窗的界面回归通过。不以程序测试代替抽取质量判断。
- 原始候选未提交论文入库，也未标记为人工核验通过。本轮临时核验工作区已清理，原有cv工作区及论文数量已核对保留；模型接口配置不改动。清理凭据见 cleanup.json。

论文来源：[Fast R-CNN v1](https://arxiv.org/abs/1504.08083v1)、[Faster R-CNN v1](https://arxiv.org/abs/1506.01497v1)、[YOLO v1](https://arxiv.org/abs/1506.02640v1)。文件哈希见冻结参考。

## 全部候选的判别清单

完整解释和建议字段在 all-judgements.json；下表保留各条的判别去向。

| 阶段 / 论文 | 候选ID | 数值 | 判别 | 复核页码 |
|---|---|---|---|---|
| round1 / fast_rcnn | assert_llm_voc_map50_b0_0 | 66 percent | 排除 | 1 |
| round1 / fast_rcnn | assert_llm_inference_latency_b0_1 | 300 ms | 排除 | 1 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_0 | 70.0 percent | 需修正 | 5 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_1 | 66.9 percent | 数值与基本归属有依据 | 5 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_2 | 68.8 percent | 需修正 | 5 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_3 | 65.7 percent | 数值与基本归属有依据 | 5 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_4 | 68.4 percent | 需修正 | 5 |
| round1 / fast_rcnn | assert_llm_inference_latency_b1_5 | 320 ms | 数值与基本归属有依据 | 6 |
| round1 / fast_rcnn | assert_llm_inference_latency_b1_6 | 100 ms | 需修正 | 6 |
| round1 / fast_rcnn | assert_llm_inference_latency_b1_7 | 150 ms | 需修正 | 6 |
| round1 / fast_rcnn | assert_llm_voc_map50_b1_8 | 66.6 percent | 数值与基本归属有依据 | 6 |
| round1 / fast_rcnn | assert_llm_inference_latency_b1_9 | 220 ms | 需修正 | 6 |
| round1 / faster_rcnn | assert_llm_voc_map50_b0_0 | 73.2 percent | 需修正 | 1,7 |
| round1 / faster_rcnn | assert_llm_voc_map50_b0_1 | 70.4 percent | 需修正 | 1,7 |
| round1 / faster_rcnn | assert_llm_inference_fps_b0_2 | 5 fps | 需修正 | 1,7 |
| round1 / faster_rcnn | assert_llm_voc_map50_b0_3 | 59.9 percent | 需修正 | 5,6 |
| round1 / faster_rcnn | assert_llm_voc_map50_b0_4 | 58.7 percent | 排除 | 5,6 |
| round1 / faster_rcnn | assert_llm_voc_map50_b0_5 | 58.6 percent | 排除 | 5,6 |
| round1 / faster_rcnn | assert_llm_voc_map50_b1_0 | 58.7 percent | 需修正 | 6 |
| round1 / yolo | assert_llm_inference_fps_b0_0 | 45 fps | 排除 | 1,7 |
| round1 / yolo | assert_llm_voc_map50_b0_1 | 54.5 percent | 数值与基本归属有依据 | 6 |
| round1 / yolo | assert_llm_voc_map50_b0_2 | 62.5 percent | 排除 | 6 |
| round1 / yolo | assert_llm_voc_map50_b1_0 | 58.8 percent | 数值与基本归属有依据 | 7 |
| round1 / yolo | assert_llm_voc_map50_b1_1 | 74.7 percent | 排除 | 8 |
| round1 / yolo | assert_llm_inference_fps_b1_2 | 45 fps | 需修正 | 7 |
| round1 / yolo | assert_llm_voc_map50_b1_3 | 54.5 percent | 排除 | 6,7 |
| round1 / yolo | assert_llm_inference_fps_b1_4 | 0.02 fps | 排除 | 7 |
| round1 / yolo | assert_llm_inference_fps_b1_5 | 0.45 fps | 排除 | 7 |
| round1 / yolo | assert_llm_inference_fps_b1_6 | 0.09 fps | 排除 | 7 |
| round1 / yolo | assert_llm_inference_fps_b1_7 | 0.48 fps | 排除 | 7 |
| round1 / yolo | assert_llm_inference_fps_b1_8 | 0.11 fps | 排除 | 7 |
| round2 / faster_rcnn | assert_llm_voc_map50_b0_0 | 73.2 percent | 数值与基本归属有依据 | 1,2,7 |
| round2 / faster_rcnn | assert_llm_voc_map50_b0_1 | 70.4 percent | 数值与基本归属有依据 | 1,2,7 |
| round2 / faster_rcnn | assert_llm_inference_fps_b0_2 | 5 fps | 需修正 | 1,7 |
| round2 / faster_rcnn | assert_llm_inference_latency_b0_3 | 10 ms | 排除 | 2,7 |
| round2 / faster_rcnn | assert_llm_voc_map50_b1_0 | 59.9 percent | 数值与基本归属有依据 | 5,6 |
| round2 / faster_rcnn | assert_llm_voc_map50_b1_1 | 58.7 percent | 数值与基本归属有依据 | 6 |
| round2 / faster_rcnn | assert_llm_voc_map50_b1_2 | 59.2 percent | 需修正 | 6 |

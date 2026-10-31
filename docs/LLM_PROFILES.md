# 在界面配置与切换模型接口

登录后，点击右下角状态栏的 **模型接口**。

“厂商预设”可选择 **DeepSeek（DS）、智谱 GLM、Kimi、Claude**，也保留本地 Ollama 和自定义接口。选择后自动填入协议、地址和默认模型；“常用模型”提供可选项，仍可手工填写其他模型 ID。预设从官方文档核对（2026-10-29），不是账户可用模型的实时列表。

| 厂商 | 自动填入的地址 | 默认模型 | 官方依据 |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-flash` | [首次调用](https://api-docs.deepseek.com/) |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.7-flash` | [兼容接口](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)、[模型列表](https://docs.bigmodel.cn/cn/guide/start/model-overview) |
| Kimi | `https://api.moonshot.cn/v1` | `kimi-k3.1-pro` | [模型列表](https://platform.kimi.com/docs/models)、[参数说明](https://platform.kimi.com/docs/guide/kimi-k3-1-pro-quickstart) |
| Claude | `https://api.anthropic.com/v1` | `claude-sonnet-5-5` | [模型列表](https://platform.claude.com/docs/en/models/overview)、[API 概览](https://platform.claude.com/docs/en/api/overview) |

Claude 使用原生 Messages 协议，JSON 由提示词要求并在返回后解析校验；不宣称服务端强制 JSON Schema。Kimi K3 使用 `max_completion_tokens` 并降低默认推理强度，K2.6 使用非思考模式；厂商预设不发送用户自定义采样温度，避免固定参数模型拒绝请求。第三方中转请按其实际支持协议选择“自定义”。

1. 点击“新增接口”，填写名称、Base URL、模型名称及 API Key。OpenAI 兼容地址通常以 `/v1` 结尾，不要追加 `/chat/completions`；本地 Ollama 可选择对应类型。
2. 点击“验证并保存配置”或“验证并启用”，都会先实际试调用模型，通过后才保存；后者同时启用。失败会当场显示原因，且不会覆盖旧配置。可以保存多组服务商、备用接口及同一服务商的不同模型。
3. 在左侧选择已保存的配置，点击“切换到此接口”。后续请求立即使用该接口，不需要重启；正在执行的请求继续使用原接口。
4. “测试已保存接口”会发送一条普通文本小请求，显示成功/失败及耗时，可能消耗少量 tokens。请先保存修改。保存时会自动验证；切换及状态栏轮询不会重复发起模型调用。状态栏显示最近一次实际调用结果，未验证的旧配置不会被标成连接正常。
5. 编辑已有接口时，同一地址和协议下密钥留空表示保留原密钥；输入新值可替换，勾选“清除”可删除原密钥。切换厂商会自动清除旧密钥，避免发给另一家服务；手动更换服务器或协议时，后端也要求重新输入或明确清除密钥。
6. 删除当前接口后回到服务器 `.env` 配置；也可随时点击“使用服务器 .env 配置”。如果 `.env` 中没有启用模型，则恢复为未配置状态。

连接验证只验证密钥、地址和模型是否能正常返回文本，不要求 JSON，也不代表论文抽取质量验收。论文抽取仍单独检查结构化数据。

配置按登录用户隔离。新配置默认不向浏览器回传密钥，仅返回 `has_api_key`；密钥不保存在 localStorage，也不会用环境中的密钥替代一个没有密钥的自定义配置。

默认保存位置为 `backend/data/llm-profiles.json`，可用 `ONTOFORGE_LLM_PROFILE_STORE` 指定其他位置。Windows 使用 DPAPI 加密，密钥绑定运行后端的 Windows 账户；更换机器或系统账户后需重新输入密钥。非 Windows 平台使用权限为 0600 的本地文件，不宣称已做磁盘加密。配置文件已被 Git 忽略。

这是单进程本地服务的配置存储，使用进程内锁和原子替换防止并发写入丢失；多 worker/多机器部署需要换用共享配置数据库和集中密钥管理。

JSON-RPC 接口：`listLLMProfiles`、`saveLLMProfile(profile, activate?)`、`activateLLMProfile(profile_id?)`、`deleteLLMProfile(profile_id)`、`testLLMProfile(profile_id)`。均要求登录，用户身份来自会话，不接受其他用户的配置 ID。运行时 provider 的选择也来自同一会话，切换不修改进程全局环境变量。

本次连接测试的自动验收使用明确标记的本地 HTTP fixture，不是真实付费 LLM 质量实验。真实科研抽取与历史回测仍需使用你配置的实际服务另行验证。


## 论文抽取兼容普通模型回复

论文抽取不再强制服务端 JSON 模式，OpenAI 兼容接口、原生 Claude 和 Ollama 均使用相同的输出适配流程。支持：

- JSON 对象/数组、Markdown 代码块中的 JSON，以及说明文字夹带的完整 JSON。
- Markdown 表格，含指标、数值、单位、来源列（支持中英文列名）。
- 标注字段的文本，每行如 `metric_name: reconfiguration_delay`、`value: 12.5`、`unit: ms`、`source_chunk_ids: chunk_0`。
- 明确的数值句子，如 `reconfiguration delay is 12.5 ms (source: chunk_0)`，必须能唯一识别指标、值、单位和片段 ID。

没有 ID 时，模型若给出逐字原文 `source_quote`，只在该引文能唯一匹配当前批次片段时补上链接；不会随意挂到某一页。含糊的自由散文、截断/缺字段结果、无法定位的证据不能作为可靠断言入库。合法的空 assertions 列表表示未找到结果。

系统逐条检查指标、单位、数值、置信度和来源 ID；文本/表格数值还需出现在引用证据中。无效行被跳过并显示警告，其余有效行保留；转换后的内容仍须在预览页人工复核。内部数据库继续使用统一字段，覆盖分析与矩阵无需依赖模型的回复排版。不会为了改格式自动追加付费模型调用。

这项兼容不保证任意模型都能正确理解论文，也不代替抽取准确率验收。其他专门的结构化任务接口仍保留其原有合同。

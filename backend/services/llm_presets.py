"""Official vendor presets verified 2026-10-29; editable model IDs remain supported."""
PRESETS = [
    {"id": "deepseek", "name": "DeepSeek（DS）", "provider": "openai_compatible",
     "api_base_url": "https://api.deepseek.com", "models": ["deepseek-flash", "deepseek-v4-pro"],
     "source_url": "https://api-docs.deepseek.com/", "note": "DeepSeek 官方接口；模型以账户实际权限为准。"},
    {"id": "zhipu", "name": "智谱 GLM", "provider": "openai_compatible",
     "api_base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4.7-flash", "glm-5.3", "glm-4.7"],
     "source_url": "https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
     "note": "智谱国内通用 API；Coding Plan 使用不同地址时可手动修改。"},
    {"id": "kimi", "name": "Kimi（月之暗面）", "provider": "openai_compatible",
     "api_base_url": "https://api.moonshot.cn/v1", "models": ["kimi-k3.1-pro", "kimi-k3.1-pro-highspeed", "kimi-k2.6"],
     "source_url": "https://platform.kimi.com/docs/models",
     "note": "国内 API。海外账号请修改地址；K2 系列存在退役计划，优先使用 K3.1。"},
    {"id": "claude", "name": "Claude（Anthropic）", "provider": "anthropic",
     "api_base_url": "https://api.anthropic.com/v1", "models": ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"],
     "source_url": "https://platform.claude.com/docs/en/models/overview",
     "note": "使用 Anthropic 原生 Messages 协议，不走 OpenAI Chat Completions。"},
    {"id": "ollama", "name": "本地 Ollama", "provider": "ollama",
     "api_base_url": "http://localhost:11434", "models": [],
     "source_url": "https://docs.ollama.com/api", "note": "填写本机已安装的模型名称；通常无需 API Key。"},
]


def get_preset(vendor):
    return next((item for item in PRESETS if item["id"] == vendor), None)

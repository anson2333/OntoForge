"""Safe actionable model errors: never expose upstream bodies, URLs or keys."""
import httpx


def model_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    messages = {
        400: "模型请求参数不兼容，请检查模型名称和接口类型。",
        401: "API 密钥鉴权失败：请在“模型接口”核对该厂商的密钥，再点击“验证并启用”。",
        403: "接口拒绝访问：请检查账户是否有该模型的使用权限。",
        404: "接口地址或模型不存在：请检查 Base URL 和模型名称。",
        413: "请求内容过大：请减小每批文献内容后重新提取。",
        429: "接口限流或额度不足：请检查账户余额/限额，稍后重试。",
    }
    if isinstance(exc, ValueError) and str(exc).startswith("模型"):
        message = str(exc)
    elif status:
        message = f"HTTP {status}：" + messages.get(status, "模型服务暂时异常，请稍后重试。")
    elif isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        message = "模型请求超时：请增加超时时间，或选择响应更快的模型。"
    else:
        message = "模型调用或结果解析失败：请检查接口连接，重试提取；回复需包含可识别的指标、数值、单位和证据。"
    return {"http_status": status, "message": message,
            "retryable": status not in {400, 401, 403, 404},
            "abort_remaining": status in {400, 401, 403, 404, 429}}

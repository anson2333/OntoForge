"""Normalize model output without evaluating code or inventing evidence."""
from __future__ import annotations

import json
import re


ALIASES = {
    "metric": "metric_name", "指标": "metric_name", "指标名称": "metric_name",
    "数值": "value", "值": "value", "单位": "unit",
    "source": "source_chunk_ids", "sources": "source_chunk_ids", "chunk_ids": "source_chunk_ids",
    "证据": "source_chunk_ids", "来源": "source_chunk_ids", "原文片段": "source_chunk_ids",
    "置信度": "confidence", "条件": "context_conditions", "context": "context_conditions",
    "说明": "reasoning", "理由": "reasoning",
    "quote": "source_quote", "原文": "source_quote", "原文引用": "source_quote",
}
FIELDS = {"metric_name", "value", "unit", "predicate", "confidence", "context_conditions",
          "source_chunk_ids", "source_formula_ids", "reasoning", "source_quote"}


def _key(value):
    value = value.strip().strip("*` ").lower().replace(" ", "_")
    return ALIASES.get(value, value)


def _normalize(row):
    if not isinstance(row, dict):
        return row
    row = {_key(str(k)): v for k, v in row.items()}
    for key in ("metric_name", "value", "unit", "confidence"):
        if isinstance(row.get(key), str):
            row[key] = row[key].strip().strip("*` ")
    for key in ("value", "unit"):
        if isinstance(row.get(key), (int, float)):
            row[key] = str(row[key])
    for key in ("source_chunk_ids", "source_formula_ids"):
        value = row.get(key)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = None
            row[key] = parsed if isinstance(parsed, list) else [x.strip(" `\"'") for x in re.split(r"[,，;；\s]+", value.strip("[] ")) if x.strip(" `\"'")]
    context = row.get("context_conditions")
    if isinstance(context, str):
        try:
            parsed = json.loads(context)
        except ValueError:
            parsed = None
        row["context_conditions"] = parsed if isinstance(parsed, dict) else {"reported_conditions": context}
    return row


def _finish(rows, warnings, output_format, chunks):
    normalized = []
    for row in rows:
        row = _normalize(row)
        if isinstance(row, dict) and not (row.get("source_chunk_ids") or row.get("source_formula_ids")):
            quote = row.get("source_quote")
            if isinstance(quote, str) and len(quote.strip()) >= 12:
                quote = quote.strip().strip('"“”')
                matches = [c.chunk_id for c in chunks if quote in c.raw_text]
                if len(matches) == 1:
                    row["source_chunk_ids"] = matches
                    context = row.get("context_conditions")
                    row["context_conditions"] = {**(context if isinstance(context, dict) else {}), "matched_source_quote": quote}
                    warnings.append("依据模型提供的原文引用唯一匹配了证据片段，请复核。")
        normalized.append(row)
    return normalized, warnings, output_format


def _json_payload(text):
    # Prefer the full response, then fenced blocks, then an embedded complete object/array.
    candidates = [text.strip()] + re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, list) or isinstance(result, dict) and "assertions" in result:
                return result
        except ValueError:
            pass
    for match in re.finditer(r"[\[{]", text):
        try:
            result, _ = decoder.raw_decode(text[match.start():])
            if isinstance(result, list) and result and all(isinstance(x, dict) and "metric_name" in x for x in result):
                return result
            if isinstance(result, dict) and ("assertions" in result or "metric_name" in result):
                return result if "assertions" in result else [result]
        except ValueError:
            continue
    return None


def adapt_assertions(structured, text, config=None, chunks=()):
    text = re.sub(r"<think\b[^>]*>[\s\S]*?</think>", "", text, flags=re.I)
    warnings = []
    payload = structured if isinstance(structured, dict) and "assertions" in structured else _json_payload(text)
    if payload is not None:
        rows = payload if isinstance(payload, list) else payload.get("assertions")
        if not isinstance(rows, list):
            raise ValueError("模型结果中的 assertions 不是列表，请重试提取。")
        if isinstance(payload, dict) and isinstance(payload.get("warnings"), list):
            warnings.extend(x for x in payload["warnings"] if isinstance(x, str))
        return _finish(rows, warnings, "json", chunks)

    rows, headers, record = [], None, {}
    def flush():
        if record:
            rows.append(_normalize(dict(record)))
            record.clear()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            flush()
            headers = None
            continue
        if "|" in line:
            cells = [x.strip().strip("`") for x in line.strip("|").split("|")]
            keys = [_key(x) for x in cells]
            if {"metric_name", "value", "unit"} <= set(keys):
                flush()
                headers = keys
            elif headers and len(cells) == len(headers) and not all(re.fullmatch(r":?-{2,}:?", x) for x in cells):
                rows.append(_normalize(dict(zip(headers, cells))))
            continue
        match = re.match(r"(?:[-*]\s*|\d+[.)]\s*)?(.+?)\s*[:：]\s*(.+)$", line)
        if match:
            key, value = _key(match[1]), match[2].strip()
            if key in FIELDS:
                if key == "metric_name" and "metric_name" in record:
                    flush()
                record[key] = value
    flush()
    if not rows and config is not None:
        # A sentence is usable only when its metric, number, unit and source ID are explicit.
        for line in text.splitlines():
            for metric in config.core_metrics:
                names = [metric.name, *metric.aliases]
                units = [metric.expected_unit, *config.validation.unit_normalization.get(metric.expected_unit, [])]
                pattern = (r"(?<!\w)(?:" + "|".join(re.escape(n).replace("_", r"[ _]") for n in names)
                           + r")\s*(?:is|was|of|equals|为|是|[:：=])\s*"
                           + r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*("
                           + "|".join(re.escape(u) for u in sorted(units, key=len, reverse=True)) + r")(?!\w)")
                matches = list(re.finditer(pattern, line, re.I))
                ids = [chunk.chunk_id for chunk in chunks if re.search(r"(?<![\w-])" + re.escape(chunk.chunk_id) + r"(?![\w-])", line)]
                if len(matches) == 1 and len(ids) == 1 and not re.search(r"\b(could|might|may|hypothetical|target|expected)\b|可能|预计|目标|假设", line, re.I):
                    match = matches[0]
                    rows.append({"metric_name": metric.name, "value": match[1], "unit": match[2],
                                 "source_chunk_ids": ids, "context_conditions": {"reported_statement": line},
                                 "reasoning": "Adapted explicit model statement; verify context against the cited source."})
    if not rows:
        raise ValueError("模型已回复，但未识别到带指标、数值、单位和证据的结果。支持 JSON、Markdown 表格和标注字段的文本；请重试或更换模型。")
    warnings.append("已将模型的表格/文本回复转换为候选断言，请在入库前复核原文证据和条件。")
    return _finish(rows, warnings, "table_or_text", chunks)

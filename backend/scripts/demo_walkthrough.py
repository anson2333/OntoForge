#!/usr/bin/env python3
"""OntoForge 端到端演示脚本。

按“登录 → 工作区 → 论文/断言 → 原文证据 → 覆盖与候选空白 → PDF 入库”的顺序
调用真实后端 JSON-RPC 接口，并在终端打印每一步的关键结果，便于课堂演示。

用法（仓库根目录，后端已启动）：

    python backend/scripts/demo_walkthrough.py
    python backend/scripts/demo_walkthrough.py --namespace optical
    python backend/scripts/demo_walkthrough.py --pdf OntoForge.pdf --namespace wireless

脚本只读取数据；只有显式传入 ``--pdf`` 时才会写入一篇论文。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

DEFAULT_RPC_URL = "http://localhost:8765/jsonrpc"


class DemoError(RuntimeError):
    """演示流程中的可预期失败。"""


def rpc(
    url: str,
    method: str,
    params: dict | None = None,
    token: str | None = None,
    timeout: int = 180,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:  # pragma: no cover - 手工演示路径
        raise DemoError(f"{method} 请求失败：HTTP {exc.code}") from exc

    if "error" in body:
        error = body["error"]
        raise DemoError(f"{method} 失败：[{error.get('code')}] {error.get('message')}")
    return body["result"]


def step(index: int, total: int, title: str) -> None:
    print(f"\n[{index}/{total}] {title}")


def truncate(value: str, limit: int = 90) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def pick_workspace(workspaces: list[dict], workspace_id: str | None) -> dict:
    if workspace_id:
        for workspace in workspaces:
            if workspace["id"] == workspace_id:
                return workspace
        raise DemoError(f"当前账号看不到工作区 {workspace_id}")
    if not workspaces:
        raise DemoError("当前账号没有可访问的工作区，请先运行 load_mock_data 或创建workspace")
    return workspaces[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="OntoForge 端到端演示")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL, help="JSON-RPC 地址")
    parser.add_argument("--username", default="demo", help="登录用户名")
    parser.add_argument("--password", default="demo1234", help="登录密码")
    parser.add_argument("--workspace-id", help="指定工作区；默认取列表中的第一个")
    parser.add_argument(
        "--namespace",
        default="wireless",
        help="演示用的领域包命名空间（optical / wireless）",
    )
    parser.add_argument("--pdf", help="可选：上传并入库这个 PDF 文件")
    args = parser.parse_args()

    total = 7 if args.pdf else 6
    health_url = args.rpc_url.rsplit("/", 1)[0] + "/health"

    step(1, total, "后端健康检查")
    try:
        with urllib.request.urlopen(health_url, timeout=10) as response:
            health = json.load(response)
    except Exception as exc:  # noqa: BLE001 - 演示脚本直接给出可读错误
        raise DemoError(f"无法连接后端 {health_url}：{exc}") from exc
    print(f"  /health → {health}")

    step(2, total, "身份认证")
    anonymous = rpc(args.rpc_url, "authStatus")
    print(f"  匿名访问：authenticated={anonymous['authenticated']}")
    login = rpc(
        args.rpc_url,
        "authLogin",
        {"username": args.username, "password": args.password},
    )
    token = login["token"]
    user = login["user"]
    print(f"  登录成功：{user['display_name']} ({user['username']}, {user['user_id']})")
    print(f"  会话令牌：{token[:12]}…（后续请求放在 Authorization: Bearer 头中）")

    step(3, total, "工作区列表（按登录身份过滤）")
    workspaces = rpc(args.rpc_url, "listWorkspaces", {}, token)["workspaces"]
    workspace = pick_workspace(workspaces, args.workspace_id)
    print(f"  可访问工作区 {len(workspaces)} 个，本次使用：{workspace['name']} ({workspace['id']})")
    print(f"  owner_id={workspace['owner_id']}")

    step(4, total, "论文与指标断言")
    papers = rpc(args.rpc_url, "getPapers", {"workspace_id": workspace["id"]}, token)["papers"]
    by_namespace = Counter(paper.get("domain_pack_namespace") or "未标注" for paper in papers)
    print(f"  论文 {len(papers)} 篇，按领域包：{dict(by_namespace)}")
    for paper in papers[:3]:
        print(f"    - [{paper.get('domain_pack_namespace')}] {truncate(paper['title'], 70)} ({paper.get('year')})")

    assertions = rpc(
        args.rpc_url,
        "getAssertions",
        {"workspace_id": workspace["id"]},
        token,
    )["assertions"]
    status_counts = Counter(assertion["status"] for assertion in assertions)
    print(f"  断言 {len(assertions)} 条，状态分布：{dict(status_counts)}")
    sample = assertions[0]
    print(
        "  示例："
        f"{sample['paperId']} / {sample['metricName']} = {sample['value']} {sample['unit']}"
        f"（{sample['status']}, confidence={sample['confidence']}）"
    )

    step(5, total, "原文证据回溯")
    evidence = rpc(
        args.rpc_url,
        "getEvidence",
        {
            "workspace_id": workspace["id"],
            "paper_id": sample["paperId"],
            "metric_name": sample["metricName"],
        },
        token,
    )
    if evidence["evidence"]:
        item = evidence["evidence"][0]
        print(f"  证据片段 {item['id']}（{item['type']}, confidence={item['confidence']}）")
        print(f"  原文：{truncate(item['text'], 110)}")
        print(f"  页码定位：{item['bounding_box']}")
    else:
        print("  该单元格暂无证据片段（mock 数据通常每条断言都有一条）")

    step(6, total, "覆盖分析与候选研究空白")
    coverage = rpc(
        args.rpc_url,
        "getCoverageAnalysis",
        {"workspace_id": workspace["id"], "domain_pack_namespace": args.namespace},
        token,
    )["coverage"]
    summary = coverage["coverage"]
    print(f"  维度：{len(coverage['methods'])} 方法 × {len(coverage['scenarios'])} 场景 × {len(coverage['metrics'])} 指标")
    print(f"  方法：{coverage['methods']}")
    print(f"  场景：{coverage['scenarios']}")
    print(f"  已覆盖单元格：{summary['covered_cells']}/{summary['total_cells']}（ratio={summary['ratio']}）")
    gaps = rpc(
        args.rpc_url,
        "getGapCandidates",
        {
            "workspace_id": workspace["id"],
            "domain_pack_namespace": args.namespace,
            "limit": 5,
        },
        token,
    )
    print(f"  候选空白总数：{gaps['gap_count']}，展示前 {len(gaps['gaps'])} 条：")
    for gap in gaps["gaps"]:
        print(
            f"    - 方法={gap['method']:<12} 场景={gap['scenario']:<14} 指标={gap['metric']:<20}"
            f" score={gap['score']}（metric_demand={gap['metric_demand']}, "
            f"method_activity={gap['method_activity']}, scenario_activity={gap['scenario_activity']}）"
        )
    print("  说明：空白表示“当前导入文献中缺少覆盖”，不等同于整个领域无人研究。")
    print("  说明：mock 断言的方法/场景按论文轮换生成，结构相近的组合会并列同一分数；真实 LLM 抽取后分数会拉开差距。")

    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.is_file():
            raise DemoError(f"找不到 PDF 文件：{pdf_path}")

        step(7, total, f"PDF 入库闭环：{pdf_path.name}")
        content = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        upload = rpc(
            args.rpc_url,
            "uploadPdf",
            {
                "file_name": pdf_path.name,
                "content_base64": content,
                "workspace_id": workspace["id"],
            },
            token,
        )
        print(f"  1) uploadPdf → {upload['upload_id']}（{upload['size_bytes']} 字节）")
        parsed = rpc(
            args.rpc_url,
            "parsePdfWithDomainPack",
            {
                "workspace_id": workspace["id"],
                "domain_pack_namespace": args.namespace,
                "upload_id": upload["upload_id"],
            },
            token,
        )
        print(
            f"  2) parsePdfWithDomainPack → status={parsed.get('status')}, "
            f"extractor={parsed.get('extraction_method')}, "
            f"assertion_source={parsed.get('assertion_extraction_method')}, "
            f"chunks={len(parsed.get('chunks') or [])}, "
            f"assertions={len(parsed.get('assertions') or [])}"
        )
        for warning in parsed.get("warnings") or []:
            print(f"     warning: {warning}")
        committed = rpc(
            args.rpc_url,
            "commitParsedPdf",
            {
                "workspace_id": workspace["id"],
                "domain_pack_namespace": args.namespace,
                "upload_id": upload["upload_id"],
                "preview_id": parsed["preview_id"],
            },
            token,
        )
        print(
            f"  3) commitParsedPdf → status={committed.get('status')}, "
            f"paper_id={committed.get('paper_id')}, "
            f"chunks_created={committed.get('chunks_created')}, "
            f"assertions_created={committed.get('assertions_created')}"
        )
        repeat = rpc(
            args.rpc_url,
            "commitParsedPdf",
            {
                "workspace_id": workspace["id"],
                "domain_pack_namespace": args.namespace,
                "upload_id": upload["upload_id"],
                "preview_id": parsed["preview_id"],
            },
            token,
        )
        print(f"  4) 重复提交 → status={repeat.get('status')}")
        for warning in repeat.get("warnings") or []:
            print(f"     warning: {warning}")
        print("  如需恢复演示数据：python -m backend.scripts.load_mock_data")

    rpc(args.rpc_url, "authLogout", {}, token)
    print("\n演示流程结束，已注销会话。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DemoError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)

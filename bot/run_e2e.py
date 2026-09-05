"""历史顾问飞书 Bot · e2e 联调脚本(D5 · 2026-09-05 落地)

启动方式:
  1. 终端 A:python -m bot.webhook --port 9777
  2. 终端 B:python -m bot.run_e2e --port 9777

覆盖 6 场景(与单测互补,验证 HTTP 入口 + 路由 + 返回卡片):
  1. URL 校验(GET /webhook?challenge=xxx)
  2. 健康检查(GET /health)
  3. 消息事件 - 人物速查(POST /webhook,im.message.receive_v1,text="秦始皇")
  4. 消息事件 - 事件回顾(text="赤壁之战")
  5. 消息事件 - 多结果(之战,候选列表)
  6. 消息事件 - 无结果(火星大战)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9777
TIMEOUT = 5.0


def _http_get(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_ready(base: str, retries: int = 20, delay: float = 0.25) -> bool:
    for _ in range(retries):
        try:
            if _http_get(f"{base}/health").get("status") == "ok":
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(delay)
    return False


def _event_payload(text: str) -> Dict[str, Any]:
    return {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "app_id": "cli_test",
            "tenant_key": "test_tenant",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou_test"}},
            "message": {
                "message_id": "om_test",
                "chat_id": "oc_test",
                "chat_type": "p2p",
                "content": json.dumps({"text": text}),
            },
        },
    }


def run_e2e(base: str) -> bool:
    print(f"=== e2e 联调 · base={base} ===")
    ok_all = True

    # 1. URL 校验
    challenge = "test_challenge_12345"
    try:
        r = _http_get(f"{base}/webhook?challenge={challenge}")
        ok = r.get("challenge") == challenge
        print(f"[{'OK' if ok else 'FAIL'}] URL 校验(GET):{r}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] URL 校验:{e}")
        ok_all = False

    # 2. 健康检查
    try:
        r = _http_get(f"{base}/health")
        ok = r.get("status") == "ok"
        print(f"[{'OK' if ok else 'FAIL'}] 健康检查:{r}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] 健康检查:{e}")
        ok_all = False

    # 3. 人物速查(单结果)
    try:
        r = _http_post(f"{base}/webhook", _event_payload("秦始皇"))
        card = r.get("card", {})
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        # command 对外接口统一为中文 "人物" / "事件"(D6 收口中文化,9/5 落地时仍用英文)
        ok = r.get("command") == "人物" and "秦始皇" in title
        print(f"[{'OK' if ok else 'FAIL'}] 人物速查(秦始皇):title={title}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] 人物速查:{e}")
        ok_all = False

    # 4. 事件回顾(单结果)
    try:
        r = _http_post(f"{base}/webhook", _event_payload("赤壁之战"))
        card = r.get("card", {})
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        ok = r.get("command") == "事件" and "赤壁之战" in title
        print(f"[{'OK' if ok else 'FAIL'}] 事件回顾(赤壁之战):title={title}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] 事件回顾:{e}")
        ok_all = False

    # 5. 多结果(之战)
    try:
        r = _http_post(f"{base}/webhook", _event_payload("之战"))
        card = r.get("card", {})
        ok = r.get("command") == "事件" and "elements" in card
        # 候选列表有 elements 列表,且每个含"title"
        n = len(card.get("elements", []))
        ok = ok and n >= 1
        print(f"[{'OK' if ok else 'FAIL'}] 多结果(之战):候选数={n}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] 多结果:{e}")
        ok_all = False

    # 6. 无结果
    try:
        r = _http_post(f"{base}/webhook", _event_payload("火星大战"))
        card = r.get("card", {})
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        ok = "未" in title or "无" in title
        print(f"[{'OK' if ok else 'FAIL'}] 无结果(火星大战):title={title}")
        ok_all &= ok
    except Exception as e:
        print(f"[FAIL] 无结果:{e}")
        ok_all = False

    print("===")
    print(f"汇总:{'ALL PASS ✅' if ok_all else 'HAS FAIL ❌'}")
    return ok_all


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="历史顾问飞书 Bot e2e 联调")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-wait", action="store_true", help="不等待 server 起来")
    args = parser.parse_args(argv)
    base = f"http://{args.host}:{args.port}"
    if not args.no_wait and not _wait_ready(base):
        print(f"server not ready at {base} (请先跑 python -m bot.webhook)", file=sys.stderr)
        return 1
    return 0 if run_e2e(base) else 2


__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "main", "run_e2e"]


if __name__ == "__main__":
    sys.exit(main())

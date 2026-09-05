"""历史顾问飞书 Bot · webhook 入口(D5 · 2026-09-05 落地)

Phase 0 第 6 项 / D5(5.75/6 → 5.9/6)。

功能:
  - URL 校验 endpoint(GET /webhook):飞书事件订阅时回传 challenge
  - 消息接收 endpoint(POST /webhook):解析 im.message.receive_v1 → 路由到 lookup / recap
  - 健康检查(GET /health)
  - 零依赖:走标准库 http.server,无需 Flask / FastAPI
  - 命令路由:lookup 优先,recap 兜底

使用:
  python -m bot.webhook                  # 启动 :9777
  python -m bot.webhook --port 9888      # 自定义端口

e2e 联调:
  python -m bot.run_e2e                  # 启动 server + 4 场景 HTTP 调用
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from . import lookup, recap

# 默认监听端口(避开常用 8000 / 9000 / 5000)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9777

logger = logging.getLogger("bot.webhook")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def route_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    """统一命令路由:lookup 优先,recap 兜底。

    注意:parse_command 兜底词(如 "之战" / "战役" / "战役" / "谁" / "生平")
    可能返回 keyword-only query(如 ("事件", "之战")),此时 query.strip() 是
    关键词本身不算空,必须放行。否则 webhook 兜底把 "之战" 错路由到人物查询。
    """
    cmd, query = lookup.parse_command(text)
    if cmd and query is not None and query.strip():
        return cmd, query
    cmd, query = recap.parse_command(text)
    if cmd and query is not None and query.strip():
        return cmd, query
    return None, None


def handle_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """飞书事件订阅 POST handler(主入口,纯函数便于 e2e / 单测)。

    约定输入(payload dict):
      - 含 "challenge" → URL 校验,透传
      - 含 "header.event_type"=="im.message.receive_v1" → 消息事件
        - event.message.content 是 JSON 字符串,内含 "text"
    """
    if "challenge" in payload:
        return {"challenge": payload["challenge"]}

    header = payload.get("header") or {}
    event_type = header.get("event_type", "")
    if event_type != "im.message.receive_v1":
        return {"code": 0, "msg": "ignored", "event_type": event_type}

    event = payload.get("event") or {}
    message = event.get("message") or {}
    raw = message.get("content", "")
    text = ""
    if raw:
        try:
            text = json.loads(raw).get("text", "")
        except (ValueError, TypeError):
            text = ""
    text = (text or "").strip()
    if not text:
        return {"code": 0, "msg": "empty text"}

    cmd, query = route_command(text)
    if cmd is None:
        cmd, query = "人物", text  # 兜底:整段当人物关键词

    if cmd == "人物":
        card = lookup.handle(query)
    elif cmd == "事件":
        card = recap.handle(query)
    else:
        card = {"err": f"unknown command: {cmd}"}
    return {"code": 0, "msg": "ok", "command": cmd, "card": card}


class WebhookHandler(BaseHTTPRequestHandler):
    """http.server handler(零依赖)"""

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: int, body: Dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.startswith("/webhook"):
            challenge = parse_qs(urlparse(self.path).query).get("challenge", [""])[0]
            if challenge:
                self._send_json(200, {"challenge": challenge})
                return
        if self.path.split("?")[0] == "/health":
            self._send_json(200, {"status": "ok", "module": "bot.webhook", "version": "0.1.5"})
            return
        self._send_json(404, {"code": 404, "msg": "not found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/webhook"):
            self._send_json(404, {"code": 404, "msg": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            self._send_json(400, {"code": 400, "msg": "empty body"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._send_json(400, {"code": 400, "msg": f"bad json: {e}"})
            return
        try:
            self._send_json(200, handle_event(payload))
        except Exception as e:  # noqa: BLE001
            logger.exception("handle_event failed")
            self._send_json(500, {"code": 500, "msg": f"internal: {e}"})


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), WebhookHandler)
    logger.info("webhook listening on http://%s:%s/webhook", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
        server.shutdown()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="历史顾问飞书 Bot webhook")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    run_server(args.host, args.port)
    return 0


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "WebhookHandler",
    "handle_event",
    "main",
    "route_command",
    "run_server",
]


if __name__ == "__main__":
    sys.exit(main())

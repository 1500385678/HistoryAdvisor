"""历史顾问 Web 后端 · W3 骨架(2026-09-09 T2 启动)

设计原则(简洁可入库,仅验证 web → SQLite 端到端联通):
- 零样式 · Hello 级别 · FastAPI 最小入口
- 3 路由:根重定向 + 人物页(/person/{id}) + 事件页(/event/{id})
- SQLite 只读连接 `data/history.db`(沿用 bot/ 模块同源 DB)
- 人物页返回 3 字段(name / role / dynasty),事件页返回 3 字段(name / year / category)
- 联表 dynasties 拿朝代名,失败兜底空字符串(不报错)
- W4+ 演进:加 CORS / 静态托管 / 搜索 / 时间线 / 地图等

启动:
    cd /Users/aaron/Mac/Consultant/34-历史-History/_HistoryLib/HistoryWeb
    python3 -m uvicorn backend.main:app --port 8765

验证:
    curl http://127.0.0.1:8765/person/1   # 秦始皇嬴政
    curl http://127.0.0.1:8765/event/1    # 大禹治水
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

# DB 路径:本文件位于 backend/main.py,DB 在 ../data/history.db(相对工程根)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "history.db"

app = FastAPI(
    title="历史顾问 Web",
    version="0.1.0",
    description="W3 骨架 9/9 启动 · Phase 1 人物页 + 事件页最小版本",
)


def _connect() -> sqlite3.Connection:
    """SQLite 只读连接(沿用 bot/ 模块约定,uri + mode=ro)"""
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"DB 不存在:{DB_PATH}")
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _dynasty_name(cur: sqlite3.Cursor, dynasty_id: Optional[int]) -> str:
    """联表查朝代名,失败兜底空字符串"""
    if dynasty_id is None:
        return ""
    row = cur.execute("SELECT name FROM dynasties WHERE id = ?", (dynasty_id,)).fetchone()
    return row[0] if row else ""


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """根路由:重定向到 index.html(静态页面由 NGINX / Caddy / python -m http.server 托管)"""
    return RedirectResponse(url="/index.html", status_code=307)


@app.get("/person/{person_id}")
def get_person(person_id: int) -> dict:
    """人物页最小版本:figures 表只读查 id = ?,返回 name / role / dynasty 3 字段"""
    with _connect() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, name, role, dynasty_id FROM figures WHERE id = ?",
            (person_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"人物 id={person_id} 不存在")
        pid, name, role, dynasty_id = row
        return {
            "id": pid,
            "name": name,
            "role": role or "",
            "dynasty": _dynasty_name(cur, dynasty_id),
        }


@app.get("/event/{event_id}")
def get_event(event_id: int) -> dict:
    """事件页最小版本:events 表只读查 id = ?,返回 name / year / category 3 字段"""
    with _connect() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, name, year, category, dynasty_id FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"事件 id={event_id} 不存在")
        eid, name, year, category, dynasty_id = row
        return {
            "id": eid,
            "name": name,
            "year": year,
            "category": category or "",
            "dynasty": _dynasty_name(cur, dynasty_id),
        }


@app.get("/health")
def health() -> dict:
    """健康检查:W4 部署阶段给 NGINX / 监控系统用"""
    return {"status": "ok", "db": str(DB_PATH), "version": app.version}


__all__ = ["app"]

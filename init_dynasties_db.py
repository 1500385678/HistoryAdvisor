#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_dynasties_db.py · v0.1 · HistoryAdvisor Phase 0 第 2 项

功能:
    读 data/dynasties.json → 写入 SQLite data/history.db 的 dynasties 表
    幂等:二次运行会先 DROP 再 CREATE,dynasty 数量与 JSON 中保持一致

设计原则:
    - 零外部依赖(只 sqlite3 / json / pathlib,全部 stdlib)
    - 表结构与「项目开发计划.md 第四章 4.3 数据模型」一致
    - 输出到 data/history.db,Phase 1 FastAPI 直接 sqlite3.connect() 复用
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------- 路径配置 ----------

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "dynasties.json"
DB_PATH = ROOT / "data" / "history.db"

# ---------- 表结构(与主计划 4.3 节一致) ----------

SCHEMA = """
CREATE TABLE IF NOT EXISTS dynasties (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  start_year INTEGER,            -- 公元前为负,公元后为正
  end_year INTEGER,              -- 至今为 NULL
  capital TEXT,
  founder TEXT,
  region TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_dynasties_name ON dynasties(name);
CREATE INDEX IF NOT EXISTS idx_dynasties_years ON dynasties(start_year, end_year);
"""


def init_db() -> sqlite3.Connection:
    """建表 + 索引,返回连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def upsert_dynasties(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """清空表再批量 INSERT,返回写入行数(便于回归测试)。"""
    conn.execute("DELETE FROM dynasties")  # 幂等:不留历史残值
    conn.executemany(
        """
        INSERT INTO dynasties (id, name, start_year, end_year, capital, founder, region, notes)
        VALUES (:id, :name, :start_year, :end_year, :capital, :founder, :region, :notes)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def verify(conn: sqlite3.Connection) -> None:
    """简单校验:总数 / 起年最早 / 起年最晚 3 个数字写到控制台。"""
    total = conn.execute("SELECT COUNT(*) FROM dynasties").fetchone()[0]
    earliest = conn.execute(
        "SELECT name, start_year FROM dynasties ORDER BY start_year ASC LIMIT 1"
    ).fetchone()
    latest = conn.execute(
        "SELECT name, COALESCE(end_year, 9999) AS ey FROM dynasties ORDER BY ey DESC LIMIT 1"
    ).fetchone()
    print(f"✓ Total dynasties: {total}")
    print(f"✓ Earliest: {earliest[0]} ({earliest[1]})")
    print(f"✓ Latest:   {latest[0]} (end={latest[1] if latest[1] != 9999 else '至今'})")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"missing: {JSON_PATH}")
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rows = payload["dynasties"]

    conn = init_db()
    n = upsert_dynasties(conn, rows)
    print(f"✓ Inserted {n} dynasties into {DB_PATH}")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()

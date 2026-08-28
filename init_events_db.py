#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_events_db.py · v0.1 · HistoryAdvisor Phase 0 第 4 项

功能:
    读 data/events.json → 写入 SQLite data/history.db 的 events 表
    幂等:二次运行会先 DELETE 再 INSERT,event 数量与 JSON 中保持一致
    与 init_dynasties_db.py / init_persons_db.py 共用同一 DB(history.db),符合"一库多表"原则

设计原则:
    - 零外部依赖(只 sqlite3 / json / pathlib,全部 stdlib)
    - 表结构与「项目开发计划.md §4.3 数据模型」events 表一致(对齐 id/name/year/dynasty_id/category/location/participants/description/significance,加 impact)
    - dynasty_id 外键 → dynasties.id,加索引 idx_events_dynasty_id 提升按朝代查事件效率
    - 事件类别按"变法/战争/发明/政变/条约/文化/制度/起义"8 类分桶,Phase 1 Web App 可按类别筛选
    - key_figures / sources 为 JSON 数组字符串(暂不拆中间表,Phase 1 需 N:M 时再升级)
    - 公元前用负数年表(与 dynasties / figures 一致)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------- 路径配置 ----------

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "events.json"
DB_PATH = ROOT / "data" / "history.db"  # 与 init_dynasties_db.py / init_persons_db.py 同库

# ---------- 表结构(与主计划 §4.3 events 表一致 + impact 字段) ----------

# events 表 schema 选段(防止脚本被独立运行时缺表):
#   CREATE TABLE IF NOT EXISTS events (
#     id INTEGER PRIMARY KEY,
#     name TEXT NOT NULL,                    -- 事件名(如"商鞅变法"/"赤壁之战")
#     year INTEGER,                          -- 发生年(公元前为负)
#     dynasty_id INTEGER REFERENCES dynasties(id),
#     category TEXT,                         -- 变法/战争/发明/政变/条约/文化/制度/起义
#     location TEXT,                         -- 发生地点
#     key_figures TEXT,                      -- JSON 数组,涉及人物名
#     summary TEXT,                          -- 简述
#     impact TEXT,                           -- 影响
#     sources TEXT                           -- JSON 数组,史料来源
#   );
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  year INTEGER,                            -- 公元前为负
  dynasty_id INTEGER REFERENCES dynasties(id),
  category TEXT,                           -- 变法/战争/发明/政变/条约/文化/制度/起义
  location TEXT,
  key_figures TEXT,                        -- JSON 数组
  summary TEXT,
  impact TEXT,
  sources TEXT                             -- JSON 数组
);
CREATE INDEX IF NOT EXISTS idx_events_dynasty_id ON events(dynasty_id);
CREATE INDEX IF NOT EXISTS idx_events_year ON events(year);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
"""


def ensure_dependencies_table(conn: sqlite3.Connection) -> None:
    """
    若 events 表所属的 history.db 还没建过 dynasties / figures 表(独立运行场景),
    同步建一个最小兼容的 dynasties / figures 占位表(仅 schema,无数据)。
    实际部署建议先跑 init_dynasties_db.py + init_persons_db.py。
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dynasties'"
    )
    if cur.fetchone() is None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dynasties (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              start_year INTEGER,
              end_year INTEGER,
              capital TEXT,
              founder TEXT,
              region TEXT,
              notes TEXT
            );
            """
        )
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='figures'"
    )
    if cur.fetchone() is None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS figures (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              dynasty_id INTEGER REFERENCES dynasties(id),
              birth_year INTEGER,
              death_year INTEGER,
              role TEXT,
              biography TEXT,
              achievements TEXT,
              evaluations TEXT
            );
            """
        )


def init_db() -> sqlite3.Connection:
    """建表 + 索引,返回连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_dependencies_table(conn)
    conn.executescript(SCHEMA)
    return conn


def upsert_events(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """清空表再批量 INSERT,返回写入行数(便于回归测试)。"""
    conn.execute("DELETE FROM events")  # 幂等:不留历史残值
    # list 字段需 json.dumps 为字符串(暂存 JSON 文本,Phase 1 需 N:M 时再拆中间表)
    normalized = [
        {
            **r,
            "key_figures": json.dumps(r["key_figures"], ensure_ascii=False),
            "sources": json.dumps(r["sources"], ensure_ascii=False),
        }
        for r in rows
    ]
    conn.executemany(
        """
        INSERT INTO events
          (id, name, year, dynasty_id, category, location, key_figures, summary, impact, sources)
        VALUES
          (:id, :name, :year, :dynasty_id, :category, :location, :key_figures, :summary, :impact, :sources)
        """,
        normalized,
    )
    conn.commit()
    return len(rows)


def verify(conn: sqlite3.Connection) -> None:
    """简单校验:总数 / 按朝代分布 / 按类别分布 写到控制台。"""
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"✓ Total events: {total}")

    print("✓ 按朝代分布(TOP 5):")
    for row in conn.execute(
        """
        SELECT d.name AS dynasty, COUNT(e.id) AS cnt
        FROM dynasties d LEFT JOIN events e ON e.dynasty_id = d.id
        GROUP BY d.id ORDER BY cnt DESC LIMIT 5
        """
    ).fetchall():
        print(f"  {row[0]:8s} {row[1]} 事")

    print("✓ 按类别分布:")
    for row in conn.execute(
        "SELECT category, COUNT(*) FROM events GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {row[0]:6s} {row[1]} 事")

    # 抽样:商鞅变法是否正确入库
    sample = conn.execute(
        "SELECT name, year, category, dynasty_id FROM events WHERE id=6"
    ).fetchone()
    if sample:
        print(f"✓ 抽样: id=6 → {sample[0]} (year={sample[1]}) [{sample[2]}] dynasty_id={sample[3]}")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"missing: {JSON_PATH}")
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rows = payload["events"]

    conn = init_db()
    n = upsert_events(conn, rows)
    print(f"✓ Inserted {n} events into {DB_PATH} (events table)")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()

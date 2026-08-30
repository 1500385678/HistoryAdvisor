#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_sources_db.py · v0.1 · HistoryAdvisor Phase 0 第 5 项

功能:
    读 data/sources.json → 写入 SQLite data/history.db 的 sources 表
    幂等:二次运行会先 DELETE 再 INSERT,source 数量与 JSON 中保持一致
    与 init_dynasties_db.py / init_persons_db.py / init_events_db.py 共用同一 DB(history.db)
    符合"一库多表"原则(Phase 0 第 5 项落地)

设计原则:
    - 零外部依赖(只 sqlite3 / json / pathlib,全部 stdlib)
    - 表结构与「项目开发计划.md §4.3 数据模型」sources 表一致
      + 扩展字段 summary(简述)/ time_span(涉及朝代范围)便于 Phase 1 Web App 检索展示
    - dynasty_id 外键 → dynasties.id,加索引 idx_sources_dynasty_id 提升按朝代查史料效率
    - 史料类型按"正史/野史/考古/学术/编年体"5 类分桶,Phase 1 Web App 可按类型筛选
    - credibility 1-5 可信度(5=正史/出土原典; 4=可信度高的二手; 3=笔记/野史; 2=传说; 1=存疑)
    - 公元前用负数年表(与 dynasties / figures / events 一致)
    - 回应 8/31 巡检 R2/A 档(Phase 0 4/6 → 5/6)+ R6 子项(sources 表 + 4 索引,延续"一库多表 + 完整索引"模式)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------- 路径配置 ----------

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "sources.json"
DB_PATH = ROOT / "data" / "history.db"  # 与 init_dynasties_db.py / init_persons_db.py / init_events_db.py 同库

# ---------- 表结构(与主计划 §4.3 sources 表一致 + summary / time_span 扩展) ----------

# sources 表 schema 选段(防止脚本被独立运行时缺表):
#   CREATE TABLE IF NOT EXISTS sources (
#     id INTEGER PRIMARY KEY,
#     title TEXT NOT NULL,                -- 史料名(如"史记"/"资治通鉴")
#     source_type TEXT,                   -- 正史/野史/考古/学术/编年体
#     author TEXT,                        -- 作者/编者/出土物代称
#     dynasty_id INTEGER REFERENCES dynasties(id),  -- 撰写/出土朝代
#     credibility INTEGER,                -- 1-5 可信度
#     summary TEXT,                       -- 简述
#     time_span TEXT,                     -- 涉及朝代范围(如"西汉(前 202-8)")
#     full_text TEXT                      -- 原文/摘录(古文一句)
#   );
SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  source_type TEXT,                       -- 正史/野史/考古/学术/编年体
  author TEXT,
  dynasty_id INTEGER REFERENCES dynasties(id),
  credibility INTEGER,                    -- 1-5 可信度
  summary TEXT,
  time_span TEXT,
  full_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_sources_dynasty_id ON sources(dynasty_id);
CREATE INDEX IF NOT EXISTS idx_sources_source_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_credibility ON sources(credibility);
CREATE INDEX IF NOT EXISTS idx_sources_title ON sources(title);
"""


def ensure_dependencies_table(conn: sqlite3.Connection) -> None:
    """
    若 sources 表所属的 history.db 还没建过 dynasties / figures / events 表(独立运行场景),
    同步建一个最小兼容的 dynasties / figures / events 占位表(仅 schema,无数据)。
    实际部署建议先跑 init_dynasties_db.py + init_persons_db.py + init_events_db.py。
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
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    )
    if cur.fetchone() is None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              year INTEGER,
              dynasty_id INTEGER REFERENCES dynasties(id),
              category TEXT,
              location TEXT,
              key_figures TEXT,
              summary TEXT,
              impact TEXT,
              sources TEXT
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


def upsert_sources(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """清空表再批量 INSERT,返回写入行数(便于回归测试)。"""
    conn.execute("DELETE FROM sources")  # 幂等:不留历史残值
    conn.executemany(
        """
        INSERT INTO sources
          (id, title, source_type, author, dynasty_id, credibility, summary, time_span, full_text)
        VALUES
          (:id, :title, :source_type, :author, :dynasty_id, :credibility, :summary, :time_span, :full_text)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def verify(conn: sqlite3.Connection) -> None:
    """简单校验:总数 / 按朝代分布 / 按类型分布 / 可信度分布 写到控制台。"""
    total = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    print(f"✓ Total sources: {total}")

    print("✓ 按朝代分布(TOP 8):")
    for row in conn.execute(
        """
        SELECT d.name AS dynasty, COUNT(s.id) AS cnt
        FROM dynasties d LEFT JOIN sources s ON s.dynasty_id = d.id
        GROUP BY d.id ORDER BY cnt DESC LIMIT 8
        """
    ).fetchall():
        print(f"  {row[0]:12s} {row[1]:3d} 部")

    print("✓ 按类型分布:")
    for row in conn.execute(
        "SELECT source_type, COUNT(*) FROM sources GROUP BY source_type ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {row[0]:6s} {row[1]:3d} 部")

    print("✓ 按可信度分布(1-5):")
    for row in conn.execute(
        "SELECT credibility, COUNT(*) FROM sources GROUP BY credibility ORDER BY credibility DESC"
    ).fetchall():
        print(f"  {row[0]}★ {row[1]:3d} 部")

    # 抽样:史记是否正确入库
    sample = conn.execute(
        "SELECT title, source_type, dynasty_id, credibility FROM sources WHERE id=1"
    ).fetchone()
    if sample:
        print(f"✓ 抽样: id=1 → {sample[0]} [{sample[1]}] dynasty_id={sample[2]} credibility={sample[3]}")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"missing: {JSON_PATH}")
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rows = payload["sources"]

    conn = init_db()
    n = upsert_sources(conn, rows)
    print(f"✓ Inserted {n} sources into {DB_PATH} (sources table)")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()

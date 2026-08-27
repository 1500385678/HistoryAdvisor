#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_persons_db.py · v0.1 · HistoryAdvisor Phase 0 第 3 项

功能:
    读 data/persons.json → 写入 SQLite data/history.db 的 figures 表
    幂等:二次运行会先 DELETE 再 INSERT,person 数量与 JSON 中保持一致
    与 init_dynasties_db.py 共用同一 DB(history.db),符合"一库多表"原则

设计原则:
    - 零外部依赖(只 sqlite3 / json / pathlib,全部 stdlib)
    - 表结构与「项目开发计划.md §4.3 数据模型」figures 表一致
    - dynasty_id 外键 → dynasties.id,加索引 idx_dynasties_id 提升按朝代查人物效率
    - 角色(role)按"帝王/名臣/思想家/名将"四类分桶,Phase 1 Web App 可按角色筛选
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------- 路径配置 ----------

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "persons.json"
DB_PATH = ROOT / "data" / "history.db"  # 与 init_dynasties_db.py 同库

# ---------- 表结构(与主计划 §4.3 figures 表一致) ----------

# figures 表 schema 选段(防止脚本被独立运行时缺表):
#   CREATE TABLE IF NOT EXISTS figures (
#     id INTEGER PRIMARY KEY,
#     name TEXT NOT NULL,
#     dynasty_id INTEGER REFERENCES dynasties(id),
#     birth_year INTEGER,            -- 公元前为负
#     death_year INTEGER,            -- 至今为 NULL
#     role TEXT,                     -- 帝王/名臣/思想家/名将
#     biography TEXT,
#     achievements TEXT,
#     evaluations TEXT
#   );
SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_figures_dynasty_id ON figures(dynasty_id);
CREATE INDEX IF NOT EXISTS idx_figures_name ON figures(name);
CREATE INDEX IF NOT EXISTS idx_figures_role ON figures(role);
CREATE INDEX IF NOT EXISTS idx_figures_years ON figures(birth_year, death_year);
"""


def ensure_dynasties_table(conn: sqlite3.Connection) -> None:
    """
    若 figures 表所属的 history.db 还没建过 dynasties 表(独立运行场景),
    同步建一个最小兼容的 dynasties 占位表(仅 schema,无数据)。
    实际部署建议先跑 init_dynasties_db.py。
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


def init_db() -> sqlite3.Connection:
    """建表 + 索引,返回连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_dynasties_table(conn)
    conn.executescript(SCHEMA)
    return conn


def upsert_persons(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """清空表再批量 INSERT,返回写入行数(便于回归测试)。"""
    conn.execute("DELETE FROM figures")  # 幂等:不留历史残值
    conn.executemany(
        """
        INSERT INTO figures
          (id, name, dynasty_id, birth_year, death_year, role, biography, achievements, evaluations)
        VALUES
          (:id, :name, :dynasty_id, :birth_year, :death_year, :role, :biography, :achievements, :evaluations)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def verify(conn: sqlite3.Connection) -> None:
    """简单校验:总数 / 按朝代分布 / 按角色分布 写到控制台。"""
    total = conn.execute("SELECT COUNT(*) FROM figures").fetchone()[0]
    print(f"✓ Total persons: {total}")

    print("✓ 按朝代分布(TOP 5):")
    for row in conn.execute(
        """
        SELECT d.name AS dynasty, COUNT(f.id) AS cnt
        FROM dynasties d LEFT JOIN figures f ON f.dynasty_id = d.id
        GROUP BY d.id ORDER BY cnt DESC LIMIT 5
        """
    ).fetchall():
        print(f"  {row[0]:8s} {row[1]} 人")

    print("✓ 按角色分布:")
    for row in conn.execute(
        "SELECT role, COUNT(*) FROM figures GROUP BY role ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {row[0]:6s} {row[1]} 人")

    # 抽样:秦始皇是否正确入库
    sample = conn.execute(
        "SELECT name, birth_year, death_year, role FROM figures WHERE id=1"
    ).fetchone()
    if sample:
        print(f"✓ 抽样: id=1 → {sample[0]} ({sample[1]}~{sample[2]}) [{sample[3]}]")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"missing: {JSON_PATH}")
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rows = payload["persons"]

    conn = init_db()
    n = upsert_persons(conn, rows)
    print(f"✓ Inserted {n} persons into {DB_PATH} (figures table)")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()

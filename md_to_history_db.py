#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_to_history_db.py · v0.1 · HistoryAdvisor Phase 0 第 1 项

功能:
    解析 _HistoryLib/02_历史分支与特点/02_历史分支与特点.md
        + _HistoryLib/06_历史大师与学者/06_历史大师与学者.md
    抽取所有 markdown 表格 → JSON
    输出: HistoryWeb/.plan/20260824-history-data.json

分类规则(基于表格列名启发):
    - 含 "分支/类型" → branches
    - 含 "时期"   → periods
    - 含 "大师" + "代表作" → masters
    - 含 "大师" + "名言" → quotes
    - 兜底 → others

设计原则:
    - 零外部依赖(只用 re / json / pathlib)
    - 一遍扫所有表格,不依赖表格前后标题
    - 输出 schema 稳定,便于 Phase 1 接 FastAPI
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------- 路径配置 ----------

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # _HistoryLib/
LIB_ROOT = PROJECT_ROOT / "_HistoryLib" if (PROJECT_ROOT / "_HistoryLib").exists() else PROJECT_ROOT

# 兼容两种目录结构:HistoryWeb/ 下 _HistoryLib/ 是同级,或者在 ProjectRoot 里
_HISTORYLIB_CANDIDATES = [
    Path(__file__).resolve().parent.parent,  # _HistoryLib/
    Path("/Users/aaron/Mac/Consultant/34-历史-History/_HistoryLib"),
]
HISTORYLIB_ROOT = next(
    (p for p in _HISTORYLIB_CANDIDATES if (p / "02_历史分支与特点").exists()),
    _HISTORYLIB_CANDIDATES[0],
)

SOURCE_FILES = [
    HISTORYLIB_ROOT / "02_历史分支与特点" / "02_历史分支与特点.md",
    HISTORYLIB_ROOT / "06_历史大师与学者" / "06_历史大师与学者.md",
]

OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / ".plan"
    / "20260824-history-data.json"
)

# ---------- 表格分类器 ----------


def classify_table(headers: list[str], source_file: str) -> str:
    """根据列名 + 来源文件,把表格分到 4 个类别之一。"""
    h = " ".join(headers)
    src_name = Path(source_file).parent.name

    # 06_历史大师与学者:含 "代表作" → 大师;含 "名言" → 名言
    if "大师" in h and "代表作" in h:
        return "masters"
    if "大师" in h and "名言" in h:
        return "quotes"
    # 02_历史分支与特点:含 "时期" → periods;否则 branches
    if "时期" in h:
        return "periods"
    if "分支" in h or "类型" in h or "特点" in h:
        return "branches"
    # 兜底:按文件来源
    if "06_" in src_name:
        return "masters"
    return "branches"


# ---------- 表格抽取 ----------


_TABLE_RE = re.compile(
    r"^\s*\|(.+)\|\s*$\n^\s*\|[-:\s|]+\|\s*$\n((?:^\s*\|.+\|\s*$\n?)+)",
    re.MULTILINE,
)


def parse_table(table_md: str) -> list[dict[str, str]]:
    """解析单个 markdown 表格 → list of dict(列名 → 单元格)。"""
    lines = [ln.strip() for ln in table_md.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    header_cells = [c.strip() for c in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:  # 跳过表头 + 分隔行
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(header_cells):
            continue
        rows.append(dict(zip(header_cells, cells)))
    return rows


def extract_tables(md_text: str, source_file: str) -> dict[str, list[dict[str, Any]]]:
    """从 md 文本抽取所有表格,按 4 类分桶。"""
    buckets: dict[str, list[dict[str, Any]]] = {
        "branches": [],
        "periods": [],
        "masters": [],
        "quotes": [],
        "others": [],
    }
    table_idx = 0
    for match in _TABLE_RE.finditer(md_text):
        table_idx += 1
        rows = parse_table(match.group(0))
        if not rows:
            continue
        category = classify_table(list(rows[0].keys()), source_file)
        for row in rows:
            row["_source_file"] = source_file
            row["_table_index"] = table_idx
            buckets[category].append(row)
    return buckets


# ---------- 主流程 ----------


def main() -> None:
    summary: dict[str, Any] = {
        "version": "v0.1",
        "generated_at": "2026-08-24",
        "sources": [str(p) for p in SOURCE_FILES],
        "counts": {},
        "data": {},
    }

    for src in SOURCE_FILES:
        if not src.exists():
            print(f"[WARN] source not found: {src}")
            continue
        text = src.read_text(encoding="utf-8")
        buckets = extract_tables(text, str(src))
        for cat, rows in buckets.items():
            summary["data"].setdefault(cat, []).extend(rows)

    summary["counts"] = {k: len(v) for k, v in summary["data"].items()}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 控制台输出:简洁摘要
    print(f"✓ Parsed {len(SOURCE_FILES)} source files")
    print(f"✓ Output: {OUTPUT_PATH}")
    print(f"✓ Counts: {summary['counts']}")


if __name__ == "__main__":
    main()

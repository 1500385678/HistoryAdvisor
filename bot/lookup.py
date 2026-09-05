"""历史顾问飞书 Bot · 人物速查流水线(D3 · 2026-09-03 落地)

Phase 0 第 6 项 / D3(5.3/6 → 5.5/6)。

功能:
  - 查 figures 表(name LIKE 模糊)+ 外键回查 dynasties 朝代名
  - 角色优先级排序:帝王 > 名臣 > 思想家 > 名将 > 其他
  - 单结果 → bot.schema.figure_card
  - 多结果(<=10) → bot.schema.figure_candidate_list
  - 无结果 → bot.schema.no_result
  - DB 异常 → bot.schema.error_card

SQL 全部走预编译参数化,防注入。
幂等:同一 query 多次调用不报错。
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from . import schema

# 默认 DB 路径(同主计划 §九 工程约定)
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "history.db",
)

# 模糊匹配最大返回数(防爆)
MAX_RESULTS = 10

# 角色优先级:越小越靠前(帝王最优先)
ROLE_PRIORITY = {
    "帝王": 1,
    "名臣": 2,
    "思想家": 3,
    "名将": 4,
}
DEFAULT_ROLE_PRIORITY = 5

# 单结果触发详情卡的最大候选阈值(超过则返回候选列表)
SINGLE_RESULT_THRESHOLD = 1


class LookupError(RuntimeError):
    """人物速查失败(DB 不可用 / SQL 异常)。"""


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """打开 SQLite 连接(只读,row_factory=Row 便于字段访问)"""
    path = db_path or DEFAULT_DB_PATH
    if not os.path.exists(path):
        raise LookupError(f"DB 文件不存在:{path}")
    try:
        # uri=True + mode=ro 强制只读,防误写
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise LookupError(f"DB 连接失败:{e}") from e
    conn.row_factory = sqlite3.Row
    return conn


def _role_order_sql() -> str:
    """构造 ORDER BY CASE 表达式,按 ROLE_PRIORITY 排序"""
    parts = [f"WHEN '{role}' THEN {pri}" for role, pri in ROLE_PRIORITY.items()]
    return "CASE f.role " + " ".join(parts) + f" ELSE {DEFAULT_ROLE_PRIORITY} END"


def search_figure(
    query: str,
    db_path: Optional[str] = None,
    *,
    exact_match: bool = False,
) -> List[Dict[str, Any]]:
    """人物速查底层函数(返回原始 row 列表,供 handler / 联调 / 单测复用)

    Args:
        query: 关键词(人物名 / 模糊字串)
        db_path: 可选,DB 路径(默认 data/history.db)
        exact_match: True → 走 = 精确匹配,False → 走 LIKE 模糊

    Returns:
        list of dict,字段:name/dynasty_name/birth_year/death_year/role/biography/achievements/evaluations

    Raises:
        LookupError: DB 不可用 / SQL 失败
    """
    if not query or not query.strip():
        return []
    keyword = query.strip()

    # 防 SQL 注入:对 LIKE 元字符做转义(% _ \)
    safe = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if exact_match:
        sql = (
            "SELECT f.id, f.name, f.birth_year, f.death_year, f.role, "
            "       f.biography, f.achievements, f.evaluations, "
            "       d.name AS dynasty_name "
            "FROM figures f "
            "LEFT JOIN dynasties d ON f.dynasty_id = d.id "
            "WHERE f.name = ? "
            f"ORDER BY {_role_order_sql()}, f.id "
            "LIMIT ?"
        )
        params: Tuple[Any, ...] = (keyword, MAX_RESULTS)
    else:
        sql = (
            "SELECT f.id, f.name, f.birth_year, f.death_year, f.role, "
            "       f.biography, f.achievements, f.evaluations, "
            "       d.name AS dynasty_name "
            "FROM figures f "
            "LEFT JOIN dynasties d ON f.dynasty_id = d.id "
            "WHERE f.name LIKE ? ESCAPE '\\' "
            f"ORDER BY {_role_order_sql()}, f.id "
            "LIMIT ?"
        )
        params = (f"%{safe}%", MAX_RESULTS)

    conn = _connect(db_path)
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    except sqlite3.Error as e:
        raise LookupError(f"SQL 执行失败:{e}") from e
    finally:
        conn.close()

    return [dict(r) for r in rows]


def _pick_suggestion(results: List[Dict[str, Any]], query: str) -> str:
    """无结果时给出候选建议(简单按人物名首字匹配推荐)"""
    if not results:
        return ""
    head = query.strip()[:1]
    matched = [r["name"] for r in results if r.get("name", "").startswith(head)]
    if matched:
        return f"试试:{', '.join(matched[:3])}"
    return ""


def handle(
    query: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """人物速查 handler(主入口,返回飞书消息卡 JSON dict)

    Args:
        query: 用户查询关键词
        db_path: 可选,DB 路径(便于单测注入)

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    if not query or not query.strip():
        return schema.no_result(query or "", suggestion="关键词不能为空")

    # 先尝试模糊,无结果再降级到 全表 模糊(避免完全漏命中)
    try:
        results = search_figure(query, db_path=db_path, exact_match=False)
    except LookupError as e:
        return schema.error_card(str(e))

    if not results:
        return schema.no_result(query.strip(), suggestion="")

    if len(results) == SINGLE_RESULT_THRESHOLD:
        return schema.figure_card(results[0])

    return schema.figure_candidate_list(results, query.strip())


# 命令路由(供后续 webhook.py 集成)
COMMANDS = {
    "人物": handle,
    "figure": handle,
    "lookup": handle,
    "查人物": handle,
    "谁": handle,  # 文本兜底:含"谁"
    "生平": handle,  # 文本兜底:含"生平"
    "简介": handle,  # 文本兜底:含"简介"
}


# 英文别名 → 中文命令(对外接口统一返回中文,英文只是输入别名)
_LOOKUP_ALIASES = {"人物", "figure", "lookup", "查人物"}


def parse_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    """从飞书消息文本解析出 (命令, 参数)。

    约定:
      - 形如 `/历史 人物 秦始皇` / `/history figure 嬴政`
      - 形如 `秦始皇生平`(纯名字 + 兜底词)

    内部把英文别名 (`figure` / `lookup`) 统一映射到中文 `"人物"`,
    兜底也返回中文。对外接口(cmd 字段)统一为中文,业务层(webhook/handler)只比对中文。

    Returns:
        (command, query) 或 (None, None) 表示无法解析
    """
    if not text:
        return None, None
    text = text.strip()
    # /命令形式
    parts = text.split(maxsplit=2)
    if parts and parts[0].startswith("/"):
        cmd = parts[0].lstrip("/").lower()
        # 兼容 /历史 /history
        if cmd in ("历史", "history"):
            if len(parts) >= 3 and parts[1] in _LOOKUP_ALIASES:
                return "人物", parts[2]
            return None, None
        if cmd in _LOOKUP_ALIASES:
            return "人物", parts[1] if len(parts) >= 2 else ""
    # 兜底:含"谁/生平/简介"且长度 > 2
    for kw in ("谁", "生平", "简介"):
        if kw in text and len(text) > 2:
            return "人物", text.replace(kw, "").strip() or text
    return None, None


__all__ = [
    "COMMANDS",
    "DEFAULT_DB_PATH",
    "LookupError",
    "MAX_RESULTS",
    "ROLE_PRIORITY",
    "handle",
    "parse_command",
    "search_figure",
]

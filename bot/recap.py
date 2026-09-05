"""历史顾问飞书 Bot · 事件回顾流水线(D4 · 2026-09-04 落地)

Phase 0 第 6 项 / D4(5.5/6 → 5.6/6)。

功能:
  - 查 events 表(name LIKE 模糊)+ 外键回查 dynasties 朝代名
  - 关联史料:sources.dynasty_id = events.dynasty_id,按 credibility DESC 取 3 部
  - 多结果按 year 升序(时间最近优先)
  - 单结果 → bot.schema.event_card
  - 多结果(<=10) → bot.schema.event_candidate_list
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

# 关联史料最大返回数
MAX_RELATED_SOURCES = 3

# 单结果触发详情卡的最大候选阈值(超过则返回候选列表)
SINGLE_RESULT_THRESHOLD = 1


class RecapError(RuntimeError):
    """事件回顾失败(DB 不可用 / SQL 异常)。"""


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """打开 SQLite 连接(只读,row_factory=Row 便于字段访问)"""
    path = db_path or DEFAULT_DB_PATH
    if not os.path.exists(path):
        raise RecapError(f"DB 文件不存在:{path}")
    try:
        # uri=True + mode=ro 强制只读,防误写
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise RecapError(f"DB 连接失败:{e}") from e
    conn.row_factory = sqlite3.Row
    return conn


def search_event(
    query: str,
    db_path: Optional[str] = None,
    *,
    exact_match: bool = False,
) -> List[Dict[str, Any]]:
    """事件回顾底层函数(返回原始 row 列表,供 handler / 联调 / 单测复用)

    Args:
        query: 关键词(事件名 / 模糊字串)
        db_path: 可选,DB 路径(默认 data/history.db)
        exact_match: True → 走 = 精确匹配,False → 走 LIKE 模糊

    Returns:
        list of dict,字段:id/name/year/dynasty_id/dynasty_name/category/location/
        key_figures/summary/impact

    Raises:
        RecapError: DB 不可用 / SQL 失败
    """
    if not query or not query.strip():
        return []
    keyword = query.strip()

    # 防 SQL 注入:对 LIKE 元字符做转义(% _ \)
    safe = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if exact_match:
        sql = (
            "SELECT e.id, e.name, e.year, e.dynasty_id, e.category, e.location, "
            "       e.key_figures, e.summary, e.impact, "
            "       d.name AS dynasty_name "
            "FROM events e "
            "LEFT JOIN dynasties d ON e.dynasty_id = d.id "
            "WHERE e.name = ? "
            "ORDER BY e.year ASC, e.id "
            "LIMIT ?"
        )
        params: Tuple[Any, ...] = (keyword, MAX_RESULTS)
    else:
        sql = (
            "SELECT e.id, e.name, e.year, e.dynasty_id, e.category, e.location, "
            "       e.key_figures, e.summary, e.impact, "
            "       d.name AS dynasty_name "
            "FROM events e "
            "LEFT JOIN dynasties d ON e.dynasty_id = d.id "
            "WHERE e.name LIKE ? ESCAPE '\\' "
            "ORDER BY e.year ASC, e.id "
            "LIMIT ?"
        )
        params = (f"%{safe}%", MAX_RESULTS)

    conn = _connect(db_path)
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    except sqlite3.Error as e:
        raise RecapError(f"SQL 执行失败:{e}") from e
    finally:
        conn.close()

    return [dict(r) for r in rows]


def fetch_related_sources(
    dynasty_id: Optional[int],
    db_path: Optional[str] = None,
    *,
    limit: int = MAX_RELATED_SOURCES,
) -> List[Dict[str, Any]]:
    """按 dynasty_id 查关联史料(按 credibility DESC 排序)

    Args:
        dynasty_id: 事件对应的朝代 ID,可为 None(None 时返回空)
        db_path: 可选,DB 路径
        limit: 返回条数上限

    Returns:
        list of dict,字段:id/title/credibility/source_type
    """
    if dynasty_id is None:
        return []

    sql = (
        "SELECT id, title, credibility, source_type "
        "FROM sources "
        "WHERE dynasty_id = ? "
        "ORDER BY credibility DESC, id "
        "LIMIT ?"
    )
    conn = _connect(db_path)
    try:
        cur = conn.execute(sql, (dynasty_id, limit))
        rows = cur.fetchall()
    except sqlite3.Error as e:
        raise RecapError(f"SQL 执行失败:{e}") from e
    finally:
        conn.close()
    return [dict(r) for r in rows]


def handle(
    query: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """事件回顾 handler(主入口,返回飞书消息卡 JSON dict)

    Args:
        query: 用户查询关键词
        db_path: 可选,DB 路径(便于单测注入)

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    if not query or not query.strip():
        return schema.no_result(query or "", suggestion="关键词不能为空")

    try:
        results = search_event(query, db_path=db_path, exact_match=False)
    except RecapError as e:
        return schema.error_card(str(e))

    if not results:
        return schema.no_result(query.strip(), suggestion="")

    if len(results) == SINGLE_RESULT_THRESHOLD:
        # 单结果:再查关联史料(若 DB 异常则降级为无关联史料,不阻塞)
        try:
            sources = fetch_related_sources(
                results[0].get("dynasty_id"), db_path=db_path
            )
        except RecapError:
            sources = []
        return schema.event_card(results[0], related_sources=sources)

    # 多结果:候选列表不查关联史料(避免 N 次额外 IO)
    return schema.event_candidate_list(results, query.strip())


# 命令路由(供后续 webhook.py 集成)
COMMANDS = {
    "事件": handle,
    "event": handle,
    "recap": handle,
    "查事件": handle,
    "战役": handle,
    "变法": handle,
    "政变": handle,
}


# 英文别名 → 中文命令(对外接口统一返回中文,英文只是输入别名)
_RECAP_ALIASES = {"事件", "event", "recap", "查事件"}


def parse_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    """从飞书消息文本解析出 (命令, 参数)。

    约定:
      - 形如 `/历史 事件 赤壁之战` / `/history event 安史之乱`
      - 形如 `赤壁之战`(含"战役/变法/政变/事件"任一兜底词,事件名兜底)

    内部把英文别名 (`event` / `recap`) 统一映射到中文 `"事件"`,
    兜底也返回中文。对外接口(cmd 字段)统一为中文,业务层(webhook/handler)只比对中文。

    Returns:
        (command, query) 或 (None, None) 表示无法解析
    """
    if not text:
        return None, None
    text = text.strip()
    parts = text.split(maxsplit=2)
    if parts and parts[0].startswith("/"):
        cmd = parts[0].lstrip("/").lower()
        if cmd in ("历史", "history"):
            if len(parts) >= 3 and parts[1] in _RECAP_ALIASES:
                return "事件", parts[2]
            return None, None
        if cmd in _RECAP_ALIASES:
            return "事件", parts[1] if len(parts) >= 2 else ""
    # 兜底:含"之战/战役/变法/政变/事件"任一关键词且长度 > 1
    # "之战" 2 字也放行(赤壁之战 4 候选最常见关键词),"战役/变法" 等也是 2 字
    for kw in ("之战", "战役", "变法", "政变", "事件"):
        if kw in text and len(text) > 1:
            return "事件", text.replace(kw, "").strip() or text
    return None, None


__all__ = [
    "COMMANDS",
    "DEFAULT_DB_PATH",
    "MAX_RELATED_SOURCES",
    "MAX_RESULTS",
    "RecapError",
    "fetch_related_sources",
    "handle",
    "parse_command",
    "search_event",
]

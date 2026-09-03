"""历史顾问飞书 Bot · 飞书消息卡 JSON 模板(D2 补落地 · 2026-09-03;D4 扩 · 2026-09-04)

9/2 巡检漏掉 D2 schema 草稿入代码(只在 README 草案提及),9/3 与 D3 同步落。
9/4 D4 事件回顾流水线扩 2 个模板:event_card / event_candidate_list。

对外暴露 5 个 JSON 模板:
  - figure_card:人物速查单结果卡
  - figure_candidate_list:多结果候选列表卡
  - event_card:事件回顾单结果卡
  - event_candidate_list:多结果候选列表卡(按时间升序)
  - no_result:无结果友好提示

消息卡遵循飞书 interactive 卡片协议 v1(参考 https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-json-structure)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# 飞书消息卡 v1 schema
CARD_VERSION = "1.0"


def _header(title: str, subtitle: str = "") -> Dict[str, Any]:
    """飞书卡片 header 块(标题 + 副标题 + 主题色)"""
    return {
        "title": {"tag": "plain_text", "content": title},
        "subtitle": {"tag": "plain_text", "content": subtitle} if subtitle else None,
        "template": "blue",  # 历史顾问主色调
    }


def _field(name: str, value: str) -> Dict[str, Any]:
    """飞书卡片 field 块(短字段,key:value 二列)"""
    return {"is_short": True, "text": {"tag": "lark_md", "content": f"**{name}**:{value}"}}


def _divider() -> Dict[str, Any]:
    return {"tag": "hr"}


def _note(content: str) -> Dict[str, Any]:
    """飞书卡片 note 块(底部备注,灰字)"""
    return {"tag": "note", "elements": [{"tag": "plain_text", "content": content}]}


def figure_card(figure: Dict[str, Any]) -> Dict[str, Any]:
    """人物速查单结果卡

    Args:
        figure: dict,字段:
            - name(str) 姓名 必填
            - dynasty_name(str|None) 朝代名
            - birth_year(int|None) 生年(负数表公元前)
            - death_year(int|None) 卒年
            - role(str|None) 角色(帝王/名臣/思想家/名将)
            - biography(str|None) 生平
            - achievements(str|None) 成就
            - evaluations(str|None) 评价

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    name = figure.get("name", "未知人物")
    dynasty = figure.get("dynasty_name") or "未详"
    role = figure.get("role") or "未详"
    birth = figure.get("birth_year")
    death = figure.get("death_year")
    life = _format_years(birth, death)

    fields: List[Dict[str, Any]] = [
        _field("朝代", dynasty),
        _field("角色", role),
        _field("生卒", life),
    ]

    elements: List[Dict[str, Any]] = [dict(_field("朝代", dynasty), **{"is_short": True})]
    # 用 lark_md 排版:每段标题 + 内容
    elements = [{"tag": "div", "fields": fields}]

    for label, key in [("生平", "biography"), ("成就", "achievements"), ("评价", "evaluations")]:
        content = (figure.get(key) or "").strip()
        if not content:
            continue
        elements.append(_divider())
        # 飞书 lark_md 单段限长 4000 字,简单截断
        snippet = content if len(content) <= 1500 else content[:1500] + "…"
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{label}**\n{snippet}",
                },
            }
        )

    elements.append(_note("数据来源:data/history.db · figures + dynasties 外键回查"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"📜 {name}", subtitle=f"{dynasty} · {role}"),
        "elements": elements,
    }


def figure_candidate_list(candidates: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """人物速查多结果候选列表卡(按 role 优先级排序后)

    Args:
        candidates: list of dict,每个含 name/dynasty_name/role/birth_year/death_year
        query: str,用户查询关键词(用于回显)

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    elements: List[Dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"关键词 **{query}** 命中 **{len(candidates)}** 位人物,请选择目标(按角色优先级排序)",
            },
        },
        _divider(),
    ]
    for idx, c in enumerate(candidates, start=1):
        name = c.get("name", "?")
        dynasty = c.get("dynasty_name") or "未详"
        role = c.get("role") or "未详"
        life = _format_years(c.get("birth_year"), c.get("death_year"))
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{idx}. {name}** · {dynasty} · {role} · {life}",
                },
            }
        )
    elements.append(_note("提示:回复「编号 N」可展开详情(联调 webhook 后生效)"))
    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"🔍 命中 {len(candidates)} 位人物", subtitle=f"关键词:{query}"),
        "elements": elements,
    }


def no_result(query: str, suggestion: str = "") -> Dict[str, Any]:
    """无结果友好提示卡"""
    msg = f"未收录 **{query}** 相关的历史人物。\n\n可尝试:换关键词 / 加朝代限定 / 简繁体切换"
    if suggestion:
        msg += f"\n\n建议:{suggestion}"
    return {
        "config": {"wide_screen_mode": True},
        "header": _header("🤔 未找到结果", subtitle="试试更宽的关键词"),
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": msg},
            },
            _note("数据来源:data/history.db · 当前 32 位核心人物(帝王 18 / 名臣 6 / 思想家 7 / 名将 1)"),
        ],
    }


def event_card(event: Dict[str, Any], related_sources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """事件回顾单结果卡

    Args:
        event: dict,字段:
            - name(str) 事件名 必填
            - dynasty_name(str|None) 朝代名
            - year(int|None) 发生年(负数表公元前)
            - category(str|None) 类别(战争/变法/政变/制度/文化/条约/起义)
            - location(str|None) 地点
            - key_figures(list[str]|None) 关键人物
            - summary(str|None) 摘要
            - impact(str|None) 影响
        related_sources: 可选,list of dict,字段 title/credibility

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    name = event.get("name", "未知事件")
    dynasty = event.get("dynasty_name") or "未详"
    category = event.get("category") or "未详"
    year = _format_year(event.get("year"))
    location = event.get("location") or "未详"

    key_figures_raw = event.get("key_figures")
    key_figures: List[str] = []
    if isinstance(key_figures_raw, str):
        try:
            import json
            key_figures = json.loads(key_figures_raw)
        except Exception:
            key_figures = [s.strip() for s in key_figures_raw.split(",") if s.strip()]
    elif isinstance(key_figures_raw, list):
        key_figures = [str(x) for x in key_figures_raw]

    fields: List[Dict[str, Any]] = [
        _field("朝代", dynasty),
        _field("类别", category),
        _field("年份", year),
        _field("地点", location),
    ]
    elements: List[Dict[str, Any]] = [{"tag": "div", "fields": fields}]

    if key_figures:
        kf_str = "、".join(key_figures[:8]) + ("…" if len(key_figures) > 8 else "")
        elements.append(_divider())
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**关键人物**\n{kf_str}",
                },
            }
        )

    for label, key in [("摘要", "summary"), ("影响", "impact")]:
        content = (event.get(key) or "").strip()
        if not content:
            continue
        elements.append(_divider())
        snippet = content if len(content) <= 1500 else content[:1500] + "…"
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{label}**\n{snippet}",
                },
            }
        )

    if related_sources:
        elements.append(_divider())
        lines = []
        for s in related_sources[:3]:
            title = s.get("title", "?")
            cred = s.get("credibility")
            cred_str = f" · {cred}★" if cred is not None else ""
            lines.append(f"• {title}{cred_str}")
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**关联史料**\n" + "\n".join(lines),
                },
            }
        )
    else:
        elements.append(_divider())
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**关联史料**\n暂无对应朝代直接关联的史料,可查询同朝代其他事件",
                },
            }
        )

    elements.append(_note("数据来源:data/history.db · events + dynasties + sources 三表外键关联"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"⚔️ {name}", subtitle=f"{dynasty} · {category} · {year}"),
        "elements": elements,
    }


def event_candidate_list(candidates: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """事件回顾多结果候选列表卡(按 year 升序,时间最近优先)

    Args:
        candidates: list of dict,每个含 name/dynasty_name/year/category
        query: str,用户查询关键词(用于回显)

    Returns:
        飞书 interactive 卡片 JSON dict
    """
    elements: List[Dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"关键词 **{query}** 命中 **{len(candidates)}** 个事件,按时间升序(近期在前)",
            },
        },
        _divider(),
    ]
    for idx, c in enumerate(candidates, start=1):
        name = c.get("name", "?")
        dynasty = c.get("dynasty_name") or "未详"
        category = c.get("category") or "未详"
        year = _format_year(c.get("year"))
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{idx}. {name}** · {dynasty} · {category} · {year}",
                },
            }
        )
    elements.append(_note("提示:回复「编号 N」可展开详情(联调 webhook 后生效)"))
    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"🔍 命中 {len(candidates)} 个事件", subtitle=f"关键词:{query}"),
        "elements": elements,
    }


def error_card(err: str) -> Dict[str, Any]:
    """DB 不可用等系统错误兜底卡"""
    return {
        "config": {"wide_screen_mode": True},
        "header": _header("⚠️ 暂时无法查询", subtitle="数据库连接失败"),
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**错误信息**\n{err}"},
            },
            _note("T1 cron 会同步检查 data/history.db 健康度,稍后重试"),
        ],
    }


def _format_years(birth: Any, death: Any) -> str:
    """格式化生卒年(公元前用 - 前缀,如 -259/-210)"""
    if birth is None and death is None:
        return "未详"

    def fmt(y: Any) -> str:
        if y is None:
            return "?"
        y = int(y)
        return f"公元前 {-y}" if y < 0 else f"{y}"

    return f"{fmt(birth)} – {fmt(death)}"


def _format_year(year: Any) -> str:
    """格式化单年份(公元前用 - 前缀)"""
    if year is None:
        return "未详"
    try:
        y = int(year)
    except (TypeError, ValueError):
        return str(year)
    return f"公元前 {-y}" if y < 0 else f"{y}"


__all__ = [
    "CARD_VERSION",
    "figure_card",
    "figure_candidate_list",
    "event_card",
    "event_candidate_list",
    "no_result",
    "error_card",
]

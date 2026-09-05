"""bot/lookup.py 单测(D5 · 2026-09-05 落地)

Phase 0 第 6 项 D5 单测,覆盖 4 场景:
  1. SQL 注入(防 LIKE 元字符绕过)
  2. 单结果(秦始皇)
  3. 多结果(之战 - 4 候选)
  4. 无结果(火星大战)

运行:
  python -m bot.tests.test_lookup
  或:python -m unittest bot.tests.test_lookup
"""
from __future__ import annotations

import os
import sys
import unittest

# 确保 bot 包可被 import(直接 python -m 也可)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bot import lookup  # noqa: E402
from bot import schema  # noqa: E402

DB_PATH = os.path.join(_ROOT, "data", "history.db")


def _has_db() -> bool:
    return os.path.exists(DB_PATH)


@unittest.skipUnless(_has_db(), f"DB 缺失:{DB_PATH}")
class LookupSqlInjectionTest(unittest.TestCase):
    """SQL 注入防御:特殊元字符 + OR 1=1 攻击向量。"""

    def test_or_injection_returns_zero(self):
        """经典 OR 注入 → 应返回 0 行(走参数化 + LIKE 转义)"""
        results = lookup.search_figure("' OR 1=1 --", db_path=DB_PATH)
        self.assertEqual(results, [], f"OR 注入应 0 行,实际 {len(results)}")

    def test_like_wildcard_injection(self):
        """LIKE 元字符注入(%)→ 应只匹配字面量 % 字符,不应全表扫"""
        results = lookup.search_figure("%", db_path=DB_PATH)
        # 转义后 % 字面量无匹配,应为 0
        self.assertEqual(results, [])

    def test_handle_injection_returns_card(self):
        """handle() 注入 → 应返回 no_result 卡(0 行)"""
        card = lookup.handle("' OR 1=1 --", db_path=DB_PATH)
        header = (card.get("header") or {})
        title = (header.get("title") or {}).get("content", "")
        self.assertIn("未", title, f"无结果卡应含'未'字,实际 title={title}")


@unittest.skipUnless(_has_db(), f"DB 缺失:{DB_PATH}")
class LookupSingleResultTest(unittest.TestCase):
    """单结果:秦始皇 → figure_card(8 字段:姓名/朝代/生卒/角色/生平/成就/评价)。"""

    def test_search_returns_qinshihuang(self):
        results = lookup.search_figure("秦始皇", db_path=DB_PATH)
        self.assertEqual(len(results), 1, f"应 1 行,实际 {len(results)}")
        r = results[0]
        # DB 存的是"秦始皇嬴政"(名+字 合并存)
        self.assertEqual(r["name"], "秦始皇嬴政")
        self.assertEqual(r["role"], "帝王")
        self.assertIn("秦", r["dynasty_name"])

    def test_handle_returns_figure_card(self):
        card = lookup.handle("秦始皇", db_path=DB_PATH)
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        self.assertIn("秦始皇", title)
        # 飞书卡必有 elements 列表
        self.assertIn("elements", card)
        self.assertGreater(len(card["elements"]), 0)


@unittest.skipUnless(_has_db(), f"DB 缺失:{DB_PATH}")
class LookupMultiResultTest(unittest.TestCase):
    """多结果:用 '帝' 查人物表(汉/晋/隋 多帝王),候选列表卡。"""

    def test_search_returns_multiple(self):
        # "之战" 在事件表(不是人物表),人物表用 "帝" 应多结果
        results = lookup.search_figure("帝", db_path=DB_PATH)
        self.assertGreater(len(results), 1, f"应多结果,实际 {len(results)}")

    def test_handle_returns_candidate_list(self):
        card = lookup.handle("帝", db_path=DB_PATH)
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        # schema 候选列表标题是 "命中 N 个..."
        self.assertIn("命中", title)
        # 候选列表必有 elements + 至少 2 个 element
        self.assertIn("elements", card)
        elements = card["elements"]
        self.assertGreaterEqual(len(elements), 2)


@unittest.skipUnless(_has_db(), f"DB 缺失:{DB_PATH}")
class LookupNoResultTest(unittest.TestCase):
    """无结果:火星大战 → no_result 卡。"""

    def test_search_returns_empty(self):
        results = lookup.search_figure("火星大战", db_path=DB_PATH)
        self.assertEqual(results, [])

    def test_handle_returns_no_result(self):
        card = lookup.handle("火星大战", db_path=DB_PATH)
        header = card.get("header", {}) or {}
        title = (header.get("title") or {}).get("content", "")
        self.assertTrue("未" in title or "无" in title, f"无结果标题应含'未'/'无',实际 {title}")


class LookupParseCommandTest(unittest.TestCase):
    """命令解析:无需 DB,纯字符串测试。"""

    def test_slash_form(self):
        self.assertEqual(lookup.parse_command("/历史 人物 秦始皇"), ("人物", "秦始皇"))
        self.assertEqual(lookup.parse_command("/history figure 嬴政"), ("人物", "嬴政"))
        self.assertEqual(lookup.parse_command("/人物 苏东坡"), ("人物", "苏东坡"))

    def test_fallback_keyword(self):
        # 含"谁"兜底(对外接口统一为中文)
        cmd, q = lookup.parse_command("秦始皇谁")
        self.assertEqual(cmd, "人物")
        self.assertIn("秦始皇", q)

    def test_no_match(self):
        self.assertEqual(lookup.parse_command(""), (None, None))
        self.assertEqual(lookup.parse_command("今天天气不错"), (None, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)

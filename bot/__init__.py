"""历史顾问飞书 Bot 模块 · Phase 0 第 6 项(2026-09-01 启动)

5 工作日倒计时:
- D1(9/1) 骨架:本 __init__.py + README.md ✅
- D2(9/2) schema:schema.py(命令路由 + 飞书消息卡 JSON 模板) ✅(9/3 补落地)
- D3(9/3) lookup:bot/lookup.py 人物速查流水线 ✅
- D4(9/4) recap:bot/recap.py 事件回顾流水线 ✅
- D5(9/5) webhook:bot/webhook.py 飞书事件订阅 + tests/ 单测 + run_e2e.py 联调 ✅
- D6(9/6) 收口:Phase 0 6/6 + 项目开发计划.md checkbox 更新 + parse_command 中文化 ✅

数据源:`data/history.db`(4 表 13 索引:dynasties 20 + figures 32 + events 60 + sources 25)

模块导出:
- bot.schema:飞书消息卡 JSON 模板(figure_card / event_card / candidate_list / no_result / error_card)
- bot.lookup:人物速查流水线(search_figure / handle / parse_command)
- bot.recap:事件回顾流水线(search_event / fetch_related_sources / handle / parse_command)
- bot.webhook:飞书事件订阅入口(handle_event / route_command / run_server)
"""

from . import schema
from . import lookup
from . import recap
from . import webhook

__version__ = "0.1.5"
__phase__ = "Phase 0 / Item 6 · D5 done (D6 收口在 9/6 commit)"
__started__ = "2026-09-01"

__all__ = ["schema", "lookup", "recap", "webhook"]

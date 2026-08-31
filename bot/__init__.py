"""历史顾问飞书 Bot 模块 · Phase 0 第 6 项(2026-09-01 启动)

5 工作日倒计时:
- D1(9/1) 骨架:本 __init__.py + README.md
- D2(9/2) schema:schema.py(命令路由 + 飞书消息卡 JSON 模板)
- D3(9/3) lookup:bot/lookup.py 人物速查流水线
- D4(9/4) recap:bot/recap.py 事件回顾流水线
- D5(9/5) webhook:bot/webhook.py 飞书事件订阅 + e2e 测试
- D6(9/6) 收口:Phase 0 6/6 + 项目开发计划.md checkbox 更新

数据源:`data/history.db`(4 表 13 索引:dynasties 20 + figures 32 + events 60 + sources 25)
"""

__version__ = "0.1.0"
__phase__ = "Phase 0 / Item 6"
__started__ = "2026-09-01"

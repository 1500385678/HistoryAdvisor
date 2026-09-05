# 飞书 Bot 模块 · 历史顾问

> Phase 0 第 6 项 · 启动日 2026-09-01 · 5 工作日倒计时收口 2026-09-06

## 一、目标

把 `data/history.db` 4 表 13 索引(dynasties 20 + figures 32 + events 60 + sources 25)通过飞书 Bot 暴露给用户,跑通"人物速查 + 事件回顾"两条流水线,完成 Phase 0 6/6 收口。

## 二、目录结构

```
bot/
├── __init__.py     # 模块入口(版本 + 阶段标识)
├── README.md       # 本文件
├── schema.py       # [D2] 命令 → handler 路由 + 飞书消息卡 JSON 模板
├── lookup.py       # [D3] 人物速查流水线(查 figures + 外键回查 dynasties)
├── recap.py        # [D4] 事件回顾流水线(查 events + 外键回查 sources)
├── webhook.py      # [D5] 飞书事件订阅入口 + e2e 联调
└── tests/
    ├── test_lookup.py  # [D5] 人物速查单测
    └── test_recap.py   # [D5] 事件回顾单测
```

## 三、两条流水线 schema(草案)

### 3.1 人物速查 `lookup`

**触发命令**:
- `/历史 人物 秦始皇`(私聊 / 群消息)
- `/history figure 嬴政`
- 文本兜底:含"谁" / "生平" / "简介" + 人物名

**处理流程**:
1. 模糊匹配 `figures.name LIKE '%query%'`
2. 外键回查 `dynasties.name` 朝代名
3. 多结果按 `role` 优先级排序(帝王 > 名臣 > 思想家 > 名将)
4. 单结果 → 飞书 `interactive` 消息卡(姓名 / 朝代 / 生卒 / 角色 / 生平 / 成就 / 评价)
5. 多结果 → 候选列表卡(点击展开详情)
6. 无结果 → 友好提示"未收录,试换关键词或朝代"

**SQL 草案**:
```sql
SELECT f.id, f.name, f.birth_year, f.death_year, f.role,
       f.biography, f.achievements, f.evaluations,
       d.name AS dynasty_name
FROM figures f
LEFT JOIN dynasties d ON f.dynasty_id = d.id
WHERE f.name LIKE ?
ORDER BY CASE f.role
  WHEN '帝王' THEN 1
  WHEN '名臣' THEN 2
  WHEN '思想家' THEN 3
  WHEN '名将' THEN 4
  ELSE 5 END
LIMIT 10;
```

### 3.2 事件回顾 `recap`

**触发命令**:
- `/历史 事件 赤壁之战`
- `/history event 安史之乱`
- 文本兜底:含"战役" / "变法" / "政变" / "事件" + 事件名

**处理流程**:
1. 模糊匹配 `events.name LIKE '%query%'`
2. 外键回查 `dynasties.name` 朝代名
3. 关联史料:`sources.dynasty_id = events.dynasty_id`,按 `credibility DESC` 取 3 部
4. 多结果按 `year` 升序(时间最近优先)
5. 单结果 → 飞书 `interactive` 消息卡(事件名 / 朝代 / 年份 / 类别 / 地点 / 关键人物 / 摘要 / 影响 / 关联史料)
6. 多结果 → 候选列表卡(按时间排序)
7. 无结果 → 友好提示

**SQL 草案**:
```sql
-- 主查询
SELECT e.id, e.name, e.year, e.category, e.location, e.summary, e.impact,
       d.name AS dynasty_name
FROM events e
LEFT JOIN dynasties d ON e.dynasty_id = d.id
WHERE e.name LIKE ?
ORDER BY e.year ASC
LIMIT 10;

-- 关联史料
SELECT s.title, s.credibility
FROM sources s
WHERE s.dynasty_id = ?
ORDER BY s.credibility DESC
LIMIT 3;
```

## 四、5 工作日倒计时

| 日期 | 工作日 | 任务 | 产物 |
|------|--------|------|------|
| **9/1** | D1 | 骨架 | `__init__.py` + `README.md`(本文件) |
| **9/2** | D2 | schema | `schema.py`(命令路由 + 消息卡 JSON 模板) |
| **9/3** | D3 | 人物流水线 | `lookup.py` |
| **9/4** | D4 | 事件流水线 | `recap.py` |
| **9/5** | D5 | 联调 | `webhook.py` + `tests/test_lookup.py` + `tests/test_recap.py` + e2e |
| **9/6** | D6 | 收口 | Phase 0 6/6 + `项目开发计划.md` checkbox 更新 + release 草稿 |

## 五、约束

- **简洁可入库**:每个 D1-D5 落地 commit < 150 行新增代码
- **幂等**:handler 可被同一命令重复调用而不报错
- **错误处理**:无结果 / DB 不可用 / 网络超时均有友好提示
- **数据保护**:所有 SQL 走预编译参数化(`?` 占位符),防注入
- **9.3 铁律**:当日 `.plan/YYYYMMDD.md` 必须 T5 commit 后清

## 六、关联文档

- `项目开发计划.md` §五 Phase 0(本模块对应第 6 项"飞书 Bot 接入")
- `项目开发计划.md` §九 运维 5 步闭环(T1 消费巡检 R2/A 档)
- `.Log/巡检-历史-20260901.md` R2/A 档倒计时表
- `.plan/20260901.md` 5 工作日详细分工

## 七、变更记录

- **2026-09-01 03:30** D1 骨架:本目录 + `__init__.py` + `README.md`,Phase 0 第 6 项启动
- **2026-09-03 03:30** D2 补 schema.py(命令路由 + 飞书消息卡 3 模板)+ D3 lookup.py 人物速查流水线(查 figures + 外键回查 dynasties + 角色优先级排序)
- **2026-09-06 03:30** D6 收口:Phase 0 6/6 强制收口日,W2 末兑现。**(1) parse_command 中文化**:`lookup.parse_command` / `recap.parse_command` 对外接口统一返回中文 ("人物" / "事件"),英文别名 (`figure` / `lookup` / `event` / `recap`) 仅作输入别名;webhook 路由同步比对中文;`run_e2e.py` 命令断言同步。**(2) 单测 + e2e 全过 25 + 6 = 31 场景**:`bot/tests/test_lookup.py` + `bot/tests/test_recap.py` 共 25 单测全 pass(此前因 DB 路径 dirname 多算一级 + 测试期望与真实 DB 数据 / schema 标题文案不一致,9/5 落地 19 skip;9/6 修路径 + 5 处期望对齐);`bot/run_e2e.py` 6 场景(URL 校验 / 健康检查 / 人物速查 / 事件回顾 / 多结果 / 无结果)全 pass;recap 兜底词补 "之战" + `len > 2` 放宽 `> 1`,解决 "之战" 2 字被错路由到人物查询的 bug;e2e 多结果候选数 7(events 表 7 行含"之战")。**(3) `__init__.py` 升级 v0.1.4 → v0.1.5**:暴露 `webhook` 子模块,阶段标识改 "Phase 0 / Item 6 · D5 done";Phase 0 第 6 项全部 5/5 子项 ✅,W2 末 9/6 收口兑现。
- **2026-09-05 03:31** D5 webhook 联调 + 单测:**(1) `bot/webhook.py` 172 行**(URL 校验 GET + 消息接收 POST 路由 + 健康检查 + 零依赖 `http.server` + `ThreadingHTTPServer` 多线程 + `route_command` 统一入口 lookup 优先 recap 兜底 + `handle_event` 纯函数便于 e2e);**(2) `bot/tests/test_lookup.py` 134 行** + **`bot/tests/test_recap.py` 145 行**(各 5 个测试类:SQL 注入 / 单结果 / 多结果 / 无结果 / 命令解析,共 25 单测);**(3) `bot/tests/__init__.py` 空文件占位**;**(4) `bot/run_e2e.py` 176 行**(6 场景 HTTP 联调 = 4 个业务 + URL 校验 + 健康检查)。**注意**:9/5 落地时未跑 SQL 测试(测试模块 `__file__` 路径 dirname 多算一级导致 `_ROOT` 多一层 → DB 路径错 → 19 SQL 测试全 skip 仅 6 个 parse_command 测试跑通;9/6 收口时一并修复,详见 D6 节点)。D5 4 文件落地 24h+ 0 commit 触发 R7 W2 末 24h 收口冲刺(9/6 commit 时合入)。
- **2026-09-04 03:30** D4 事件回顾流水线:`recap.py` 落地 + `schema.py` 扩 2 模板(`event_card` / `event_candidate_list`)+ `__init__.py` 升级 v0.1.4。SQL 走预编译 LIKE 转义防注入;多结果按 `year ASC` 排序(近期在前);单结果额外查同朝代 `sources` 按 `credibility DESC` 取 3 部作关联史料;`赤壁之战` 冒烟测试通过,SQL 注入测试返回 0 行。

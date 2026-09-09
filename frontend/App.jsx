// 历史顾问 Web 前端 · W3 骨架(2026-09-09 T2 启动)
//
// 设计原则:
// - React 最小入口占位,W3 末 9/13 节点评估前不实际编译
// - 实际数据由 FastAPI /person/<id> / /event/<id> JSON 提供,前端不直接查 DB
// - 未来 W4 阶段:Vite + npm 编译 + 路由 + 状态管理 + 响应式样式
//
// 此文件当前仅作为目录骨架与 React 入口约定,留待 W4 实际接入。

import React from "react";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, -apple-system, sans-serif", padding: 24 }}>
      <h1>历史顾问 · Web 入口</h1>
      <p>W3 骨架 9/9 启动 + W4 朝代页 9/10 落地 · FastAPI 后端 + React 前端最小版本</p>
      <ul>
        <li>人物页:<a href="/person/1">/person/1</a>(秦始皇嬴政)</li>
        <li>事件页:<a href="/event/1">/event/1</a>(大禹治水)</li>
        <li>朝代页:<a href="/dynasty/4">/dynasty/4</a>(秦 · 9/10 新增)</li>
      </ul>
      <p style={{ color: "#666", fontSize: 14 }}>
        W4 演进:/dynasties 列表 + 状态管理 + 响应式 + 朝代切换 + 搜索框
      </p>
    </div>
  );
}

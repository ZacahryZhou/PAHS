# PAHS Dev Lab — 开发路线

本地开发测试页：`pah dev-ui` → 浏览器打开 `http://127.0.0.1:8765`，聊天式测试 + 实时架构进度。

---

## 目标

| 能力 | 说明 |
|------|------|
| 聊天界面 | 像 AI 对话一样发命令 |
| 实时进度 | 右侧显示 LangGraph / 架构跑到哪一层 |
| 阶段审核 | 网页点「通过」或输入修改意见 |
| 开发可见 | 可查看 `run_id`、ExecutionPlan、事件流 |

---

## Phase 1 — MVP 后端 ✅ 本迭代

- [x] `FastAPI` + `uvicorn` 依赖
- [x] `POST /api/chat` — 后台线程启动 `start_run`
- [x] `GET /api/runs/{id}` — Run 状态
- [x] `GET /api/runs/{id}/events/stream` — SSE 推送 `run_events`
- [x] `POST /api/runs/{id}/reply` — `resume_run`（阶段审核）
- [x] `pah dev-ui` CLI 命令

## Phase 2 — 架构进度面板 ✅ 本迭代

- [x] `architecture_map.py` — `event_type` → LangGraph 节点
- [x] `GET /api/runs/{id}/progress` — 节点状态 JSON
- [x] 前端右侧固定架构图 + 高亮（pending / active / done / waiting）

## Phase 3 — 聊天体验 ✅ 本迭代

- [x] 单页 `static/index.html` — 左聊天右进度
- [x] 流式事件更新进度条
- [x] 等待审核时显示输入框 + 通过按钮

## Phase 4 — 开发增强（下一步）

- [ ] `GET /api/runs/{id}/plan` — 展开 ExecutionPlan JSON
- [ ] 显示 Search Router 决策、artifacts
- [ ] Path B 开关（模拟 Telegram 直达 SMAS/PIP）
- [ ] 在 graph 节点补 `log_event`（更细粒度）

## Phase 5 — 打磨（下一步）

- [ ] 多 Run 历史列表
- [ ] 深色/浅色主题
- [ ] WebSocket 替代 SSE 轮询（可选）
- [ ] 与 Telegram 共用同一 gateway 层

---

## 使用

```bash
pah init-db
pah dev-ui
# 浏览器打开 http://127.0.0.1:8765
```

---

## 文件结构

```text
src/pahs/devlab/
├── __init__.py
├── architecture_map.py   # 事件 → 架构节点
├── run_manager.py        # 后台 Run + 状态
├── server.py             # FastAPI
└── static/
    └── index.html        # Dev Lab UI
```

# PAHS 架构流程图

> Orchestrator 中枢 + 分步计划 + Harness 团队执行 + Learner 复盘  
> 打分机制（Triage Step Router / Search Router 调参）在整体架构就绪后最后统一修改。

---

## 总览

```mermaid
flowchart TB
    subgraph Input["用户入口"]
        U[用户输入]
        TG[Telegram 直连]
        CLI[pah run / CLI]
    end

    subgraph Orchestrator["Layer 1 — Orchestrator 发令"]
        T[Triage 粗分类<br/>暂保留原逻辑]
        OP[Orchestrator Planner<br/>LLM 写 ExecutionPlan]
        PV[Plan Validate<br/>Step Router 结构校验]
        STORE[(plan_json 存储<br/>不默认展示给用户)]
    end

    subgraph Harness["Layer 2 — Harness 团队执行"]
        GR[Global Rules]
        TR[Target Rules / Tools]
        ENV[Env + Budget 预检]
        EP[Execute Plan Phase<br/>按阶段执行]
        VF[Verify Pipeline]
        MR[Milestone Review]
    end

    subgraph Agents["专员 Agents"]
        SR[Searcher<br/>+ Search Router]
        CR[Creator]
        EX[Executor]
        EXT[SMAS / PIP External]
    end

    subgraph SubRoute["Layer 3 — 子路由"]
        SROUT[Search Router<br/>Tavily / Perplexity<br/>五维打分 ✅]
    end

    subgraph Learn["Layer 4 — Learner 复盘"]
        FB[用户反馈]
        LR[Learner 分析]
        RULES[rules / standards]
        PAT[plan_patterns]
    end

    U --> TG
    U --> CLI
    CLI --> GR
    TG -.->|未来统一| OP
    GR --> T --> OP --> PV --> STORE
    PV --> ENV --> TR --> EP
    EP --> SR & CR & EX & EXT
    SR --> SROUT
    EP --> VF
    VF -->|通过| MR
    VF -->|失败| EP
    MR -->|下一阶段| ENV
    MR -->|最终| FB
    FB --> LR --> RULES & PAT
    PAT -.->|下次优化计划| OP
    RULES -.->|下次优化执行| EP
```

---

## ExecutionPlan 结构

```mermaid
flowchart LR
    subgraph Plan["ExecutionPlan 任务表"]
        P1[Phase 1<br/>parallel=true]
        P2[Phase 2]
        P3[Phase 3]
    end

    subgraph P1T["Phase 1 Tasks"]
        T1[Searcher t1]
        T2[Searcher t2]
    end

    subgraph P2T["Phase 2 Tasks"]
        T3[Creator t3<br/>inputs_from: t1,t2]
    end

    subgraph P3T["Phase 3 Tasks"]
        T4[SMAS t4<br/>inputs_from: t3]
    end

    P1 --> P1T
    P2 --> P2T
    P3 --> P3T
    P1 -->|depends_on| P2 --> P3

    T1 & T2 -->|artifacts| T3 -->|artifacts| T4
```

---

## 单次 `pah run` 时序

```mermaid
sequenceDiagram
    participant User
    participant Graph as LangGraph
    participant Orch as Orchestrator
    participant Plan as ExecutionPlan
    participant Team as Phase Executor
    participant Agent as Worker Agents
    participant Harness
    participant Learner

    User->>Graph: 输入命令
    Graph->>Orch: triage + plan_with_llm
    Orch->>Plan: 生成 phases/tasks
    Plan-->>Graph: 存入 plan_json
    Graph->>Harness: validate + env + rules

    loop 每个 Phase
        Graph->>Team: execute_plan_phase
        alt parallel=true
            Team->>Agent: 多 task 共行
        else sequential
            Team->>Agent: 顺序 task
        end
        Agent-->>Team: artifacts
        Team->>Harness: verify
        Harness->>User: milestone review（可选）
        User-->>Graph: approved / 修改
    end

    Graph->>User: 最终交付
    User->>Learner: 总反馈
    Learner->>Plan: 优化 plan_patterns（下次）
```

---

## 两套机制触发时机（打分最后改）

| 机制 | 何时触发 | 当前状态 |
|------|----------|----------|
| **Triage** | 每次 run 开头，给 Orchestrator 上下文 | 原逻辑保留，打分待最后改 |
| **Step Router** | Orchestrator 出 plan 后，结构校验 | ✅ 仅校验，无打分 |
| **Search Router** | Searcher task 执行时 | ✅ 五维打分已完成 |

---

## 关键 CLI

```bash
pah plan-preview "你的命令"        # 看内部任务表（不执行）
pah route-preview "你的命令"         # 看 Triage 路由（打分待改）
pah search-route-preview "查询"    # 看 Search 子路由
pah run "你的命令"                 # 完整团队执行
```

---

## 代码地图

| 模块 | 路径 |
|------|------|
| ExecutionPlan schema | `src/pahs/planning/schema.py` |
| 能力清单 | `src/pahs/planning/capability_catalog.py` |
| Orchestrator Planner | `src/pahs/planning/orchestrator_planner.py` |
| Step Router 校验 | `src/pahs/planning/step_router.py` |
| Phase 执行器 | `src/pahs/planning/plan_executor.py` |
| Graph 节点 | `src/pahs/agents/plan_nodes.py` |
| LangGraph 编排 | `src/pahs/graph/main.py` |
| Search Router | `src/pahs/agents/search_router.py` |
| Learner 计划学习 | `src/pahs/learning/learner.py` |
| 计划模式库 | `standards/learned/plan_patterns/` |

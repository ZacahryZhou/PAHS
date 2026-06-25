# PAHS 深度学习教程（详细版）

**给 Zachary Zhou 的自学用书 — 不是清单，是逐段解释**

| 项目 | 说明 |
|------|------|
| 项目路径 | `~/Desktop/PAHS` |
| 配套项目 | SMAS `~/Desktop/SMAS`、PIP `~/Desktop/PIP` |
| 版本 | 2026-06 详细版 v2 |
| 怎么用 | 按章顺序读；每章末尾做「动手」和「自测」 |

---

## 写在前面：这份教程和上一份有什么不同

上一份手册像「地图」——告诉你有什么山、什么河。  
**这一份像「导游讲解」**——带你一步一步走，解释路上每一块石头是什么、为什么放在这里。

学习时请记住你大哥（Sam）的那句话应该怎么理解：

- **要学**：这套系统**能稳定做到哪一步**、**为什么这样设计**、**坏了怎么查**
- **不必主攻**：从零默写每一行 Python 语法
- **但必须能**：合上电脑，用自己的话讲清楚「用户发一句话后发生了什么」

---

# 第一章 · 这个项目到底是什么（建立心智模型）

## 1.1 用一句话定义 PAHS

**PAHS（Personal Agent Harness System）= 你的私人 AI 总调度台。**

它不像 ChatGPT 网页那样「你问一句它答一句」就结束。它更像一个**项目经理**：

1. 听懂你要什么（Telegram / CLI）
2. 判断这事该谁干（自己写？搜索？调 SMAS 做图？调 PIP 做视频？）
3. 盯着干完（调用工具、检查输出）
4. 把结果给你看，**等你点头**（重要内容必须人审）
5. （可选）记住你的偏好，下次做得更好

## 1.2 三个项目的关系（一定要记牢）

很多人第一次学时会晕：**PAHS、SMAS、PIP 到底是三个东西还是一个？**

| 项目 | 比喻 | 技术角色 |
|------|------|----------|
| **PAHS** | 公司前台 + 项目经理 | 接需求、路由、记账、审核、学习 |
| **SMAS** | 设计部（专做 IG 图文） | 独立 Python 项目，有自己的 AI 流水线 |
| **PIP** | 视频部（专做短视频） | 同上 |

PAHS **不代替** SMAS 生成图片。PAHS 只做一件事：**用 subprocess 调用 `~/Desktop/SMAS/scripts/smas.sh generate "你的需求"`，然后把结果转成 Telegram 能发的图片和文字。**

这叫 **External Agent Bridge（外部工具桥接）**。好处是：

- SMAS 可以单独开发、单独测试
- 以后加「建站工具」「发邮件工具」只需改 `config/external_agents.yaml`
- PAHS 主控代码保持薄

## 1.3 你日常用的路径 vs 课本里的路径

你现在 Telegram 上主要走的是 **「直调路径」**：

```
Telegram 消息 → PAHS 认意图 → 直接调 SMAS → 回图
```

PAHS 代码里还有一条 **「LangGraph 全流程」**（`pah run "..."`）：

```
命令 → 分流 Triage → 编排计划 → Creator/Searcher 干活 → 多轮审核 → 结束反馈 → Learner
```

**为什么要两条？**

- **直调**：快、像真人助理，适合「给咖啡店做 IG」这种单一任务
- **全流程**：复杂、可暂停恢复，适合调研、写长文、写代码、多里程碑

学习时两条都要懂。你现在的产品体验靠直调；你 co-op 简历和系统完整度靠 LangGraph。

---

# 第二章 · 实战走读：一条 Telegram 消息的完整一生

这一章是最核心的。请对着代码读。

**假设你在 Telegram 对 bot 说：**

> 给咖啡店做一条开业 IG 图文

---

## 2.1 第一步：终端里谁在监听？

你运行：

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate
pah telegram
```

`pah telegram` 调用 `telegram_adapter.py` 里的 `run_telegram_bot()`，内部是：

```python
app.run_polling()
```

**polling 的意思**：Python 进程每隔一小段时间问 Telegram 服务器：「有新消息吗？」  
所以终端「停住不动」= **正常**，不是卡死。这个进程必须一直开着，bot 才在线。

**学习点**：任何「聊天机器人」都需要一个**常驻进程**。以后上云，就是把这段跑在 VPS/Fly.io 上，而不是你笔记本上。

---

## 2.2 第二步：Telegram 把消息交给谁？

文件：`src/pahs/gateway/telegram_adapter.py`

```python
async def on_message(update, context):
    await _process_message(update, raw_text=update.message.text)
```

`_process_message` 做三件事：

### （1）取出 chat_id

```python
chat_id = str(update.effective_chat.id)
```

这是 Telegram 给你的对话唯一 ID。以后「这个聊天是否在等 SMAS 审核」就靠它查 session。

### （2）规范化用户输入

```python
normalized = normalize_telegram_input(raw_text)
```

`persona.py` 里：如果你发 `/generate 咖啡店开业`，会转成 `做一条 IG 图文：咖啡店开业`。  
目的是让后面路由规则更简单。

### （3）如果像是要调工具，先回一句「人话」

```python
tool = infer_external_agent(normalized)
if tool is not None:
    await update.message.reply_text(friendly_working(tool.name))
    # → "好，我先帮你做 IG 图文，可能要一两分钟，稍等～"
```

**产品细节**：先回一句，用户不会以为 bot 死了。生成可能要 1–3 分钟（要调 DeepSeek、fal 生图）。

### （4）交给统一大脑

```python
payload = handle_inbound_text(
    normalized,
    channel="telegram",
    channel_user_id=chat_id,
    normalized=True,
)
```

**学习点**：Telegram 适配器很薄。真正逻辑在 `service.py` 的 `handle_inbound_text`——这样以后加 WhatsApp 不用重写业务。

---

## 2.3 第三步：`handle_inbound_text` 怎么决策？

文件：`src/pahs/gateway/service.py`

函数按 **优先级从上到下** 判断（这段顺序极其重要）：

### 判断 1：是不是 `reply run_xxx ...` ？

CLI 跨渠道审核会用。Telegram 直调模式你一般不用。

### 判断 2：是不是查 `pending` / `status` ？

运维命令。

### 判断 3：Telegram 直调模式（你现在的主路径）

```python
if channel == "telegram" and _telegram_direct_tools():
```

读 `config/gateway.yaml`：

```yaml
telegram_direct_tools: true
```

#### 3a. 你是不是在回复上一张预览图？

```python
if is_smas_review_reply(stripped) and get_session(channel_user_id):
    return execute_smas_review(...)
```

`telegram_session.py` 里，`好` / `ok` / `改：字大一点` 会识别为审核回复。  
但**只有** `data/telegram_sessions.json` 里记录「这个 chat 正在等 SMAS 审核」时才生效。

#### 3b. 是不是新任务，要调外部工具？

```python
tool = infer_external_agent(stripped)
if tool is not None:
    return execute_direct_tool(tool.name, stripped, ...)
```

「给咖啡店做开业 IG」→ 命中 `smas`（下一章细讲）。

### 判断 4：是不是 `run ...` 或 `@smas` 显式命令？

走 LangGraph `start_run`。

### 判断 5：闲聊

```python
return _handle_telegram_chat(stripped)
```

先匹配 `quick_reply`（「在吗」「看得到吗」），否则调 DeepSeek 用 `PAHS_PERSONA_SYSTEM` 人格回复。

---

## 2.4 第四步：意图路由——为什么知道要调 SMAS？

文件：`src/pahs/gateway/intent_router.py`

```python
def infer_external_agent(text: str) -> ExternalAgentSpec | None:
```

两层匹配：

**第一层：显式前缀**（`registry.py` 的 `match_external_agent`）

- `@smas 做图`
- `smas: 做图`

**第二层：自然语言关键词**（`INTENT_RULES`）

```python
("smas", ["instagram", "ins post", "发帖", "图文", "做一条图文", ...])
```

你的句子「给咖啡店做一条开业 **IG 图文**」——  
注意：`IG` 单独不在列表里，但 **「图文」** 在。所以会返回 SMAS。

**如果路由失败会怎样？**  
`infer_external_agent` 返回 `None` → 不会调 SMAS → 掉进闲聊或 `friendly_help()`。  
**学习时的调试命令：**

```bash
pah route-preview "给咖啡店做一条开业 IG 图文"
```

---

## 2.5 第五步：`execute_direct_tool` 里发生什么？

文件：`src/pahs/gateway/direct_tools.py`

### 5.1 创建 run 记录

```python
run_id = new_run_id()   # 例如 run_20260624_153045_a3f2
db.create_run(run_id, prompt, channel="telegram", status="ACTIVE")
```

即使直调模式不走 LangGraph，**仍然记账**。以后查历史、接 Learner 都靠这个。

### 5.2 调用外部工具

```python
result = run_external_agent(agent_name, prompt, run_id=run_id)
```

`runner.py` 根据 type 分发到 `run_smas()` 或 `run_pip()`。

### 5.3 格式化交付内容

SMAS 专用：

```python
delivery_text, image_path = _format_smas_delivery(result)
```

- 从 result 里拿 `preview_image` 路径
- 文案用 `result["text"]`（已在 bridge 里从 caption.json 格式化过）
- 若有图，追加审核脚：

```
满意回复：好
要修改回复：改：你的修改意见
```

### 5.4 设置「等待审核」状态

```python
if agent_name == "smas" and image_path and channel == "telegram":
    status = "AWAITING_REVIEW"
    set_smas_review(channel_user_id, run_id=run_id, image_path=image_path)
```

`telegram_sessions.json` 示例：

```json
{
  "123456789": {
    "tool": "smas",
    "run_id": "run_20260624_153045_a3f2",
    "status": "awaiting_review"
  }
}
```

### 5.5 返回给 Telegram 适配器

```python
return {
    "action": "deliver",
    "text": delivery_text,
    "image_path": image_path,
    "awaiting_review": True,
    ...
}
```

---

## 2.6 第六步：Telegram 怎么把图发给你？

回到 `telegram_adapter.py`：

```python
if action == "deliver":
    intro = friendly_delivery_intro("smas", awaiting_review=True)
    # → "预览图来了（SMAS），你看下这版："
    body = intro + "\n\n" + delivery_text

    if image_path and Path(image_path).is_file():
        await update.message.reply_photo(photo=handle, caption=body[:1024])
```

**学习点**：

- Telegram 图片 caption 最长 1024 字符，超长要 `reply_text` 发剩余
- 图片是 **本地文件路径**，不是 URL——PAHS 读盘上传给 Telegram

---

## 2.7 第七步：你回复「好」或「改：…」

再发「好」→ `is_smas_review_reply` 为真 → `execute_smas_review`：

```python
action, payload = parse_smas_review_reply("好")  # → ("approve", "好")
smas_text = "ok"
result = run_smas_action(spec, "ok")  # 调用 smas.sh message ok
```

「改：标题字大一点」→ `smas_text = "edit: 标题字大一点"` → SMAS 内部走 edit 流程。

---

## 2.8 本章自测（合上电脑回答）

1. 为什么 `pah telegram` 终端看起来「卡住」？
2. `handle_inbound_text` 在调 SMAS 之前检查哪几件事？
3. `run_id` 在直调模式里有什么用？
4. 预览图存在你电脑的什么位置？（提示：SMAS state 目录）
5. 若用户说「你好」会不会调 SMAS？走哪条逻辑？

---

# 第三章 · SMAS Bridge 深度讲解：PAHS 如何与 SMAS 对话

文件：`src/pahs/external/smas_bridge.py`

PAHS 和 SMAS 之间 **没有 import 关系**，只有 **命令行 + JSON**：

```bash
~/Desktop/SMAS/scripts/smas.sh generate "给咖啡店做一条开业 IG 图文"
```

stdout 是一坨 JSON，PAHS 解析它。

---

## 3.1 为什么要 `generate` 而不是 `message`？

SMAS 有两个入口（`openclaw_bridge.py`）：

| 子命令 | 调用 | 适合 |
|--------|------|------|
| `generate <需求>` | `Orchestrator().generate(request)` | **从零生成新帖** |
| `message <文本>` | `Orchestrator().handle_text(text)` | 对话、审核 ok/skip、改图 |

`handle_text` 里有意图路由器。若它听不懂，会返回 `_help_message()`——就是你看过的那堆 `/generate` 说明书。

**所以 PAHS 直调必须用 `generate`**，配置在：

```yaml
# config/external_agents.yaml
smas:
  subcommand: generate
```

---

## 3.2 `clean_smas_prompt` 干什么？

用户有时说：「帮我做 IG post **并且告诉我你调用了什么 agent**」

这句话里的后半句是**问 PAHS 的**，不是给 SMAS 的创作需求。  
`clean_smas_prompt` 用正则删掉这类尾巴，避免 SMAS 困惑。

---

## 3.3 `_clear_smas_pending` — 为什么要先 skip？

SMAS 内部有状态机（`~/Desktop/SMAS/state/state.json`）。

若上一次生成完后你没点 ok/skip，状态是：

```json
{ "status": "waiting_review", ... }
```

此时再 `generate`，SMAS 会拒绝：

> The previous content is still waiting for review.

PAHS 在生成前自动执行：

```bash
smas.sh message skip
```

**学习点**：两个系统都有状态。PAHS 的 session 管「Telegram 是否在等人审」；SMAS 的 state 管「内容流水线是否结束」。桥接层要处理两边。

---

## 3.4 `_parse_bridge_output` 和 `_finalize_smas_payload`

SMAS 返回的 JSON 里有：

```json
{
  "ok": true,
  "text": "Preview ready. Please review: ... Reply ok / publish ...",
  "preview_image": "/Users/.../SMAS/state/preview_feed.png",
  "caption_file": ".../caption.json"
}
```

PAHS **故意不用** `text` 里的说明书，而是：

1. 读 `caption.json` 拼 Hook / 正文 / Hashtags（`_format_smas_text`）
2. 过滤「Generation failed」「waiting for review」→ 友好中文（`_smas_failure_message`）
3. 判断 `ok`：必须有真实存在的 `preview_image` 才算成功

**为什么？** 因为 SMAS 的 `text` 是给「直接用 SMAS CLI 的人」看的；PAHS 要给 Telegram 用户看**产品级文案**。

---

## 3.5 动手：自己跑一遍 bridge

```bash
cd ~/Desktop/PAHS && source .venv/bin/activate
pah externals test smas "给咖啡店做一条开业 IG 图文"
```

观察输出字段：

- `command`：实际执行的 shell 命令
- `preview_image`：有没有路径
- `text`：PAHS 格式化后的文案
- `ok`：最终是否算成功

再打开：

```bash
cat ~/Desktop/SMAS/state/state.json
cat ~/Desktop/SMAS/state/caption.json
ls -la ~/Desktop/SMAS/state/preview_feed.png
```

**建立直觉**：生成 = 改一堆 state 文件 + 出一张 png。

---

# 第四章 · SMAS 内部：生成一张 IG 图要经过什么

你在 PAHS 项目里学习，也必须懂 SMAS 在桥接层后面干什么，否则报错你看不懂。

文件：`~/Desktop/SMAS/core/orchestrator.py`

## 4.1 `generate(user_request)` 流程

```
1. 检查 state.json — 是否 waiting_review / confirm_post_type
2. ContentPipeline().run_guided(user_request)
3. 读 caption.json
4. build_review_prompt(caption) + preview_path 返回
```

## 4.2 `run_guided` 大致阶段

（名称在 `content_pipeline.py`，你学习时知道顺序即可）

```
classify（分类帖子类型）
  → brief（创意简报）
  → caption（文案 hook/body/hashtags）
  → visual_director（选 Path A/B/C、视觉参数）
  → image（调 fal 等 API 生图）
  → preview（合成 IG 预览框图）
  → critic（AI 打分建议）
  → 状态变为 waiting_review
```

## 4.3 Path A / B / C 是什么？

| Path | 含义 | 何时用 |
|------|------|--------|
| A | 纯 AI 文生图场景 | 没有产品图 |
| B | 用产品参考图 + fal edit 合成场景 | 有产品资产 |
| C | 模板 + 文字叠层 Pillow | 开业、活动海报类 |

「咖啡店开业」常走 **Path C**，需要 `text_overlay.lines` 是结构化对象。  
你遇到过 Pydantic 报错，就是因为 LLM 返回了字符串列表 `["NOW OPEN", ...]` 而不是 `[{"text":"NOW OPEN","zone":"top-left",...}]`。  
PAHS/SMAS 侧已加归一化，这是 **LLM 输出不可靠 → 工程要清洗** 的典型案例。

---

# 第五章 · LangGraph 全流程（`pah run`）详解

当你执行：

```bash
pah run "调研 LangGraph checkpoint 并写中文笔记"
```

## 5.1 `start_run` 做什么？

文件：`src/pahs/graph/runner.py`

```python
graph = build_graph()
config = graph_config(run_id)  # thread_id = run_id，用于 checkpoint
initial_state = {"run_id": run_id, "user_command": command, "channel": channel}
result = graph.invoke(initial_state, config=config)
```

**invoke** = 从图入口跑到遇到 `interrupt` 或 `END`。

## 5.2 图的主干（`graph/main.py`）

用白话讲每个节点：

| 节点 | 干什么 |
|------|--------|
| ingest | 标记开始 |
| load_global_rules | 加载全局规则（安全、预算） |
| triage_score | 判断任务简单还是复杂 |
| orchestrator_plan | 出计划：用哪个 worker、几个里程碑 |
| env_precheck | 检查预算、API、是否降级模型 |
| load_target_rules | 加载该 worker 专属规则 |
| worker_execute | 真干活：Creator / Searcher / Executor / External |
| verify_pipeline | 校验输出质量 |
| present_milestone | 把结果呈现给你 |
| milestone_human_review | **interrupt — 暂停等你输入** |
| final_present | 最终呈现 |
| final_feedback_request | **再 interrupt — 要最终反馈** |

## 5.3 什么是 `interrupt`？

LangGraph 里：

```python
feedback = interrupt({"type": "milestone_review", "presentation": "..."})
```

程序在这里**冻结**，状态存进 checkpoint（SQLite）。  
你执行：

```bash
pah reply run_xxx "approved"
```

`resume_run` 用 `Command(resume=user_input)` 从冻结处继续。

**和直调的区别**：LangGraph 路径**天生为多轮审核设计**；直调是为**一次交付**优化。

## 5.4 完成后 Learner 怎么触发？

`resume_run` 末尾：

```python
if not interrupts and result.get("status") == "COMPLETED":
    proposals = learn_from_final_feedback(run_id, feedback)
```

**注意**：Telegram 直调 SMAS **目前不会自动走这里**。这是你项目「还没接满」的重要一点。

---

# 第六章 · Harness 四层：为什么叫 Harness（挽具）

Harness 原意是套在马身上控制方向的挽具。  
**PAHS 的 Harness = 套在 AI 外面，防止它乱跑。**

## 6.1 Rule Layer（规则层）

文件：`harness/rules.py`、`rules/` 目录

**问题**：如果每次把全部公司规定塞给 AI，prompt 会爆、成本高、注意力散。  
**做法**：全局规则每次加载；具体到 Creator 的规则只有选中 Creator 时才加载。

Learner 批准后，内容 append 到 `standards/user_preferences.md` 等，下次 `standards_loader.py` 会读进来。

## 6.2 Tool Layer（工具层）

文件：`harness/tools.py`、`external/registry.py`

**原则**：Orchestrator 只能调用**注册过**的工具。  
Builder 在 `tools/staging/` 生成的工具，**不会**出现在生产列表里，直到你 `pah tools approve`。

## 6.3 Validation Layer（校验层）

文件：`harness/validation.py`

多层：确定性检查 → 启发式 → 必要时 LLM 再审 → 最后才是人审。  
**省钱**：不是所有输出都要再问一次 GPT「好不好」。

## 6.4 Environment Layer（环境层）

文件：`harness/environment.py`、`harness/budget.py`

管：token 预算、超时、模型降级、API 挂了怎么办。  
**商业意识**：大哥会问「跑一条多少钱」——答案在这层记。

---

# 第七章 · 数据存在哪：SQLite 与文件

## 7.1 `~/Desktop/PAHS/data/runs.db`

表（见 `storage/schema.sql`）：

- **runs**：每次任务一条，含 status、command、channel
- **review_queue**：LangGraph 路径等人审的队列
- **events**：日志流，`pah events <run_id>` 可看

## 7.2 `data/telegram_sessions.json`

直调 SMAS 后「等用户说好/改」的临时.session，不是长期偏好库。

## 7.3 SMAS 的 `state/` 目录

一次生成的「工作台」：caption、visual_spec、preview 图、critic 报告全在这。

**学习练习**：生成一次后，逐个打开 json 文件，看字段含义。

---

# 第八章 · Learner：反馈怎么变成系统记忆

文件：`learning/learner.py`

## 8.1 设计哲学

- **里程碑审核**（「这版大纲不行」）→ 只影响**这一次**任务
- **最终反馈**（「以后都要更口语」）→ 可以变成**永久提案**

且永久提案默认 **pending**，要你：

```bash
pah proposals approve <id>
```

才会写入 `standards/` 或 `rules/`。

## 8.2 为什么不让 AI 自动改自己？

想象 AI 学歪了：「用户骂了一句」→ 系统永久改成「永远只写一句话」→ 以后全毁。  
**人工批准**是安全阀。

## 8.3 现状诚实说明

`analyze_feedback` 目前是**关键词规则**（Mock），不是 DeepSeek 深度分析。  
Telegram 里「改：标题大一点」**还没有**自动进 Learner——这是你下一步开发的好课题。

---

# 第九章 · 配置文件逐行读懂

## 9.1 `.env`

```bash
TELEGRAM_BOT_TOKEN=123456:AAFxxxx   # 必须含一个冒号，BotFather 全长
DEEPSEEK_API_KEY=sk-xxxx
PAHS_LLM_PROVIDER=auto
```

## 9.2 `config/external_agents.yaml`

每个外部工具一段：

- `enabled`：开关
- `project_dir`：SMAS/PIP 根目录
- `subcommand`：SMAS 用 generate
- `match_keywords`：自然语言路由
- `timeout_seconds`：防止生图卡死

## 9.3 `config/gateway.yaml`

```yaml
telegram_direct_tools: true    # false 则 Telegram 只闲聊/走 run
telegram_chat_fallback: true # 无工具匹配时是否 DeepSeek 闲聊
```

---

# 第十章 · 故障排查：像工程师一样分层

| 症状 | 先查哪一层 | 怎么查 |
|------|------------|--------|
| Bot 完全无回复 | PAHS 进程 | 终端是否在跑 `pah telegram` |
| InvalidToken | 配置 | `.env` token 是否完整 |
| 返回命令说明书 | SMAS 子命令 | 是否误用 message；看 smas_bridge |
| 无图只有字 | SMAS 生成 | `pah externals test smas`；看 state.json error |
| waiting for review | SMAS 状态 | state.json；是否需 skip |
| Pydantic 报错 | SMAS visual | LLM 输出格式；归一化是否生效 |
| Connection error | API/网络 | SMAS .env 里 fal/DeepSeek key |

**口诀**：用户看到的 → PAHS → bridge 命令 → SMAS 状态文件 → 外部 API。

---

# 第十一章 · 和大哥（Sam）的话怎么对齐

大哥说学「能力能做多少」——用本教程，你应该能答：

**现在能做：**

- Telegram 自然语言 → IG 预览图 + 分块文案 → 人审 ok/改

**现在不能做：**

- 自动发帖、自动开号、全自动建站上线

**技术为什么可信：**

- Harness 有人审、有状态、有桥接隔离，不是裸 ChatGPT

**你学的不是语法，是：**

- 第二章的完整链路（Telegram 一条消息从头到尾）
- 第三章的 bridge 契约（PAHS 和 SMAS 怎么说话）
- 第六章为什么直调和 LangGraph 并存

---

# 第十二章 · 12 周学习作业（每周可检验）

| 周 | 作业 | 合格标准 |
|----|------|----------|
| 1 | 手绘第二章数据流图 | 能讲给同学听 5 分钟 |
| 2 | 跑 externals test smas 并读 4 个 state 文件 | 能说出每个文件作用 |
| 3 | 改 INTENT_RULES 加一个关键词 | Telegram 新句式可路由 |
| 4 | 走通一次 pah run 加 pah reply | 理解 interrupt |
| 5 | 读 graph/main.py 列出所有节点 | 能对应 Harness |
| 6 | 创建并 approve 一条 proposal | 文件出现在 standards 目录 |
| 7 | 写 1 页给 Sam 的能力边界 | 他看得懂、无夸大 |
| 8 | 录 60 秒 demo 视频 | 开业 IG 全链路 |
| 9 | 讲清 Harness 四层各举一个例子 | 不看笔记能说完 |
| 10 | 独立排查一次生成失败 | 能说出是哪一层坏了 |
| 11 | 把 Learner 接到 Telegram 改：反馈 | 能生成 proposal |
| 12 | 整理 co-op 用项目介绍稿 | 英文 2 分钟能讲完 |

---

# 附录 · 关键文件与函数索引

| 你想理解… | 打开 |
|-----------|------|
| Telegram 入口 | `gateway/telegram_adapter.py` → `_process_message` |
| 总调度决策 | `gateway/service.py` → `handle_inbound_text` |
| 自然语言路由 | `gateway/intent_router.py` |
| 直调交付 | `gateway/direct_tools.py` |
| SMAS 桥接 | `external/smas_bridge.py` |
| 外部工具注册 | `config/external_agents.yaml` |
| LangGraph 图 | `graph/main.py` → `build_graph` |
| 启动/恢复 run | `graph/runner.py` |
| 学习闭环 | `learning/learner.py` |
| SMAS 生成核心 | `~/Desktop/SMAS/core/orchestrator.py` |

---

**教程结束。建议：打印本章自测题，每周重做一遍，直到不用看代码也能答。**

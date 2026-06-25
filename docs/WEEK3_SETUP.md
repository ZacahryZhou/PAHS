# Week 3 Setup | 第 3 周说明

Week 3 adds:

- Searcher worker with `search_web`
- Executor modes: `DEEP_THINK`, `CODE`, `ANALYSIS`
- Telegram gateway
- Cross-channel review through the same `review_queue`

## Upgrade | 升级

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
pah init-db
```

Optional `.env` keys:

```env
TAVILY_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

Without Tavily, Searcher uses mock sources.
Without Telegram token, CLI still works.

## Demo 1: Searcher | 调研任务

```bash
pah run "research LangGraph checkpoint and write notes"
pah events <run_id>
```

Expected:

- worker = `searcher`
- output includes source URLs
- milestone review before final feedback

## Demo 2: CODE mode | 代码任务

```bash
pah run "write python result and save file"
pah events <run_id>
```

Expected:

- worker = `executor`
- mode = `CODE`
- file saved under `data/outputs/`

## Demo 3: ANALYSIS mode | 分析任务

```bash
pah run "analysis csv metrics chart"
```

Expected:

- worker = `executor`
- mode = `ANALYSIS`

## Demo 4: Cross-channel review | 跨通道审核

1. Start from CLI:

```bash
pah run "research LangGraph checkpoint"
```

2. Reply from Telegram using the same protocol:

```text
reply run_xxx approved
reply run_xxx looks good
```

Or finish from CLI:

```bash
pah reply run_xxx "approved"
pah reply run_xxx "looks good"
```

## Telegram bot | 启动 Telegram

```bash
pah telegram
```

Telegram message format:

```text
run write a short post about AI
reply run_xxx approved
pending
```

## Week 3 acceptance | 验收

- CLI start, Telegram reply works
- Searcher returns sources
- CODE mode can save a file in sandbox
- Same `run_id` works across channels

## Clear all test data | 一键清理测试数据

Use this when `pah pending` has too many old test runs:

```bash
pah reset-test
```

Flow:

1. Shows counts
2. First confirm: `Continue? [y/N]`
3. Second confirm: type `DELETE ALL`

Optional (skip typed confirm, still needs first yes):

```bash
pah reset-test --force
```

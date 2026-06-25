# Week 2 Setup | 第 2 周说明

Week 2 adds the Harness governance layers:

- Rule layer with lazy loading
- Tool registry with approved tools only
- Validation pipeline (Stage 1 + Stage 1.5)
- Environment and budget checks with event logging

## Upgrade local DB | 升级本地数据库

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate
pah init-db
```

## Demo 1: Simple task skips milestone review | 简单任务跳过阶段审核

```bash
pah run "write a short post about AI"
pah pending
```

Expected:

- First pending item should be `final_feedback`, not `milestone_review`
- `pah events <run_id>` shows `rules_loaded` and `environment_precheck`

## Demo 2: Medium task uses milestone review | 中等任务需要阶段审核

```bash
pah run "research LangGraph checkpoint and write notes"
pah pending
```

Expected:

- First pending item should be `milestone_review`

## Demo 3: Inspect lazy rules | 查看按需规则

```bash
pah rules-show global
pah rules-show creator
```

## Finish a run | 完成一次运行

Use the same two-step reply flow as Week 1:

```bash
pah reply <run_id> "approved"
pah reply <run_id> "looks good"
pah status <run_id>
pah events <run_id>
```

## Week 2 acceptance | 验收标准

- Simple task -> final feedback only
- Complex/medium task -> milestone review first
- Global rules load at start; creator rules load later
- Validation can retry before failing
- Budget/environment checks are logged in `run_events`

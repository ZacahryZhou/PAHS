# Week 4 Setup — Routing, Cost Control, and Standards

Week 4 adds smarter routing before execution:

- structured `RoutingContext`
- model selection with downgrade chain
- cost estimate before execution
- standards loaded by task type
- no-progress detector on validation retries

## New files

```text
src/pahs/routing/
├── task_classifier.py
├── llm_router.py
├── cost_estimator.py
├── standards_loader.py
└── no_progress.py

standards/
├── user_preferences.md
└── by_task_type/
    ├── research_report.md
    ├── social_post.md
    └── code_task.md
```

## Install / refresh

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt -e .
pah init-db
```

## Quick tests

### 1. Preview routing (no run)

```bash
pah route-preview "write a short post about AI"
pah route-preview "research LangGraph docs"
pah route-preview "deep think: prove why this algorithm works"
pah route-preview "write python code to parse a csv file"
```

Expected:

- simple post → `lite`, worker `creator`, cheap model
- research → worker `searcher`
- deep think → worker `executor`, mode `DEEP_THINK`, model `deepseek-reasoner`
- code/csv → worker `executor`, mode `CODE` or `ANALYSIS`

### 2. Run and inspect events

```bash
pah reset-test
pah run "research LangGraph checkpointing"
pah pending
pah reply <run_id> "approved"
pah reply <run_id> "looks good"
pah events <run_id>
```

Look for event types:

- `triage_routing`
- `routing_decision`
- `cost_tracking` (pre_execution + post_run)
- `environment_precheck`

### 3. Daily budget snapshot

```bash
pah costs-today
```

## What `pah` means

`pah` is the **PAHS CLI command** — like `git` for Git.

It is **not** an agent. It is how you talk to PAHS from terminal:

- `pah run` — start a task
- `pah route-preview` — preview routing
- `pah pending` / `pah reply` — human review
- `pah events` — harness logs

## Acceptance checklist

- [ ] Simple task routes to lite + cheap model
- [ ] Research routes to searcher
- [ ] Deep reasoning routes to DEEP_THINK + reasoner
- [ ] `pah events` shows estimated vs actual cost
- [ ] Standards paths appear in plan / output

## Next

Week 5: Learner + `pah feedback` + proposal approval flow.

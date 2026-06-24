# PAHS

**PAHS** (Personal Agent Harness System) is a private multi-agent assistant project.

Project path: `~/Desktop/PAHS`

Current design:

- LangGraph from week 1
- CLI first, Telegram second, WhatsApp later
- SQLite for v1
- Supabase later if needed
- no local LLM for now
- Triage routes to Orchestrator Lite or Full
- milestone review is separate from final feedback learning
- Builder-created tools stay in staging until manual approval

Start with:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

## What is a run_id?

A `run_id` is the unique ID for one user request.

Example:

```text
run_20260624_155900_a3f9
```

It connects:

- the original command
- current milestone
- pending review
- checkpoint resume state
- feedback
- costs and logs
- channel replies from CLI, Telegram, or WhatsApp

Think of it as the task tracking number.

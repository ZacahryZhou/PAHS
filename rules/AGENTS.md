# Rules Index

This file is the rule index. It should stay short.

## Always Loaded

- `global/safety.md`
- `global/budget.md`

## Loaded Only After Routing

Agents:

- `orchestrator` -> `agents/orchestrator.md`
- `creator` -> `agents/creator.md`
- `searcher` -> `agents/searcher.md`

Modes:

- `DEEP_THINK` -> `modes/deep_think.md`
- `CODE` -> `modes/code.md`
- `ANALYSIS` -> `modes/analysis.md`

## Hard Rules

- Builder-generated tools must stay in staging until manual approval.
- Learner can only create pending proposals.
- Milestone feedback is local to the current run.
- Final feedback is the primary learning signal.
- API keys must stay in local environment files and must never be committed.

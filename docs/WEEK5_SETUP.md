# Week 5 Setup — Learner and Feedback Approval

Week 5 adds learning from **final feedback only**. Nothing is applied automatically.

## New pieces

```text
src/pahs/learning/
├── learner.py
├── proposals.py
└── approvals.py

rules/learnings/
├── pending/
├── approved/
└── rejected/
```

## Install / refresh

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate
pah init-db
```

Only run full `pip install ...` if dependencies changed.

## Flow

1. Finish a run with `pah reply` during final feedback
2. Learner creates **pending** proposals (not active yet)
3. You review with `pah proposals pending`
4. Approve or reject manually

Alternative: after a run is `COMPLETED`, you can also run:

```bash
pah feedback <run_id> "next time include official doc links"
```

## Test script

```bash
pah reset-test
pah run "research LangGraph checkpointing"
pah pending
pah reply <run_id> "approved"
pah reply <run_id> "next time include official doc links in research reports"
pah proposals pending
pah proposals approve <proposal_id>
```

Check:

- `standards/by_task_type/research_report.md` should gain an approved block
- `pah events <run_id>` should show `learner_proposals_created`
- rejected proposals stay in DB with reason

## CLI commands

```bash
pah feedback <run_id> "your final feedback"
pah proposals pending
pah proposals approve <proposal_id>
pah proposals reject <proposal_id> --reason "too broad"
```

## Acceptance checklist

- [ ] Final feedback creates pending proposal(s)
- [ ] Pending proposals are not applied until approved
- [ ] Approved proposals update standards/rules for future runs
- [ ] Rejected proposals are stored with reason

## Next

Week 6: Builder staging + `pah tools staging/review/approve`.

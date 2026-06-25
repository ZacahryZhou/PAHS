# PAHS Development Roadmap

**PAHS** (Personal Agent Harness System) — development plan.

Project path: `~/Desktop/PAHS`

This roadmap reflects the current architecture decisions:

- LangGraph is used from week 1.
- CLI is built first.
- Telegram comes after the CLI.
- WhatsApp is later because official WhatsApp integration is more complex.
- SQLite is used for v1.
- Supabase is optional later.
- No local LLM for now.
- Triage routes tasks to Orchestrator Lite or Orchestrator Full.
- Feedback learning happens after the whole run, not after every milestone.
- Builder-generated tools must stay in staging until manual approval.

## Phase 0: Project Setup

Goal: create the repository baseline and documentation.

Deliverables:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- initial folder layout
- `.env.example`
- base config files

Acceptance:

- Project folder exists.
- Architecture and roadmap are written.
- No secrets are stored in the repo.

## Week 1: Minimal Runnable Core

Goal: run one simple command from CLI through LangGraph and pause for user review.

### Build

Files:

```text
src/pah/
├── cli.py
├── graph/
│   ├── state.py
│   ├── main.py
│   └── checkpoints.py
├── gateway/
│   ├── messages.py
│   └── cli_adapter.py
├── storage/
│   ├── db.py
│   └── schema.sqlpah run "write a short post about AI"
pah pending
pah reply <run_id> "approved"
pah reply <run_id> "looks good"
pah status <run_id>

├── agents/
│   ├── triage.py
│   ├── orchestrator.py
│   └── creator.py
└── providers/
    └── deepseek.py
```

Graph:

```text
channel_ingest
→ triage_score
→ orchestrator_plan_lite_or_full
→ creator_execute
→ verify_basic
→ present_milestone
→ interrupt_for_review
→ final_feedback_request
→ end
```

CLI commands:

```bash
pah run "write a short post about AI"
pah status <run_id>
pah pending
pah reply <run_id> "approved"
```

### Concepts Learned

- `run_id`
- LangGraph state
- node and edge
- checkpoint
- interrupt and resume
- SQLite storage

### Acceptance

- `pah run` creates a Run.
- The system generates one milestone.
- The graph pauses for review.
- `pah reply <run_id> "approved"` resumes the run.
- Final feedback is requested after the run.

## Week 2: Harness Governance Layer

Goal: add the four harness layers around execution.

### Build

Files:

```text
src/pah/harness/
├── rules.py
├── tools.py
├── validation.py
├── environment.py
└── budget.py

rules/
├── AGENTS.md
├── global/
│   ├── safety.md
│   └── budget.md
├── agents/
│   ├── orchestrator.md
│   ├── creator.md
│   └── searcher.md
└── modes/
    ├── deep_think.md
    ├── code.md
    └── analysis.md

config/
├── budget.yaml
├── review_policy.yaml
└── models.yaml
```

Harness features:

- Global rules loaded every run.
- Agent and mode rules loaded only after routing.
- Basic deterministic validation.
- Cost and token budget checks.
- Review policy for simple vs complex tasks.

### Review Policy v1

Suggested default:

```yaml
review_policy:
  simple:
    plan_confirmation: false
    milestone_reviews: final_only
  medium:
    plan_confirmation: false
    milestone_reviews: key_milestones
  complex:
    plan_confirmation: true
    milestone_reviews: every_milestone
```

### Acceptance

- Simple task requires only final review.
- Complex task can require plan confirmation and milestone reviews.
- Rules are not fully loaded at run start.
- Validation can reject a bad output.
- Budget checks are logged.

## Week 3: Searcher, Executor Modes, and Telegram

Goal: support research, code/data modes, and mobile review through Telegram.

### Build

Files:

```text
src/pah/agents/
├── searcher.py
└── executor.py

src/pah/gateway/
└── telegram_adapter.py

src/pah/tools/
├── registry.py
├── search_web.py
├── file_tools.py
└── python_sandbox.py
```

Features:

- Searcher with search API.
- Executor mode `DEEP_THINK`.
- Executor mode `CODE`.
- Executor mode `ANALYSIS`.
- Telegram Bot adapter.
- Cross-channel review via the same `review_queue`.

### Acceptance

- A run can start from CLI and be approved from Telegram.
- A run can start from Telegram and be approved from CLI.
- Searcher can return sources.
- Executor can run a safe Python task.

## Week 4: Routing, Cost Control, and Standards

Goal: make the model and execution routing more intelligent.

### Build

Files:

```text
src/pah/routing/
├── llm_router.py
├── task_classifier.py
└── cost_estimator.py

standards/
├── user_preferences.md
└── by_task_type/
    ├── research_report.md
    ├── social_post.md
    └── code_task.md
```

Features:

- Structured routing context.
- Model downgrade chain.
- Cost estimate before execution.
- No-progress detector.
- Standards loaded when relevant.

### Acceptance

- Triage picks Lite or Full correctly on test prompts.
- Hard reasoning tasks can use `DEEP_THINK`.
- Low-risk simple tasks stay cheap and quick.
- The system logs estimated cost vs actual cost.

## Week 5: Learner and Feedback Approval

Goal: learn from final feedback, but never apply changes automatically.

### Build

Files:

```text
src/pah/learning/
├── learner.py
├── proposals.py
└── approvals.py

rules/learnings/
├── pending/
└── approved/
```

CLI commands:

```bash
pah feedback <run_id> "next time make research reports include official docs"
pah proposals pending
pah proposals approve <proposal_id>
pah proposals reject <proposal_id>
```

Learner can propose:

- new user standard
- agent rule update
- mode rule update
- routing policy update
- review policy update

### Acceptance

- Final feedback creates a pending proposal.
- Pending proposals are not active by default.
- Approved proposals become available to future runs.
- Rejected proposals are stored with reason.

## Week 6: Builder Staging and WhatsApp Planning

Goal: allow the system to generate new tools safely, without automatic production use.

### Build

Files:

```text
src/pah/builder/
├── builder.py
├── sandbox.py
├── tool_manifest.py
└── review.py

tools/
├── builtin/
└── staging/
```

CLI commands:

```bash
pah tools staging
pah tools review <tool_name>
pah tools approve <tool_name>
pah tools reject <tool_name> --reason "not safe enough"
```

Builder lifecycle:

```text
DRAFT → TESTING → PENDING_REVIEW → APPROVED | REJECTED
```

WhatsApp:

- design adapter interface
- decide later between Meta WhatsApp Cloud API or Twilio
- do not block earlier phases on WhatsApp

### Acceptance

- Builder can generate a staged tool and tests.
- Tests can pass while tool remains unavailable to Orchestrator.
- Only approved tools enter production registry.
- Rejected tools remain blocked.

## Later Phase: Supabase

Goal: optionally sync local SQLite state to Supabase for cloud access, dashboard, or multi-device querying.

Possible Supabase tables:

- runs
- milestones
- review_queue
- feedback
- proposals
- tool_registry
- routing_stats

Approach:

- keep SQLite as local source first
- add storage interface
- implement Supabase mirror or backend
- do not introduce Supabase until core loop is stable

## Current Top Risks

### 1. Orchestrator overload

Mitigation:

- Triage Agent first.
- Lite vs Full profiles.
- Use `DEEP_THINK` mode only when needed.
- Split planning and presentation calls.

### 2. Too many reviews annoy the user

Mitigation:

- `review_policy.yaml`.
- Simple tasks get final review only.
- Complex tasks use milestone review.

### 3. Cross-channel state confusion

Mitigation:

- central SQLite state
- `run_id` in every review message
- `review_queue` as the only pending-review source
- duplicate reply protection

### 4. Learner learns wrong things

Mitigation:

- learn from final feedback, not every milestone comment
- write pending proposals only
- manual approval required

### 5. Builder safety

Mitigation:

- staging only
- tests required
- sandbox required
- manual approval required
- Orchestrator cannot call staging tools

## Immediate Next Step

Build Week 1:

1. create Python project files
2. create SQLite schema
3. create CLI adapter
4. create minimal LangGraph state and graph
5. implement Triage stub
6. implement Orchestrator Lite/Full stub
7. implement Creator stub
8. implement interrupt review and reply resume

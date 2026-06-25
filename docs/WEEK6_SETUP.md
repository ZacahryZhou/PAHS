# Week 6 Setup — Builder Staging and WhatsApp Planning

Week 6 adds safe tool creation:

- Builder writes tools to `tools/staging/`
- Sandbox tests can pass while tool stays non-callable
- Only `pah tools approve` moves a tool into production
- WhatsApp adapter interface is designed but not fully wired

## New pieces

```text
src/pahs/builder/
├── builder.py
├── sandbox.py
├── tool_manifest.py
└── review.py

src/pahs/gateway/whatsapp_adapter.py

tools/
├── builtin/
└── staging/
```

## Quick test

```bash
cd ~/Desktop/PAHS
source .venv/bin/activate

# 1) Draft a staged tool
pah tools draft "tool that counts words in text"

# 2) Inspect staging
pah tools staging
pah tools review count_words

# 3) Confirm production cannot call it yet
python -c "from pahs.tools.registry import call_tool; call_tool('count_words', text='hi')"
# should raise PermissionError

# 4) Approve
pah tools approve count_words

# 5) Now production can call it
python -c "from pahs.tools.registry import call_tool; print(call_tool('count_words', text='hi there'))"
```

## Lifecycle

```text
DRAFT → TESTING → PENDING_REVIEW → APPROVED | REJECTED
```

## CLI commands

```bash
pah tools staging
pah tools draft "requirement text"
pah tools review <tool_name>
pah tools approve <tool_name>
pah tools reject <tool_name> --reason "not safe enough"
```

## Acceptance checklist

- [ ] Builder draft creates code + tests in staging
- [ ] Tests can pass while tool is still not callable
- [ ] Approve moves tool to `tools/builtin/` and production registry
- [ ] Reject blocks tool from production
- [ ] Orchestrator only sees approved tools via Harness

## WhatsApp

Week 6 only adds `whatsapp_adapter.py` as an interface.

Later you can choose:

- Meta WhatsApp Cloud API
- Twilio WhatsApp API

This does not block CLI or Telegram usage.

## Next

Later phase: Supabase sync for runs, reviews, proposals, and tool registry.

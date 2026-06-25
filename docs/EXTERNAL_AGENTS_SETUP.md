# External Agents + DeepSeek Setup

This phase adds:

1. **DeepSeek** for PAHS internal agents (Creator, Searcher, Executor)
2. **External agent bridge** for local tools like **OpenClaw**

## 1. Configure DeepSeek

Create `~/Desktop/PAHS/.env`:

```bash
DEEPSEEK_API_KEY=sk-your-key-here
PAHS_LLM_PROVIDER=auto
```

Check:

```bash
pah llm-status
```

Expected:

```json
{
  "active_provider": "deepseek",
  "deepseek_api_key_set": true
}
```

If no key is set, PAHS falls back to mock output.

Install dependency once if needed:

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt -e .
```

## 2. Configure external agents

Edit `config/external_agents.yaml`.

OpenClaw is enabled by default on your machine (`/opt/homebrew/bin/openclaw`).

Add your own shell bridge example:

```yaml
external_agents:
  my_project:
    enabled: true
    type: shell
    description: My local project CLI
    working_directory: ~/Desktop/MyProject
    command:
      - bash
      - -lc
      - ./scripts/ask.sh "$PAHS_PROMPT"
    match_keywords:
      - myproject
      - my project
```

List configured bridges:

```bash
pah externals list
```

## 3. How auto-routing works

PAHS is the **main controller**. SMAS and PIP are **tools**.

If your command matches keywords or prefixes, PAHS routes to that tool:

| You say | PAHS calls |
|---------|------------|
| `@smas 给咖啡店做一条开业 IG 图文` | SMAS (`scripts/smas.sh message ...`) |
| `@pip 做一条 10 秒咖啡品牌短视频` | PIP (`python -m video_pipeline.main --payload ...`) |
| `write a blog post` (no tool keyword) | PAHS internal Creator + DeepSeek |

Preview routing:

```bash
pah route-preview "@smas create an IG post for a coffee shop opening"
pah route-preview "@pip create a 10 second coffee promo video"
```

## 4. Test OpenClaw directly

```bash
pah externals test openclaw "say hello in one sentence"
```

OpenClaw uses your existing local setup:

- default agent: `main`
- mode: `--local --json`

If OpenClaw itself cannot reach DeepSeek, fix OpenClaw credentials first (`openclaw doctor`).

## 5. Full PAHS run with external agent

```bash
pah run "@openclaw help me draft a short plan for PAHS Week 7"
pah pending
pah reply <run_id> "approved"
pah reply <run_id> "looks good"
pah events <run_id>
```

Look for `external_agent_called` in events.

## 6. What still uses DeepSeek inside PAHS

When `DEEPSEEK_API_KEY` is set:

- Creator output
- Searcher summary
- Executor explanations / DEEP_THINK
- optional triage enhancement

External OpenClaw calls use **OpenClaw's own model config**, not PAHS's key directly.

## Safety

- External agents only run if listed and `enabled: true`
- Staging Builder tools remain blocked
- Milestone/final review still applies
- Same `run_id` tracks external calls in `run_events`

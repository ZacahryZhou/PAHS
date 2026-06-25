# External agent delegation rules

- External agents run outside PAHS but stay under the same run_id and review flow.
- Only agents listed in `config/external_agents.yaml` with `enabled: true` may be called.
- Staging tools remain blocked even when external agents are used.
- User milestone feedback can be forwarded to the same external agent on retry.

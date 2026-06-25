"""Mock Learner — turns final feedback into pending proposals."""

from __future__ import annotations

from typing import Any

from pahs.learning.proposals import Proposal, create_proposal
from pahs.storage import db


def _has_any(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered or needle in text for needle in needles)


def analyze_feedback(feedback: str, *, run_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return proposal drafts before persistence."""
    context = run_context or {}
    task_type = context.get("task_type", "general_task")
    worker = context.get("worker", "creator")
    drafts: list[dict[str, Any]] = []

    if _has_any(feedback, "official doc", "official documentation", "官方文档", "官方文档链接"):
        drafts.append(
            {
                "proposal_type": "user_standard",
                "target_path": "standards/by_task_type/research_report.md",
                "title": "Require official documentation links in research reports",
                "proposed_content": (
                    "- Always include at least one official documentation link when available.\n"
                    "- Prefer primary sources over blog summaries."
                ),
                "rationale": "User asked for official docs in research output.",
            }
        )

    if _has_any(feedback, "casual", "relaxed tone", "轻松", "随意", "口语"):
        drafts.append(
            {
                "proposal_type": "user_standard",
                "target_path": "standards/user_preferences.md",
                "title": "Prefer casual tone for social content",
                "proposed_content": "- Prefer a casual, conversational tone unless the user asks for formal writing.",
                "rationale": "User requested a more casual tone.",
            }
        )

    if worker == "searcher" or _has_any(feedback, "searcher", "research", "调研", "搜索"):
        if _has_any(feedback, "source", "citation", "链接", "来源", "引用"):
            drafts.append(
                {
                    "proposal_type": "agent_rule_update",
                    "target_path": "rules/agents/searcher.md",
                    "title": "Searcher should emphasize source quality",
                    "proposed_content": (
                        "## Learned preference\n"
                        "- Cite sources explicitly in the output.\n"
                        "- Prefer official docs and primary references."
                    ),
                    "rationale": "Feedback focused on research source quality.",
                }
            )

    if worker == "creator" or _has_any(feedback, "creator", "draft", "文案", "创作"):
        if _has_any(feedback, "shorter", "concise", "简短", "精简"):
            drafts.append(
                {
                    "proposal_type": "agent_rule_update",
                    "target_path": "rules/agents/creator.md",
                    "title": "Creator should keep drafts concise",
                    "proposed_content": (
                        "## Learned preference\n"
                        "- Default to concise drafts unless the user asks for length."
                    ),
                    "rationale": "User wants shorter creator output.",
                }
            )

    if _has_any(feedback, "deep think", "reasoning", "推理", "深入分析"):
        drafts.append(
            {
                "proposal_type": "mode_rule_update",
                "target_path": "rules/modes/deep_think.md",
                "title": "Deep think should show reasoning steps",
                "proposed_content": (
                    "## Learned preference\n"
                    "- Show step-by-step reasoning before the final answer."
                ),
                "rationale": "User asked for clearer reasoning.",
            }
        )

    if _has_any(feedback, "cheaper", "cheaper model", "lite", "便宜", "省钱", "降本"):
        drafts.append(
            {
                "proposal_type": "routing_policy_update",
                "target_path": "standards/learned/routing_notes.md",
                "title": "Prefer cheaper routing when quality is sufficient",
                "proposed_content": (
                    "- Prefer orchestrator lite and deepseek-chat for low-risk tasks.\n"
                    "- Downgrade expensive models unless the user asks for high quality."
                ),
                "rationale": "User asked to reduce cost.",
            }
        )

    if _has_any(feedback, "review", "milestone", "审核", "阶段"):
        drafts.append(
            {
                "proposal_type": "review_policy_update",
                "target_path": "standards/learned/review_notes.md",
                "title": "Adjust review expectations from feedback",
                "proposed_content": (
                    "- Follow user review preferences captured in final feedback.\n"
                    "- Keep milestone review focused on deliverable quality."
                ),
                "rationale": "User commented on review behavior.",
            }
        )

    if not drafts and task_type == "research_report":
        drafts.append(
            {
                "proposal_type": "user_standard",
                "target_path": "standards/by_task_type/research_report.md",
                "title": "Capture research feedback as a user standard",
                "proposed_content": f"- User feedback: {feedback.strip()}",
                "rationale": "Generic research feedback with no exact keyword match.",
            }
        )

    if not drafts:
        drafts.append(
            {
                "proposal_type": "user_standard",
                "target_path": "standards/user_preferences.md",
                "title": "Capture general user preference",
                "proposed_content": f"- User feedback: {feedback.strip()}",
                "rationale": "Generic final feedback captured as a pending standard.",
            }
        )

    return drafts


def learn_from_final_feedback(run_id: str, feedback: str) -> list[Proposal]:
    run = db.get_run(run_id)
    if run is None:
        raise ValueError(f"Unknown run_id={run_id}")

    plan = {}
    if run.get("plan_json"):
        import json

        plan = json.loads(run["plan_json"])

    context = {
        "task_type": plan.get("triage", {}).get("task_type"),
        "worker": plan.get("worker"),
        "orchestrator_profile": plan.get("orchestrator_profile"),
    }

    drafts = analyze_feedback(feedback, run_context=context)
    created: list[Proposal] = []
    for draft in drafts:
        proposal = create_proposal(
            run_id=run_id,
            feedback_text=feedback,
            **draft,
        )
        created.append(proposal)

    db.log_event(
        run_id,
        "learner_proposals_created",
        {
            "feedback": feedback,
            "proposal_ids": [item.proposal_id for item in created],
            "count": len(created),
        },
    )
    return created

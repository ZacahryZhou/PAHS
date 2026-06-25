"""Learning proposal records and file storage."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pahs.paths import PROJECT_ROOT
from pahs.storage import db

LEARNINGS_DIR = PROJECT_ROOT / "rules" / "learnings"
PENDING_DIR = LEARNINGS_DIR / "pending"
APPROVED_DIR = LEARNINGS_DIR / "approved"
REJECTED_DIR = LEARNINGS_DIR / "rejected"

ProposalType = Literal[
    "user_standard",
    "agent_rule_update",
    "mode_rule_update",
    "routing_policy_update",
    "review_policy_update",
]
ProposalStatus = Literal["pending", "approved", "rejected"]


@dataclass
class Proposal:
    proposal_id: str
    run_id: str
    proposal_type: ProposalType
    status: ProposalStatus
    target_path: str
    title: str
    feedback_text: str
    proposed_content: str
    rationale: str
    reject_reason: str | None = None
    pending_file: str | None = None
    created_at: str = ""
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_proposal_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"prop_{stamp}_{suffix}"


def ensure_learning_dirs() -> None:
    for path in (PENDING_DIR, APPROVED_DIR, REJECTED_DIR):
        path.mkdir(parents=True, exist_ok=True)


def save_pending_file(proposal: Proposal) -> str:
    ensure_learning_dirs()
    rel = f"rules/learnings/pending/{proposal.proposal_id}.json"
    path = PROJECT_ROOT / rel
    path.write_text(json.dumps(proposal.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return rel


def move_proposal_file(proposal_id: str, *, to: Literal["approved", "rejected"]) -> str | None:
    src = PENDING_DIR / f"{proposal_id}.json"
    if not src.exists():
        return None
    dest_dir = APPROVED_DIR if to == "approved" else REJECTED_DIR
    ensure_learning_dirs()
    dest = dest_dir / f"{proposal_id}.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return str(dest.relative_to(PROJECT_ROOT))


def create_proposal(
    *,
    run_id: str,
    proposal_type: ProposalType,
    target_path: str,
    title: str,
    feedback_text: str,
    proposed_content: str,
    rationale: str,
) -> Proposal:
    proposal = Proposal(
        proposal_id=new_proposal_id(),
        run_id=run_id,
        proposal_type=proposal_type,
        status="pending",
        target_path=target_path,
        title=title,
        feedback_text=feedback_text,
        proposed_content=proposed_content,
        rationale=rationale,
        created_at=_utc_now(),
    )
    proposal.pending_file = save_pending_file(proposal)
    db.insert_proposal(proposal.to_dict())
    return proposal


def get_proposal(proposal_id: str) -> Proposal | None:
    row = db.get_proposal(proposal_id)
    if row is None:
        return None
    return Proposal(**row)


def list_pending_proposals() -> list[Proposal]:
    return [Proposal(**row) for row in db.list_proposals(status="pending")]

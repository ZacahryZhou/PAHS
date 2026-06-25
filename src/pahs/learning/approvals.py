"""Approve or reject Learner proposals."""

from __future__ import annotations

from pahs.learning.proposals import APPROVED_DIR, get_proposal, move_proposal_file
from pahs.paths import PROJECT_ROOT
from pahs.storage import db


def _append_to_target(proposal) -> str:
    target = PROJECT_ROOT / proposal.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    marker = f"\n\n<!-- approved: {proposal.proposal_id} run: {proposal.run_id} -->\n"
    block = marker + proposal.proposed_content.strip() + "\n"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        target.write_text(existing.rstrip() + block, encoding="utf-8")
    else:
        header = f"# Learned update from {proposal.proposal_id}\n"
        target.write_text(header + block, encoding="utf-8")
    return str(target.relative_to(PROJECT_ROOT))


def approve_proposal(proposal_id: str) -> dict:
    proposal = get_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Unknown proposal_id={proposal_id}")
    if proposal.status != "pending":
        raise ValueError(f"Proposal {proposal_id} is not pending (status={proposal.status})")

    applied_path = _append_to_target(proposal)
    archived = move_proposal_file(proposal_id, to="approved")
    db.update_proposal_status(
        proposal_id,
        status="approved",
        reject_reason=None,
        pending_file=archived,
    )
    db.log_event(
        proposal.run_id,
        "proposal_approved",
        {
            "proposal_id": proposal_id,
            "proposal_type": proposal.proposal_type,
            "target_path": applied_path,
        },
    )
    return {
        "proposal_id": proposal_id,
        "status": "approved",
        "applied_to": applied_path,
        "archived_file": archived,
    }


def reject_proposal(proposal_id: str, *, reason: str) -> dict:
    proposal = get_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Unknown proposal_id={proposal_id}")
    if proposal.status != "pending":
        raise ValueError(f"Proposal {proposal_id} is not pending (status={proposal.status})")

    archived = move_proposal_file(proposal_id, to="rejected")
    db.update_proposal_status(
        proposal_id,
        status="rejected",
        reject_reason=reason,
        pending_file=archived,
    )
    db.log_event(
        proposal.run_id,
        "proposal_rejected",
        {
            "proposal_id": proposal_id,
            "reason": reason,
        },
    )
    return {
        "proposal_id": proposal_id,
        "status": "rejected",
        "reason": reason,
        "archived_file": archived,
    }


def list_approved_files() -> list[str]:
    if not APPROVED_DIR.exists():
        return []
    return sorted(str(path.relative_to(PROJECT_ROOT)) for path in APPROVED_DIR.glob("*.json"))

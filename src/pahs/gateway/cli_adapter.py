"""CLI channel adapter."""

from __future__ import annotations

from pahs.gateway.messages import InboundMessage, OutboundMessage


def to_inbound(text: str, *, run_id: str | None = None) -> InboundMessage:
    return InboundMessage(channel="cli", user_id="default", text=text, run_id=run_id)


def to_outbound(text: str, *, run_id: str | None = None, expects_reply: bool = False) -> OutboundMessage:
    return OutboundMessage(text=text, run_id=run_id, expects_reply=expects_reply)

"""Internal message format shared by all channels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Channel = Literal["cli", "telegram", "whatsapp"]


@dataclass
class InboundMessage:
    channel: Channel
    user_id: str
    text: str
    run_id: str | None = None
    attachments: list[Any] = field(default_factory=list)


@dataclass
class OutboundMessage:
    text: str
    run_id: str | None = None
    expects_reply: bool = False

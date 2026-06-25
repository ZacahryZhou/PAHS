"""WhatsApp gateway adapter interface (design only for Week 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class WhatsAppInboundMessage:
    channel_user_id: str
    text: str
    message_id: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class WhatsAppOutboundMessage:
    channel_user_id: str
    text: str


class WhatsAppProvider(Protocol):
    """Provider-specific adapter for Meta Cloud API or Twilio."""

    provider_name: str

    async def send_text(self, message: WhatsAppOutboundMessage) -> None:
        ...

    async def parse_webhook(self, payload: dict[str, Any]) -> list[WhatsAppInboundMessage]:
        ...


class WhatsAppGateway:
    """
    Future WhatsApp entry point.

    Week 6 only defines the interface. Actual provider choice is deferred:
    - Meta WhatsApp Cloud API
    - Twilio WhatsApp API
    """

    def __init__(self, provider: WhatsAppProvider) -> None:
        self.provider = provider

    async def handle_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        from pahs.gateway.service import handle_inbound_text

        responses: list[dict[str, Any]] = []
        messages = await self.provider.parse_webhook(payload)
        for item in messages:
            result = handle_inbound_text(
                item.text,
                channel="whatsapp",
                channel_user_id=item.channel_user_id,
            )
            responses.append(result)
            if result.get("reply_text"):
                await self.provider.send_text(
                    WhatsAppOutboundMessage(
                        channel_user_id=item.channel_user_id,
                        text=str(result["reply_text"]),
                    )
                )
        return responses


class UnconfiguredWhatsAppProvider:
    """Placeholder until a real provider is wired in."""

    provider_name = "unconfigured"

    async def send_text(self, message: WhatsAppOutboundMessage) -> None:
        raise RuntimeError(
            "WhatsApp provider is not configured yet. "
            "Choose Meta Cloud API or Twilio in a later phase."
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> list[WhatsAppInboundMessage]:
        raise RuntimeError("WhatsApp webhook parsing is not configured yet.")

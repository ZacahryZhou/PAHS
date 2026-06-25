"""DeepSeek chat completions provider."""

from __future__ import annotations

import os
from typing import Any

import requests

from pahs.config_loader import llm_config

DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    def __init__(self) -> None:
        cfg = llm_config().get("llm", {}).get("deepseek", {})
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = str(cfg.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
        self.chat_model = str(cfg.get("chat_model", "deepseek-chat"))
        self.reasoner_model = str(cfg.get("reasoner_model", "deepseek-reasoner"))
        self.timeout = int(cfg.get("timeout_seconds", 120))
        self.max_tokens = int(cfg.get("max_tokens", 4096))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("DEEPSEEK_API_KEY is not set.")

        selected = model or self.chat_model
        if selected == "deepseek-reasoner":
            selected = self.reasoner_model

        payload = {
            "model": selected,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return {
            "content": content,
            "model": selected,
            "provider": "deepseek",
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
        }

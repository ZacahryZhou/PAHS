"""Web search tool — Perplexity (preferred), Tavily, or mock fallback."""

from __future__ import annotations

import os
from typing import Any

import requests

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
TAVILY_API_URL = "https://api.tavily.com/search"


def _resolve_provider() -> str:
    explicit = os.getenv("SEARCH_PROVIDER", "auto").strip().lower()
    if explicit in {"perplexity", "tavily", "mock", "smart"}:
        return explicit

    if os.getenv("PERPLEXITY_API_KEY", "").strip():
        return "perplexity"
    if os.getenv("TAVILY_API_KEY", "").strip():
        return "tavily"
    return "mock"


def search_web(
    query: str,
    *,
    max_results: int = 5,
    provider: str | None = None,
) -> dict[str, Any]:
    """Step 1 of Searcher: retrieve grounded research (Perplexity or Tavily)."""
    resolved = (provider or _resolve_provider()).strip().lower()
    if resolved == "smart":
        resolved = "auto"

    if resolved == "perplexity":
        return _search_perplexity(query, max_results=max_results)
    if resolved == "tavily":
        return _search_tavily(query, max_results=max_results)
    if resolved == "auto":
        if os.getenv("PERPLEXITY_API_KEY", "").strip():
            return _search_perplexity(query, max_results=max_results)
        if os.getenv("TAVILY_API_KEY", "").strip():
            return _search_tavily(query, max_results=max_results)
        return _mock_search(query, max_results=max_results)
    return _mock_search(query, max_results=max_results)


def _search_perplexity(query: str, *, max_results: int = 5) -> dict[str, Any]:
    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        fallback = _mock_search(query, max_results=max_results)
        fallback["warning"] = "PERPLEXITY_API_KEY is missing; using mock search."
        return fallback

    model = os.getenv("PERPLEXITY_MODEL", "sonar").strip() or "sonar"

    try:
        response = requests.post(
            PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a research assistant. Answer with accurate, "
                            "up-to-date information and cite sources. Prefer official docs."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        if os.getenv("TAVILY_API_KEY", "").strip():
            fallback = _search_tavily(query, max_results=max_results)
            fallback["warning"] = f"Perplexity failed, fell back to Tavily: {exc}"
            return fallback
        fallback = _mock_search(query, max_results=max_results)
        fallback["warning"] = f"Perplexity failed, using mock search: {exc}"
        return fallback

    message = (data.get("choices") or [{}])[0].get("message") or {}
    research_text = str(message.get("content") or "").strip()
    sources = _sources_from_perplexity(data, max_results=max_results)

    return {
        "provider": "perplexity",
        "model": data.get("model", model),
        "query": query,
        "sources": sources,
        "summary": research_text or _summarize_sources(query, sources),
        "research_draft": research_text,
        "usage": data.get("usage"),
    }


def _sources_from_perplexity(data: dict[str, Any], *, max_results: int) -> list[dict[str, Any]]:
    search_results = data.get("search_results") or []
    if search_results:
        sources: list[dict[str, Any]] = []
        for item in search_results[:max_results]:
            if not isinstance(item, dict):
                continue
            sources.append(
                {
                    "title": str(item.get("title") or item.get("url") or "Source"),
                    "url": str(item.get("url") or ""),
                    "snippet": str(item.get("snippet") or "")[:400],
                }
            )
        if sources:
            return sources

    citations = data.get("citations") or []
    return [
        {
            "title": url,
            "url": str(url),
            "snippet": "",
        }
        for url in citations[:max_results]
        if url
    ]


def _search_tavily(query: str, *, max_results: int = 5) -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        fallback = _mock_search(query, max_results=max_results)
        fallback["warning"] = "TAVILY_API_KEY is missing; using mock search."
        return fallback

    try:
        response = requests.post(
            TAVILY_API_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        sources = [
            {
                "title": item.get("title", "Untitled"),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:400],
            }
            for item in data.get("results", [])
        ]
        return {
            "provider": "tavily",
            "query": query,
            "sources": sources,
            "summary": _summarize_sources(query, sources),
            "research_draft": _summarize_sources(query, sources),
        }
    except Exception as exc:
        fallback = _mock_search(query, max_results=max_results)
        fallback["warning"] = f"Tavily failed, using mock search: {exc}"
        return fallback


def _mock_search(query: str, *, max_results: int = 3) -> dict[str, Any]:
    sources = [
        {
            "title": f"Mock Source {index + 1} for {query}",
            "url": f"https://example.com/search/{index + 1}",
            "snippet": f"Placeholder research snippet about {query}.",
        }
        for index in range(max_results)
    ]
    draft = _summarize_sources(query, sources)
    return {
        "provider": "mock",
        "query": query,
        "sources": sources,
        "summary": draft,
        "research_draft": draft,
        "warning": "Using mock search. Set PERPLEXITY_API_KEY or TAVILY_API_KEY in .env.",
    }


def _summarize_sources(query: str, sources: list[dict[str, Any]]) -> str:
    lines = [f"Research summary for: {query}", "", "Sources:"]
    for source in sources:
        lines.append(f"- {source['title']} ({source['url']})")
        if source.get("snippet"):
            lines.append(f"  {source['snippet']}")
    return "\n".join(lines)

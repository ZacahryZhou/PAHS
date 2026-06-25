"""Web search tool — Tavily when configured, mock otherwise."""

from __future__ import annotations

import os
from typing import Any

import requests


def search_web(query: str, *, max_results: int = 3) -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return _mock_search(query, max_results=max_results)

    try:
        response = requests.post(
            "https://api.tavily.com/search",
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
                "snippet": item.get("content", "")[:240],
            }
            for item in data.get("results", [])
        ]
        return {
            "provider": "tavily",
            "query": query,
            "sources": sources,
            "summary": _summarize_sources(query, sources),
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
    return {
        "provider": "mock",
        "query": query,
        "sources": sources,
        "summary": _summarize_sources(query, sources),
    }


def _summarize_sources(query: str, sources: list[dict[str, Any]]) -> str:
    lines = [f"Research summary for: {query}", "", "Sources:"]
    for source in sources:
        lines.append(f"- {source['title']} ({source['url']})")
        lines.append(f"  {source['snippet']}")
    return "\n".join(lines)

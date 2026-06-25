"""Route Searcher step-1 to Tavily or Perplexity based on search-task signals."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

# Perplexity strengths — each dimension adds score when detected.
_DIMENSION_PATTERNS: dict[str, tuple[str, ...]] = {
    "realtime": (
        r"\blatest\b",
        r"\bcurrent\b",
        r"\btoday\b",
        r"\bnow\b",
        r"\brecent\b",
        r"\bnews\b",
        r"\bupdate[ds]?\b",
        r"\bstock price\b",
        r"\bmarket\b",
        r"20\d{2}",
        r"实时",
        r"最新",
        r"今天",
        r"现在",
        r"近期",
        r"新闻",
        r"股价",
        r"行情",
        r"政策变化",
        r"刚刚",
    ),
    "accuracy": (
        r"\baccurate\b",
        r"\bprecise\b",
        r"\bverified\b",
        r"\bfact[- ]check",
        r"\bcitation",
        r"\bsource",
        r"准确",
        r"精确",
        r"可靠",
        r"核实",
        r"数据来源",
        r"有依据",
        r"引用来源",
    ),
    "depth": (
        r"\bin[- ]depth\b",
        r"\bcomprehensive\b",
        r"\bdetailed\b",
        r"\bthorough\b",
        r"\bresearch report\b",
        r"深入",
        r"全面",
        r"详细",
        r"深度",
        r"调研",
        r"研究报告",
        r"系统性",
    ),
    "authority": (
        r"\bofficial\b",
        r"\bdocumentation\b",
        r"\bapi doc",
        r"\bwhitepaper\b",
        r"\bgovernment\b",
        r"\buniversity\b",
        r"\bstandard\b",
        r"\brfc\b",
        r"官方",
        r"权威",
        r"官网",
        r"政府",
        r"大学",
        r"标准",
        r"白皮书",
    ),
    "synthesis": (
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bpros and cons\b",
        r"\bintegrat",
        r"\bmulti[- ]source",
        r"\bmultiple\b",
        r"\bbenchmark\b",
        r"对比",
        r"比较",
        r"综合",
        r"整合",
        r"多个方案",
        r"优缺点",
        r"竞品",
        r"选型",
    ),
}

_DIMENSION_WEIGHTS: dict[str, int] = {
    "realtime": 18,
    "accuracy": 14,
    "depth": 12,
    "authority": 16,
    "synthesis": 18,
}

# Fast definition / single-fact lookup → Tavily + step-2 LLM
_SIMPLE_PATTERNS: tuple[str, ...] = (
    r"^what is\b",
    r"^what's\b",
    r"^define\b",
    r"^explain\b",
    r"^简介",
    r"^什么是",
    r"^是什么",
    r"^什么叫",
    r"^简单介绍",
    r"定义",
)

_BASE_SCORE = 15
_SIMPLE_LOOKUP_PENALTY = 22
_PERPLEXITY_THRESHOLD = 45
_GRAY_LOW = 38
_GRAY_HIGH = 52
_MIN_PERPLEXITY_DIMENSIONS = 2


@dataclass
class SearchDimensions:
    realtime: bool = False
    accuracy: bool = False
    depth: bool = False
    authority: bool = False
    synthesis: bool = False
    hits: dict[str, list[str]] = field(default_factory=dict)

    def active_count(self) -> int:
        return sum(
            1
            for name in _DIMENSION_PATTERNS
            if getattr(self, name)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in _DIMENSION_PATTERNS
        } | {"hits": self.hits, "active_count": self.active_count()}


@dataclass
class SearchRouteDecision:
    level: str
    provider: str
    score: int
    reasons: list[str]
    method: str
    query: str
    user_task: str
    dimensions: dict[str, Any] = field(default_factory=dict)
    budget_tier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_any(text: str, patterns: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for pattern in patterns:
        if re.search(pattern, lowered, flags=re.IGNORECASE) or re.search(pattern, text):
            hits.append(pattern)
    return hits


def _detect_dimensions(text: str) -> SearchDimensions:
    dims = SearchDimensions()
    hits: dict[str, list[str]] = {}
    for name, patterns in _DIMENSION_PATTERNS.items():
        matched = _has_any(text, patterns)
        hits[name] = matched
        setattr(dims, name, bool(matched))
    dims.hits = hits
    return dims


def _available_providers() -> dict[str, bool]:
    return {
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY", "").strip()),
        "tavily": bool(os.getenv("TAVILY_API_KEY", "").strip()),
    }


def _pick_provider(*, prefer_perplexity: bool) -> tuple[str, list[str]]:
    avail = _available_providers()
    reasons: list[str] = []

    if prefer_perplexity:
        if avail["perplexity"]:
            reasons.append("Route target: Perplexity (high-signal research).")
            return "perplexity", reasons
        if avail["tavily"]:
            reasons.append("Perplexity preferred but key missing; using Tavily.")
            return "tavily", reasons
        reasons.append("No search API keys; using mock.")
        return "mock", reasons

    if avail["tavily"]:
        reasons.append("Route target: Tavily + LLM step 2 (light lookup).")
        return "tavily", reasons
    if avail["perplexity"]:
        reasons.append("Tavily preferred but key missing; using Perplexity.")
        return "perplexity", reasons
    reasons.append("No search API keys; using mock.")
    return "mock", reasons


def apply_budget_adjustment(score: int, budget_tier: str | None) -> tuple[int, list[str]]:
    """Future hook: shift threshold appetite by user budget tier.

    Not wired yet — pass budget_tier=None today.
    """
    if not budget_tier:
        return score, []

    tier = budget_tier.strip().lower()
    reasons: list[str] = []
    if tier in {"high", "premium"}:
        score += 8
        reasons.append("Budget tier high: easier Perplexity routing.")
    elif tier in {"low", "economy"}:
        score -= 10
        reasons.append("Budget tier low: favor Tavily routing.")
    elif tier in {"medium", "standard"}:
        reasons.append("Budget tier medium: neutral routing adjustment.")
    return max(0, min(100, score)), reasons


def _score_from_dimensions(dims: SearchDimensions) -> tuple[int, list[str]]:
    score = _BASE_SCORE
    reasons: list[str] = []

    for name, weight in _DIMENSION_WEIGHTS.items():
        if getattr(dims, name):
            score += weight
            label = name.replace("_", " ")
            sample = ", ".join(dims.hits.get(name, [])[:2])
            reasons.append(f"+{weight} {label}" + (f" ({sample})" if sample else ""))

    return score, reasons


def _score_search_task(
    query: str,
    *,
    user_task: str,
    routing_context: dict[str, Any] | None,
    budget_tier: str | None = None,
) -> tuple[int, list[str], SearchDimensions]:
    text = f"{user_task}\n{query}".strip()
    dims = _detect_dimensions(text)
    score, reasons = _score_from_dimensions(dims)

    simple_hits = _has_any(text, _SIMPLE_PATTERNS)
    if simple_hits and dims.active_count() == 0:
        score -= _SIMPLE_LOOKUP_PENALTY
        reasons.append(
            f"Simple lookup only (-{_SIMPLE_LOOKUP_PENALTY}): {', '.join(simple_hits[:2])}"
        )
    elif simple_hits:
        score -= min(12, 6 * len(simple_hits))
        reasons.append(f"Simple phrasing present but research signals also detected.")

    ctx = routing_context or {}
    band = str(ctx.get("complexity_band") or "")
    if band == "complex":
        score += 8
        reasons.append("Graph triage: complexity_band=complex (+8)")
    elif band == "medium":
        score += 4
        reasons.append("Graph triage: complexity_band=medium (+4)")
    elif band == "simple":
        score -= 6
        reasons.append("Graph triage: complexity_band=simple (-6)")

    if ctx.get("needs_deep_reasoning"):
        score += 6
        reasons.append("Graph triage: needs_deep_reasoning (+6)")

    score, budget_reasons = apply_budget_adjustment(score, budget_tier)
    reasons.extend(budget_reasons)

    score = max(0, min(100, score))
    return score, reasons, dims


def _prefer_perplexity(score: int, dims: SearchDimensions) -> bool:
    if dims.active_count() >= _MIN_PERPLEXITY_DIMENSIONS:
        return True
    if score >= _PERPLEXITY_THRESHOLD:
        return True
    # Single strong Perplexity-native signal (e.g. official docs only)
    if dims.authority and score >= 30:
        return True
    if dims.synthesis and score >= 30:
        return True
    if dims.realtime and score >= 33:
        return True
    return False


def _level_from_score(score: int, dims: SearchDimensions) -> str:
    if _prefer_perplexity(score, dims):
        return "deep_research"
    if score >= 28 or dims.active_count() == 1:
        return "standard"
    return "simple"


def _llm_refine_route(
    query: str,
    *,
    user_task: str,
    rule_score: int,
    dims: SearchDimensions,
    run_id: str | None,
) -> tuple[int, str, list[str], SearchDimensions] | None:
    use_llm = os.getenv("SEARCH_ROUTE_USE_LLM", "false").lower() in {"1", "true", "yes"}
    in_gray = _GRAY_LOW <= rule_score <= _GRAY_HIGH
    if not use_llm or not in_gray:
        return None

    from pahs.providers.router import llm_complete

    raw = llm_complete(
        system=(
            "You classify PAHS search routing. Return JSON only with keys: "
            "score (0-100), level (simple|standard|deep_research), reason (short string), "
            "dimensions (object with booleans: realtime, accuracy, depth, authority, synthesis). "
            "Prefer deep_research / Perplexity when the user needs fresh info, verified facts, "
            "official docs, deep research, or multi-source synthesis."
        ),
        user=(
            f"User task:\n{user_task}\n\n"
            f"Search query:\n{query}\n\n"
            f"Rule-based score: {rule_score}\n"
            f"Rule dimensions: {dims.to_dict()}"
        ),
        run_id=run_id,
        phase="search_route",
    )
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        payload = json.loads(raw[start : end + 1])
        score = int(payload.get("score", rule_score))
        level = str(payload.get("level") or _level_from_score(score, dims))
        reason = str(payload.get("reason") or "LLM route refinement.")
        llm_dims = payload.get("dimensions") or {}
        for name in _DIMENSION_PATTERNS:
            if name in llm_dims:
                setattr(dims, name, bool(llm_dims[name]))
        return max(0, min(100, score)), level, [reason], dims
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def route_search_task(
    query: str,
    *,
    user_task: str | None = None,
    routing_context: dict[str, Any] | None = None,
    run_id: str | None = None,
    budget_tier: str | None = None,
) -> SearchRouteDecision:
    """Decide Tavily vs Perplexity for Searcher step 1."""
    task = (user_task or query).strip()
    score, reasons, dims = _score_search_task(
        query,
        user_task=task,
        routing_context=routing_context,
        budget_tier=budget_tier,
    )
    method = "rule"
    level = _level_from_score(score, dims)

    refined = _llm_refine_route(
        query, user_task=task, rule_score=score, dims=dims, run_id=run_id
    )
    if refined is not None:
        score, level, llm_reasons, dims = refined
        reasons.extend(llm_reasons)
        method = "rule+llm"

    prefer_perplexity = _prefer_perplexity(score, dims) or level == "deep_research"
    provider, pick_reasons = _pick_provider(prefer_perplexity=prefer_perplexity)
    reasons.extend(pick_reasons)

    return SearchRouteDecision(
        level=level,
        provider=provider,
        score=score,
        reasons=reasons,
        method=method,
        query=query,
        user_task=task,
        dimensions=dims.to_dict(),
        budget_tier=budget_tier,
    )

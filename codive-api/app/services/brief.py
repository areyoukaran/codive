from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.llm import ASK_SYSTEM_PROMPT, TemplateProvider, get_llm_provider


def compute_counters(*, pulls: list[dict], issues: list[dict], runs: list[dict]) -> dict:
    open_prs = [p for p in pulls if p.get("state") == "open" and not p.get("is_draft")]
    waiting = [p for p in open_prs if p.get("review_decision") in (None, "none", "changes_requested")]
    failing = [r for r in runs[:10] if r.get("status") == "failing"]
    stale_issues = [i for i in issues if i.get("state") == "open" and i.get("age_days", 0) >= 21]
    return {
        "open_prs": len(open_prs),
        "waiting_on_you": len(waiting),
        "ci_failures": len({r.get("workflow_name") for r in failing}),
        "stale_issues": len(stale_issues),
    }


def _template_lede(counters: dict, top_item: dict | None) -> str:
    parts = []
    if counters["waiting_on_you"]:
        parts.append(f"{counters['waiting_on_you']} pull request{'s are' if counters['waiting_on_you'] != 1 else ' is'} waiting on you")
    if counters["ci_failures"]:
        parts.append(f"{counters['ci_failures']} workflow{'s are' if counters['ci_failures'] != 1 else ' is'} failing on main")
    if not parts:
        return "Nothing urgent since your last visit — a quiet morning."
    lede = "Since you last looked: " + ", and ".join(parts) + "."
    if top_item:
        lede += f" Start with {top_item.get('repo', '')}#{top_item.get('number', '')}."
    return lede


async def generate_lede(*, counters: dict, top_items: list[dict]) -> tuple[str, str]:
    """Returns (lede_text, generated_by). Falls back to the template lede on
    any provider error — a brief must never fail to render."""
    provider = get_llm_provider()
    if isinstance(provider, TemplateProvider):
        return _template_lede(counters, top_items[0] if top_items else None), "template"
    try:
        user_prompt = (
            "Write the opening line of a developer's morning brief from this state. "
            "Two sentences maximum, under 45 words, plain declarative prose, no greeting, "
            "no markdown, no emoji. Name a specific repository or PR number where it matters. "
            "Lead with whatever needs action today.\n\nSTATE:\n"
            f"counters={counters}\ntop_items={top_items[:5]}"
        )
        text = await provider.complete(ASK_SYSTEM_PROMPT, user_prompt, max_tokens=120)
        return text, provider.name
    except Exception:  # noqa: BLE001
        return _template_lede(counters, top_items[0] if top_items else None), "template"

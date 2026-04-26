"""
AI Narrative Layer for NPI Readiness Assessment.

This module wraps Anthropic Claude API to generate executive narrative,
recommended actions, and confidence flagging. It is called AFTER the
deterministic rules engine has produced flagged items.

Design principle: AI explains the data, it does not invent the rubric.
The rules engine provides facts. The LLM provides synthesis.
"""

import json
import os
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # type: ignore


SYSTEM_PROMPT = """You are an experienced NPI Program Manager assistant.
You are reviewing the output of a deterministic readiness assessment for a hardware phase-gate review.

Your job is to:
1. Synthesize the flagged items into a 2-3 sentence executive summary.
2. For each flagged item, recommend a concrete next action (one short sentence).
3. Flag any item where the data is ambiguous and requires human judgment.

You MUST NOT:
- Invent gate criteria. The rubric is fixed and was already applied.
- Change the GREEN/YELLOW/RED status of any category. That decision is the rules engine's.
- Add risks not present in the input data.
- Use jargon without grounding it in the specific flagged item.

Output STRICTLY as JSON in this schema:

{
  "executive_summary": "2-3 sentences for an exec audience.",
  "recommendations": [
    {
      "flagged_item": "short label of the item",
      "recommended_action": "one-sentence next action",
      "owner_role": "who should drive it (e.g., Quality Lead, ME Lead)",
      "confidence": "HIGH | MEDIUM | LOW",
      "confidence_reason": "why you have this confidence level"
    }
  ],
  "ambiguity_flags": [
    {
      "item": "what is ambiguous",
      "human_judgment_needed": "what a human should verify"
    }
  ]
}

Return only the JSON. No preamble, no markdown fencing."""


def build_user_message(rules_output: dict) -> str:
    """Format the rules engine output into a structured message for Claude."""
    lines = [
        f"Phase Gate: {rules_output['gate']}",
        f"Overall Status (from rules engine): {rules_output['overall_status']}",
        "",
        "Flagged items by category:",
        "",
    ]

    for cat in rules_output["categories"]:
        lines.append(f"--- {cat['category']} : {cat['status']} ---")
        for finding in cat["findings"]:
            lines.append(f"  Finding: {finding}")
        for item in cat["flagged_items"]:
            keys = list(item.keys())
            label = item.get(keys[0], "")
            issue = item.get("issue", "")
            detail = item.get("detail", "")
            lines.append(f"  - [{label}] {issue} | {detail}")
        lines.append("")

    lines.append(
        "Generate the executive summary, per-item recommendations, "
        "and ambiguity flags as specified."
    )
    return "\n".join(lines)


def generate_narrative(
    rules_output: dict,
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-7",
) -> dict:
    """
    Call Claude API to generate executive narrative and recommendations.

    Falls back to a deterministic mock if no API key is set, so the demo
    always works for portfolio review even without API credentials.
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key is None or Anthropic is None:
        return _mock_narrative(rules_output)

    client = Anthropic(api_key=api_key)
    user_message = build_user_message(rules_output)

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text and parse as JSON
    text = response.content[0].text.strip()

    # Defensive: strip markdown fencing if model adds it despite instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        # If parsing fails, return a structured error rather than crashing the report
        return {
            "executive_summary": (
                "AI narrative generation returned malformed output. "
                "See rules-engine output for the underlying findings."
            ),
            "recommendations": [],
            "ambiguity_flags": [
                {"item": "AI parsing failure", "human_judgment_needed": str(e)}
            ],
        }

    return parsed


def _mock_narrative(rules_output: dict) -> dict:
    """
    Deterministic fallback narrative for offline / no-API-key demo mode.

    Generates a useful summary directly from the rules output without an LLM.
    This keeps the demo functional for resume reviewers who clone the repo.
    """
    overall = rules_output["overall_status"]
    cats = rules_output["categories"]

    flagged_total = sum(len(c["flagged_items"]) for c in cats)
    red_cats = [c["category"] for c in cats if c["status"] == "RED"]
    yellow_cats = [c["category"] for c in cats if c["status"] == "YELLOW"]

    if overall == "RED":
        summary = (
            f"Gate {rules_output['gate']} is NOT READY. "
            f"{len(red_cats)} category(ies) at RED: {', '.join(red_cats)}. "
            f"{flagged_total} items require attention before signoff."
        )
    elif overall == "YELLOW":
        summary = (
            f"Gate {rules_output['gate']} is conditionally ready. "
            f"{len(yellow_cats)} category(ies) at YELLOW. "
            f"Review {flagged_total} flagged items and accept residual risk before proceeding."
        )
    else:
        summary = (
            f"Gate {rules_output['gate']} is GREEN across all categories. "
            f"Proceed with standard signoff."
        )

    recs = []
    for cat in cats:
        for item in cat["flagged_items"]:
            label = next(iter(item.values()), "item")
            issue = item.get("issue", "")
            recs.append({
                "flagged_item": f"{label}: {issue}",
                "recommended_action": _suggest_action(cat["category"], item),
                "owner_role": _suggest_owner(cat["category"]),
                "confidence": "MEDIUM",
                "confidence_reason": (
                    "Mock narrative mode (no LLM). Recommendation derived from "
                    "category type and issue keywords."
                ),
            })

    return {
        "executive_summary": summary,
        "recommendations": recs,
        "ambiguity_flags": [],
    }


def _suggest_action(category: str, item: dict) -> str:
    issue = item.get("issue", "").lower()
    if "ppap" in issue and "quality" in issue:
        return "Pull-in quality review with supplier before gate signoff."
    if "ppap" in issue:
        return "Drive supplier to PPAP completion or accept conditional risk."
    if "lifecycle" in issue or "rev" in issue:
        return "Confirm revision lock and lifecycle promotion before build kickoff."
    if "p1" in issue.lower() or "P1" in item.get("severity", ""):
        return "Escalate to gate review; gate cannot proceed without resolution."
    if "insufficient resolution" in issue:
        return "Verify closure with the listed owner before accepting."
    return "Review with the responsible cross-functional lead and document decision."


def _suggest_owner(category: str) -> str:
    return {
        "BOM Stability": "BOM / Component Engineering Lead",
        "Supplier Readiness": "Supplier Quality Engineer",
        "DFM Closure": "Manufacturing Engineering Lead",
    }.get(category, "Program Manager")


if __name__ == "__main__":
    from rules_engine import assess_gate_readiness

    rules_out = assess_gate_readiness(
        "data/bom.csv", "data/suppliers.csv", "data/dfm_issues.csv", gate="PVT"
    )
    narrative = generate_narrative(rules_out)
    print(json.dumps(narrative, indent=2))

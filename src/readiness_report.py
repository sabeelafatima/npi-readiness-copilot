"""
Readiness Report Orchestrator.

Ties the deterministic rules engine and the AI narrative layer together,
emits a human-readable phase-gate readiness report.
"""

import argparse
import json
from pathlib import Path

from rules_engine import assess_gate_readiness
from ai_narrative import generate_narrative


STATUS_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}


def render_text_report(rules_out: dict, narrative: dict) -> str:
    """Render a CLI-friendly phase-gate readiness report."""
    lines = []
    bar = "═" * 65
    lines.append(bar)
    lines.append(f"  {rules_out['gate']} GATE READINESS REPORT")
    lines.append(bar)
    lines.append("")

    overall = rules_out["overall_status"]
    label_map = {
        "GREEN": "GREEN (proceed with standard signoff)",
        "YELLOW": "YELLOW (proceed with risk acceptance)",
        "RED": "RED (NOT ready, hold gate)",
    }
    lines.append(f"OVERALL: {STATUS_EMOJI[overall]} {label_map[overall]}")
    lines.append("")

    for cat in rules_out["categories"]:
        emoji = STATUS_EMOJI[cat["status"]]
        lines.append(
            f"{cat['category']:<22} {emoji} {cat['status']:<7} "
            f"(score {cat['score']:.0%})"
        )
    lines.append("")

    if narrative.get("executive_summary"):
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 65)
        lines.append(narrative["executive_summary"])
        lines.append("")

    if narrative.get("recommendations"):
        lines.append("KEY RECOMMENDATIONS")
        lines.append("-" * 65)
        for rec in narrative["recommendations"][:8]:
            lines.append(f"  - {rec['flagged_item']}")
            lines.append(f"    Action: {rec['recommended_action']}")
            lines.append(
                f"    Owner: {rec['owner_role']} | "
                f"Confidence: {rec['confidence']}"
            )
            lines.append("")

    if narrative.get("ambiguity_flags"):
        lines.append("AMBIGUITY FLAGS (requires human judgment)")
        lines.append("-" * 65)
        for flag in narrative["ambiguity_flags"]:
            lines.append(f"  - {flag['item']}")
            lines.append(f"    Verify: {flag['human_judgment_needed']}")
        lines.append("")

    lines.append(bar)
    return "\n".join(lines)


def run(gate: str, data_dir: str = "data", output: str = None) -> dict:
    base = Path(data_dir)
    rules_out = assess_gate_readiness(
        str(base / "bom.csv"),
        str(base / "suppliers.csv"),
        str(base / "dfm_issues.csv"),
        gate=gate,
    )
    narrative = generate_narrative(rules_out)

    report = {
        "rules_output": rules_out,
        "narrative": narrative,
    }

    if output:
        Path(output).write_text(json.dumps(report, indent=2, default=str))

    print(render_text_report(rules_out, narrative))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", choices=["DVT", "PVT", "MP"], default="PVT")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    args = parser.parse_args()
    run(args.gate, args.data_dir, args.output)

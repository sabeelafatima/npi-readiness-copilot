"""
Rules Engine for NPI Readiness Assessment.

This module contains the deterministic scoring logic. It does NOT call an LLM.
Gate decisions are based on hard thresholds, configurable per gate type.

Design principle: AI handles narrative and ambiguity. Rules handle thresholds.
A phase-gate decision should never rest on an LLM alone.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
import pandas as pd

Status = Literal["GREEN", "YELLOW", "RED"]


@dataclass
class CategoryScore:
    category: str
    status: Status
    score: float  # 0.0 to 1.0
    findings: list[str]
    flagged_items: list[dict]


# Gate-specific thresholds. Tunable per product class in production.
GATE_THRESHOLDS = {
    "DVT": {
        "bom_revision_lock_min": 0.70,
        "supplier_ppap_approved_min": 0.50,
        "supplier_otd_min": 80.0,
        "dfm_p1_open_max": 3,
        "dfm_p2_open_max": 8,
    },
    "PVT": {
        "bom_revision_lock_min": 0.90,
        "supplier_ppap_approved_min": 0.85,
        "supplier_otd_min": 88.0,
        "dfm_p1_open_max": 1,
        "dfm_p2_open_max": 4,
    },
    "MP": {
        "bom_revision_lock_min": 1.00,
        "supplier_ppap_approved_min": 1.00,
        "supplier_otd_min": 92.0,
        "dfm_p1_open_max": 0,
        "dfm_p2_open_max": 1,
    },
}


def score_bom(bom_df: pd.DataFrame, gate: str) -> CategoryScore:
    """Score BOM stability for the given gate."""
    thresholds = GATE_THRESHOLDS[gate]
    total = len(bom_df)

    # Revision lock check: any BOM line with notes suggesting active rev change is flagged
    in_flux_mask = bom_df["notes"].fillna("").str.contains(
        "rev change|not locked|in flux|active rev", case=False, regex=True
    )
    locked_count = total - in_flux_mask.sum()
    locked_pct = locked_count / total

    # NPI lifecycle parts on a PVT or MP gate are flagged
    npi_parts = bom_df[bom_df["lifecycle_status"] == "NPI"]

    # Single-source critical parts
    single_source = bom_df[bom_df["second_source"] == "No"]

    findings = []
    flagged = []

    if locked_pct < thresholds["bom_revision_lock_min"]:
        findings.append(
            f"BOM revision lock at {locked_pct:.0%}, "
            f"below {thresholds['bom_revision_lock_min']:.0%} threshold for {gate}"
        )
        for _, row in bom_df[in_flux_mask].iterrows():
            flagged.append({
                "part": row["part_number"],
                "issue": "Revision in flux",
                "detail": row["notes"],
            })

    if gate in ("PVT", "MP") and len(npi_parts) > 0:
        findings.append(
            f"{len(npi_parts)} parts still in NPI lifecycle status at {gate} gate"
        )
        for _, row in npi_parts.iterrows():
            flagged.append({
                "part": row["part_number"],
                "issue": "Lifecycle status NPI at production gate",
                "detail": row["description"],
            })

    if len(single_source) > 0:
        findings.append(
            f"{len(single_source)} single-source parts identified, supply risk"
        )

    # Status determination
    if locked_pct < thresholds["bom_revision_lock_min"] - 0.10:
        status: Status = "RED"
    elif locked_pct < thresholds["bom_revision_lock_min"]:
        status = "YELLOW"
    elif gate in ("PVT", "MP") and len(npi_parts) > 0:
        status = "YELLOW"
    else:
        status = "GREEN"

    return CategoryScore(
        category="BOM Stability",
        status=status,
        score=locked_pct,
        findings=findings,
        flagged_items=flagged,
    )


def score_suppliers(supplier_df: pd.DataFrame, gate: str) -> CategoryScore:
    """Score supplier readiness for the given gate."""
    thresholds = GATE_THRESHOLDS[gate]
    total = len(supplier_df)

    approved = supplier_df[supplier_df["ppap_status"] == "Approved"]
    approved_pct = len(approved) / total

    avg_otd = supplier_df["on_time_delivery_pct"].mean()

    # The interesting case: PPAP approved but with quality issues
    conflict_suppliers = supplier_df[
        (supplier_df["ppap_status"] == "Approved")
        & (supplier_df["quality_escapes_60d"] >= 3)
    ]

    findings = []
    flagged = []

    if approved_pct < thresholds["supplier_ppap_approved_min"]:
        findings.append(
            f"PPAP approval at {approved_pct:.0%}, "
            f"below {thresholds['supplier_ppap_approved_min']:.0%} threshold for {gate}"
        )

    if avg_otd < thresholds["supplier_otd_min"]:
        findings.append(
            f"Average on-time delivery at {avg_otd:.1f}%, "
            f"below {thresholds['supplier_otd_min']:.1f}% threshold"
        )

    for _, row in conflict_suppliers.iterrows():
        flagged.append({
            "supplier": row["supplier_name"],
            "issue": "PPAP approved but quality escapes elevated",
            "detail": (
                f"{int(row['quality_escapes_60d'])} escapes in last 60d, "
                f"OTD {row['on_time_delivery_pct']:.1f}%"
            ),
        })

    pending = supplier_df[supplier_df["ppap_status"].isin(["Pending", "Conditional"])]
    for _, row in pending.iterrows():
        flagged.append({
            "supplier": row["supplier_name"],
            "issue": f"PPAP {row['ppap_status'].lower()}",
            "detail": row["notes"] if pd.notna(row["notes"]) else "No detail",
        })

    if approved_pct < thresholds["supplier_ppap_approved_min"] - 0.10:
        status: Status = "RED"
    elif approved_pct < thresholds["supplier_ppap_approved_min"] or len(conflict_suppliers) > 0:
        status = "YELLOW"
    else:
        status = "GREEN"

    return CategoryScore(
        category="Supplier Readiness",
        status=status,
        score=approved_pct,
        findings=findings,
        flagged_items=flagged,
    )


def score_dfm(dfm_df: pd.DataFrame, gate: str) -> CategoryScore:
    """Score DFM closure status for the given gate."""
    thresholds = GATE_THRESHOLDS[gate]

    open_issues = dfm_df[dfm_df["status"] == "Open"]
    p1_open = open_issues[open_issues["severity"] == "P1"]
    p2_open = open_issues[open_issues["severity"] == "P2"]

    # Ambiguous closures: closed with very short resolution notes
    closed = dfm_df[dfm_df["status"] == "Closed"]
    ambiguous_closures = closed[
        closed["resolution_notes"].fillna("").str.len() < 15
    ]

    total = len(dfm_df)
    closure_rate = len(closed) / total if total > 0 else 0

    findings = []
    flagged = []

    if len(p1_open) > thresholds["dfm_p1_open_max"]:
        findings.append(
            f"{len(p1_open)} P1 issues open, "
            f"threshold for {gate} is {thresholds['dfm_p1_open_max']}"
        )

    if len(p2_open) > thresholds["dfm_p2_open_max"]:
        findings.append(
            f"{len(p2_open)} P2 issues open, "
            f"threshold for {gate} is {thresholds['dfm_p2_open_max']}"
        )

    for _, row in p1_open.iterrows():
        flagged.append({
            "issue_id": row["issue_id"],
            "severity": row["severity"],
            "issue": row["description"],
            "detail": f"Open since {row['opened_date']}, owner {row['owner']}",
        })

    for _, row in ambiguous_closures.iterrows():
        flagged.append({
            "issue_id": row["issue_id"],
            "severity": row["severity"],
            "issue": "Closed with insufficient resolution detail",
            "detail": (
                f"{row['description']} | "
                f"resolution: '{row['resolution_notes']}'"
            ),
        })

    if len(p1_open) > thresholds["dfm_p1_open_max"]:
        status: Status = "RED"
    elif len(p2_open) > thresholds["dfm_p2_open_max"] or len(ambiguous_closures) > 0:
        status = "YELLOW"
    else:
        status = "GREEN"

    return CategoryScore(
        category="DFM Closure",
        status=status,
        score=closure_rate,
        findings=findings,
        flagged_items=flagged,
    )


def overall_status(scores: list[CategoryScore]) -> Status:
    """Roll up category statuses to an overall gate status."""
    statuses = [s.status for s in scores]
    if "RED" in statuses:
        return "RED"
    if "YELLOW" in statuses:
        return "YELLOW"
    return "GREEN"


def assess_gate_readiness(
    bom_path: str,
    suppliers_path: str,
    dfm_path: str,
    gate: str = "PVT",
) -> dict:
    """
    Run the full deterministic readiness assessment.

    Returns a dict with category scores, flagged items, and overall status.
    No LLM calls are made here. This is the trust-the-numbers layer.
    """
    if gate not in GATE_THRESHOLDS:
        raise ValueError(f"Unknown gate {gate}. Use one of {list(GATE_THRESHOLDS)}")

    bom_df = pd.read_csv(bom_path)
    supplier_df = pd.read_csv(suppliers_path)
    dfm_df = pd.read_csv(dfm_path)

    scores = [
        score_bom(bom_df, gate),
        score_suppliers(supplier_df, gate),
        score_dfm(dfm_df, gate),
    ]

    return {
        "gate": gate,
        "overall_status": overall_status(scores),
        "categories": [
            {
                "category": s.category,
                "status": s.status,
                "score": s.score,
                "findings": s.findings,
                "flagged_items": s.flagged_items,
            }
            for s in scores
        ],
        "assessed_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import json
    result = assess_gate_readiness(
        "data/bom.csv",
        "data/suppliers.csv",
        "data/dfm_issues.csv",
        gate="PVT",
    )
    print(json.dumps(result, indent=2, default=str))

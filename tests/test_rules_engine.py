"""
Unit tests for the rules engine.

Run with:
    python -m pytest tests/

These tests exist to make the rules engine behavior interview-defensible.
For each test, you should be able to explain what the test is verifying
and why it matters for a real NPI gate review.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from rules_engine import (
    score_bom,
    score_suppliers,
    score_dfm,
    overall_status,
    GATE_THRESHOLDS,
    CategoryScore,
)


def test_overall_status_red_dominates() -> None:
    """If any category is RED, overall is RED. This is a hard gate rule."""
    scores = [
        CategoryScore("A", "GREEN", 1.0, [], []),
        CategoryScore("B", "RED", 0.5, [], []),
        CategoryScore("C", "GREEN", 1.0, [], []),
    ]
    assert overall_status(scores) == "RED"


def test_overall_status_yellow_when_no_red() -> None:
    scores = [
        CategoryScore("A", "GREEN", 1.0, [], []),
        CategoryScore("B", "YELLOW", 0.85, [], []),
    ]
    assert overall_status(scores) == "YELLOW"


def test_overall_status_green_only_when_all_green() -> None:
    scores = [
        CategoryScore("A", "GREEN", 1.0, [], []),
        CategoryScore("B", "GREEN", 0.95, [], []),
    ]
    assert overall_status(scores) == "GREEN"


def test_supplier_conflict_flagged() -> None:
    """The PPAP-approved-but-failing-quality case must be surfaced."""
    df = pd.DataFrame([{
        "supplier_id": "MFG-X",
        "supplier_name": "Test Supplier",
        "region": "APAC",
        "category": "Test",
        "ppap_status": "Approved",
        "ppap_approval_date": "2025-08-15",
        "on_time_delivery_pct": 80.0,
        "quality_escapes_60d": 4,
        "capacity_confirmed": "Yes",
        "relationship_years": 3,
        "notes": "",
    }])
    result = score_suppliers(df, "PVT")
    flagged = [item["issue"] for item in result.flagged_items]
    assert any("quality escapes elevated" in f for f in flagged)


def test_dfm_ambiguous_closure_flagged() -> None:
    """Closed issue with one-word resolution must be flagged for verification."""
    df = pd.DataFrame([
        {
            "issue_id": "DFM-X",
            "severity": "P2",
            "category": "Test",
            "description": "Test issue",
            "opened_date": "2025-09-01",
            "status": "Closed",
            "closed_date": "2025-09-15",
            "owner": "Owner",
            "resolution_notes": "Closed",
        }
    ])
    result = score_dfm(df, "PVT")
    flagged = [item["issue"] for item in result.flagged_items]
    assert any("insufficient resolution detail" in f for f in flagged)


def test_gate_thresholds_strictest_at_mp() -> None:
    """MP gate thresholds must be at least as strict as PVT, which is at least as strict as DVT."""
    assert (
        GATE_THRESHOLDS["DVT"]["bom_revision_lock_min"]
        <= GATE_THRESHOLDS["PVT"]["bom_revision_lock_min"]
        <= GATE_THRESHOLDS["MP"]["bom_revision_lock_min"]
    )
    assert (
        GATE_THRESHOLDS["DVT"]["dfm_p1_open_max"]
        >= GATE_THRESHOLDS["PVT"]["dfm_p1_open_max"]
        >= GATE_THRESHOLDS["MP"]["dfm_p1_open_max"]
    )

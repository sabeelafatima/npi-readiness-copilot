"""
Streamlit Demo App for NPI Readiness Copilot.

Run with:
    streamlit run src/streamlit_app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from rules_engine import assess_gate_readiness  # noqa: E402
from ai_narrative import generate_narrative  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"


STATUS_COLOR = {
    "GREEN": "#16a34a",
    "YELLOW": "#eab308",
    "RED": "#dc2626",
}


def status_badge(status: str) -> str:
    color = STATUS_COLOR.get(status, "#6b7280")
    return (
        f"<span style='background-color:{color};color:white;"
        f"padding:4px 12px;border-radius:12px;font-weight:600;'>"
        f"{status}</span>"
    )


def main() -> None:
    st.set_page_config(
        page_title="NPI Readiness Copilot",
        page_icon="🛠️",
        layout="wide",
    )

    st.title("🛠️ NPI Readiness Copilot")
    st.caption(
        "AI-augmented phase-gate readiness assessment for hardware NPI programs. "
        "All data is synthetic."
    )

    with st.sidebar:
        st.header("Configuration")
        gate = st.selectbox("Phase Gate", ["DVT", "PVT", "MP"], index=1)
        st.markdown("---")
        st.markdown("**Data Sources**")
        st.markdown("- BOM CSV (30 parts)")
        st.markdown("- Supplier CSV (15 suppliers)")
        st.markdown("- DFM Issues CSV (20 issues)")
        st.markdown("---")
        st.caption(
            "AI narrative uses Claude API if `ANTHROPIC_API_KEY` is set, "
            "otherwise falls back to a deterministic mock so the demo always works."
        )
        run_button = st.button("Run Readiness Assessment", type="primary")

    if not run_button:
        st.info("Select a gate and click 'Run Readiness Assessment' in the sidebar.")
        st.markdown("### How this works")
        st.markdown(
            """
1. **Deterministic rules engine** scores BOM, suppliers, and DFM against gate-specific thresholds.
2. **AI narrative layer** synthesizes flagged items into an executive summary and recommended actions.
3. **The AI does not change the rules engine's status decisions.** That separation is the design.
            """
        )
        return

    with st.spinner("Running deterministic rules engine..."):
        rules_out = assess_gate_readiness(
            str(DATA_DIR / "bom.csv"),
            str(DATA_DIR / "suppliers.csv"),
            str(DATA_DIR / "dfm_issues.csv"),
            gate=gate,
        )

    with st.spinner("Generating AI narrative..."):
        narrative = generate_narrative(rules_out)

    st.markdown("## Overall Status")
    st.markdown(
        f"**Gate {gate}**: {status_badge(rules_out['overall_status'])}",
        unsafe_allow_html=True,
    )
    st.write("")

    cols = st.columns(3)
    for col, cat in zip(cols, rules_out["categories"]):
        with col:
            st.markdown(f"**{cat['category']}**")
            st.markdown(status_badge(cat["status"]), unsafe_allow_html=True)
            st.metric("Score", f"{cat['score']:.0%}")

    st.markdown("---")
    st.markdown("## Executive Summary")
    st.write(narrative.get("executive_summary", ""))

    st.markdown("## Flagged Items by Category")
    for cat in rules_out["categories"]:
        if not cat["flagged_items"]:
            continue
        with st.expander(
            f"{cat['category']} - {cat['status']} ({len(cat['flagged_items'])} items)",
            expanded=cat["status"] == "RED",
        ):
            df = pd.DataFrame(cat["flagged_items"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("## Recommendations")
    if narrative.get("recommendations"):
        rec_df = pd.DataFrame(narrative["recommendations"])
        st.dataframe(rec_df, use_container_width=True, hide_index=True)
    else:
        st.write("No recommendations.")

    if narrative.get("ambiguity_flags"):
        st.markdown("## Ambiguity Flags")
        st.warning("These items require human judgment:")
        for flag in narrative["ambiguity_flags"]:
            st.write(f"- **{flag['item']}**: {flag['human_judgment_needed']}")

    with st.expander("Raw JSON output"):
        st.json({"rules_output": rules_out, "narrative": narrative})


if __name__ == "__main__":
    main()

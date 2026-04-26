# NPI Readiness Copilot

> An AI-augmented phase-gate readiness assessment tool for hardware New Product Introduction programs.

**Status**: v1 prototype, active build
**Author**: Sabeela Fatima
**Stack**: Python, Anthropic Claude API, Streamlit, Power BI

---

## The Problem This Solves

In hardware New Product Introduction (NPI) programs, phase-gate reviews are the single most important checkpoint between concept and ramp. A typical Phase Gate review (DVT to PVT, or PVT to MP) requires the Program Manager to manually verify readiness across:

- **Bill of Materials (BOM) stability**: revision lock, second-source coverage, lifecycle status
- **Supplier readiness**: PPAP status, capacity confirmation, on-time delivery history
- **Design for Manufacturability (DFM)**: signoffs from manufacturing engineering, identified risks
- **Test coverage**: ATE program readiness, yield baseline
- **Tooling and fixturing**: status, lead times, capacity

In a traditional NPI org, this prep takes a Program Manager 6-10 hours per gate, scattered across spreadsheets, supplier portals, email threads, and tribal knowledge. The cost of a missed signal is high: late-stage escalations, build slips, and ramp delays measured in weeks of revenue.

This tool automates the readiness assessment. Given structured inputs from BOM, supplier, and DFM data sources, it produces a gate-readiness report with red/yellow/green flags per category, recommended actions, and a confidence-weighted risk summary suitable for an executive gate review.

## Why AI

The 80/20 of gate prep is rule-based: thresholds on PPAP completion, BOM revision count, DFM open issues. That part doesn't need AI.

The remaining 20% is where AI earns its place: synthesizing free-text supplier notes, reasoning over conflicting signals (a supplier passed PPAP but has 3 quality escapes in the last 60 days), and translating raw status into stakeholder-ready narrative. That's where Claude API is used in this project.

The system is deliberately designed so AI handles narrative and ambiguity, while deterministic logic handles thresholds and red flags. This is important: a phase-gate decision should never rest on an LLM alone.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT DATA SOURCES                       │
│  BOM CSV    │   Supplier CSV   │   DFM Issues CSV          │
└──────┬──────────────┬──────────────────┬────────────────────┘
       │              │                  │
       ▼              ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│            DETERMINISTIC RULES ENGINE (Python)              │
│  - BOM stability score (revision count, lifecycle flags)    │
│  - Supplier readiness score (PPAP %, on-time delivery %)    │
│  - DFM closure rate (open vs. closed issues by severity)    │
│  - Per-category thresholds → red / yellow / green           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                AI NARRATIVE LAYER (Claude API)              │
│  - Synthesizes flagged items into exec summary              │
│  - Recommends actions per red flag                          │
│  - Confidence flagging on ambiguous signals                 │
│  - Outputs structured JSON → consumed by UI                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUT LAYER                             │
│  - Streamlit dashboard (interactive demo)                   │
│  - Power BI report (exec view, optional)                    │
│  - JSON export (for downstream automation)                  │
└─────────────────────────────────────────────────────────────┘
```

**Key design choice**: The AI never makes the gate decision. It explains the data the rules engine flagged. This separation is the difference between a defensible system and a black box.

## Synthetic Data

All data in this repo is synthetic. It models industry-typical NPI workflows but does not represent any real company, supplier, or product.

The dataset includes:

- **30-part BOM** with mix of mature, NPI, and end-of-life components
- **15 suppliers** with varied PPAP status, geographic distribution (APAC / EMEA / Americas), and quality history
- **20 DFM issues** across severity tiers, with realistic open/closed mix

Realistic ugliness intentionally injected:
- One supplier with PPAP marked "Approved" but 4 quality escapes in last 60 days (conflict)
- Two BOM line items with active revisions in flux
- Three DFM issues marked closed with one-line resolution notes (ambiguous)

This intentional messiness is what makes the AI layer valuable. Clean data doesn't need an LLM.

See [`docs/synthetic_data_methodology.md`](docs/synthetic_data_methodology.md) for the full data design rationale.

## Project Structure

```
npi-readiness-copilot/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── data/
│   ├── bom.csv                       # Synthetic BOM
│   ├── suppliers.csv                 # Synthetic supplier data
│   └── dfm_issues.csv                # Synthetic DFM issues
├── src/
│   ├── rules_engine.py               # Deterministic scoring
│   ├── ai_narrative.py               # Claude API integration
│   ├── readiness_report.py           # Orchestrator
│   └── streamlit_app.py              # Interactive demo UI
├── docs/
│   ├── architecture.md               # Detailed architecture
│   ├── synthetic_data_methodology.md # Data design rationale
│   ├── prompt_design.md              # Prompt engineering choices
│   └── failed_approaches.md          # What didn't work and why
└── tests/
    └── test_rules_engine.py          # Unit tests for scoring
```

## How to Run

```bash
# Clone and install
git clone https://github.com/sabeela/npi-readiness-copilot.git
cd npi-readiness-copilot
pip install -r requirements.txt

# Set your Claude API key
export ANTHROPIC_API_KEY="your_key_here"

# Run CLI version
python src/readiness_report.py --gate PVT

# Run interactive Streamlit demo
streamlit run src/streamlit_app.py
```

## Sample Output

For the included synthetic dataset at the PVT gate:

```
═══════════════════════════════════════════════════════════
  PVT GATE READINESS REPORT
═══════════════════════════════════════════════════════════

OVERALL: 🟡 YELLOW (proceed with risk acceptance)

BOM STABILITY:        🟢 GREEN  (28/30 parts revision-locked)
SUPPLIER READINESS:   🟡 YELLOW (12/15 PPAP approved, 1 conflict)
DFM CLOSURE:          🟡 YELLOW (3 P2 issues open)

KEY RISKS:
  • Supplier MFG-007: PPAP approved but 4 quality escapes in last 60d.
    Recommended: pull-in quality review before gate signoff.
  • DFM-014: marked closed but resolution unclear in record.
    Recommended: verify with ME lead before proceeding.
  • BOM line 23: active revision in flux as of 4 days ago.
    Recommended: confirm rev lock before build kickoff.

═══════════════════════════════════════════════════════════
```

## What I Learned Building This

(See [`docs/failed_approaches.md`](docs/failed_approaches.md) for the longer version.)

Three things worth calling out:

1. **My first prompt let Claude invent gate criteria.** I had to restructure the system prompt to pass the gate rubric in explicitly and have Claude reason over it, not generate it. This is the most important design decision in the project.

2. **JSON-structured output beat free-text every time.** The first version asked Claude for a narrative summary and parsed it. Brittle. Switching to a strict JSON schema with field validation reduced parsing failures from ~15% to under 1%.

3. **Confidence flagging matters more than I expected.** When Claude flags its own uncertainty (e.g., "this DFM resolution note is ambiguous"), it lets the PM know where to spend their human attention. This is the actual product insight: AI as a triage tool for human judgment, not a replacement for it.

## What's Next

- [ ] Add "diff since last gate" view (what changed)
- [ ] Slack integration to post readiness summary to a channel
- [ ] Multi-gate support (DVT, PVT, MP) with gate-specific rubrics
- [ ] Per-supplier deep dive with external risk signals (financial, geopolitical)

## Honest Limitations

- Synthetic data is modeled on industry patterns, not validated against real fab/contract-manufacturer datasets
- Gate criteria are illustrative; real programs would tune thresholds per product class
- Claude API calls add latency (~3-5 seconds per report); production version would cache and batch
- This is a prototype. It demonstrates the pattern. It is not a production-ready tool.

## License

MIT. Synthetic data and prompt templates are free to adapt. If you build something on top of this, I'd love to hear about it.

---

**Built by Sabeela Fatima** | [LinkedIn](https://linkedin.com/in/sabeela-fatima) | [Portfolio](https://...)

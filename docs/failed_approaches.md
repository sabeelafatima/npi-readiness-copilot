# Failed Approaches: What Didn't Work and Why

This document is the most useful one in the repo for an interviewer. It records what I tried, what broke, and what I changed. If you're hiring me, this is where you see how I think.

---

## 1. Letting the LLM Generate Gate Criteria

**What I tried first.** My first prompt was something like: "You are an NPI program manager. Given this BOM, supplier, and DFM data, assess the readiness for a PVT gate."

**Why it broke.** Claude generated plausible-sounding gate criteria that varied between runs. One run flagged single-source parts as a P1 issue, another treated them as informational. For a phase-gate review, this is unacceptable: the rubric must be stable.

**What I changed.** Restructured the system entirely. The deterministic rules engine now owns the rubric. Thresholds are codified per gate (`GATE_THRESHOLDS` in `rules_engine.py`). Claude only operates on the output of the rules engine, generating narrative and recommendations. The system prompt now explicitly states: "You MUST NOT invent gate criteria. The rubric is fixed and was already applied."

**Lesson.** AI handles narrative and ambiguity. Rules handle thresholds. A phase-gate decision should never rest on an LLM alone.

---

## 2. Free-Text Narrative Output

**What I tried first.** Asked Claude to return a markdown-formatted executive summary and bulleted recommendations.

**Why it broke.** Roughly 1 in 7 outputs had structural variations: missing sections, extra preambles ("Here is the summary..."), reordered fields. Parsing this into the dashboard was fragile.

**What I changed.** Switched to a strict JSON schema with explicit field names. The system prompt ends with the schema and "Return only the JSON. No preamble, no markdown fencing." Added defensive parsing that strips ` ```json ` fences if Claude adds them anyway.

**Lesson.** For any AI output that downstream code consumes, structured JSON beats free text every time. Parse failures dropped from ~15% to under 1%.

---

## 3. No Confidence Flagging

**What I tried first.** Each AI recommendation was treated as equally trustworthy.

**Why it broke.** When testing on the synthetic dataset, I noticed the AI made confident-sounding recommendations even on ambiguous data (like DFM-014, the issue closed with the resolution note "Closed"). A PM reading the report had no signal that some items needed extra human verification.

**What I changed.** Added a `confidence` field per recommendation (HIGH/MEDIUM/LOW) and an `ambiguity_flags` array for items where human judgment is needed. The system prompt explicitly asks Claude to flag its own uncertainty.

**Lesson.** Confidence flagging is the actual product insight. The AI doesn't replace human judgment, it triages where human attention should go. This was the most useful change for making the tool feel like a real PM aid instead of a decoration.

---

## 4. Caching and Latency

**What I tried first.** Re-running the AI narrative on every dashboard interaction.

**Why it broke.** Each Claude API call is 3-5 seconds. The Streamlit demo felt sluggish, especially when changing the gate selection.

**What I changed (partially).** For now, the Streamlit demo runs the assessment only when the user clicks the button. A production version would cache results keyed on the data hash + gate selection, and only invalidate when source data changes.

**Lesson.** AI calls are expensive in latency, not just dollars. Design the UX around when fresh AI synthesis is actually needed, not as a default.

---

## 5. The Conflict Case (PPAP Approved + Quality Escapes)

**What I tried first.** Treated PPAP status and quality escapes as independent variables.

**Why it broke.** Supplier MFG-007 (EastBay Magnetics) has PPAP "Approved" but 4 quality escapes in the last 60 days and 78.5% on-time delivery. A naive scoring model marked them GREEN on PPAP and didn't surface the contradiction.

**What I changed.** Added a conflict detection rule in `score_suppliers()`: "PPAP approved AND quality_escapes_60d >= 3" triggers an explicit flagged item with the message "PPAP approved but quality escapes elevated." The AI narrative then synthesizes this into a recommendation to "pull-in quality review with supplier before gate signoff."

**Lesson.** The interesting cases in NPI data are almost always conflicts between dimensions. Scoring each dimension independently misses the most important risks. This is the kind of pattern a real PM would catch but a generic dashboard would not.

---

## What I'd Do Next

If I had another weekend:

1. **Diff view since last gate.** Show what changed (new flagged items, items that closed, items that worsened).
2. **Sensitivity analysis.** "What changes if Supplier X goes down for 4 weeks?"
3. **Real prompt eval harness.** Right now I tested prompts manually. A small eval set with golden outputs would catch regressions.

These aren't done because the goal of this prototype is to demonstrate the system design, not to ship a production tool. The honest scope is: this proves the pattern works on a representative dataset.

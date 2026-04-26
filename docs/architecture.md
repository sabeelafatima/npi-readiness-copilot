# Architecture Deep Dive

## The Two-Layer Pattern

Every interesting AI-augmented PM tool I've thought about lives or dies on this question: where does deterministic logic end and where does the LLM begin?

For NPI readiness, the answer is:

| Concern | Layer | Why |
|---------|-------|-----|
| Gate rubric definition | Rules engine (config) | Must be stable, auditable, version-controlled |
| Threshold checks | Rules engine | Deterministic, testable, fast |
| Status (R/Y/G) | Rules engine | This is the gate decision; never an LLM |
| Conflict detection (multi-dimension) | Rules engine | Patterns are codifiable |
| Narrative synthesis | AI layer | LLM strength: reading scattered data into one summary |
| Recommended actions | AI layer | Context-sensitive, benefits from world knowledge |
| Confidence flagging | AI layer | "Where should a human look?" is a judgment call |

Anything that affects the gate decision is in the rules engine. Anything that helps a human understand or act on the rules engine output is in the AI layer.

## Data Flow

```
1. Source CSVs (or in production: PLM/ERP/QMS API pulls)
                  │
                  ▼
2. Rules Engine (rules_engine.py)
   - Parses CSV
   - Applies per-gate thresholds
   - Detects conflict patterns
   - Returns: CategoryScore objects + overall_status
                  │
                  ▼
3. AI Narrative Layer (ai_narrative.py)
   - Formats rules output into structured user message
   - Calls Claude with system prompt + user message
   - Parses JSON response
   - Falls back to deterministic mock if no API key
                  │
                  ▼
4. Renderer (readiness_report.py or streamlit_app.py)
   - Combines rules output + narrative
   - Emits text report (CLI) or interactive UI (Streamlit)
   - Optional: JSON export for downstream automation
```

## Key Design Decisions and Tradeoffs

### Decision 1: Hand-crafted synthetic data instead of generated

**Tradeoff**: Less scalable, but more defensible in interviews.

**Why**: I can point to any row in the dataset and explain why it's there. A randomly generated dataset would force me to either (a) admit I don't know what's in it or (b) claim properties I can't verify. The hand-crafted version makes every edge case intentional.

### Decision 2: Mock fallback when no API key is set

**Tradeoff**: More code complexity, but the demo always works.

**Why**: Anyone reviewing my GitHub repo (a recruiter, a hiring manager) shouldn't need to set up an API key to see the tool in action. The mock generates real recommendations from the rules output, just without the LLM polish. Same architecture, deterministic output.

### Decision 3: JSON-only output from the LLM

**Tradeoff**: Slightly more rigid prompts, but eliminates parsing failures.

**Why**: Free-text LLM output is brittle to consume. A strict JSON schema with explicit field names cuts the parse-failure rate from ~15% to under 1%. The cost is one extra paragraph in the system prompt.

### Decision 4: Gate-aware thresholds

**Tradeoff**: More config, but matches how real NPI programs work.

**Why**: A 70% PPAP completion is fine for DVT, conditional at PVT, unacceptable at MP. A single threshold across gates would either over-flag early or under-flag late. The `GATE_THRESHOLDS` dict lets each gate have its own rubric.

### Decision 5: No streaming responses

**Tradeoff**: Slightly higher perceived latency, but simpler integration.

**Why**: The narrative is consumed atomically, not streamed to a chat interface. Streaming would add complexity without UX benefit for this use case.

## What This Architecture Buys You

1. **Auditable gate decisions.** Every R/Y/G can be traced to a specific threshold in `GATE_THRESHOLDS` and a specific row of source data. No "the AI decided" handwaving.
2. **AI is replaceable.** Swap Claude for GPT, Gemini, Llama, or no LLM at all (mock mode), no rules engine changes.
3. **Testable.** The rules engine has unit tests. The AI layer has structural assertions. Real prompt evals are the next step.
4. **Honest scope.** The demo demonstrates the pattern. It does not claim to be production-ready.

## What This Architecture Does Not Do

1. No real-time data ingestion. Source CSVs are static. A production version would pull from PLM/ERP/QMS APIs.
2. No multi-product support. The synthetic dataset is one product. Multi-tenancy and product-specific rubrics are out of scope.
3. No historical comparison. The "diff since last gate" view is on the next-iteration list.
4. No write-back. The tool reads data, generates a report. It does not update any source system.

These are intentional scope cuts, not oversights.

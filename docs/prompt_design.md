# Prompt Design Choices

## The Core Decision

Claude is asked to do exactly three things, in this order:

1. Synthesize flagged items into a 2-3 sentence executive summary.
2. Recommend an action per flagged item.
3. Flag where the data is ambiguous and a human should look.

It is explicitly told NOT to:

- Invent gate criteria
- Change category status (GREEN/YELLOW/RED)
- Add risks not present in the input data
- Use jargon without grounding it in the specific item

This is the most important design choice in the whole project. Without it, Claude will hallucinate plausible-sounding gate criteria that vary between runs.

## The System Prompt

See `src/ai_narrative.py` for the production version. Key elements:

- **Role grounding**: "You are an experienced NPI Program Manager assistant."
- **Hard constraints in `MUST NOT` form**: explicit, capitalized.
- **Output schema as JSON**: every field named, optional vs. required clear.
- **Final instruction**: "Return only the JSON. No preamble, no markdown fencing."

## The User Message Format

The rules engine output is converted into a structured user message. Format:

```
Phase Gate: PVT
Overall Status (from rules engine): RED

Flagged items by category:

--- BOM Stability : YELLOW ---
  Finding: 6 parts still in NPI lifecycle status at PVT gate
  - [IC-103] Lifecycle status NPI at production gate | Bluetooth LE Module
  - [SEN-302] Lifecycle status NPI at production gate | Pressure Sensor
  ...

--- Supplier Readiness : YELLOW ---
  - [EastBay Magnetics] PPAP approved but quality escapes elevated | 4 escapes in last 60d, OTD 78.5%
  ...
```

Why this format:

- **Pre-grouped by category** so Claude doesn't have to do that work.
- **One item per line** with consistent delimiter, easy for the model to parse.
- **Status already provided** so Claude knows what the rules decided and won't try to re-decide it.

## Confidence Flagging

The schema requires every recommendation to have a `confidence` (HIGH/MEDIUM/LOW) and a `confidence_reason`. This forces Claude to think about uncertainty rather than producing equally-confident output for every item.

## Failure Modes Handled

1. **Markdown fencing despite instructions**: defensive parser strips ` ```json ` if present.
2. **Malformed JSON**: parser returns a structured error rather than crashing the report.
3. **No API key available**: falls back to a deterministic mock so the demo works for portfolio reviewers without credentials.

## What I'd Add Next

1. **Eval harness**: a small set of (input rules output, expected narrative shape) test cases with assertions.
2. **Prompt versioning**: tag the prompt with a version, log which version produced which output.
3. **Few-shot examples**: include 1-2 example outputs in the system prompt for shape consistency.

These are deferred because the goal of the prototype is to demonstrate the architecture, not to ship a production prompt.

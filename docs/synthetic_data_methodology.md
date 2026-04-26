# Synthetic Data Methodology

This document explains how the synthetic data in this repo was constructed, what real-world distributions it mimics, and what edge cases were intentionally injected.

This is here for one reason: an interviewer who looks at the data should be able to verify that I think about test data the way a PM thinks about a real dataset. Random data is easy. Believable data with the right edge cases is the actual signal.

---

## Design Goals

1. **Representative scale.** ~30-part BOM, ~15 suppliers, ~20 DFM issues. Big enough to feel like a real product, small enough to read end-to-end.
2. **Industry-typical structure.** Field names and value distributions modeled on what a typical hardware product (consumer-grade IoT or wearable) would have at PVT gate.
3. **Intentional ugliness.** At least one realistic edge case per category that a naive readiness check would miss.
4. **No real company data.** All supplier names, part numbers, and identifiers are fabricated.

---

## BOM Design

The 30-part BOM structure mirrors a typical small-form-factor connected device:

| Category | Part Count | Rationale |
|----------|------------|-----------|
| PCB / PCBA | 2 | Main board + daughterboard |
| Integrated Circuits | 3 | SoC, PMIC, BLE module |
| Memory | 2 | DDR + NAND |
| Sensors | 3 | IMU, pressure, hall-effect |
| Connectors | 3 | USB-C, B2B, FPC |
| Passives | 6 | Generic R/C/L + crystals |
| Display | 1 | Single-source long-lead |
| Battery | 1 | Li-Po |
| Mechanical | 3 | Housing top/bottom, light pipe |
| Labels / Packaging / Accessories | 6 | Standard ramp components |

### Intentional edge cases in the BOM

- **ENC-801 (Plastic Housing Top)**: notes contain "Tooling change in progress, rev not locked". This is the BOM-instability flag, models a common late-PVT scenario where mechanical tooling slips.
- **CON-403 (FPC 30pin)**: notes contain "Active rev change in progress". Tests the regex matching on revision-flux signals.
- **6 parts marked "NPI" lifecycle status while assessing PVT gate**: tests the gate-aware logic that flags non-production lifecycle parts at production gates.
- **8 single-source parts**: tests that single-source risk surfaces but does not by itself cause a RED flag.

---

## Supplier Design

15 suppliers across 3 regions (APAC majority, reflecting hardware reality), 8 categories.

### Intentional edge cases in supplier data

- **MFG-007 (EastBay Magnetics)**: PPAP status "Approved" but `quality_escapes_60d = 4` and OTD 78.5%. **This is the headline conflict case.** A naive PPAP-only check would mark this supplier as ready. A PM who has worked an NPI cycle would see "approved on paper, struggling in practice" instantly. Tests whether the system surfaces multi-dimensional risk.
- **MFG-013 (FormFlex Plastics)**: PPAP status "Pending", relationship 1 year, OTD 82.4%. Tests handling of explicitly not-ready suppliers and missing PPAP date fields.
- **MFG-006 (Sensorium Tech)**: PPAP "Conditional" with capacity "Pending". Tests the middle-ground case where supplier is making progress but not gate-ready.
- **MFG-011 (DisplayWorks)**: PPAP approved but capacity "Conditional" for Q1 ramp. Models a supplier ready for PVT but not for MP.

### Distributions

- OTD ranges from 78.5% to 99.0%, mean ~91%. Realistic for a mid-volume consumer product supplier base.
- Quality escapes range 0-4 in 60 days. Most suppliers at 0-1.
- Relationship years range 1-10. Mix of strategic and new suppliers.

---

## DFM Issues Design

20 issues across 4 categories (Assembly, Mechanical, Test, Cosmetic) and 3 severity tiers (P1, P2, P3).

### Closure status mix at "PVT gate" snapshot

- **14 closed, 6 open**. A real PVT gate would typically have most early issues closed but some active workstream items.
- **2 P1 open** (DFM-013 sensor yield, DFM-017 firmware download fail). Both block PVT under the rubric.
- **3 P2 open** (DFM-005 BGA wetting, DFM-007 FPC routing, DFM-010 battery seating, DFM-012 humidity yield). Realistic mid-investigation states.

### Intentional edge cases

- **DFM-014**: marked "Closed" with resolution note "Closed". This is the **ambiguous closure case**. A real PM would catch this and ask "closed how?" The rules engine flags any closed issue with resolution_notes shorter than 15 characters.
- **DFM-009**: closed with note "Within spec; closed as acceptable". Models a legitimate "closed because we accepted it" scenario, distinct from genuinely-resolved issues.
- **DFM-016**: closed with note "Within Pantone tolerance per QA; accepted". Same pattern, different category.
- **DFM-005**: P2 open with detailed investigation note ("Zone 4 temperature variance"). Models an actively-worked issue that should not be flagged as ambiguous.

---

## What Real Data Would Add

If this were instantiated against a real fab + contract-manufacturer dataset, the following would change:

1. **BOM size**: real consumer products have 50-300 line items, not 30. Scaling tested separately.
2. **Supplier metadata depth**: real PPAP packages contain Cpk values, dimensional reports, FAI data. This synthetic version stops at the status flag.
3. **DFM issue descriptions**: real issues contain images, CAD references, correlation data. Text-only descriptions here are the simplification.
4. **Time series**: real readiness assessments compare current snapshot to last gate. A "diff view" is on the next-iteration list.

---

## How to Regenerate or Extend

The data is hand-crafted, not generated by a script, because hand-crafting forces the realistic edge cases. A future pass could parameterize a generator:

```python
# Pseudocode for a generator
generate_bom(
    n_parts=30,
    npi_lifecycle_pct=0.20,
    single_source_pct=0.25,
    in_flux_pct=0.07,
)
```

But for the prototype, the hand-crafted approach is more defensible in interviews. I can point to any line and say "I put that there because..." which I cannot do for randomly generated rows.

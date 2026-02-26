# AxNano Smart-Feed Algorithm v9 — Open Technical Questions

> **Purpose**: Reference document for discussions with reactor design engineers and chemistry faculty  
> **Date**: 2026-02-26  
> **Context**: MVP stage — these questions directly affect the reliability of algorithm outputs  
> **Codebase**: `smart_feed_v9/` (Python, ~600 LOC)

---

## A. Questions for Reactor Design Engineer

### A1. Simultaneous Equation Physical Premise ⭐ Highest Priority

**Current model** (`gatekeeper.py → calc_throughput`):

```
W = F_total / (1 + r_water + r_diesel + r_naoh)
```

All external inputs (water, diesel, NaOH) share the F_total = 11 L/min pipeline capacity with waste feed. This means every liter of diesel or NaOH added displaces a liter of waste throughput.

**Question**: Does diesel enter the reactor through an independent injection nozzle (not consuming F_total), or is it mixed into the feed stream? Same question for NaOH and DI water.

If diesel has a dedicated injector, r_diesel should not appear in the denominator, and the throughput and cost model changes fundamentally.

**Need to confirm**:
- Which external inputs share the main feed line (consuming F_total)?
- Which have independent injection points (not consuming F_total)?
- What physically controls F_total — pump speed, valve position, or something else?

---

### A2. Uniform Density Assumption (ρ ≈ 1 kg/L)

**Current model** (`models.py`, assumption «A8»): All volume-mass conversions assume density = 1 kg/L.

**Problem**: Actual waste densities vary significantly:

| Material | Estimated ρ (kg/L) |
|----------|-------------------|
| Resin (100% solid) | 1.1–1.4 (bulk) |
| 35% NaOH solution | ~1.38 |
| Caustic waste | >1.0 |
| AFFF solution | ~1.0 |
| Diesel | ~0.85 |

This affects:
- **BTU calculation**: BTU/lb is mass-based, but W is computed in L/min → mass throughput is over/underestimated depending on actual density
- **Runtime**: `runtime = Q_phase(L) / W(L/min)` — if the pump moves volume, this is correct; if it moves mass, it's wrong
- **BTU dilution formula**: `BTU_eff = BTU_blend / (1 + r_water)` divides by volume ratio, but BTU/lb is a mass-based unit

**Need to confirm**:
- Does the reactor pump control volumetric flow or mass flow?
- Is heat balance calculated on a mass or volume basis?
- For 100% solid waste like Resin, what does "quantity_L = 200" represent operationally — 200 liters of bulk volume? Slurry after pre-mixing?

---

### A3. Is F_total a Hard Constraint or a Soft Range?

**Current model**: F_total = 11.0 L/min as a fixed constant.

**Documented**: Observed range 9.4–11.4 L/min across historical runs.

**Question**: Does F_total fluctuate with mixture viscosity, solid content, temperature, or back-pressure? If so, the throughput calculation needs a correction factor or a range rather than a single value.

**Need to confirm**:
- Primary drivers of F_total variation
- What operating conditions correspond to the 9.4 vs 11.4 extremes?
- Should the algorithm use a conservative (lower) F_total for safety?

---

### A4. Physical Meaning of Solid_max = 15%

**Current model** (`gatekeeper.py → calc_r_water`): Add water to dilute solid content to ≤ 15%.

**Question**: What does 15% refer to?
- Solid content limit before the high-pressure pump (pumpability limit)?
- Solid content inside the reactor (reaction efficiency)?
- Solid content at reactor outlet (clogging/plugging risk)?

The location of water addition matters — if water is added before the pump, it clearly consumes F_total. If inside the reactor, it may have a separate injection point.

**Need to confirm**:
- Source of the 15% limit (equipment manual? operating experience? regulatory?)
- Physical location of water addition in the process flow
- Whether different solid types (organic vs inorganic) have different limits

---

### A5. BTU_target = 2200 — Threshold or Optimum?

**Current model** (`gatekeeper.py → calc_r_diesel`): When effective BTU falls below 2200, diesel is added to make up the difference.

**Question**: Is 2200 BTU/lb the minimum for self-sustaining reaction (below which the reactor quenches), or the optimal operating point? What happens if the actual BTU is slightly below — gradual efficiency loss, or abrupt failure?

**Need to confirm**:
- Origin and physical meaning of 2200 BTU/lb
- Consequence severity if feed falls below this value
- Whether there's a safe operating band (e.g., 2000–2500) rather than a single threshold

---

### A6. Linearity of BTU and Solid% Blending

**Current model** (`blending.py → blend_linear`): BTU, Solid%, Salt ppm, and F ppm are all computed as volume-weighted linear averages.

**Question**: When blending Resin (100% solid, BTU=12500) with AFFF (liquid, BTU=1), the two-phase solid-liquid system's effective heat value may not be linearly additive. The solid may not combust at the same rate as a homogeneous liquid feed. Similarly, linear mixing of Solid% ignores potential dissolution effects.

**Need to confirm**:
- Does linear BTU blending hold for solid-liquid mixtures in SCWO conditions?
- Is there empirical data on actual BTU recovery vs predicted BTU for blended feeds?
- Does Salt ppm change during mixing (e.g., NaF precipitation when high-F waste meets high-Na waste)?

---

## B. Questions for Chemistry Professor

### B1. pH Blending Model ⭐ Highest Priority

**Current model** (`blending.py → blend_pH`):

```python
h_blend = Σ(10^(-pH_i) × ratio_i) / Σ(ratio_i)
pH_blend = -log10(h_blend)
```

Volume-weighted average of [H⁺] concentration, then convert back to pH.

**Problems**:

1. **Only accounts for [H⁺], ignores [OH⁻]**: When mixing Caustic (pH=13.5, [OH⁻] ≈ 0.3 M) with Resin (pH=3.0, [H⁺] = 0.001 M), the actual result depends on the neutralization reaction H⁺ + OH⁻ → H₂O. The current model takes `10^(-13.5)` as the [H⁺] contribution from Caustic, which is astronomically small and essentially ignores the massive [OH⁻] present.

2. **Buffer systems ignored**: The code comments acknowledge this. Waste streams with high F ppm contain HF (a weak acid, Ka ≈ 6.6×10⁻⁴), forming an HF/F⁻ buffer system. Actual pH changes upon mixing will be much smaller than the model predicts.

3. **Resin at pH=3 with 15000 ppm F**: At pH 3, most fluorine exists as molecular HF rather than dissociated H⁺ + F⁻. Using pH alone to represent acidity severely underestimates the total acid content. The reservoir of undissociated HF means that adding NaOH will cause pH to rise much more slowly than a strong-acid model predicts.

**Need to discuss**:
- Is there a practical correction for [H⁺]-only blending when mixing across the neutral point (acid + base)?
- How significant is the HF buffer effect at the concentration levels in these wastes?
- Would a titration-curve-based model be more appropriate, or is the current model acceptable as a first approximation for SCWO pre-treatment?

---

### B2. NaOH Demand Chemical Model

**Current model** (`gatekeeper.py → calc_r_naoh`):

```python
acid_load = f_ppm × K_F_TO_ACID           # F → acid equivalents (meq/L)
base_load = max(0, (pH - 7)) × K_PH_TO_BASE   # alkaline contribution (meq/L)
net_acid  = max(0, acid_load - base_load)
r_naoh    = net_acid × K_ACID_TO_NAOH_VOL      # NaOH volume per L waste
```

Three fitted constants:

| Constant | Value | Derivation |
|----------|-------|------------|
| K_F_TO_ACID | 0.053 meq/(L·ppm) | Stoichiometric: 1 ppm F⁻ = 1 mg/L, MW=19 → 0.053 mmol/L |
| K_PH_TO_BASE | 50.0 meq/(L·pH unit) | **No derivation — estimated** |
| K_ACID_TO_NAOH_VOL | 8.28×10⁻⁵ L/meq | Theoretical: 35% NaOH = 12075 meq/L → 1/12075 |

**Chemical issues**:

1. **K_F_TO_ACID assumes all F exists as HF needing 1:1 NaOH neutralization.** In reality:
   - F may exist in multiple forms: F⁻, HF, HF₂⁻, metal fluoride complexes
   - Under SCWO conditions (374°C+, 22+ MPa), fluorine chemistry may be entirely different from ambient
   - Some F may already be neutralized (as NaF, CaF₂) and not require additional NaOH

2. **K_PH_TO_BASE = 50 is a linear model for a logarithmic relationship.** The model says each pH unit above 7 contributes 50 meq/L of base capacity. But actual [OH⁻] is exponential:
   - pH 8: [OH⁻] = 10⁻⁶ M = 0.001 meq/L
   - pH 10: [OH⁻] = 10⁻⁴ M = 0.1 meq/L
   - pH 13: [OH⁻] = 10⁻¹ M = 100 meq/L

   A linear model with K=50 would predict pH 8 → 50 meq/L and pH 13 → 300 meq/L. The actual values span 5 orders of magnitude. This constant may work acceptably in a narrow pH range but will produce large errors across the 7–13.5 range present in these wastes.

3. **What is NaOH actually for in SCWO?** The model assumes NaOH neutralizes acid from fluorine. But in SCWO, NaOH may serve multiple purposes:
   - Preventing HF corrosion of reactor internals (Hastelloy, Inconel)
   - Converting F to soluble NaF rather than corrosive HF
   - Maintaining pH in a safe range for reactor metallurgy
   - Controlling salt precipitation behavior

   If corrosion prevention is the primary driver, the NaOH requirement might be stoichiometric to total F (not just "net acid"), regardless of the feed pH.

**Need to discuss**:
- Is the F → acid → NaOH chain the correct chemical model, or should NaOH be dosed stoichiometrically to total F content?
- Can you help derive a physically meaningful K_PH_TO_BASE, or should this term be replaced with a [OH⁻]-based calculation?
- Under SCWO conditions, does F chemistry change so fundamentally that ambient-condition models are unreliable?

---

### B3. Fitting the Three K Constants

K_F_TO_ACID has a stoichiometric derivation. K_ACID_TO_NAOH_VOL has a clear physical basis (35% NaOH concentration). But K_PH_TO_BASE = 50 has no derivation.

**Need to discuss**:
- Is there an experiment or calculation method to calibrate these three values?
- Can we use existing AxNano operational logs (input waste properties + actual NaOH consumption) to back-calculate K values?
- At minimum, are the orders of magnitude reasonable?

---

## C. Cross-Cutting Questions (Both Parties)

### C1. pH_min / pH_max Enforcement Gap

**Current state** (`models.py` defines pH_min=6, pH_max=9; flagged as P1 bug):

The gatekeeper only checks `pH > pH_max` (rejects overly alkaline blends). It never checks `pH < pH_min`. Meanwhile, the NaOH model only neutralizes F-derived acid — it does not attempt to raise pH to the safe range.

**Consequence**: A blend with pH=3.0 but low F ppm will have near-zero NaOH addition and enter the reactor at pH 3. The algorithm considers this "feasible."

**For engineer**: Is operating at pH 3 acceptable? What are the corrosion/safety implications?  
**For professor**: Should the NaOH model include a term to raise pH to pH_min regardless of F content?

---

### C2. Role of Moisture% in the Model

**Current model** (assumption «A9»): Moisture% is display-only, not used in calculations. The rationale is that its effects are captured by BTU (wet waste has lower heat value) and Solid% (wet waste has lower solid content).

**Question**: Water content directly affects the SCWO reaction system — supercritical water is the reaction medium. High-moisture waste (AFFF at 99.5%) may not need additional water to achieve supercritical conditions. Is this already implicit in the r_water calculation, or is there a missing link?

**For engineer**: Does the reactor need a minimum water fraction in the feed to maintain supercritical conditions?  
**For professor**: Is there a thermodynamic relationship between feed moisture and the water addition needed for SCWO?

---

### C3. Salt Behavior During Mixing

**Current model**: Salt ppm blends linearly. No chemical interaction considered.

**Question**: When Caustic waste (8000 ppm salt, likely NaCl or Na₂SO₄) mixes with high-F waste (Resin at 15000 ppm F), NaF precipitation may occur (NaF solubility ≈ 42 g/L at 25°C, much lower under SCWO conditions). This would:
- Reduce effective salt ppm (good for the salt constraint)
- Reduce effective F ppm (good for NaOH demand)
- But create solid precipitates (bad for the solid constraint and potential plugging)

**For engineer**: Have you observed salt precipitation or plugging when processing high-F + high-Na feeds?  
**For professor**: Under pre-mixing conditions (ambient T/P), is NaF precipitation likely at these concentrations?

---

## D. Summary: Priority Ranking

| # | Question | Audience | Impact on Algorithm | Priority |
|---|----------|----------|---------------------|----------|
| A1 | Does diesel share F_total? | Engineer | Changes core throughput equation | ⭐⭐⭐ |
| B2 | NaOH chemical model validity | Professor | Changes NaOH cost calculation | ⭐⭐⭐ |
| B1 | pH blending with buffers | Professor | Changes blend feasibility filtering | ⭐⭐⭐ |
| A2 | Density ≈ 1 assumption | Engineer | Changes throughput + runtime | ⭐⭐ |
| C1 | pH_min not enforced | Both | Safety concern | ⭐⭐ |
| B3 | K constant calibration | Professor | Accuracy of NaOH cost | ⭐⭐ |
| A3 | F_total fixed vs variable | Engineer | Model robustness | ⭐ |
| A4 | Solid_max physical meaning | Engineer | Water addition model | ⭐ |
| A5 | BTU_target meaning | Engineer | Diesel addition model | ⭐ |
| A6 | Linear blending validity | Engineer | Blend property accuracy | ⭐ |
| C2 | Moisture% role | Both | Potential missing term | ⭐ |
| C3 | Salt precipitation | Both | Constraint interaction | ⭐ |

---

## E. Reference: Current Algorithm Flow

```
User Input (waste streams with BTU, pH, F ppm, Solid%, Salt ppm)
    │
    ▼
Blend Properties (linear avg + [H⁺] pH)        ← B1, A6 affect this
    │
    ▼
Gatekeeper:
    r_water  = max(solid_dilution, salt_dilution)       ← A4 affects this
    BTU_eff  = BTU_blend / (1 + r_water)                ← A2 affects this
    r_diesel = (BTU_target - BTU_eff) / (BTU_diesel × η)    ← A5 affects this
    r_naoh   = (F_acid - pH_base) × K_vol               ← B2, B3 affect this
    │
    ▼
Throughput:
    W = F_total / (1 + r_water + r_diesel + r_naoh)     ← A1, A3 affect this
    │
    ▼
Cost = f(W, r_water, r_diesel, r_naoh, runtime)
```

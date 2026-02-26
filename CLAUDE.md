# CLAUDE.md — AxNano Smart-Feed Algorithm v9

## Overview

Multi-phase feed optimization algorithm for SCWO (Supercritical Water Oxidation) reactors. Reduces operating costs by intelligently blending complementary waste streams. Core insight: different wastes have complementary properties (e.g. high BTU + low BTU, acidic + alkaline, solid + liquid); blending significantly reduces external inputs (diesel, NaOH, water), thereby increasing throughput, shortening runtime, and lowering total cost.

MVP prototype, aiming to validate product viability with exact search optimization for ≤5 waste streams.

## Usage

```bash
# Use default input (input/example_input.json)
python -m smart_feed_v9

# Specify a file in the input/ directory
python -m smart_feed_v9 --input my_waste.json

# Adjust parameters
python -m smart_feed_v9 --input my_waste.json --F_total 10.5 --eta 0.85

# Run tests
python -m pytest tests/ -v
```

Input files go in the `input/` directory; reports are auto-saved to the `report/` directory.

## Project Structure

```
code/                        Project root (VSCode workspace)
├── CLAUDE.md                Project documentation
├── pyproject.toml           pytest configuration
├── input/                   Input files directory
│   ├── example_input.json   Default input (3 streams: Resin + AFFF + Caustic)
│   ├── test_4streams.json   4-stream test
│   └── test_5streams.json   5-stream test
├── report/                  Report output directory (auto-generated)
│   └── report_YYYYMMDD_HHMMSS.txt
├── smart_feed_v9/           Algorithm package
│   ├── models.py            Data structures (WasteStream user-required, SystemConfig tunable with defaults)
│   ├── blending.py          Blend property calculations (linear blending + pH via [H⁺] concentration)
│   ├── gatekeeper.py        Core engine: r_water → r_diesel → r_naoh → W → cost
│   ├── baseline.py          Baseline: solo processing cost per stream
│   ├── ratios.py            Ratio enumeration: GCD=1, sum≤11
│   ├── search.py            Recursive search: pre-computed templates + B&B + Memo + sorted exploration
│   ├── reporter.py          Formatted report output (6 sections)
│   ├── __init__.py          Public API + input validation
│   └── __main__.py          CLI entry + JSON loading + parameter overrides + report saving
└── tests/                   Test suite (23 tests)
    ├── conftest.py          pytest path configuration
    └── test_core.py         blending / gatekeeper / search core tests
```

## Core Algorithm Flow

1. User provides waste inventory (each stream: ID, quantity, BTU, pH, F ppm, Solid%, Salt ppm, Moisture%)
2. Baseline: process each stream solo, compute total cost as benchmark
3. Pre-compute: evaluate all (subset × ratio) blend properties and Gatekeeper results, filter infeasible combos, store as templates
4. Recursive search: enumerate all feasible multi-phase feed plans (templates × inventory → cost-sorted → B&B pruning → recurse)
5. Select the globally lowest-cost schedule
6. Output: optimal plan + baseline comparison + safety report, printed to terminal + saved to file

## Key Design Decisions

- **r_water computed first**: computation order r_water → BTU_eff → r_diesel → r_naoh eliminates circular dependencies
- **BTU_eff dilution**: `BTU_eff = BTU_blend / (1 + r_water)`, all water addition dilutes BTU
- **pH blending**: uses [H⁺] concentration method `pH = -log10(Σ(10^(-pH_i) × r_i) / Σr_i)`, not linear average
- **r_naoh chemical model**: acid_load(F ppm) - base_load(pH>7) = net_acid → NaOH volume
- **Baseline has no W_min floor**: allows extremely high costs to demonstrate blending optimization value
- **Active threshold 0.5L**: inventory < 0.5L treated as depleted, eliminates degenerate phases from floating-point residuals
- **Ratio order-sensitive**: (1,2) ≠ (2,1), representing different blending schemes
- **Parameter priority**: CLI > JSON config > SystemConfig defaults

## Search Strategy

### Search Space Control (3 Bounds + 2 Pruning)

- **Bound 1**: ratio sum ≤ ratio_sum_max (default 11)
- **Bound 2**: GCD = 1 (remove proportionally-scaled duplicates)
- **Bound 3**: depth ≤ N (N streams → max N phases, each phase exhausts at least one stream)
- **Prune 1**: pH > pH_max or W < W_min → filtered once during pre-computation
- **Prune 2**: phase.cost ≥ best_sub_cost → local B&B pruning (break after sort)

### Performance Optimizations

1. **Pre-computed templates**: blend properties, Gatekeeper rates, throughput are inventory-independent, evaluated once and stored as `_PhaseTemplate`
2. **Template quota**: keep only the 30 lowest cost_per_batch templates per subset, reducing branching factor
3. **cost_per_batch**: pre-computed cost rate, search-time cost = `num_batches × cost_per_batch` (one multiply)
4. **Sorted exploration**: candidates sorted by cost ascending at each node, cheapest first, break on first exceed
5. **Integer memo**: `round(qty, 0)` rounds inventory to nearest liter, merging nearby states

### Memoization Correctness

`_search(inv, depth)` returns **sub-problem cost** (min cost from current inventory to depletion), excluding the caller's cost_so_far. B&B pruning condition `phase.cost >= best_sub_cost` is purely local; memo cached values are independent of call path.

### Performance Benchmarks

| Input | Time | Savings |
|-------|------|---------|
| 3 streams | 0.01s | ~47% |
| 4 streams | 0.8s | ~36% |
| 5 streams | ~60s | ~41% |

## Parameters Pending Fitting

The following three K values need fitting from operational data; current values are theoretical estimates:
- `K_F_TO_ACID = 0.053` — F ppm → acid equivalent (meq/L·ppm)
- `K_PH_TO_BASE = 50.0` — pH base contribution (meq/L·pH_unit)
- `K_ACID_TO_NAOH_VOL = 8.28e-5` — acid → NaOH volume (L/meq), theoretically derived

## Unit Conventions

- Volume: L | Flow rate: L/min | Time: internal min, output converted to hr
- Heat value: BTU/lb | Mass: assumes ρ ≈ 1 kg/L «A8»
- Cost: $ | Power: kW

## References

- v9 flowchart: smart_feed_flowchart_v9.html (complete algorithm architecture diagram)
- 9 MVP assumptions labeled «A1»–«A9» throughout all code comments

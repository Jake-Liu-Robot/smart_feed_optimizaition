"""
AxNano Smart-Feed Algorithm v9 — Recursive Search Engine
==========================================================
Step 4: Enumerate all feasible multi-phase feed plans
        using 3 bounds + 2 pruning + memoization

Search strategy:
  Bound 1: ratio sum ≤ ratio_sum_max
  Bound 2: GCD = 1 (deduplication)
  Bound 3: depth ≤ N (max N phases for N streams)
  Prune 1: W < W_min or pH > pH_max → filtered once during pre-computation
  Prune 2: phase.cost ≥ best_sub_cost → local B&B pruning (break after sort)
  Memo:    cache sub-problem optimal solutions (return value is sub-problem
           cost, independent of external context)

P0 fix notes:
  _search returns sub-problem cost (min cost from current inventory to depletion),
  B&B pruning condition phase.cost >= best_sub_cost (purely local),
  memo cached values are independent of call path, ensuring correctness.

Performance optimizations:
  1. Pre-evaluation: all (subset, ratios) blend properties and Gatekeeper results
     are inventory-independent, evaluated once. Infeasible combos filtered here.
  2. Template quota: keep only the K lowest cost_per_batch templates per subset,
     greatly reducing branching factor (5 streams: ~4000 → ~785).
  3. Cost rate budget: pre-compute cost_per_batch per template; during search,
     only num_batches × cost_per_batch needed for phase cost.
  4. Sorted exploration: candidates sorted by cost ascending at each search node,
     cheapest first → B&B tightens faster, can break on first exceed.
  5. Integer memo: round(qty, 0) rounds inventory to nearest liter,
     greatly reducing unique states; negligible impact for 100L+ inventories.
"""

from itertools import combinations
from dataclasses import dataclass
from .models import WasteStream, SystemConfig, PhaseResult, Schedule, BlendProperties
from .ratios import generate_ratios
from .gatekeeper import gatekeeper, calc_throughput, calc_phase_cost
from .blending import calc_blend_properties

# MVP search parameters
_MAX_TEMPLATES_PER_SUBSET = 30  # Max templates kept per subset
_ACTIVE_THRESHOLD_L = 0.5       # Inventory < 0.5L treated as depleted


# ═══════════════════════════════════════════════════════════════
# Phase Template — inventory-independent pre-computed structure
# ═══════════════════════════════════════════════════════════════

@dataclass
class _PhaseTemplate:
    """
    Pre-evaluated phase template — inventory-independent portion.

    Blend properties, Gatekeeper rates, and throughput depend only on
    waste properties and ratios, not on inventory state. These can be
    pre-computed and reused across all search nodes.

    cost_per_batch simplifies search-time cost calculation to one multiply:
      cost_total = num_batches × cost_per_batch
    """
    stream_ids: tuple         # Participating stream IDs
    ratios: tuple             # Ratio parts
    blend: BlendProperties    # Blended properties
    r_water: float
    r_diesel: float
    r_naoh: float
    r_ext: float
    W: float                  # Throughput L/min
    cost_per_batch: float     # cost_total = num_batches × cost_per_batch
    sum_ratios: int           # sum(ratios), used for Q_phase calculation


def _precompute_templates(streams, cfg, ratio_cache):
    """
    Pre-evaluate all (subset, ratios) combinations for feasibility.

    Blend properties, Gatekeeper results, and throughput are all
    inventory-independent — computed once and reused across all search nodes.

    Each subset keeps only the K lowest cost_per_batch templates:
    - Reduces search branching factor (5 streams: ~4000 → ~785)
    - Most economical ratios are most likely to appear in optimal solution

    Math derivation — cost_per_batch:
      runtime_min = sum_ratios × num_batches / W
      cost_total  = runtime_min × cost_rate_per_min
                  = num_batches × (sum_ratios / W × cost_rate_per_min)
                  = num_batches × cost_per_batch

    Returns:
        (templates_by_subset, n_total, n_infeasible, n_feasible)
    """
    streams_map = {s.stream_id: s for s in streams}
    all_ids = sorted(streams_map.keys())
    templates_by_subset = {}
    n_total = 0
    n_infeasible = 0
    n_feasible = 0

    # Pre-compute fixed overhead rate ($/min): electricity + labor
    fixed_cost_per_min = (
        cfg.P_system * cfg.cost_electricity_per_kWh + cfg.cost_labor_per_hr
    ) / 60.0

    for subset_size in range(1, len(all_ids) + 1):
        for subset in combinations(all_ids, subset_size):
            subset_streams = [streams_map[sid] for sid in subset]
            ratios_list = ratio_cache.get(len(subset), [(1,)])

            templates = []
            for ratios in ratios_list:
                n_total += 1
                blend = calc_blend_properties(subset_streams, ratios)

                # Prune 1a: pH upper bound check
                if blend.pH > cfg.pH_max:
                    n_infeasible += 1
                    continue

                r_water, r_diesel, r_naoh = gatekeeper(blend, cfg)
                W = calc_throughput(r_water, r_diesel, r_naoh, cfg)

                # Prune 1b: throughput too low
                if W < cfg.W_min:
                    n_infeasible += 1
                    continue

                # Pre-compute cost_per_batch
                sum_ratios = sum(ratios)
                material_cost_per_min = W * (
                    r_diesel * cfg.cost_diesel_per_L
                    + r_naoh * cfg.cost_naoh_per_L
                    + r_water * cfg.cost_water_per_L
                )
                cost_rate_per_min = material_cost_per_min + fixed_cost_per_min
                cost_per_batch = sum_ratios / W * cost_rate_per_min

                templates.append(_PhaseTemplate(
                    stream_ids=subset,
                    ratios=ratios,
                    blend=blend,
                    r_water=r_water,
                    r_diesel=r_diesel,
                    r_naoh=r_naoh,
                    r_ext=r_water + r_diesel + r_naoh,
                    W=W,
                    cost_per_batch=cost_per_batch,
                    sum_ratios=sum_ratios,
                ))

            if templates:
                # Sort by cost_per_batch, keep only the K most economical
                templates.sort(key=lambda t: t.cost_per_batch)
                kept = templates[:_MAX_TEMPLATES_PER_SUBSET]
                templates_by_subset[frozenset(subset)] = kept
                n_feasible += len(kept)

    return templates_by_subset, n_total, n_infeasible, n_feasible


# ═══════════════════════════════════════════════════════════════
# Search main function
# ═══════════════════════════════════════════════════════════════

def search(
    streams: list,
    cfg: SystemConfig,
) -> tuple:
    """
    Search for the optimal feed plan.

    Args:
        streams: All waste streams
        cfg: System configuration

    Returns:
        (best_cost, best_phases, stats)
    """
    streams_map = {s.stream_id: s for s in streams}
    inventory = {s.stream_id: s.quantity_L for s in streams}
    N = len(streams)

    # Pre-generate ratios for each subset size
    ratio_cache = {}
    for n in range(1, N + 1):
        ratio_cache[n] = generate_ratios(n, cfg.ratio_sum_max)

    # Pre-evaluate all feasible phase templates
    all_templates, n_total, n_infeasible, n_feasible = _precompute_templates(
        streams, cfg, ratio_cache
    )

    # Memoization cache: memo_key → (sub_cost, phases)
    memo = {}

    # Search statistics
    stats = {
        "evaluated": n_total,
        "pruned_infeasible": n_infeasible,
        "templates_kept": n_feasible,
        "pruned_bound": 0,
        "memo_hits": 0,
    }

    def _search(inv: dict, depth: int) -> tuple:
        """
        Recursive core — returns sub-problem cost.

        Args:
            inv: Current inventory {stream_id: remaining_L}
            depth: Current recursion depth

        Returns:
            (sub_cost, phases_list)
            sub_cost: Min cost from current inventory to depletion
        """
        # Get streams that still have inventory (< 0.5L treated as depleted,
        # eliminates floating-point residuals)
        active = {sid: qty for sid, qty in inv.items()
                  if qty > _ACTIVE_THRESHOLD_L}

        # Terminal: all inventory depleted
        if not active:
            return 0.0, []

        # BOUND 3: max phase count = total number of streams
        if depth > N:
            return float("inf"), []

        # Memoization: integer precision merges nearby states
        # For 100L+ inventories, <0.5L rounding error is negligible
        memo_key = frozenset(
            (sid, round(qty, 0)) for sid, qty in sorted(active.items())
        )
        if memo_key in memo:
            stats["memo_hits"] += 1
            return memo[memo_key]

        active_ids_set = frozenset(active.keys())

        # ── Collect candidate phases: (cost, template, num_batches) ──
        # Cost only needs num_batches × cost_per_batch (one min + one multiply)
        candidates = []
        for subset_key, templates in all_templates.items():
            if not subset_key.issubset(active_ids_set):
                continue
            for tmpl in templates:
                num_batches = min(
                    active[sid] / ratio
                    for sid, ratio in zip(tmpl.stream_ids, tmpl.ratios)
                )
                cost = num_batches * tmpl.cost_per_batch
                candidates.append((cost, tmpl, num_batches))

        # ── Sort by cost ascending — explore cheapest first ──
        candidates.sort(key=lambda x: x[0])

        best_sub_cost = float("inf")
        best_phases = None

        for i, (cost_total, tmpl, num_batches) in enumerate(candidates):
            # PRUNE 2: local B&B — after sorting, first exceed means break
            # All subsequent costs are higher, total_from_here ≥ cost_total ≥ best_sub_cost
            if cost_total >= best_sub_cost:
                stats["pruned_bound"] += len(candidates) - i
                break

            # Update inventory
            new_inv = dict(inv)
            for sid, ratio in zip(tmpl.stream_ids, tmpl.ratios):
                new_inv[sid] = active[sid] - ratio * num_batches

            # Recurse: get optimal cost for remaining inventory
            remaining_cost, remaining_phases = _search(new_inv, depth + 1)

            total_from_here = cost_total + remaining_cost
            if total_from_here < best_sub_cost:
                best_sub_cost = total_from_here
                # Deferred PhaseResult construction — only when a better solution is found
                Q_phase = tmpl.sum_ratios * num_batches
                runtime_min = Q_phase / tmpl.W
                costs = calc_phase_cost(
                    tmpl.W, tmpl.r_water, tmpl.r_diesel, tmpl.r_naoh,
                    runtime_min, cfg
                )
                phase = PhaseResult(
                    streams=dict(zip(tmpl.stream_ids, tmpl.ratios)),
                    blend_props=tmpl.blend,
                    r_water=tmpl.r_water,
                    r_diesel=tmpl.r_diesel,
                    r_naoh=tmpl.r_naoh,
                    r_ext=tmpl.r_ext,
                    W=tmpl.W,
                    runtime_min=runtime_min,
                    Q_phase=Q_phase,
                    **costs,
                )
                best_phases = [phase] + remaining_phases

        # Cache sub-problem optimal solution
        if best_phases is not None:
            memo[memo_key] = (best_sub_cost, list(best_phases))
        else:
            memo[memo_key] = (float("inf"), [])

        return memo[memo_key]

    best_cost, best_phases = _search(inventory, 0)

    return best_cost, best_phases, stats


def build_optimized_schedule(
    streams: list,
    cfg: SystemConfig,
) -> tuple:
    """
    Build the optimal feed plan.

    Returns:
        (Schedule, search_stats)
    """
    best_cost, best_phases, stats = search(streams, cfg)

    if best_phases is None or best_cost == float("inf"):
        return None, stats

    schedule = Schedule(
        phases=best_phases,
        total_cost=best_cost,
        total_runtime_min=sum(p.runtime_min for p in best_phases),
    )
    return schedule, stats

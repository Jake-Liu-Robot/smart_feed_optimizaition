"""
AxNano Smart-Feed Algorithm v9 — Ratio Enumerator
===================================================
Generates all valid waste blending ratios.

Bounds:
  1. sum(ratio_parts) ≤ ratio_sum_max (= 11)
  2. GCD = 1 (removes proportionally-scaled duplicates, e.g. 4:2 ≡ 2:1)
  3. Each component ≥ 1 (all streams in the subset participate)

Note: (1,2) and (2,1) are considered different ratios (more A vs more B)
"""

from math import gcd
from functools import reduce
from itertools import product


def generate_ratios(n_streams: int, max_sum: int) -> list:
    """
    Generate all valid ratios for n_streams components.

    Args:
        n_streams: Number of waste streams in the blend (1-5)
        max_sum: Max sum of ratio parts, default 11 (= F_total rounded)

    Returns:
        list of tuple[int, ...]: All valid ratios

    Example:
        generate_ratios(2, 11) →
        [(1,1), (1,2), (2,1), (1,3), (3,1), (2,3), (3,2), ...]
    """
    if n_streams == 1:
        return [(1,)]  # Single stream has only one ratio

    results = []
    upper = max_sum - n_streams + 1  # Max value for a single component

    for combo in product(range(1, upper + 1), repeat=n_streams):
        if sum(combo) > max_sum:
            continue
        if reduce(gcd, combo) != 1:
            continue
        results.append(combo)

    return results


# ─── Pre-computed statistics ───

def ratio_stats(max_streams: int = 5, max_sum: int = 11) -> dict:
    """
    Compute ratio counts for each stream count, used to estimate search space.
    """
    stats = {}
    for n in range(1, max_streams + 1):
        ratios = generate_ratios(n, max_sum)
        stats[n] = len(ratios)
    return stats

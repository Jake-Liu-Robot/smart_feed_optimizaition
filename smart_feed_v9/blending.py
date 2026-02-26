"""
AxNano Smart-Feed Algorithm v9 — Blend Property Calculations
=============================================================
- Linear blending: BTU, F ppm, Solid%, Salt ppm «A4»
- pH blending: [H⁺] concentration method (chemically correct)
"""

import math
from .models import WasteStream, BlendProperties


def blend_linear(values: list, ratios: list) -> float:
    """
    Weighted average, used for BTU, F ppm, Solid%, Salt ppm «A4»

    P_blend = Σ(P_i * ratio_i) / Σ(ratio_i)
    """
    total = sum(ratios)
    if total == 0:
        return 0.0
    return sum(v * r for v, r in zip(values, ratios)) / total


def blend_pH(pH_values: list, ratios: list) -> float:
    """
    Chemically correct pH blending:
    1. pH → [H⁺] = 10^(-pH)
    2. Volume-weighted average of [H⁺]
    3. [H⁺]_blend → pH = -log10([H⁺]_blend)

    Note: Ignores buffer capacity; results are reasonable for strong acid/base waste.
    """
    total = sum(ratios)
    if total == 0:
        return 7.0

    h_concentration = sum(
        (10.0 ** (-pH)) * ratio
        for pH, ratio in zip(pH_values, ratios)
    ) / total

    if h_concentration <= 0:
        return 14.0  # Extremely alkaline
    return -math.log10(h_concentration)


def calc_blend_properties(
    streams: list, ratios: tuple
) -> BlendProperties:
    """
    Calculate blended properties for a set of waste streams at given ratios.

    BTU, F ppm, Solid%, Salt: linear weighted average «A4»
    pH: [H⁺] concentration mixing method
    """
    ratio_list = list(ratios)

    return BlendProperties(
        btu_per_lb=blend_linear([s.btu_per_lb for s in streams], ratio_list),
        pH=blend_pH([s.pH for s in streams], ratio_list),
        f_ppm=blend_linear([s.f_ppm for s in streams], ratio_list),
        solid_pct=blend_linear([s.solid_pct for s in streams], ratio_list),
        salt_ppm=blend_linear([s.salt_ppm for s in streams], ratio_list),
    )

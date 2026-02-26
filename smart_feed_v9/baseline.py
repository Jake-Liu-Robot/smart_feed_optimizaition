"""
AxNano Smart-Feed Algorithm v9 — Baseline Cost Calculation
===========================================================
Step 2: Process each waste stream individually (no blending),
        compute total cost as the optimization benchmark.

Even if a solo stream is extremely uneconomical (W near 0),
we still compute the astronomical cost to demonstrate the value
of blending optimization.
"""

from .models import (
    WasteStream, SystemConfig, BlendProperties,
    PhaseResult, Schedule,
)
from .gatekeeper import (
    gatekeeper, calc_throughput, calc_phase_cost,
)


def calc_baseline(streams: list, cfg: SystemConfig) -> Schedule:
    """
    Baseline: process each waste stream individually.

    Runs Gatekeeper + synchronous equation independently for each stream.
    No W_min floor — allows extremely high costs to demonstrate
    the value of blending optimization.
    """
    phases = []

    for stream in streams:
        # Single stream = its own properties are the "blend" properties
        blend = BlendProperties(
            btu_per_lb=stream.btu_per_lb,
            pH=stream.pH,
            f_ppm=stream.f_ppm,
            solid_pct=stream.solid_pct,
            salt_ppm=stream.salt_ppm,
        )

        r_water, r_diesel, r_naoh = gatekeeper(blend, cfg)
        r_ext = r_water + r_diesel + r_naoh
        W = calc_throughput(r_water, r_diesel, r_naoh, cfg)

        # No W_min floor — allow very low throughput to produce very high cost
        runtime_min = stream.quantity_L / W if W > 0 else float("inf")

        costs = calc_phase_cost(
            W, r_water, r_diesel, r_naoh, runtime_min, cfg
        )

        phases.append(PhaseResult(
            streams={stream.stream_id: 1},
            blend_props=blend,
            r_water=r_water,
            r_diesel=r_diesel,
            r_naoh=r_naoh,
            r_ext=r_ext,
            W=W,
            runtime_min=runtime_min,
            Q_phase=stream.quantity_L,
            **costs,
        ))

    return Schedule(
        phases=phases,
        total_cost=sum(p.cost_total for p in phases),
        total_runtime_min=sum(p.runtime_min for p in phases),
    )

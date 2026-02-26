"""
AxNano Smart-Feed Algorithm v9
==============================
Multi-phase feed optimization algorithm that reduces SCWO reactor
operating costs by intelligently blending complementary waste streams.

Usage:
    from smart_feed_v9 import WasteStream, SystemConfig, run_optimization
"""

from .models import (
    WasteStream,
    SystemConfig,
    BlendProperties,
    PhaseResult,
    Schedule,
)
from .blending import blend_linear, blend_pH, calc_blend_properties
from .gatekeeper import gatekeeper, calc_throughput, calc_phase_cost
from .baseline import calc_baseline
from .search import search, build_optimized_schedule
from .reporter import full_report


def run_optimization(streams: list, cfg: SystemConfig = None,
                     verbose: bool = True) -> dict:
    """
    Run the complete optimization pipeline.

    Args:
        streams: list[WasteStream] — user-provided waste inventory
        cfg: SystemConfig — tunable parameters (None uses all defaults)
        verbose: whether to print the full report

    Returns:
        dict with keys:
            baseline: Schedule
            optimized: Schedule (or None)
            stats: search statistics
            savings_pct: float
    """
    if cfg is None:
        cfg = SystemConfig()

    # Input validation
    _validate_streams(streams)

    # Step 2: Baseline
    baseline = calc_baseline(streams, cfg)

    # Step 4-6: Search for optimum
    optimized, stats = build_optimized_schedule(streams, cfg)

    # Step 7: Report
    if verbose:
        full_report(streams, cfg, baseline, optimized, stats)

    savings_pct = 0.0
    if optimized and baseline.total_cost > 0:
        savings_pct = (1 - optimized.total_cost / baseline.total_cost) * 100

    return {
        "baseline": baseline,
        "optimized": optimized,
        "stats": stats,
        "savings_pct": savings_pct,
    }


def _validate_streams(streams: list):
    """Basic input validation"""
    if not streams:
        raise ValueError("At least 1 waste stream is required")
    if len(streams) > 5:
        raise ValueError(f"Maximum 5 waste streams supported, got {len(streams)}")

    ids = set()
    for s in streams:
        if not isinstance(s, WasteStream):
            raise TypeError(f"Expected WasteStream, got {type(s)}")
        if s.stream_id in ids:
            raise ValueError(f"Duplicate stream_id: {s.stream_id}")
        ids.add(s.stream_id)

        if s.quantity_L <= 0:
            raise ValueError(f"{s.stream_id}: quantity_L must be > 0")
        if s.btu_per_lb < 0:
            raise ValueError(f"{s.stream_id}: btu_per_lb cannot be negative")
        if not (0 <= s.pH <= 14):
            raise ValueError(f"{s.stream_id}: pH must be between 0 and 14")
        if s.f_ppm < 0:
            raise ValueError(f"{s.stream_id}: f_ppm cannot be negative")
        if not (0 <= s.solid_pct <= 100):
            raise ValueError(f"{s.stream_id}: solid_pct must be between 0 and 100")
        if s.salt_ppm < 0:
            raise ValueError(f"{s.stream_id}: salt_ppm cannot be negative")

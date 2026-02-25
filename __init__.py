"""
AxNano Smart-Feed Algorithm v9
==============================
多相喂料优化算法，通过智能混合互补废料流
降低 SCWO 反应器的运行成本。

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
    一键运行完整优化流程。

    Args:
        streams: list[WasteStream] — 用户提供的废料清单
        cfg: SystemConfig — 可调节参数（None 则使用全部默认值）
        verbose: 是否打印完整报告

    Returns:
        dict with keys:
            baseline: Schedule
            optimized: Schedule (or None)
            stats: search statistics
            savings_pct: float
    """
    if cfg is None:
        cfg = SystemConfig()

    # 输入验证
    _validate_streams(streams)

    # Step 2: Baseline
    baseline = calc_baseline(streams, cfg)

    # Step 4-6: 搜索最优
    optimized, stats = build_optimized_schedule(streams, cfg)

    # Step 7: 报告
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
    """基础输入验证"""
    if not streams:
        raise ValueError("至少需要 1 条废料流")
    if len(streams) > 5:
        raise ValueError(f"最多支持 5 条废料流，当前 {len(streams)} 条")

    ids = set()
    for s in streams:
        if not isinstance(s, WasteStream):
            raise TypeError(f"期望 WasteStream，收到 {type(s)}")
        if s.stream_id in ids:
            raise ValueError(f"重复的 stream_id: {s.stream_id}")
        ids.add(s.stream_id)

        if s.quantity_L <= 0:
            raise ValueError(f"{s.stream_id}: quantity_L 必须 > 0")
        if s.btu_per_lb < 0:
            raise ValueError(f"{s.stream_id}: btu_per_lb 不能为负")
        if not (0 <= s.pH <= 14):
            raise ValueError(f"{s.stream_id}: pH 必须在 0-14 之间")
        if s.f_ppm < 0:
            raise ValueError(f"{s.stream_id}: f_ppm 不能为负")
        if not (0 <= s.solid_pct <= 100):
            raise ValueError(f"{s.stream_id}: solid_pct 必须在 0-100 之间")
        if s.salt_ppm < 0:
            raise ValueError(f"{s.stream_id}: salt_ppm 不能为负")

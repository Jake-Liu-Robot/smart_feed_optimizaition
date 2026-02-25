"""
AxNano Smart-Feed Algorithm v9 — Baseline 成本计算
===================================================
Step 2: 每条废料单独处理（不混合），计算总成本。
       作为优化结果的对照基准。

即使某条流 solo 极不经济 (W 接近 0)，仍计算天文数字成本，
以展示混合优化的价值。
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
    Baseline: 每条废料单独处理。

    对每条流独立运行 Gatekeeper + 同步方程，
    不设 W_min 下限 — 让极高成本体现混合优化的价值。
    """
    phases = []

    for stream in streams:
        # 单流 = 自身属性就是"混合"属性
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

        # 不设 W_min 下限，允许极低吞吐量产生极高成本
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

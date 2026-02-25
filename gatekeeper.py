"""
AxNano Smart-Feed Algorithm v9 — Gatekeeper 核心引擎
=====================================================
计算每单位废料的外部输入率 (r_water, r_diesel, r_naoh)
以及由此推导的吞吐量 W 和阶段成本。

★ 计算顺序至关重要: r_water → BTU_eff → r_diesel → r_naoh
  这保证了一步求解，无循环依赖。
"""

from .models import BlendProperties, SystemConfig, PhaseResult


def calc_r_water(blend: BlendProperties, cfg: SystemConfig) -> float:
    """
    Step A: 计算水需求率（独立，最先计算）

    驱动因素:
    - Solid% > solid_max → 需要加水稀释固体
    - Salt ppm > salt_max → 需要加水稀释盐

    精确处理交叉稀释: 为一个原因加的水同时稀释另一个参数。
    """
    r_solid = max(0.0, blend.solid_pct / cfg.solid_max_pct - 1.0)
    r_salt = max(0.0, blend.salt_ppm / cfg.salt_max_ppm - 1.0)

    if r_solid == 0.0 and r_salt == 0.0:
        return 0.0

    # 精确交叉稀释检查
    if r_solid >= r_salt:
        # solid 需要更多水 → 检查这些水是否也足够稀释 salt
        salt_after = blend.salt_ppm / (1.0 + r_solid)
        if salt_after <= cfg.salt_max_ppm:
            return r_solid
        else:
            return blend.salt_ppm / cfg.salt_max_ppm - 1.0
    else:
        # salt 需要更多水 → 检查这些水是否也足够稀释 solid
        solid_after = blend.solid_pct / (1.0 + r_salt)
        if solid_after <= cfg.solid_max_pct:
            return r_salt
        else:
            return blend.solid_pct / cfg.solid_max_pct - 1.0


def calc_r_diesel(blend: BlendProperties, r_water: float,
                  cfg: SystemConfig) -> float:
    """
    Step B: 计算柴油需求率（依赖 r_water）

    所有加水（无论来自 Solid% 还是 Salt）都稀释 BTU。
    BTU_eff = BTU_blend / (1 + r_water)
    """
    BTU_eff = blend.btu_per_lb / (1.0 + r_water)
    return max(0.0,
               (cfg.BTU_target - BTU_eff) / (cfg.BTU_diesel * cfg.eta))


def calc_r_naoh(blend: BlendProperties, cfg: SystemConfig) -> float:
    """
    Step C: 计算 NaOH 需求率（独立于 r_water 和 r_diesel）

    化学直觉模型:
    - 酸负荷: F ppm → HF (在 SCWO 条件下)
    - 碱负荷: 碱性废料 (pH > 7) 的内部碱贡献
    - NaOH 填补 净酸缺口

    所有 K 常数均可由用户调节。
    """
    # 酸负荷 (meq/L waste)
    acid_load = blend.f_ppm * cfg.K_F_TO_ACID

    # 碱负荷 (meq/L waste) — 仅当 blend pH > 7 时有内部碱贡献
    base_load = max(0.0, (blend.pH - 7.0)) * cfg.K_PH_TO_BASE

    # 净酸缺口
    net_acid = max(0.0, acid_load - base_load)

    # NaOH 体积需求 (L NaOH / L waste)
    return net_acid * cfg.K_ACID_TO_NAOH_VOL


def gatekeeper(blend: BlendProperties, cfg: SystemConfig) -> tuple:
    """
    Gatekeeper 主函数 (Step 5)

    严格按顺序计算: r_water → r_diesel → r_naoh
    返回: (r_water, r_diesel, r_naoh)
    """
    r_water = calc_r_water(blend, cfg)
    r_diesel = calc_r_diesel(blend, r_water, cfg)
    r_naoh = calc_r_naoh(blend, cfg)
    return r_water, r_diesel, r_naoh


def calc_throughput(r_water: float, r_diesel: float, r_naoh: float,
                    cfg: SystemConfig) -> float:
    """
    同步方程求解 «A2»

    W = F_total / (1 + r_ext)

    无循环依赖，一步求解。
    """
    r_ext = r_water + r_diesel + r_naoh
    return cfg.F_total / (1.0 + r_ext)


def calc_phase_cost(W: float, r_water: float, r_diesel: float,
                    r_naoh: float, runtime_min: float,
                    cfg: SystemConfig) -> dict:
    """
    计算单个 phase 的 5 项成本。

    内部单位: 分钟 → 输出时转小时用于电力和人工。
    材料成本: 流量(L/min) × 比率 × 时间(min) = 体积(L) × 单价($/L)
    """
    runtime_hr = runtime_min / 60.0

    cost_diesel = W * r_diesel * runtime_min * cfg.cost_diesel_per_L
    cost_naoh = W * r_naoh * runtime_min * cfg.cost_naoh_per_L
    cost_water = W * r_water * runtime_min * cfg.cost_water_per_L
    cost_electricity = cfg.P_system * runtime_hr * cfg.cost_electricity_per_kWh
    cost_labor = runtime_hr * cfg.cost_labor_per_hr

    return {
        "cost_diesel": cost_diesel,
        "cost_naoh": cost_naoh,
        "cost_water": cost_water,
        "cost_electricity": cost_electricity,
        "cost_labor": cost_labor,
        "cost_total": cost_diesel + cost_naoh + cost_water
                      + cost_electricity + cost_labor,
    }


def evaluate_phase(streams: list, ratios: tuple, inventory: dict,
                   cfg: SystemConfig) -> PhaseResult | None:
    """
    完整评估一个 phase: 混合 → Gatekeeper → 吞吐量 → 成本

    如果 W < W_min 则返回 None（不可行）。
    """
    from .blending import calc_blend_properties

    stream_ids = [s.stream_id for s in streams]
    blend = calc_blend_properties(streams, ratios)
    r_water, r_diesel, r_naoh = gatekeeper(blend, cfg)
    r_ext = r_water + r_diesel + r_naoh
    W = calc_throughput(r_water, r_diesel, r_naoh, cfg)

    if W < cfg.W_min:
        return None  # 吞吐量过低，不可行

    # 计算 phase 持续时间
    # num_batches = min(Q_i / ratio_i) — 最先耗尽的流决定 phase 长度
    num_batches = min(
        inventory[sid] / ratio
        for sid, ratio in zip(stream_ids, ratios)
    )
    Q_phase = sum(r * num_batches for r in ratios)
    runtime_min = Q_phase / W

    costs = calc_phase_cost(W, r_water, r_diesel, r_naoh, runtime_min, cfg)

    return PhaseResult(
        streams=dict(zip(stream_ids, ratios)),
        blend_props=blend,
        r_water=r_water, r_diesel=r_diesel, r_naoh=r_naoh,
        r_ext=r_ext, W=W,
        runtime_min=runtime_min,
        Q_phase=Q_phase,
        **costs,
    )

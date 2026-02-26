"""
AxNano Smart-Feed Algorithm v9 — Gatekeeper Core Engine
========================================================
Computes per-unit-waste external input rates (r_water, r_diesel, r_naoh)
and derives throughput W and phase cost.

★ Computation order is critical: r_water → BTU_eff → r_diesel → r_naoh
  This guarantees a single-pass solution with no circular dependencies.
"""

from .models import BlendProperties, SystemConfig, PhaseResult


def calc_r_water(blend: BlendProperties, cfg: SystemConfig) -> float:
    """
    Step A: Compute water demand rate (independent, computed first)

    Drivers:
    - Solid% > solid_max → need water to dilute solids
    - Salt ppm > salt_max → need water to dilute salt

    Take max(r_solid, r_salt): water added for the larger constraint
    automatically satisfies the smaller one (cross-dilution math equivalence).

    Proof: If r_solid ≥ r_salt, then salt_after = salt_ppm/(1+r_solid)
           ≤ salt_ppm/(1+r_salt) = salt_max_ppm ✓  Symmetric for the reverse.
    """
    r_solid = max(0.0, blend.solid_pct / cfg.solid_max_pct - 1.0)
    r_salt = max(0.0, blend.salt_ppm / cfg.salt_max_ppm - 1.0)
    return max(r_solid, r_salt)


def calc_r_diesel(blend: BlendProperties, r_water: float,
                  cfg: SystemConfig) -> float:
    """
    Step B: Compute diesel demand rate (depends on r_water)

    All water addition (whether from Solid% or Salt) dilutes BTU.
    BTU_eff = BTU_blend / (1 + r_water)
    """
    BTU_eff = blend.btu_per_lb / (1.0 + r_water)
    return max(0.0,
               (cfg.BTU_target - BTU_eff) / (cfg.BTU_diesel * cfg.eta))


def calc_r_naoh(blend: BlendProperties, cfg: SystemConfig) -> float:
    """
    Step C: Compute NaOH demand rate (independent of r_water and r_diesel)

    Chemical intuition model:
    - Acid load: F ppm → HF (under SCWO conditions)
    - Base load: alkaline waste (pH > 7) provides internal base contribution
    - NaOH fills the net acid gap

    All K constants are user-tunable.
    """
    # Acid load (meq/L waste)
    acid_load = blend.f_ppm * cfg.K_F_TO_ACID

    # Base load (meq/L waste) — only when blend pH > 7 has internal base contribution
    base_load = max(0.0, (blend.pH - 7.0)) * cfg.K_PH_TO_BASE

    # Net acid gap
    net_acid = max(0.0, acid_load - base_load)

    # NaOH volume demand (L NaOH / L waste)
    return net_acid * cfg.K_ACID_TO_NAOH_VOL


def gatekeeper(blend: BlendProperties, cfg: SystemConfig) -> tuple:
    """
    Gatekeeper main function (Step 5)

    Strict computation order: r_water → r_diesel → r_naoh
    Returns: (r_water, r_diesel, r_naoh)
    """
    r_water = calc_r_water(blend, cfg)
    r_diesel = calc_r_diesel(blend, r_water, cfg)
    r_naoh = calc_r_naoh(blend, cfg)
    return r_water, r_diesel, r_naoh


def calc_throughput(r_water: float, r_diesel: float, r_naoh: float,
                    cfg: SystemConfig) -> float:
    """
    Synchronous equation «A2»

    W = F_total / (1 + r_ext)

    No circular dependency, single-pass solution.
    """
    r_ext = r_water + r_diesel + r_naoh
    return cfg.F_total / (1.0 + r_ext)


def calc_phase_cost(W: float, r_water: float, r_diesel: float,
                    r_naoh: float, runtime_min: float,
                    cfg: SystemConfig) -> dict:
    """
    Compute the 5 cost components for a single phase.

    Internal units: minutes → converted to hours for electricity and labor.
    Material costs: flow_rate(L/min) × ratio × time(min) = volume(L) × unit_price($/L)
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
    Fully evaluate a phase: blend → Gatekeeper → throughput → cost

    Returns None if infeasible (W < W_min or pH > pH_max).
    """
    from .blending import calc_blend_properties

    stream_ids = [s.stream_id for s in streams]
    blend = calc_blend_properties(streams, ratios)
    # pH upper bound check: overly alkaline mixtures cannot be processed
    # (current model has no mechanism to lower pH)
    if blend.pH > cfg.pH_max:
        return None

    r_water, r_diesel, r_naoh = gatekeeper(blend, cfg)
    r_ext = r_water + r_diesel + r_naoh
    W = calc_throughput(r_water, r_diesel, r_naoh, cfg)

    if W < cfg.W_min:
        return None  # Throughput too low, infeasible

    # Compute phase duration
    # num_batches = min(Q_i / ratio_i) — the first-exhausted stream determines phase length
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

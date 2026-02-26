"""
AxNano Smart-Feed Algorithm v9 — Data Models
=============================================
WasteStream:     User-provided waste properties (no defaults)
SystemConfig:    All tunable parameters (with defaults, user-adjustable)
BlendProperties: Intermediate calculation results
PhaseResult:     Complete result for a single phase
Schedule:        Complete feed plan (multiple phases)
"""

from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# User-provided — properties for each waste stream
# ═══════════════════════════════════════════════════════════════

@dataclass
class WasteStream:
    """
    A single waste stream. All fields are user-provided, no defaults.
    Properties use raw waste values «A7», not AFS-preprocessed values.
    """
    stream_id: str          # Unique identifier, e.g. "Resin-001", "AFFF-003"
    quantity_L: float       # Total volume (liters)
    btu_per_lb: float       # Heat value (BTU/lb), raw
    pH: float               # pH value
    f_ppm: float            # Fluorine concentration (ppm)
    solid_pct: float        # Solid content (%), raw
    salt_ppm: float         # Salt concentration (ppm)
    moisture_pct: float     # Moisture (%), display only «A9», not used in calculations


# ═══════════════════════════════════════════════════════════════
# All tunable parameters — with defaults, user-adjustable
# ═══════════════════════════════════════════════════════════════

@dataclass
class SystemConfig:
    """
    System configuration. All parameters have defaults based on AxNano
    operational data; users can adjust based on specific equipment and
    operating conditions.

    Grouped into five categories:
    1. Reactor parameters
    2. Reactor boundary conditions
    3. Chemical constants (fitted values)
    4. Unit costs
    5. Search parameters
    """

    # ─── 1. Reactor parameters «A1, A3» ───
    F_total: float = 11.0           # Total feed capacity (L/min), includes waste + all external inputs
                                    # Observed range: 9.4–11.4 L/min
    P_system: float = 400.0         # System power (kW)
                                    # Observed range: 376–400 kW
    BTU_diesel: float = 18300.0     # Diesel heat value (BTU/lb), physical constant
    eta: float = 0.89               # Thermal efficiency factor (validated from operational data)

    # ─── 2. Reactor boundary conditions ───
    BTU_target: float = 2200.0      # Target heat value (BTU/lb)
    solid_max_pct: float = 15.0     # Max solid content (%), above which pumping fails
    pH_min: float = 6.0             # Min pH (pending engineering confirmation)
    pH_max: float = 9.0             # Max pH (pending engineering confirmation)
    salt_max_ppm: float = 5000.0    # Max salt concentration (ppm), above which clogging risk

    # ─── 3. Chemical constants (fitted, tunable) ───
    # F ppm → acid equivalent conversion factor
    # Default based on stoichiometry: 1 ppm F⁻ = 1mg/L, MW=19, → ~0.053 mmol/L
    K_F_TO_ACID: float = 0.053      # meq / (L·ppm)

    # pH alkaline contribution coefficient
    # When blend pH > 7: (pH - 7) × K_PH_TO_BASE = base equivalent (meq/L)
    # Linear approximation, needs calibration from operational data
    K_PH_TO_BASE: float = 50.0      # meq / (L·pH_unit)

    # Volume of 35% NaOH needed to neutralize 1 meq acid
    # Theoretical derivation: 35% NaOH → 12075 meq/L → 1/12075 ≈ 8.28e-5
    K_ACID_TO_NAOH_VOL: float = 8.28e-5  # L_NaOH / meq

    # ─── 4. Unit costs «A5» ───
    cost_diesel_per_L: float = 1.00       # $/L
    cost_naoh_per_L: float = 1.51         # $/L (35% NaOH solution)
    cost_water_per_L: float = 0.00199     # $/L (DI water)
    cost_electricity_per_kWh: float = 0.12  # $/kWh
    cost_labor_per_hr: float = 100.0      # $/hr

    # ─── 5. Search parameters ───
    ratio_sum_max: int = 11         # Max ratio sum (= F_total rounded)
    W_min: float = 0.5              # Min feasible throughput (L/min)


# ═══════════════════════════════════════════════════════════════
# Intermediate results and output structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class BlendProperties:
    """Blended waste properties (intermediate calculation result)"""
    btu_per_lb: float       # Linear weighted average
    pH: float               # [H⁺] concentration mixing then converted back
    f_ppm: float            # Linear weighted average
    solid_pct: float        # Linear weighted average
    salt_ppm: float         # Linear weighted average


@dataclass
class PhaseResult:
    """Complete result for a single phase"""
    streams: dict               # {stream_id: ratio_part}, e.g. {"Resin": 1, "AFFF": 3}
    blend_props: BlendProperties
    r_water: float              # Water demand rate (L water / L waste)
    r_diesel: float             # Diesel demand rate (L diesel / L waste)
    r_naoh: float               # NaOH demand rate (L NaOH / L waste)
    r_ext: float                # Total external input rate = r_water + r_diesel + r_naoh
    W: float                    # Waste throughput (L/min)
    runtime_min: float          # Runtime (minutes)
    Q_phase: float              # Total waste consumed in this phase (L)
    # Itemized costs
    cost_diesel: float = 0.0
    cost_naoh: float = 0.0
    cost_water: float = 0.0
    cost_electricity: float = 0.0
    cost_labor: float = 0.0
    cost_total: float = 0.0


@dataclass
class Schedule:
    """Complete feed plan"""
    phases: list                # list[PhaseResult]
    total_cost: float
    total_runtime_min: float

    @property
    def total_runtime_hr(self) -> float:
        return self.total_runtime_min / 60.0

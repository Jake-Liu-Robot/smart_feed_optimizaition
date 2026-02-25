"""
AxNano Smart-Feed Algorithm v9 — 数据模型
==========================================
WasteStream:     用户必须提供的废料属性（无默认值）
SystemConfig:    所有可调节参数（均有默认值，用户可按实际情况修改）
BlendProperties: 中间计算结果
PhaseResult:     单个 phase 的完整计算结果
Schedule:        完整喂料计划（多个 phase）
"""

from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# 用户必须提供 — 每条废料流的属性
# ═══════════════════════════════════════════════════════════════

@dataclass
class WasteStream:
    """
    单条废料流。所有字段由用户提供，无默认值。
    属性使用原始废料值 «A7»，非 AFS 预处理后的值。
    """
    stream_id: str          # 唯一标识，如 "Resin-001", "AFFF-003"
    quantity_L: float       # 总量 (升)
    btu_per_lb: float       # 热值 (BTU/lb)，原始值
    pH: float               # pH 值
    f_ppm: float            # 氟浓度 (ppm)
    solid_pct: float        # 固体含量 (%)，原始值
    salt_ppm: float         # 盐浓度 (ppm)
    moisture_pct: float     # 水分 (%)，仅展示 «A9»，不参与计算


# ═══════════════════════════════════════════════════════════════
# 所有可调节参数 — 均有默认值，用户可按实际情况修改
# ═══════════════════════════════════════════════════════════════

@dataclass
class SystemConfig:
    """
    系统配置。所有参数均有基于 AxNano 运行数据的默认值，
    用户可根据具体设备和运行条件调整。

    分为四组：
    1. 反应器参数
    2. 反应器边界条件
    3. 化学常数（拟合值）
    4. 单位成本
    5. 搜索参数
    """

    # ─── 1. 反应器参数 «A1, A3» ───
    F_total: float = 11.0           # 总进料容量 (L/min)，含废料+所有外部输入
                                    # 观测范围: 9.4–11.4 L/min
    P_system: float = 400.0         # 系统功率 (kW)
                                    # 观测范围: 376–400 kW

    # ─── 2. 反应器边界条件 ───
    BTU_target: float = 2200.0      # 目标热值 (BTU/lb)
    solid_max_pct: float = 15.0     # 最大固体含量 (%)，超过则无法泵送
    pH_min: float = 6.0             # 最低 pH（待工程确认）
    pH_max: float = 9.0             # 最高 pH（待工程确认）
    salt_max_ppm: float = 5000.0    # 最大盐浓度 (ppm)，超过则堵塞风险
    BTU_diesel: float = 18300.0     # 柴油热值 (BTU/lb)
    eta: float = 0.89               # 热效率因子（已从运行数据验证）

    # ─── 3. 化学常数（拟合值，可调节）───
    # F ppm → 酸当量转换系数
    # 默认值基于化学计量: 1 ppm F⁻ = 1mg/L, MW=19, → ~0.053 mmol/L
    K_F_TO_ACID: float = 0.053      # meq / (L·ppm)

    # pH 碱性贡献系数
    # 当 blend pH > 7 时，(pH - 7) × K_PH_TO_BASE = 碱当量 (meq/L)
    # 此为线性近似，需从运行数据校准
    K_PH_TO_BASE: float = 50.0      # meq / (L·pH_unit)

    # 中和 1 meq 酸需要的 35% NaOH 体积
    # 理论推导: 35% NaOH → 12075 meq/L → 1/12075 ≈ 8.28e-5
    K_ACID_TO_NAOH_VOL: float = 8.28e-5  # L_NaOH / meq

    # ─── 4. 单位成本 «A5» ───
    cost_diesel_per_L: float = 1.00       # $/L
    cost_naoh_per_L: float = 1.51         # $/L (35% NaOH 溶液)
    cost_water_per_L: float = 0.00199     # $/L (DI 水)
    cost_electricity_per_kWh: float = 0.12  # $/kWh
    cost_labor_per_hr: float = 100.0      # $/hr

    # ─── 5. 搜索参数 ───
    ratio_sum_max: int = 11         # 配比总和上限 (= F_total 取整)
    W_min: float = 0.5              # 最低可行吞吐量 (L/min)


# ═══════════════════════════════════════════════════════════════
# 中间计算结果与输出结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class BlendProperties:
    """混合后的废料属性（中间计算结果）"""
    btu_per_lb: float       # 线性加权平均
    pH: float               # [H⁺] 浓度混合后转回
    f_ppm: float            # 线性加权平均
    solid_pct: float        # 线性加权平均
    salt_ppm: float         # 线性加权平均


@dataclass
class PhaseResult:
    """单个 phase 的完整计算结果"""
    streams: dict               # {stream_id: ratio_part}，如 {"Resin": 1, "AFFF": 3}
    blend_props: BlendProperties
    r_water: float              # 水需求率 (L water / L waste)
    r_diesel: float             # 柴油需求率 (L diesel / L waste)
    r_naoh: float               # NaOH 需求率 (L NaOH / L waste)
    r_ext: float                # 总外部输入率 = r_water + r_diesel + r_naoh
    W: float                    # 废料吞吐量 (L/min)
    runtime_min: float          # 运行时间 (分钟)
    Q_phase: float              # 本 phase 消耗的废料总量 (L)
    # 分项成本
    cost_diesel: float = 0.0
    cost_naoh: float = 0.0
    cost_water: float = 0.0
    cost_electricity: float = 0.0
    cost_labor: float = 0.0
    cost_total: float = 0.0


@dataclass
class Schedule:
    """完整的喂料计划"""
    phases: list                # list[PhaseResult]
    total_cost: float
    total_runtime_min: float

    @property
    def total_runtime_hr(self) -> float:
        return self.total_runtime_min / 60.0

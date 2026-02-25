"""
AxNano Smart-Feed Algorithm v9 — 输出报告
==========================================
Step 7: 格式化输出最优计划、成本对比、安全边界报告。
"""

from .models import WasteStream, SystemConfig, Schedule, PhaseResult


def _fmt_cost(val: float) -> str:
    if val >= 1_000_000:
        return f"${val:,.0f}"
    return f"${val:,.2f}"


def _fmt_time(minutes: float) -> str:
    if minutes == float("inf"):
        return "∞"
    if minutes >= 60:
        return f"{minutes / 60:.1f} hr"
    return f"{minutes:.1f} min"


def _fmt_rate(val: float) -> str:
    if val < 0.001:
        return "0"
    return f"{val:.4f}"


def _pct_change(baseline: float, optimized: float) -> str:
    if baseline == 0 or baseline == float("inf"):
        return "N/A"
    pct = (optimized - baseline) / baseline * 100
    return f"{pct:+.1f}%"


def print_separator(char: str = "═", width: int = 72):
    print(char * width)


def print_header(title: str, width: int = 72):
    print()
    print_separator()
    print(f"  {title}")
    print_separator()


def report_streams(streams: list):
    """打印废料清单"""
    print_header("废料清单 (用户输入)")

    headers = f"{'ID':<12} {'数量(L)':>8} {'BTU/lb':>8} {'pH':>6} {'F ppm':>8} {'Solid%':>7} {'Salt ppm':>9}"
    print(f"  {headers}")
    print(f"  {'─' * len(headers)}")

    for s in streams:
        print(f"  {s.stream_id:<12} {s.quantity_L:>8.1f} {s.btu_per_lb:>8.0f}"
              f" {s.pH:>6.1f} {s.f_ppm:>8.0f} {s.solid_pct:>7.1f}"
              f" {s.salt_ppm:>9.0f}")

    total_qty = sum(s.quantity_L for s in streams)
    print(f"\n  总库存: {total_qty:,.1f} L | 废料种类: {len(streams)}")


def report_config(cfg: SystemConfig):
    """打印系统配置（用户可调节参数）"""
    print_header("系统配置 (可调节参数)")

    print("  ┌─ 反应器参数 ─────────────────────┐")
    print(f"  │ F_total     = {cfg.F_total:.1f} L/min          │")
    print(f"  │ P_system    = {cfg.P_system:.0f} kW              │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ 边界条件 ───────────────────────┐")
    print(f"  │ BTU_target  = {cfg.BTU_target:.0f} BTU/lb         │")
    print(f"  │ Solid_max   = {cfg.solid_max_pct:.0f}%                  │")
    print(f"  │ pH_range    = {cfg.pH_min:.0f} – {cfg.pH_max:.0f}                │")
    print(f"  │ Salt_max    = {cfg.salt_max_ppm:.0f} ppm             │")
    print(f"  │ BTU_diesel  = {cfg.BTU_diesel:.0f} BTU/lb        │")
    print(f"  │ η (效率)    = {cfg.eta:.2f}                  │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ 化学常数 (拟合值) ─────────────┐")
    print(f"  │ K_F_TO_ACID       = {cfg.K_F_TO_ACID:.4f}          │")
    print(f"  │ K_PH_TO_BASE      = {cfg.K_PH_TO_BASE:.1f}            │")
    print(f"  │ K_ACID_TO_NAOH_VOL= {cfg.K_ACID_TO_NAOH_VOL:.2e}      │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ 单位成本 ───────────────────────┐")
    print(f"  │ 柴油    = ${cfg.cost_diesel_per_L:.2f}/L              │")
    print(f"  │ NaOH    = ${cfg.cost_naoh_per_L:.2f}/L              │")
    print(f"  │ DI Water= ${cfg.cost_water_per_L:.5f}/L           │")
    print(f"  │ 电力    = ${cfg.cost_electricity_per_kWh:.2f}/kWh            │")
    print(f"  │ 人工    = ${cfg.cost_labor_per_hr:.0f}/hr               │")
    print("  └────────────────────────────────────┘")


def report_baseline(baseline: Schedule):
    """打印 Baseline 结果"""
    print_header("BASELINE — 单独处理 (无混合)")

    for i, phase in enumerate(baseline.phases):
        sid = list(phase.streams.keys())[0]
        print(f"\n  Stream: {sid}")
        print(f"    W = {phase.W:.2f} L/min | Runtime = {_fmt_time(phase.runtime_min)}"
              f" | r_ext = {phase.r_ext:.3f}")
        print(f"    r_water={_fmt_rate(phase.r_water)}"
              f"  r_diesel={_fmt_rate(phase.r_diesel)}"
              f"  r_naoh={_fmt_rate(phase.r_naoh)}")
        print(f"    成本: {_fmt_cost(phase.cost_total)}"
              f"  (柴油={_fmt_cost(phase.cost_diesel)}"
              f"  NaOH={_fmt_cost(phase.cost_naoh)}"
              f"  水={_fmt_cost(phase.cost_water)}"
              f"  电={_fmt_cost(phase.cost_electricity)}"
              f"  人工={_fmt_cost(phase.cost_labor)})")

    print(f"\n  ── Baseline 汇总 ──")
    print(f"  总成本:   {_fmt_cost(baseline.total_cost)}")
    print(f"  总运行:   {_fmt_time(baseline.total_runtime_min)}")


def report_optimized(optimized: Schedule, stats: dict = None):
    """打印优化结果"""
    print_header("OPTIMIZED — 最优喂料计划")

    if optimized is None:
        print("  ⚠ 未找到可行解")
        return

    for i, phase in enumerate(optimized.phases):
        ratio_str = " : ".join(
            f"{sid}={r}" for sid, r in phase.streams.items()
        )
        print(f"\n  Phase {i + 1}: [{ratio_str}]")
        print(f"    混合属性: BTU={phase.blend_props.btu_per_lb:.0f}"
              f"  pH={phase.blend_props.pH:.1f}"
              f"  F={phase.blend_props.f_ppm:.0f}ppm"
              f"  Solid={phase.blend_props.solid_pct:.1f}%"
              f"  Salt={phase.blend_props.salt_ppm:.0f}ppm")
        print(f"    W = {phase.W:.2f} L/min | Runtime = {_fmt_time(phase.runtime_min)}"
              f" | Q = {phase.Q_phase:.1f} L")
        print(f"    r_water={_fmt_rate(phase.r_water)}"
              f"  r_diesel={_fmt_rate(phase.r_diesel)}"
              f"  r_naoh={_fmt_rate(phase.r_naoh)}")
        print(f"    成本: {_fmt_cost(phase.cost_total)}"
              f"  (柴油={_fmt_cost(phase.cost_diesel)}"
              f"  NaOH={_fmt_cost(phase.cost_naoh)}"
              f"  水={_fmt_cost(phase.cost_water)}"
              f"  电={_fmt_cost(phase.cost_electricity)}"
              f"  人工={_fmt_cost(phase.cost_labor)})")

    print(f"\n  ── 优化汇总 ──")
    print(f"  总成本:   {_fmt_cost(optimized.total_cost)}")
    print(f"  总运行:   {_fmt_time(optimized.total_runtime_min)}")

    if stats:
        print(f"\n  搜索统计: 评估={stats['evaluated']:,}"
              f"  不可行剪枝={stats['pruned_infeasible']:,}"
              f"  成本剪枝={stats['pruned_bound']:,}"
              f"  缓存命中={stats['memo_hits']:,}")


def report_comparison(baseline: Schedule, optimized: Schedule):
    """打印 Baseline vs Optimized 对比"""
    print_header("成本对比 — Baseline vs Optimized")

    if optimized is None:
        print("  无法对比: 优化未找到可行解")
        return

    # 汇总成本对比
    b_diesel = sum(p.cost_diesel for p in baseline.phases)
    b_naoh = sum(p.cost_naoh for p in baseline.phases)
    b_water = sum(p.cost_water for p in baseline.phases)
    b_elec = sum(p.cost_electricity for p in baseline.phases)
    b_labor = sum(p.cost_labor for p in baseline.phases)

    o_diesel = sum(p.cost_diesel for p in optimized.phases)
    o_naoh = sum(p.cost_naoh for p in optimized.phases)
    o_water = sum(p.cost_water for p in optimized.phases)
    o_elec = sum(p.cost_electricity for p in optimized.phases)
    o_labor = sum(p.cost_labor for p in optimized.phases)

    items = [
        ("柴油", b_diesel, o_diesel),
        ("NaOH", b_naoh, o_naoh),
        ("DI Water", b_water, o_water),
        ("电力", b_elec, o_elec),
        ("人工", b_labor, o_labor),
        ("═ 总计", baseline.total_cost, optimized.total_cost),
    ]

    header = f"  {'项目':<10} {'Baseline':>14} {'Optimized':>14} {'节省':>10}"
    print(header)
    print(f"  {'─' * 50}")

    for name, bval, oval in items:
        print(f"  {name:<10} {_fmt_cost(bval):>14} {_fmt_cost(oval):>14}"
              f" {_pct_change(bval, oval):>10}")

    # 运行时间对比
    print(f"\n  运行时间:  {_fmt_time(baseline.total_runtime_min):>14}"
          f" {_fmt_time(optimized.total_runtime_min):>14}"
          f" {_pct_change(baseline.total_runtime_min, optimized.total_runtime_min):>10}")

    # 总节省
    savings = baseline.total_cost - optimized.total_cost
    savings_pct = savings / baseline.total_cost * 100 if baseline.total_cost > 0 else 0
    print(f"\n  💰 总节省: {_fmt_cost(savings)} ({savings_pct:.1f}%)")


def report_safety(optimized: Schedule, cfg: SystemConfig):
    """打印安全边界报告"""
    print_header("安全报告 — 属性 vs 边界")

    if optimized is None:
        print("  无优化结果")
        return

    for i, phase in enumerate(optimized.phases):
        b = phase.blend_props
        # 加水后的有效值
        effective_solid = b.solid_pct / (1.0 + phase.r_water) if phase.r_water > 0 else b.solid_pct
        effective_salt = b.salt_ppm / (1.0 + phase.r_water) if phase.r_water > 0 else b.salt_ppm
        BTU_eff = b.btu_per_lb / (1.0 + phase.r_water)

        ratio_str = ":".join(str(r) for r in phase.streams.values())
        print(f"\n  Phase {i + 1} [{ratio_str}]")
        print(f"    BTU_eff   = {BTU_eff:>8.0f}  (target: {cfg.BTU_target:.0f})"
              f"  {'✓ OK' if BTU_eff + phase.r_diesel * cfg.BTU_diesel * cfg.eta >= cfg.BTU_target else '⚠'}")
        print(f"    Solid_eff = {effective_solid:>8.1f}%  (max: {cfg.solid_max_pct:.0f}%)"
              f"  {'✓ OK' if effective_solid <= cfg.solid_max_pct else '⚠ OVER'}")
        print(f"    Salt_eff  = {effective_salt:>8.0f}  (max: {cfg.salt_max_ppm:.0f})"
              f"  {'✓ OK' if effective_salt <= cfg.salt_max_ppm else '⚠ OVER'}")
        print(f"    W         = {phase.W:>8.2f}  (min: {cfg.W_min:.1f})"
              f"  {'✓ OK' if phase.W >= cfg.W_min else '⚠ LOW'}")


def full_report(streams: list, cfg: SystemConfig,
                baseline: Schedule, optimized: Schedule,
                stats: dict = None):
    """完整报告"""
    print("\n" + "▓" * 72)
    print("  AxNano Smart-Feed Algorithm v9 — 优化报告")
    print("▓" * 72)

    report_streams(streams)
    report_config(cfg)
    report_baseline(baseline)
    report_optimized(optimized, stats)
    report_comparison(baseline, optimized)
    report_safety(optimized, cfg)

    print()
    print_separator()
    print("  报告完成")
    print_separator()
    print()

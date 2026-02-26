"""
AxNano Smart-Feed Algorithm v9 — Report Output
================================================
Step 7: Format and output optimal plan, cost comparison, safety boundary report.
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
    """Print waste stream inventory"""
    print_header("Waste Streams (User Input)")

    headers = f"{'ID':<12} {'Qty(L)':>8} {'BTU/lb':>8} {'pH':>6} {'F ppm':>8} {'Solid%':>7} {'Salt ppm':>9}"
    print(f"  {headers}")
    print(f"  {'─' * len(headers)}")

    for s in streams:
        print(f"  {s.stream_id:<12} {s.quantity_L:>8.1f} {s.btu_per_lb:>8.0f}"
              f" {s.pH:>6.1f} {s.f_ppm:>8.0f} {s.solid_pct:>7.1f}"
              f" {s.salt_ppm:>9.0f}")

    total_qty = sum(s.quantity_L for s in streams)
    print(f"\n  Total inventory: {total_qty:,.1f} L | Stream count: {len(streams)}")


def report_config(cfg: SystemConfig):
    """Print system configuration (tunable parameters)"""
    print_header("System Configuration (Tunable Parameters)")

    print("  ┌─ Reactor Parameters ─────────────┐")
    print(f"  │ F_total     = {cfg.F_total:.1f} L/min          │")
    print(f"  │ P_system    = {cfg.P_system:.0f} kW              │")
    print(f"  │ BTU_diesel  = {cfg.BTU_diesel:.0f} BTU/lb        │")
    print(f"  │ η (eff.)    = {cfg.eta:.2f}                  │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ Boundary Conditions ─────────────┐")
    print(f"  │ BTU_target  = {cfg.BTU_target:.0f} BTU/lb         │")
    print(f"  │ Solid_max   = {cfg.solid_max_pct:.0f}%                  │")
    print(f"  │ pH_range    = {cfg.pH_min:.0f} – {cfg.pH_max:.0f}                │")
    print(f"  │ Salt_max    = {cfg.salt_max_ppm:.0f} ppm             │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ Chemical Constants (fitted) ─────┐")
    print(f"  │ K_F_TO_ACID       = {cfg.K_F_TO_ACID:.4f}          │")
    print(f"  │ K_PH_TO_BASE      = {cfg.K_PH_TO_BASE:.1f}            │")
    print(f"  │ K_ACID_TO_NAOH_VOL= {cfg.K_ACID_TO_NAOH_VOL:.2e}      │")
    print("  └────────────────────────────────────┘")

    print("  ┌─ Unit Costs ─────────────────────┐")
    print(f"  │ Diesel  = ${cfg.cost_diesel_per_L:.2f}/L              │")
    print(f"  │ NaOH    = ${cfg.cost_naoh_per_L:.2f}/L              │")
    print(f"  │ DI Water= ${cfg.cost_water_per_L:.5f}/L           │")
    print(f"  │ Power   = ${cfg.cost_electricity_per_kWh:.2f}/kWh            │")
    print(f"  │ Labor   = ${cfg.cost_labor_per_hr:.0f}/hr               │")
    print("  └────────────────────────────────────┘")


def report_baseline(baseline: Schedule):
    """Print baseline results"""
    print_header("BASELINE — Solo Processing (No Blending)")

    for i, phase in enumerate(baseline.phases):
        sid = list(phase.streams.keys())[0]
        print(f"\n  Stream: {sid}")
        print(f"    W = {phase.W:.2f} L/min | Runtime = {_fmt_time(phase.runtime_min)}"
              f" | r_ext = {phase.r_ext:.3f}")
        print(f"    r_water={_fmt_rate(phase.r_water)}"
              f"  r_diesel={_fmt_rate(phase.r_diesel)}"
              f"  r_naoh={_fmt_rate(phase.r_naoh)}")
        print(f"    Cost: {_fmt_cost(phase.cost_total)}"
              f"  (diesel={_fmt_cost(phase.cost_diesel)}"
              f"  NaOH={_fmt_cost(phase.cost_naoh)}"
              f"  water={_fmt_cost(phase.cost_water)}"
              f"  power={_fmt_cost(phase.cost_electricity)}"
              f"  labor={_fmt_cost(phase.cost_labor)})")

    print(f"\n  ── Baseline Summary ──")
    print(f"  Total cost:    {_fmt_cost(baseline.total_cost)}")
    print(f"  Total runtime: {_fmt_time(baseline.total_runtime_min)}")


def report_optimized(optimized: Schedule, stats: dict = None):
    """Print optimized results"""
    print_header("OPTIMIZED — Optimal Feed Plan")

    if optimized is None:
        print("  ⚠ No feasible solution found")
        return

    for i, phase in enumerate(optimized.phases):
        ratio_str = " : ".join(
            f"{sid}={r}" for sid, r in phase.streams.items()
        )
        print(f"\n  Phase {i + 1}: [{ratio_str}]")
        print(f"    Blend props: BTU={phase.blend_props.btu_per_lb:.0f}"
              f"  pH={phase.blend_props.pH:.1f}"
              f"  F={phase.blend_props.f_ppm:.0f}ppm"
              f"  Solid={phase.blend_props.solid_pct:.1f}%"
              f"  Salt={phase.blend_props.salt_ppm:.0f}ppm")
        print(f"    W = {phase.W:.2f} L/min | Runtime = {_fmt_time(phase.runtime_min)}"
              f" | Q = {phase.Q_phase:.1f} L")
        print(f"    r_water={_fmt_rate(phase.r_water)}"
              f"  r_diesel={_fmt_rate(phase.r_diesel)}"
              f"  r_naoh={_fmt_rate(phase.r_naoh)}")
        print(f"    Cost: {_fmt_cost(phase.cost_total)}"
              f"  (diesel={_fmt_cost(phase.cost_diesel)}"
              f"  NaOH={_fmt_cost(phase.cost_naoh)}"
              f"  water={_fmt_cost(phase.cost_water)}"
              f"  power={_fmt_cost(phase.cost_electricity)}"
              f"  labor={_fmt_cost(phase.cost_labor)})")

    print(f"\n  ── Optimization Summary ──")
    print(f"  Total cost:    {_fmt_cost(optimized.total_cost)}")
    print(f"  Total runtime: {_fmt_time(optimized.total_runtime_min)}")

    if stats:
        print(f"\n  Search stats: evaluated={stats['evaluated']:,}"
              f"  infeasible_pruned={stats['pruned_infeasible']:,}"
              f"  templates_kept={stats.get('templates_kept', 'N/A')}"
              f"  cost_pruned={stats['pruned_bound']:,}"
              f"  memo_hits={stats['memo_hits']:,}")


def report_comparison(baseline: Schedule, optimized: Schedule):
    """Print Baseline vs Optimized comparison"""
    print_header("Cost Comparison — Baseline vs Optimized")

    if optimized is None:
        print("  Cannot compare: optimization found no feasible solution")
        return

    # Aggregate cost comparison
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
        ("Diesel", b_diesel, o_diesel),
        ("NaOH", b_naoh, o_naoh),
        ("DI Water", b_water, o_water),
        ("Power", b_elec, o_elec),
        ("Labor", b_labor, o_labor),
        ("═ TOTAL", baseline.total_cost, optimized.total_cost),
    ]

    header = f"  {'Item':<10} {'Baseline':>14} {'Optimized':>14} {'Savings':>10}"
    print(header)
    print(f"  {'─' * 50}")

    for name, bval, oval in items:
        print(f"  {name:<10} {_fmt_cost(bval):>14} {_fmt_cost(oval):>14}"
              f" {_pct_change(bval, oval):>10}")

    # Runtime comparison
    print(f"\n  Runtime:    {_fmt_time(baseline.total_runtime_min):>14}"
          f" {_fmt_time(optimized.total_runtime_min):>14}"
          f" {_pct_change(baseline.total_runtime_min, optimized.total_runtime_min):>10}")

    # Total savings
    savings = baseline.total_cost - optimized.total_cost
    savings_pct = savings / baseline.total_cost * 100 if baseline.total_cost > 0 else 0
    print(f"\n  Total savings: {_fmt_cost(savings)} ({savings_pct:.1f}%)")


def report_safety(optimized: Schedule, cfg: SystemConfig):
    """Print safety boundary report"""
    print_header("Safety Report — Properties vs Boundaries")

    if optimized is None:
        print("  No optimization results")
        return

    for i, phase in enumerate(optimized.phases):
        b = phase.blend_props
        # Effective values after water addition
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
    """Full report"""
    print("\n" + "▓" * 72)
    print("  AxNano Smart-Feed Algorithm v9 — Optimization Report")
    print("▓" * 72)

    report_streams(streams)
    report_config(cfg)
    report_baseline(baseline)
    report_optimized(optimized, stats)
    report_comparison(baseline, optimized)
    report_safety(optimized, cfg)

    print()
    print_separator()
    print("  Report complete")
    print_separator()
    print()

"""
═══════════════════════════════════════════════════════════════
  AxNano Smart-Feed Algorithm v9 — Streamlit Dashboard
  Industrial Dark Theme · SCWO Reactor Optimization
  ────────────────────────────────────────────────────
  PRECISELY ALIGNED with smart_feed_v9 package
═══════════════════════════════════════════════════════════════

SETUP:
  1. Place this file at the project root (next to smart_feed_v9/)
  2. pip install streamlit plotly pandas
  3. streamlit run smartfeed_dashboard.py

PROJECT STRUCTURE:
    code/                         ← project root
    ├── smartfeed_dashboard.py    ← this file
    ├── smart_feed_v9/            ← your package (unchanged)
    │   ├── __init__.py           ← run_optimization(), WasteStream, SystemConfig
    │   ├── models.py             ← WasteStream, SystemConfig, BlendProperties,
    │   │                            PhaseResult, Schedule
    │   ├── blending.py           ← calc_blend_properties, blend_linear, blend_pH
    │   ├── gatekeeper.py         ← gatekeeper, calc_throughput, calc_phase_cost
    │   ├── baseline.py           ← calc_baseline
    │   ├── search.py             ← search, build_optimized_schedule
    │   ├── ratios.py             ← generate_ratios
    │   ├── reporter.py           ← full_report
    │   └── __main__.py           ← CLI entry
    ├── input/                    ← JSON input files
    └── report/                   ← auto-generated reports
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import math
import time
import os
import sys
from dataclasses import asdict

# ═══════════════════════════════════════════════════════════════
# IMPORT smart_feed_v9 PACKAGE
# ═══════════════════════════════════════════════════════════════
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

try:
    from smart_feed_v9.models import (
        WasteStream, SystemConfig, BlendProperties, PhaseResult, Schedule,
    )
    from smart_feed_v9.blending import calc_blend_properties
    from smart_feed_v9.gatekeeper import (
        gatekeeper, calc_throughput, calc_phase_cost, calc_r_water,
    )
    from smart_feed_v9.baseline import calc_baseline
    from smart_feed_v9.search import build_optimized_schedule
    ALGO_AVAILABLE = True
except ImportError as e:
    ALGO_AVAILABLE = False
    IMPORT_ERROR = str(e)


# ═══════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════
DARK_BG = "#080F1A"
PANEL_BG = "#0C1624"
BORDER = "#1A2738"
TEXT_PRI = "#C8D6E5"
TEXT_DIM = "#4A5A6D"
ACCENT = "#F59E0B"
BLUE = "#3B82F6"
GREEN = "#10B981"
RED = "#EF4444"
PURPLE = "#8B5CF6"
STREAM_COLORS = [ACCENT, BLUE, GREEN, RED, PURPLE]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
.stApp {{ background:{DARK_BG}; color:{TEXT_PRI}; font-family:'IBM Plex Sans',sans-serif; }}
.stApp header {{ background:{DARK_BG}!important; }}
section[data-testid="stSidebar"] {{ background:#0A1420!important; border-right:1px solid {BORDER}; }}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label {{ color:{TEXT_PRI}!important; }}
div[data-testid="stMetric"] {{ background:{PANEL_BG}; border:1px solid {BORDER}; border-radius:8px; padding:16px; }}
div[data-testid="stMetric"] label {{ color:{TEXT_DIM}!important; font-family:'JetBrains Mono',monospace!important; font-size:11px!important; text-transform:uppercase; letter-spacing:0.08em; }}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{ color:{ACCENT}!important; font-family:'JetBrains Mono',monospace!important; }}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {{ font-family:'JetBrains Mono',monospace!important; }}
.stTabs [data-baseweb="tab-list"] {{ background:#0A1420; border-bottom:1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ color:{TEXT_DIM}!important; font-family:'JetBrains Mono',monospace!important; font-size:12px!important; letter-spacing:0.06em; }}
.stTabs [aria-selected="true"] {{ color:{ACCENT}!important; border-bottom:2px solid {ACCENT}!important; }}
.stButton>button {{ background:{ACCENT}22!important; border:1px solid {ACCENT}55!important; color:{ACCENT}!important; font-family:'JetBrains Mono',monospace!important; font-weight:600; }}
.stButton>button:hover {{ background:{ACCENT}44!important; box-shadow:0 0 20px {ACCENT}22; }}
.stButton>button[kind="primary"] {{ background:linear-gradient(135deg,{ACCENT},#D97706)!important; color:{DARK_BG}!important; border:none!important; font-weight:700; }}
.stNumberInput input,.stTextInput input {{ background:#0D1520!important; border:1px solid {BORDER}!important; color:{TEXT_PRI}!important; font-family:'JetBrains Mono',monospace!important; }}
.streamlit-expanderHeader {{ background:{PANEL_BG}!important; border:1px solid {BORDER}!important; color:{TEXT_PRI}!important; font-family:'JetBrains Mono',monospace!important; }}
hr {{ border-color:{BORDER}!important; }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
.dim {{ color:{TEXT_DIM}; }}
.header-badge {{ display:inline-block; background:{ACCENT}18; border:1px solid {ACCENT}33; color:{ACCENT}; padding:2px 10px; border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:600; }}
.status-ok {{ display:inline-block; width:7px; height:7px; border-radius:50%; background:{GREEN}; box-shadow:0 0 6px {GREEN}; margin-right:6px; }}
.status-warn {{ display:inline-block; width:7px; height:7px; border-radius:50%; background:{RED}; box-shadow:0 0 6px {RED}; margin-right:6px; }}
</style>
"""

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=TEXT_PRI, size=11),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#111D2B", zerolinecolor="#1A2738"),
    yaxis=dict(gridcolor="#111D2B", zerolinecolor="#1A2738"),
)


# ═══════════════════════════════════════════════════════════════
# CHART BUILDERS (use real Schedule / PhaseResult objects)
# ═══════════════════════════════════════════════════════════════

def _gauge(value, title, max_val, color, suffix=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title=dict(text=title, font=dict(size=12, color=TEXT_DIM)),
        number=dict(font=dict(size=22, color=color), suffix=suffix),
        gauge=dict(
            axis=dict(range=[0, max_val], tickcolor=TEXT_DIM, tickfont=dict(size=9)),
            bar=dict(color=color, thickness=0.7),
            bgcolor="#111D2B", borderwidth=1, bordercolor=BORDER,
            steps=[dict(range=[0, max_val*0.7], color="#111D2B"),
                   dict(range=[max_val*0.7, max_val*0.9], color="#1A2332"),
                   dict(range=[max_val*0.9, max_val], color="#2A1A1A")],
        ),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, height=180, margin=dict(l=20, r=20, t=50, b=10))
    return fig


def _cost_comparison_bar(baseline: Schedule, optimized: Schedule):
    """5-component cost breakdown, Baseline vs Optimized."""
    cats = ["Diesel", "NaOH", "DI Water", "Electricity", "Labor"]
    keys = ["cost_diesel", "cost_naoh", "cost_water", "cost_electricity", "cost_labor"]
    colors = [ACCENT, GREEN, BLUE, PURPLE, RED]

    bv = [sum(getattr(p, k) for p in baseline.phases) for k in keys]
    ov = [sum(getattr(p, k) for p in optimized.phases) for k in keys]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=cats, x=bv, orientation="h", name="Baseline",
        marker_color="#1E2D3D",
        text=[f"${v:.0f}" for v in bv], textposition="auto",
        textfont=dict(color=TEXT_DIM, size=10),
    ))
    fig.add_trace(go.Bar(
        y=cats, x=ov, orientation="h", name="Optimized",
        marker_color=colors,
        text=[f"${v:.0f}" for v in ov], textposition="auto",
        textfont=dict(color=TEXT_PRI, size=10),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, barmode="overlay", height=260,
                      legend=dict(orientation="h", y=1.15, font=dict(size=10)),
                      margin=dict(l=80, r=20, t=40, b=20))
    return fig


def _phase_timeline(optimized: Schedule):
    """Gantt-style timeline from Schedule.phases."""
    if not optimized or not optimized.phases:
        return None
    fig = go.Figure()
    t = 0
    for i, ph in enumerate(optimized.phases):
        ratio_str = ":".join(f"{sid}={r}" for sid, r in ph.streams.items())
        fig.add_trace(go.Bar(
            x=[ph.runtime_min], y=["Schedule"], orientation="h",
            base=t, name=f"P{i+1}",
            marker_color=STREAM_COLORS[i % len(STREAM_COLORS)] + "BB",
            text=f"P{i+1} [{ratio_str}] {ph.runtime_min:.0f}min · ${ph.cost_total:.0f}",
            textposition="inside", textfont=dict(size=9, color=TEXT_PRI),
            hovertext=(f"Phase {i+1}: [{ratio_str}]<br>"
                       f"W={ph.W:.2f} L/min<br>Q={ph.Q_phase:.1f}L<br>"
                       f"Cost: ${ph.cost_total:.2f}"),
        ))
        t += ph.runtime_min
    fig.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=110, showlegend=False,
                      xaxis_title="Runtime (min)", yaxis=dict(visible=False),
                      margin=dict(l=60, r=20, t=10, b=40))
    return fig


def _blend_radar(blend: BlendProperties, cfg: SystemConfig):
    cats = ["BTU/lb", "pH", "Solid%", "Salt ppm", "F⁻ ppm"]
    vals = [
        min(blend.btu_per_lb / 15000, 1.0),
        blend.pH / 14.0,
        blend.solid_pct / (cfg.solid_max_pct * 3),
        blend.salt_ppm / (cfg.salt_max_ppm * 3),
        blend.f_ppm / 20000,
    ]
    vals.append(vals[0]); cats.append(cats[0])
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals, theta=cats, fill="toself",
        fillcolor=f"{ACCENT}22", line=dict(color=ACCENT, width=2),
        marker=dict(size=5, color=ACCENT),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, height=270,
                      polar=dict(bgcolor="rgba(0,0,0,0)",
                                 radialaxis=dict(visible=True, range=[0,1],
                                                 gridcolor="#111D2B",
                                                 tickfont=dict(size=8, color=TEXT_DIM)),
                                 angularaxis=dict(gridcolor="#1A2738",
                                                  tickfont=dict(size=10, color=TEXT_PRI))),
                      margin=dict(l=40, r=40, t=30, b=30))
    return fig


def _sensitivity(streams, base_cfg, param, label, x_range):
    """Vary one SystemConfig param, plot baseline total cost."""
    base_dict = {f: getattr(base_cfg, f) for f in SystemConfig.__dataclass_fields__}
    costs = []
    for v in x_range:
        try:
            cfg_copy = SystemConfig(**{**base_dict, param: v})
            bl = calc_baseline(streams, cfg_copy)
            costs.append(bl.total_cost if bl.total_cost < 1e8 else None)
        except Exception:
            costs.append(None)
    valid = [(x, c) for x, c in zip(x_range, costs) if c is not None]
    if not valid:
        return None
    xs, ys = zip(*valid)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers",
                             line=dict(color=ACCENT, width=2),
                             marker=dict(size=4, color=ACCENT),
                             fill="tozeroy", fillcolor=f"{ACCENT}11"))
    # Current value marker
    cur = getattr(base_cfg, param)
    try:
        cur_bl = calc_baseline(streams, base_cfg)
        fig.add_trace(go.Scatter(x=[cur], y=[cur_bl.total_cost], mode="markers",
                                 marker=dict(size=10, color=RED, symbol="diamond"),
                                 name="Current"))
    except Exception:
        pass
    fig.update_layout(**PLOTLY_LAYOUT, height=240, showlegend=False,
                      xaxis_title=label, yaxis_title="Baseline Cost ($)",
                      margin=dict(l=60, r=20, t=20, b=50))
    return fig


# ═══════════════════════════════════════════════════════════════
# JSON LOADER (exact same format as input/example_input.json)
# ═══════════════════════════════════════════════════════════════

def _load_json(text: str):
    data = json.loads(text)
    streams = [WasteStream(**item) for item in data["streams"]]
    return streams, data.get("config", {})

def _apply_overrides(cfg: SystemConfig, overrides: dict):
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, type(getattr(cfg, k))(v))
    return cfg


# ═══════════════════════════════════════════════════════════════
# DEFAULT STREAMS (= input/example_input.json)
# ═══════════════════════════════════════════════════════════════

def _defaults():
    return [
        WasteStream(stream_id="Resin", quantity_L=200.0, btu_per_lb=12500,
                     pH=3.0, f_ppm=15000, solid_pct=100.0, salt_ppm=500, moisture_pct=0.0),
        WasteStream(stream_id="AFFF", quantity_L=500.0, btu_per_lb=1,
                     pH=7.5, f_ppm=5000, solid_pct=0.5, salt_ppm=200, moisture_pct=99.5),
        WasteStream(stream_id="Caustic", quantity_L=300.0, btu_per_lb=0,
                     pH=13.5, f_ppm=0, solid_pct=0.0, salt_ppm=8000, moisture_pct=65.0),
    ]


# ═══════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="AxNano Smart-Feed v9", page_icon="▲",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Check package availability ──
    if not ALGO_AVAILABLE:
        st.error(f"""
**smart_feed_v9 package not found.**

Import error: `{IMPORT_ERROR}`

Place this file at the project root, next to the `smart_feed_v9/` directory:
```
code/
├── smartfeed_dashboard.py   ← this file
└── smart_feed_v9/           ← your package
    ├── __init__.py
    ├── models.py
    ├── blending.py
    ├── gatekeeper.py
    ├── baseline.py
    ├── search.py
    ├── ratios.py
    └── reporter.py
```
        """)
        return

    # ── Session state ──
    if "streams" not in st.session_state:
        st.session_state.streams = _defaults()
    if "cfg" not in st.session_state:
        st.session_state.cfg = SystemConfig()
    if "result" not in st.session_state:
        st.session_state.result = None

    streams = st.session_state.streams
    cfg = st.session_state.cfg

    # ═══ HEADER ═══
    h1, h2 = st.columns([5, 5])
    with h1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:4px 0;">
            <div style="width:36px;height:36px;border-radius:6px;
                background:linear-gradient(135deg,{ACCENT}22,{ACCENT}08);
                border:1px solid {ACCENT}33;display:flex;align-items:center;
                justify-content:center;font-size:16px;font-weight:700;
                color:{ACCENT};font-family:JetBrains Mono;">▲</div>
            <div>
                <div style="font-size:18px;font-weight:600;color:#E2E8F0;letter-spacing:-0.02em;">
                    AxNano Smart-Feed</div>
                <div style="font-size:10px;color:{TEXT_DIM};font-family:JetBrains Mono;">
                    SCWO Reactor Optimization v9 ·
                    <span class="header-badge">LIVE ALGORITHM</span></div>
            </div>
        </div>""", unsafe_allow_html=True)
    with h2:
        st.markdown(f"""<div style="text-align:right;padding-top:10px;">
            <span class="mono dim" style="font-size:10px;">
            <span class="status-ok"></span>SYSTEM NOMINAL │
            F_total: {cfg.F_total} L/min │ η: {cfg.eta} │
            BTU_target: {cfg.BTU_target:.0f} │ P_system: {cfg.P_system:.0f}kW
            </span></div>""", unsafe_allow_html=True)
    st.markdown("---")

    # ═══ SIDEBAR: SystemConfig editor ═══
    with st.sidebar:
        st.markdown(f'<div class="mono" style="color:{ACCENT};font-size:13px;font-weight:600;letter-spacing:0.05em;">⚙ SYSTEM CONFIG</div>', unsafe_allow_html=True)
        st.markdown("")

        with st.expander("Reactor Parameters «A1,A3»", expanded=True):
            cfg.F_total = st.number_input("F_total (L/min)", 1.0, 50.0, cfg.F_total, 0.5)
            cfg.P_system = st.number_input("P_system (kW)", 100.0, 1000.0, cfg.P_system, 10.0)
            cfg.BTU_diesel = st.number_input("BTU_diesel (BTU/lb)", 10000.0, 25000.0, cfg.BTU_diesel, 100.0)
            cfg.eta = st.number_input("η (thermal efficiency)", 0.5, 1.0, cfg.eta, 0.01)

        with st.expander("Boundary Conditions"):
            cfg.BTU_target = st.number_input("BTU_target (BTU/lb)", 500.0, 10000.0, cfg.BTU_target, 100.0)
            cfg.solid_max_pct = st.number_input("solid_max_pct (%)", 1.0, 50.0, cfg.solid_max_pct, 0.5)
            cfg.pH_min = st.number_input("pH_min", 0.0, 7.0, cfg.pH_min, 0.5)
            cfg.pH_max = st.number_input("pH_max", 7.0, 14.0, cfg.pH_max, 0.5)
            cfg.salt_max_ppm = st.number_input("salt_max_ppm", 500.0, 50000.0, cfg.salt_max_ppm, 500.0)

        with st.expander("Unit Costs «A5»"):
            cfg.cost_diesel_per_L = st.number_input("Diesel ($/L)", 0.1, 10.0, cfg.cost_diesel_per_L, 0.1)
            cfg.cost_naoh_per_L = st.number_input("NaOH ($/L)", 0.1, 10.0, cfg.cost_naoh_per_L, 0.01)
            cfg.cost_water_per_L = st.number_input("DI Water ($/L)", 0.0001, 0.1, cfg.cost_water_per_L, 0.0001, format="%.4f")
            cfg.cost_electricity_per_kWh = st.number_input("Electricity ($/kWh)", 0.01, 1.0, cfg.cost_electricity_per_kWh, 0.01)
            cfg.cost_labor_per_hr = st.number_input("Labor ($/hr)", 10.0, 500.0, cfg.cost_labor_per_hr, 10.0)

        with st.expander("K-Value Calibration «B2,B3»"):
            cfg.K_F_TO_ACID = st.number_input("K_F_TO_ACID (meq/L·ppm)", 0.01, 0.2, cfg.K_F_TO_ACID, 0.001, format="%.4f")
            cfg.K_PH_TO_BASE = st.number_input("K_PH_TO_BASE (meq/L·pH)", 5.0, 200.0, cfg.K_PH_TO_BASE, 5.0)
            cfg.K_ACID_TO_NAOH_VOL = st.number_input("K_ACID_TO_NAOH_VOL (L/meq)", 1e-6, 1e-3, cfg.K_ACID_TO_NAOH_VOL, 1e-6, format="%.2e")
            st.markdown(f'<div class="mono dim" style="font-size:9px;margin-top:8px;">⚠ K-values are theoretical estimates. Pending calibration from operational data.</div>', unsafe_allow_html=True)

        with st.expander("Search Parameters"):
            cfg.ratio_sum_max = st.number_input("ratio_sum_max", 5, 20, cfg.ratio_sum_max, 1)
            cfg.W_min = st.number_input("W_min (L/min)", 0.1, 5.0, cfg.W_min, 0.1)

        st.markdown("---")

        # ── Load from input/ directory ──
        with st.expander("📂 Load from input/"):
            input_dir = os.path.join(_THIS_DIR, "input")
            if os.path.isdir(input_dir):
                json_files = sorted(f for f in os.listdir(input_dir) if f.endswith(".json"))
                if json_files:
                    sel = st.selectbox("Select file", json_files)
                    if st.button("Load File"):
                        try:
                            with open(os.path.join(input_dir, sel)) as f:
                                new_streams, overrides = _load_json(f.read())
                            st.session_state.streams = new_streams
                            st.session_state.cfg = SystemConfig()
                            _apply_overrides(st.session_state.cfg, overrides)
                            st.success(f"✓ {sel}: {len(new_streams)} streams")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        # ── Paste JSON ──
        with st.expander("📥 Paste JSON"):
            st.markdown(f'<div class="dim" style="font-size:10px;margin-bottom:8px;">Same format as input/example_input.json</div>', unsafe_allow_html=True)
            json_in = st.text_area("JSON", height=120, placeholder='{"streams":[...],"config":{...}}')
            if st.button("Parse & Load"):
                try:
                    new_streams, overrides = _load_json(json_in)
                    st.session_state.streams = new_streams
                    st.session_state.cfg = SystemConfig()
                    _apply_overrides(st.session_state.cfg, overrides)
                    st.success(f"✓ Loaded {len(new_streams)} streams")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # ═══ TABS ═══
    tab_streams, tab_opt, tab_phases, tab_sens = st.tabs([
        "◆ WASTE STREAMS", "◆ OPTIMIZATION", "◆ PHASE DETAILS", "◆ SENSITIVITY",
    ])

    # ═══════════════════════════════════════════════════════════
    # TAB 1: WASTE STREAMS — edit real WasteStream objects
    # ═══════════════════════════════════════════════════════════
    with tab_streams:
        st.markdown(f'<div class="mono dim" style="font-size:11px;margin-bottom:12px;">{len(streams)} STREAMS · Total: {sum(s.quantity_L for s in streams):,.0f} L</div>', unsafe_allow_html=True)

        for i, s in enumerate(streams):
            with st.expander(f"🔶 {s.stream_id} — {s.quantity_L:.0f} L, BTU={s.btu_per_lb:.0f}, pH={s.pH:.1f}", expanded=(i==0)):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    s.stream_id = st.text_input("stream_id", s.stream_id, key=f"sid_{i}")
                    s.quantity_L = st.number_input("quantity_L", 0.1, 100000.0, s.quantity_L, 10.0, key=f"qty_{i}")
                with c2:
                    s.btu_per_lb = st.number_input("btu_per_lb", 0.0, 25000.0, float(s.btu_per_lb), 100.0, key=f"btu_{i}")
                    s.pH = st.number_input("pH", 0.0, 14.0, s.pH, 0.1, key=f"ph_{i}")
                with c3:
                    s.f_ppm = st.number_input("f_ppm", 0.0, 50000.0, float(s.f_ppm), 100.0, key=f"fp_{i}")
                    s.solid_pct = st.number_input("solid_pct", 0.0, 100.0, s.solid_pct, 0.5, key=f"sol_{i}")
                with c4:
                    s.salt_ppm = st.number_input("salt_ppm", 0.0, 50000.0, float(s.salt_ppm), 100.0, key=f"salt_{i}")
                    s.moisture_pct = st.number_input("moisture_pct «A9»", 0.0, 100.0, s.moisture_pct, 1.0, key=f"moi_{i}")
                if st.button(f"🗑 Remove {s.stream_id}", key=f"rm_{i}"):
                    st.session_state.streams.pop(i); st.rerun()

        c_add, _, _ = st.columns([2, 2, 6])
        with c_add:
            if st.button("➕ ADD STREAM"):
                streams.append(WasteStream(
                    stream_id=f"Stream_{len(streams)+1}", quantity_L=100.0,
                    btu_per_lb=2000, pH=7.0, f_ppm=500,
                    solid_pct=5.0, salt_ppm=1000, moisture_pct=50.0))
                st.rerun()

        if streams:
            st.markdown("---")
            st.markdown(f'<div class="mono dim" style="font-size:11px;">COMPARISON TABLE</div>', unsafe_allow_html=True)
            df = pd.DataFrame([{
                "stream_id": s.stream_id, "quantity_L": s.quantity_L,
                "BTU/lb": s.btu_per_lb, "pH": s.pH, "F⁻(ppm)": s.f_ppm,
                "Solid%": s.solid_pct, "Salt(ppm)": s.salt_ppm, "H₂O%": s.moisture_pct,
            } for s in streams])
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════
    # TAB 2: OPTIMIZATION — calls REAL calc_baseline + build_optimized_schedule
    # ═══════════════════════════════════════════════════════════
    with tab_opt:
        n = len(streams)
        if not (1 <= n <= 5):
            st.warning(f"Need 1–5 streams (currently {n}).")
        else:
            c_btn, c_warn = st.columns([3, 7])
            with c_btn:
                run = st.button("▶ RUN OPTIMIZATION", type="primary", use_container_width=True)
            with c_warn:
                if n >= 4:
                    st.markdown(f'<div class="mono" style="color:{ACCENT};font-size:10px;padding-top:8px;">⚠ {n} streams: ~{"1s" if n==4 else "60s"} compute time</div>', unsafe_allow_html=True)

            if run:
                with st.spinner(f"Running full v9 search for {n} streams..."):
                    t0 = time.time()
                    try:
                        baseline = calc_baseline(streams, cfg)
                        optimized, stats = build_optimized_schedule(streams, cfg)
                        savings_pct = 0.0
                        if optimized and baseline.total_cost > 0:
                            savings_pct = (1 - optimized.total_cost / baseline.total_cost) * 100
                        st.session_state.result = {
                            "baseline": baseline, "optimized": optimized,
                            "stats": stats, "savings_pct": savings_pct,
                            "elapsed": time.time() - t0,
                        }
                    except Exception as e:
                        st.error(f"Error: {e}")
                        import traceback; st.code(traceback.format_exc())

            res = st.session_state.result
            if res is None:
                st.markdown(f"""<div style="text-align:center;padding:80px 0;color:{TEXT_DIM};">
                    <div style="font-size:48px;margin-bottom:12px;">⚡</div>
                    <div class="mono" style="font-size:14px;">No results yet</div>
                    <div class="mono dim" style="font-size:11px;margin-top:6px;">Press RUN OPTIMIZATION to call calc_baseline() + build_optimized_schedule()</div>
                </div>""", unsafe_allow_html=True)
            else:
                bl = res["baseline"]
                opt = res["optimized"]
                stats = res["stats"]
                sp = res["savings_pct"]
                elapsed = res["elapsed"]

                if opt is None:
                    st.warning("⚠ No feasible optimized solution. Showing baseline only.")
                    m1, m2 = st.columns(2)
                    with m1: st.metric("BASELINE COST", f"${bl.total_cost:,.2f}")
                    with m2: st.metric("BASELINE RUNTIME", f"{bl.total_runtime_hr:.2f} hr")
                else:
                    sav = bl.total_cost - opt.total_cost

                    # ── Metrics ──
                    m1, m2, m3, m4, m5 = st.columns(5)
                    with m1: st.metric("BASELINE", f"${bl.total_cost:,.0f}")
                    with m2: st.metric("OPTIMIZED", f"${opt.total_cost:,.0f}", delta=f"-${sav:,.0f}", delta_color="normal")
                    with m3: st.metric("SAVINGS", f"{sp:.1f}%")
                    with m4: st.metric("RUNTIME", f"{opt.total_runtime_hr:.1f} hr", delta=f"vs {bl.total_runtime_hr:.1f} hr")
                    with m5: st.metric("PHASES", f"{len(opt.phases)}", delta=f"{elapsed:.2f}s")

                    st.markdown("")

                    # ── Charts ──
                    cl, cr = st.columns([5, 5])
                    with cl:
                        st.markdown(f'<div class="mono" style="font-size:11px;color:{ACCENT};margin-bottom:8px;">◆ COST BREAKDOWN</div>', unsafe_allow_html=True)
                        st.plotly_chart(_cost_comparison_bar(bl, opt), use_container_width=True, config={"displayModeBar": False})
                    with cr:
                        st.markdown(f'<div class="mono" style="font-size:11px;color:{BLUE};margin-bottom:8px;">◆ FEED SCHEDULE TIMELINE</div>', unsafe_allow_html=True)
                        tf = _phase_timeline(opt)
                        if tf: st.plotly_chart(tf, use_container_width=True, config={"displayModeBar": False})

                    # ── Gauges: first phase ──
                    st.markdown("")
                    p1 = opt.phases[0]
                    btu_eff = p1.blend_props.btu_per_lb / (1 + p1.r_water) if p1.r_water > 0 else p1.blend_props.btu_per_lb
                    g1, g2, g3, g4 = st.columns(4)
                    with g1: st.plotly_chart(_gauge(p1.W, "P1 Throughput (W)", cfg.F_total, ACCENT, " L/min"), use_container_width=True, config={"displayModeBar": False})
                    with g2: st.plotly_chart(_gauge(btu_eff, "P1 BTU_eff", cfg.BTU_target * 1.5, RED), use_container_width=True, config={"displayModeBar": False})
                    with g3: st.plotly_chart(_gauge(p1.r_water, "P1 r_water", max(3.0, p1.r_water * 1.5), BLUE), use_container_width=True, config={"displayModeBar": False})
                    with g4: st.plotly_chart(_gauge(p1.r_diesel, "P1 r_diesel", max(0.2, p1.r_diesel * 2), GREEN), use_container_width=True, config={"displayModeBar": False})

                    # ── Search stats ──
                    st.markdown(f"""<div class="mono dim" style="font-size:10px;margin-top:16px;">
                        SEARCH: evaluated={stats['evaluated']:,} ·
                        infeasible_pruned={stats['pruned_infeasible']:,} ·
                        templates_kept={stats.get('templates_kept','N/A')} ·
                        cost_pruned={stats['pruned_bound']:,} ·
                        memo_hits={stats['memo_hits']:,}
                    </div>""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # TAB 3: PHASE DETAILS — full PhaseResult breakdowns
    # ═══════════════════════════════════════════════════════════
    with tab_phases:
        res = st.session_state.result
        if res is None or res.get("optimized") is None:
            st.info("Run optimization first.")
        else:
            bl = res["baseline"]
            opt = res["optimized"]

            # ── Baseline ──
            st.markdown(f'<div class="mono" style="font-size:12px;color:{RED};margin-bottom:12px;">◆ BASELINE — SOLO PROCESSING (calc_baseline)</div>', unsafe_allow_html=True)
            for ph in bl.phases:
                sid = list(ph.streams.keys())[0]
                st.markdown(f"""<div style="background:{PANEL_BG};border:1px solid {BORDER};border-radius:6px;padding:12px;margin-bottom:8px;">
                    <div class="mono" style="color:{TEXT_PRI};font-size:12px;font-weight:600;">{sid} — ${ph.cost_total:,.2f}</div>
                    <div class="mono dim" style="font-size:10px;margin-top:4px;">
                        W={ph.W:.2f} L/min · Runtime={ph.runtime_min:.1f}min · r_ext={ph.r_ext:.3f}<br>
                        r_water={ph.r_water:.4f} · r_diesel={ph.r_diesel:.4f} · r_naoh={ph.r_naoh:.6f}<br>
                        diesel=${ph.cost_diesel:.2f} · NaOH=${ph.cost_naoh:.2f} · water=${ph.cost_water:.2f} ·
                        electricity=${ph.cost_electricity:.2f} · labor=${ph.cost_labor:.2f}
                    </div></div>""", unsafe_allow_html=True)

            st.markdown("---")

            # ── Optimized ──
            st.markdown(f'<div class="mono" style="font-size:12px;color:{GREEN};margin-bottom:12px;">◆ OPTIMIZED — MULTI-PHASE FEED PLAN (build_optimized_schedule)</div>', unsafe_allow_html=True)
            for i, ph in enumerate(opt.phases):
                ratio_str = " : ".join(f"{sid}={r}" for sid, r in ph.streams.items())
                color = STREAM_COLORS[i % len(STREAM_COLORS)]
                b = ph.blend_props

                # Safety checks (same logic as reporter.py → report_safety)
                eff_solid = b.solid_pct / (1 + ph.r_water) if ph.r_water > 0 else b.solid_pct
                eff_salt = b.salt_ppm / (1 + ph.r_water) if ph.r_water > 0 else b.salt_ppm
                btu_eff = b.btu_per_lb / (1 + ph.r_water)
                solid_ok = eff_solid <= cfg.solid_max_pct
                salt_ok = eff_salt <= cfg.salt_max_ppm
                w_ok = ph.W >= cfg.W_min
                all_ok = solid_ok and salt_ok and w_ok

                st.markdown(f"""<div style="background:{PANEL_BG};border:1px solid {color}44;border-left:3px solid {color};border-radius:6px;padding:14px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div class="mono" style="color:{color};font-size:13px;font-weight:600;">Phase {i+1}: [{ratio_str}]</div>
                        <div class="mono" style="color:{ACCENT};font-size:14px;font-weight:700;">${ph.cost_total:,.2f}</div>
                    </div>
                    <div class="mono dim" style="font-size:10px;margin-top:6px;">
                        Blend: BTU={b.btu_per_lb:.0f} · pH={b.pH:.1f} · F={b.f_ppm:.0f}ppm · Solid={b.solid_pct:.1f}% · Salt={b.salt_ppm:.0f}ppm
                    </div>
                    <div class="mono dim" style="font-size:10px;margin-top:4px;">
                        W={ph.W:.2f} L/min · Runtime={ph.runtime_min:.1f}min · Q={ph.Q_phase:.1f}L ·
                        r_water={ph.r_water:.4f} · r_diesel={ph.r_diesel:.4f} · r_naoh={ph.r_naoh:.6f}
                    </div>
                    <div class="mono" style="font-size:10px;margin-top:4px;">
                        diesel=${ph.cost_diesel:.2f} · NaOH=${ph.cost_naoh:.2f} · water=${ph.cost_water:.2f} ·
                        electricity=${ph.cost_electricity:.2f} · labor=${ph.cost_labor:.2f}
                    </div>
                    <div class="mono" style="font-size:10px;margin-top:6px;">
                        <span class="status-{'ok' if all_ok else 'warn'}"></span>
                        BTU_eff={btu_eff:.0f} · Solid_eff={eff_solid:.1f}% {'✓' if solid_ok else '⚠ OVER'} ·
                        Salt_eff={eff_salt:.0f} {'✓' if salt_ok else '⚠ OVER'} ·
                        W={ph.W:.2f} {'✓' if w_ok else '⚠ LOW'}
                    </div>
                </div>""", unsafe_allow_html=True)

            # Radar for P1
            cr1, cr2 = st.columns(2)
            with cr1:
                st.markdown(f'<div class="mono" style="font-size:11px;color:{ACCENT};margin-bottom:8px;">◆ PHASE 1 BLEND PROPERTIES</div>', unsafe_allow_html=True)
                st.plotly_chart(_blend_radar(opt.phases[0].blend_props, cfg), use_container_width=True, config={"displayModeBar": False})

    # ═══════════════════════════════════════════════════════════
    # TAB 4: SENSITIVITY — uses real calc_baseline
    # ═══════════════════════════════════════════════════════════
    with tab_sens:
        if not streams:
            st.warning("Add at least 1 stream.")
        else:
            st.markdown(f'<div class="mono" style="font-size:11px;color:{ACCENT};margin-bottom:4px;">◆ PARAMETER SENSITIVITY (BASELINE COST)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="dim" style="font-size:11px;margin-bottom:20px;">Red diamond = current value. Shows how baseline cost responds to parameter changes.</div>', unsafe_allow_html=True)

            s1, s2 = st.columns(2)
            with s1:
                st.markdown(f'<div class="mono dim" style="font-size:10px;">F_TOTAL (L/min)</div>', unsafe_allow_html=True)
                fig = _sensitivity(streams, cfg, "F_total", "F_total (L/min)", [x/2 for x in range(4,40)])
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                st.markdown(f'<div class="mono dim" style="font-size:10px;">BTU_TARGET</div>', unsafe_allow_html=True)
                fig = _sensitivity(streams, cfg, "BTU_target", "BTU_target", list(range(1000,5000,100)))
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with s2:
                st.markdown(f'<div class="mono dim" style="font-size:10px;">η (THERMAL EFFICIENCY)</div>', unsafe_allow_html=True)
                fig = _sensitivity(streams, cfg, "eta", "η", [x/100 for x in range(50,100,2)])
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                st.markdown(f'<div class="mono dim" style="font-size:10px;">SOLID_MAX_PCT (%)</div>', unsafe_allow_html=True)
                fig = _sensitivity(streams, cfg, "solid_max_pct", "solid_max_pct (%)", [x/2 for x in range(4,60)])
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.markdown(f'<div class="mono dim" style="font-size:10px;">DIESEL COST ($/L)</div>', unsafe_allow_html=True)
            fig = _sensitivity(streams, cfg, "cost_diesel_per_L", "cost_diesel_per_L ($/L)", [x/10 for x in range(5,40)])
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Footer ──
    st.markdown("---")
    st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:4px 0;">
        <span class="mono dim" style="font-size:9px;">
            AXNANO SMART-FEED v9 · LIVE ALGORITHM · «A1»–«A9» ASSUMPTIONS ACTIVE</span>
        <span class="mono dim" style="font-size:9px;">
            smart_feed_v9 package · Streamlit Dashboard</span>
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

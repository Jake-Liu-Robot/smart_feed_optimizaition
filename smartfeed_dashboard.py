"""
═══════════════════════════════════════════════════════════════
  AxNano Smart-Feed Algorithm v9 — Streamlit Dashboard
  Industrial Theme · SCWO Reactor Optimization
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
# THEME — Industrial Dark (steel + amber)
# ═══════════════════════════════════════════════════════════════
BG = "#12151A"
PANEL_BG = "#1A1E26"
BORDER = "#2A3040"
TEXT_PRI = "#D4DAE3"
TEXT_DIM = "#6B7A8D"
ACCENT = "#F59E0B"          # industrial amber
BLUE = "#5E81AC"            # steel blue
GREEN = "#4CAF50"           # indicator green
RED = "#E74C3C"             # alarm red
PURPLE = "#9B8EC4"          # muted violet
CYAN = "#56B6C2"            # coolant cyan
STREAM_COLORS = [ACCENT, BLUE, GREEN, RED, PURPLE]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
.stApp {{ background:{BG}; color:{TEXT_PRI}; font-family:'Inter',sans-serif; }}
.stApp header {{ background:{BG}!important; border-bottom:2px solid {BORDER}; }}
section[data-testid="stSidebar"] {{ background:{PANEL_BG}!important; border-right:2px solid {BORDER}; }}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label {{ color:{TEXT_PRI}!important; }}
div[data-testid="stMetric"] {{ background:{PANEL_BG}; border:1px solid {BORDER}; border-top:3px solid {ACCENT}; border-radius:4px; padding:18px; }}
div[data-testid="stMetric"] label {{ color:{TEXT_DIM}!important; font-family:'JetBrains Mono',monospace!important; font-size:10px!important; text-transform:uppercase; letter-spacing:0.12em; font-weight:600; }}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{ color:{ACCENT}!important; font-family:'JetBrains Mono',monospace!important; font-size:26px!important; font-weight:700!important; }}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {{ font-family:'JetBrains Mono',monospace!important; font-size:12px!important; font-weight:600!important; }}
.stTabs [data-baseweb="tab-list"] {{ background:{BG}; border-bottom:2px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ color:{TEXT_DIM}!important; font-family:'JetBrains Mono',monospace!important; font-size:12px!important; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; padding:10px 18px!important; }}
.stTabs [aria-selected="true"] {{ color:{ACCENT}!important; border-bottom:3px solid {ACCENT}!important; background:rgba(245,158,11,0.06)!important; border-radius:2px 2px 0 0; }}
.stButton>button {{ background:rgba(245,158,11,0.08)!important; border:1px solid rgba(245,158,11,0.25)!important; color:{ACCENT}!important; font-family:'JetBrains Mono',monospace!important; font-weight:600; letter-spacing:0.04em; border-radius:3px!important; transition:all 0.15s ease; }}
.stButton>button:hover {{ background:rgba(245,158,11,0.15)!important; border-color:{ACCENT}!important; }}
.stDataFrame {{ border:1px solid {BORDER}; border-radius:4px; overflow:hidden; }}
.stDataFrame th {{ background:#1E2430!important; color:{ACCENT}!important; font-family:'JetBrains Mono',monospace!important; font-size:10px!important; font-weight:700!important; text-transform:uppercase; letter-spacing:0.08em; }}
.stDataFrame td {{ font-family:'JetBrains Mono',monospace!important; font-size:12px!important; font-weight:500; color:{TEXT_PRI}!important; }}
.stButton>button[kind="primary"] {{ background:{ACCENT}!important; color:#12151A!important; border:none!important; font-weight:800; font-size:13px!important; padding:10px 28px!important; letter-spacing:0.06em; border-radius:3px!important; box-shadow:0 0 20px rgba(245,158,11,0.25); transition:all 0.15s ease; }}
.stButton>button[kind="primary"]:hover {{ background:#D97706!important; box-shadow:0 0 30px rgba(245,158,11,0.4); }}
.stNumberInput label,.stTextInput label,.stTextArea label {{ color:{TEXT_PRI}!important; font-family:'JetBrains Mono',monospace!important; font-size:12px!important; font-weight:600!important; }}
.stNumberInput input,.stTextInput input,.stTextArea textarea {{ background:#151920!important; border:1px solid {BORDER}!important; color:{TEXT_PRI}!important; font-family:'JetBrains Mono',monospace!important; border-radius:3px!important; font-weight:500; }}
[data-baseweb="input"] {{ background-color:#151920!important; }}
[data-baseweb="input"] input {{ background-color:#151920!important; color:{TEXT_PRI}!important; }}
.stSelectbox [data-baseweb="select"] {{ background-color:#151920!important; }}
.stSelectbox [data-baseweb="select"] > div {{ background-color:#151920!important; color:{TEXT_PRI}!important; }}
.streamlit-expanderHeader {{ background:{PANEL_BG}!important; border:1px solid {BORDER}!important; color:{TEXT_PRI}!important; font-family:'JetBrains Mono',monospace!important; border-radius:4px!important; font-weight:600!important; }}
[data-testid="stExpander"] summary {{ color:{TEXT_PRI}!important; }}
[data-testid="stExpander"] summary span {{ color:{TEXT_PRI}!important; font-weight:600!important; }}
[data-testid="stExpander"] details {{ border:1px solid {BORDER}!important; background:{PANEL_BG}!important; }}
[data-testid="stExpander"] summary p {{ color:{TEXT_PRI}!important; font-size:14px!important; font-weight:600!important; }}
hr {{ border-color:{BORDER}!important; }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
.dim {{ color:{TEXT_DIM}; }}
.header-badge {{ display:inline-block; background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.35); color:{ACCENT}; padding:3px 10px; border-radius:2px; font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:800; letter-spacing:0.1em; text-transform:uppercase; }}
.status-ok {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:{GREEN}; box-shadow:0 0 6px rgba(76,175,80,0.5); margin-right:6px; animation:pulse-green 2s ease-in-out infinite; }}
.status-warn {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:{RED}; box-shadow:0 0 6px rgba(231,76,60,0.5); margin-right:6px; animation:pulse-red 1s ease-in-out infinite; }}
@keyframes pulse-green {{ 0%,100% {{ box-shadow:0 0 4px rgba(76,175,80,0.3); }} 50% {{ box-shadow:0 0 10px rgba(76,175,80,0.6); }} }}
@keyframes pulse-red {{ 0%,100% {{ box-shadow:0 0 4px rgba(231,76,60,0.3); }} 50% {{ box-shadow:0 0 12px rgba(231,76,60,0.7); }} }}
</style>
"""

def _rgba(hex_color, alpha):
    """Convert #RRGGBB + alpha (0.0–1.0) to rgba() string for Plotly."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _layout(**kw):
    """Base Plotly layout with per-chart overrides (avoids duplicate-kwarg errors)."""
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, monospace", color=TEXT_PRI, size=11),
        margin=dict(l=40, r=20, t=40, b=40),
        xaxis=dict(gridcolor="#2A3040", zerolinecolor="#3A4555"),
        yaxis=dict(gridcolor="#2A3040", zerolinecolor="#3A4555"),
    )
    base.update(kw)
    return base


# ═══════════════════════════════════════════════════════════════
# CHART BUILDERS (use real Schedule / PhaseResult objects)
# ═══════════════════════════════════════════════════════════════


def _cost_comparison_bar(baseline: Schedule, optimized: Schedule):
    """5-component cost breakdown, Baseline vs Optimized."""
    cats = ["Diesel", "NaOH", "DI Water", "Electricity", "Labor"]
    keys = ["cost_diesel", "cost_naoh", "cost_water", "cost_electricity", "cost_labor"]

    bv = [sum(getattr(p, k) for p in baseline.phases) for k in keys]
    ov = [sum(getattr(p, k) for p in optimized.phases) for k in keys]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=cats, x=bv, orientation="h", name="Baseline",
        marker_color="#3A4555",
        text=[f"${v:.0f}" for v in bv], textposition="auto",
        textfont=dict(color=TEXT_DIM, size=10),
    ))
    fig.add_trace(go.Bar(
        y=cats, x=ov, orientation="h", name="Optimized",
        marker_color=ACCENT,
        text=[f"${v:.0f}" for v in ov], textposition="auto",
        textfont=dict(color="#12151A", size=10, family="JetBrains Mono"),
    ))
    fig.update_layout(**_layout(barmode="overlay", height=260,
                      legend=dict(orientation="h", y=1.15, font=dict(size=10)),
                      margin=dict(l=80, r=20, t=40, b=20)))
    return fig


def _phase_timeline(optimized: Schedule):
    """Vertical phase list: label [feed plan] → time and cost."""
    if not optimized or not optimized.phases:
        return None
    # Build horizontal stacked bar per phase row
    phase_labels = []
    for i, ph in enumerate(optimized.phases):
        parts = " + ".join(f"{sid}×{r}" for sid, r in ph.streams.items())
        phase_labels.append(f"Phase {i+1}: {parts}")
    # Reverse for bottom-to-top display
    phase_labels = phase_labels[::-1]
    phases_rev = list(reversed(optimized.phases))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=phase_labels,
        x=[ph.runtime_min for ph in phases_rev],
        orientation="h",
        marker_color=[_rgba(STREAM_COLORS[i % len(STREAM_COLORS)], 0.8)
                      for i in range(len(phases_rev)-1, -1, -1)],
        text=[f"{ph.runtime_min:.0f} min · ${ph.cost_total:.0f}" for ph in phases_rev],
        textposition="inside",
        textfont=dict(size=11, color="#FFFFFF", family="JetBrains Mono"),
        hovertext=[f"Feed: {' + '.join(f'{sid}×{r}' for sid, r in ph.streams.items())}<br>"
                   f"Throughput: {ph.W:.2f} L/min<br>"
                   f"Volume: {ph.Q_phase:.1f} L<br>"
                   f"Cost: ${ph.cost_total:.2f}" for ph in phases_rev],
        hoverinfo="text",
    ))
    h = max(120, 50 * len(optimized.phases) + 40)
    fig.update_layout(**_layout(barmode="stack", height=h, showlegend=False,
                      xaxis_title="Runtime (min)",
                      yaxis=dict(tickfont=dict(size=10, color=TEXT_PRI)),
                      margin=dict(l=200, r=20, t=10, b=40)))
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
        <div style="display:flex;align-items:center;gap:14px;padding:6px 0;">
            <div style="width:42px;height:42px;border-radius:3px;
                background:{ACCENT};
                display:flex;align-items:center;
                justify-content:center;font-size:18px;font-weight:800;
                color:#12151A;font-family:JetBrains Mono;
                box-shadow:0 0 20px rgba(245,158,11,0.3);">▲</div>
            <div>
                <div style="font-size:20px;font-weight:700;color:{TEXT_PRI};letter-spacing:0.02em;
                    font-family:'JetBrains Mono',monospace;">
                    AXNANO SMART-FEED</div>
                <div style="font-size:10px;color:{TEXT_DIM};font-family:JetBrains Mono;margin-top:3px;
                    letter-spacing:0.1em;text-transform:uppercase;">
                    SCWO REACTOR OPTIMIZATION v9 ·
                    <span class="header-badge">LIVE</span></div>
            </div>
        </div>""", unsafe_allow_html=True)
    with h2:
        st.markdown(f"""<div style="text-align:right;padding-top:12px;">
            <span class="mono" style="font-size:10px;color:{TEXT_DIM};letter-spacing:0.06em;">
            <span class="status-ok"></span>SYSTEM NOMINAL │
            F_total: <b style="color:{ACCENT}">{cfg.F_total}</b> L/min │
            η: <b style="color:{ACCENT}">{cfg.eta}</b> │
            BTU: <b style="color:{ACCENT}">{cfg.BTU_target:.0f}</b> │
            P: <b style="color:{ACCENT}">{cfg.P_system:.0f}</b>kW
            </span></div>""", unsafe_allow_html=True)
    st.markdown("---")

    # ═══ SIDEBAR: SystemConfig editor ═══
    with st.sidebar:
        st.markdown(f'<div class="mono" style="color:{ACCENT};font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">⚙ SYSTEM CONFIG</div>', unsafe_allow_html=True)
        st.markdown("")

        with st.expander("Reactor Parameters", expanded=True):
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

        with st.expander("Unit Costs"):
            cfg.cost_diesel_per_L = st.number_input("Diesel ($/L)", 0.1, 10.0, cfg.cost_diesel_per_L, 0.1)
            cfg.cost_naoh_per_L = st.number_input("NaOH ($/L)", 0.1, 10.0, cfg.cost_naoh_per_L, 0.01)
            cfg.cost_water_per_L = st.number_input("DI Water ($/L)", 0.0001, 0.1, cfg.cost_water_per_L, 0.0001, format="%.4f")
            cfg.cost_electricity_per_kWh = st.number_input("Electricity ($/kWh)", 0.01, 1.0, cfg.cost_electricity_per_kWh, 0.01)
            cfg.cost_labor_per_hr = st.number_input("Labor ($/hr)", 10.0, 500.0, cfg.cost_labor_per_hr, 10.0)

        with st.expander("K-Value Calibration"):
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
    tab_intro, tab_streams, tab_opt, tab_ops, tab_phases = st.tabs([
        "◆ INTRODUCTION", "◆ WASTE STREAMS", "◆ OPTIMIZATION", "◆ OPERATION", "◆ PHASE DETAILS",
    ])

    # ═══════════════════════════════════════════════════════════
    # TAB 0: INTRODUCTION
    # ═══════════════════════════════════════════════════════════
    with tab_intro:
        # ── shared card / section styles ──
        _CARD = f"background:{PANEL_BG};border:1px solid {BORDER};border-radius:8px;padding:24px 28px;"
        _CARD_ACC = f"background:{PANEL_BG};border:1px solid {BORDER};border-top:3px solid {ACCENT};border-radius:8px;padding:20px 24px;"
        _SEC_TITLE = f"font-family:'JetBrains Mono',monospace;font-size:10px;color:{ACCENT};font-weight:700;letter-spacing:0.12em;text-transform:uppercase;margin:0 0 14px 0;"

        # ────────────────────── Hero Banner ──────────────────────
        st.markdown(f"""
<div style="text-align:center;padding:36px 20px 28px 20px;">
  <div style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:800;color:{TEXT_PRI};letter-spacing:0.04em;">
    SMART<span style="color:{ACCENT};">-</span>FEED</div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{TEXT_DIM};letter-spacing:0.15em;margin-top:6px;">
    SCWO REACTOR · FEED OPTIMIZATION · v9</div>
  <div style="width:60px;height:3px;background:{ACCENT};margin:16px auto 0 auto;border-radius:2px;"></div>
</div>
""", unsafe_allow_html=True)

        # ──────────────── About + Key Highlights (two cols) ──────────────────
        st.markdown(f"""
<div style="display:flex;gap:20px;margin-bottom:24px;flex-wrap:wrap;align-items:stretch;">
  <div style="flex:3;min-width:340px;{_CARD}display:flex;flex-direction:column;justify-content:center;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:{ACCENT};font-weight:700;letter-spacing:0.12em;text-transform:uppercase;margin:0 0 16px 0;">What is Smart-Feed?</div>
    <div style="color:{TEXT_PRI};font-size:14px;line-height:1.9;">
      AxNano's SCWO (Supercritical Water Oxidation) reactor destroys <b style="color:{CYAN};">PFAS</b> and hazardous waste.
      However, waste streams are chaotic — if fed arbitrarily into the reactor, large amounts of costly
      external additives (diesel, NaOH, DI water) are required to meet reactor boundary conditions.<br><br>
      Different waste streams have complementary properties — high BTU vs low BTU,
      acidic vs alkaline, solid vs liquid.
      <span style="color:{ACCENT};font-weight:700;">Smart-Feed</span> finds the optimal blending plan to minimize
      external inputs, reducing operating cost by up to
      <span style="color:{GREEN};font-weight:700;">20 %</span> compared to processing each stream individually.
    </div>
  </div>
  <div style="flex:2;min-width:240px;display:flex;flex-direction:column;gap:12px;justify-content:center;">
    <div style="{_CARD_ACC}text-align:center;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:800;color:{ACCENT};">20%</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{TEXT_DIM};letter-spacing:0.1em;margin-top:4px;">COST REDUCTION</div>
    </div>
    <div style="{_CARD_ACC}text-align:center;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:800;color:{ACCENT};">≤ 5</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{TEXT_DIM};letter-spacing:0.1em;margin-top:4px;">WASTE STREAMS</div>
    </div>
    <div style="{_CARD_ACC}text-align:center;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:800;color:{ACCENT};">EXACT</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{TEXT_DIM};letter-spacing:0.1em;margin-top:4px;">GLOBAL OPTIMUM</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ──────────────── Dashboard Tabs — compact list ──────────────────
        _tab_items = [
            ("①", "WASTE STREAMS",  "Input and edit waste stream properties — quantity, BTU, pH, fluorine, solids, salt"),
            ("②", "OPTIMIZATION",   "Run the algorithm, view cost savings, cost breakdown, and feed schedule"),
            ("③", "OPERATION",      "Operator instructions — per-phase pump rates, additive flow rates, runtime"),
            ("④", "PHASE DETAILS",  "Engineering deep-dive — blend properties, safety checks, full cost itemization"),
        ]
        _list_html = ""
        for num, name, desc in _tab_items:
            _list_html += (
                f'<div style="display:flex;align-items:baseline;gap:10px;padding:10px 0;'
                f'border-bottom:1px solid {BORDER};">'
                f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:14px;color:{ACCENT};font-weight:700;min-width:22px;">{num}</span>'
                f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:{TEXT_PRI};font-weight:700;letter-spacing:0.04em;min-width:140px;">{name}</span>'
                f'<span style="color:{TEXT_DIM};font-size:11px;">{desc}</span>'
                f'</div>'
            )

        st.markdown(
            f'<div style="{_CARD}margin-bottom:28px;">'
            f'<div style="{_SEC_TITLE}">Dashboard Tabs</div>'
            f'{_list_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ──────────────── Flowchart: HOW TO USE ──────────────────
        _ARROW = f"display:flex;align-items:center;padding:0 2px;font-size:22px;color:{ACCENT};font-weight:700;"

        _flow_steps = [
            (ACCENT, "1", "WASTE STREAMS",  "Enter waste inventory<br>or load from JSON"),
            (BLUE,   "2", "CONFIGURE",      "Adjust reactor params<br>in sidebar if needed"),
            (GREEN,  "3", "OPTIMIZE",       "Click ▶ RUN<br>OPTIMIZATION"),
            (PURPLE, "4", "REVIEW",         "Operation (operators)<br>Phase Details (eng.)"),
        ]
        _flow_html = ""
        for idx, (color, num, title, desc) in enumerate(_flow_steps):
            if idx > 0:
                _flow_html += f'<div style="{_ARROW}">&#10141;</div>'
            _r, _g, _b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            _flow_html += (
                f'<div style="flex:1;min-width:150px;max-width:220px;text-align:center;">'
                f'<div style="background:rgba({_r},{_g},{_b},0.10);border:2px solid {color};border-radius:10px;padding:18px 12px 14px 12px;">'
                f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:20px;font-weight:800;color:{color};line-height:1;">{num}</div>'
                f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;font-weight:700;color:{TEXT_PRI};letter-spacing:0.06em;margin-top:8px;">{title}</div>'
                f'<div style="color:{TEXT_DIM};font-size:10px;margin-top:6px;line-height:1.5;">{desc}</div>'
                f'</div></div>'
            )

        st.markdown(
            f'<div style="{_CARD}margin-bottom:20px;">'
            f'<div style="{_SEC_TITLE}">How to Use — Workflow</div>'
            f'<div style="display:flex;align-items:center;gap:0;margin:12px 0 4px 0;flex-wrap:wrap;justify-content:center;">'
            f'{_flow_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # ──────────────── Algorithm footer ──────────────────
        st.markdown(f"""
<div style="background:{PANEL_BG};border:1px solid {BORDER};border-radius:6px;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
  <span style="font-family:'JetBrains Mono',monospace;color:{TEXT_DIM};font-size:9px;letter-spacing:0.08em;">
    ALGORITHM v9 · EXACT SEARCH · PRE-COMPUTED TEMPLATES + BRANCH & BOUND + MEMOIZATION</span>
  <span style="font-family:'JetBrains Mono',monospace;color:{TEXT_DIM};font-size:9px;letter-spacing:0.08em;">
    MVP PROTOTYPE · K-VALUES PENDING CALIBRATION</span>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # TAB 1: WASTE STREAMS — edit real WasteStream objects
    # ═══════════════════════════════════════════════════════════
    with tab_streams:
        st.markdown(f'<div class="mono dim" style="font-size:11px;margin-bottom:12px;">{len(streams)} STREAMS · Total: {sum(s.quantity_L for s in streams):,.0f} L</div>', unsafe_allow_html=True)

        for i, s in enumerate(streams):
            with st.expander(f"🔶 {s.stream_id}", expanded=(i==0)):
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
                    s.moisture_pct = st.number_input("moisture_pct", 0.0, 100.0, s.moisture_pct, 1.0, key=f"moi_{i}")
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
                    <div class="mono" style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;">AWAITING INPUT</div>
                    <div class="mono dim" style="font-size:10px;margin-top:6px;letter-spacing:0.04em;">Press RUN OPTIMIZATION to execute calc_baseline() + build_optimized_schedule()</div>
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
                    with m1: st.metric("BASELINE COST", f"${bl.total_cost:,.0f}")
                    with m2: st.metric("OPTIMIZED COST", f"${opt.total_cost:,.0f}", delta=f"-${sav:,.0f}", delta_color="inverse")
                    with m3: st.metric("COST SAVINGS", f"{sp:.1f}%")
                    with m4: st.metric("TOTAL RUNTIME", f"{opt.total_runtime_hr:.1f} hr", delta=f"-{bl.total_runtime_hr - opt.total_runtime_hr:.1f} hr", delta_color="inverse")
                    with m5: st.metric("FEED PHASES", f"{len(opt.phases)}")

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

                    # ── Search stats ──
                    st.markdown(f"""<div class="mono dim" style="font-size:10px;margin-top:16px;">
                        SEARCH: evaluated={stats['evaluated']:,} ·
                        infeasible_pruned={stats['pruned_infeasible']:,} ·
                        templates_kept={stats.get('templates_kept','N/A')} ·
                        cost_pruned={stats['pruned_bound']:,} ·
                        memo_hits={stats['memo_hits']:,}
                    </div>""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # TAB 3: OPERATION — Operator feed plan instructions
    # ═══════════════════════════════════════════════════════════
    with tab_ops:
        res = st.session_state.result
        if res is None or res.get("optimized") is None:
            st.info("Run optimization first.")
        else:
            opt = res["optimized"]

            # ── Styles ──
            _OP_LBL = f"color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;"
            _OP_HDR = f"background:{PANEL_BG};border:1px solid {BORDER};border-radius:6px;padding:14px;margin-bottom:2px;"
            _OP_ROW = f"background:{PANEL_BG};border-left:1px solid {BORDER};border-right:1px solid {BORDER};border-bottom:1px solid {BORDER};padding:8px 14px;"
            _OP_TH = f"color:{ACCENT};font-size:9px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:4px 8px;"
            _OP_TD = f"color:{TEXT_PRI};font-size:12px;font-weight:500;padding:4px 8px;font-family:JetBrains Mono,monospace;"
            _OP_NOTE = f"color:{TEXT_DIM};font-size:9px;font-style:italic;"

            st.markdown(f'<div class="mono" style="font-size:12px;color:{ACCENT};margin-bottom:4px;">◆ FEED PLAN — OPERATOR INSTRUCTIONS</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="{_OP_NOTE}">Set pump rates and timers for each phase in sequence. All flow rates in L/min.</div>', unsafe_allow_html=True)
            st.markdown("")

            for i, ph in enumerate(opt.phases):
                color = STREAM_COLORS[i % len(STREAM_COLORS)]
                ratio_sum = sum(ph.streams.values())
                rt_h = int(ph.runtime_min // 60)
                rt_m = int(ph.runtime_min % 60)
                runtime_fmt = f"{rt_h}h {rt_m}m" if rt_h > 0 else f"{rt_m} min"

                # ── Phase header ──
                st.markdown(f'<div style="{_OP_HDR}border-left:3px solid {color};display:flex;justify-content:space-between;align-items:center;"><span class="mono" style="color:{color};font-size:14px;font-weight:700;">PHASE {i+1}</span><span class="mono" style="color:{TEXT_PRI};font-size:12px;">⏱ {runtime_fmt} · {ph.Q_phase:.0f} L · <span style="color:{ACCENT};font-weight:700;">${ph.cost_total:,.2f}</span></span></div>', unsafe_allow_html=True)

                # ── ① WASTE FEED table ──
                st.markdown(f'<div style="{_OP_ROW}"><span style="{_OP_LBL}">① WASTE FEED</span></div>', unsafe_allow_html=True)
                # Table header
                waste_hdr = f'<div style="{_OP_ROW}display:flex;border-bottom:1px solid {BORDER};"><span style="{_OP_TH}flex:2;">Stream</span><span style="{_OP_TH}flex:1;text-align:right;">Ratio</span><span style="{_OP_TH}flex:1.5;text-align:right;">Feed Rate</span><span style="{_OP_TH}flex:1.5;text-align:right;">Volume</span></div>'
                st.markdown(waste_hdr, unsafe_allow_html=True)
                # Table rows
                for sid, r in ph.streams.items():
                    rate = r / ratio_sum * ph.W
                    vol = r / ratio_sum * ph.Q_phase
                    st.markdown(f'<div style="{_OP_ROW}display:flex;"><span style="{_OP_TD}flex:2;color:{ACCENT};font-weight:600;">{sid}</span><span style="{_OP_TD}flex:1;text-align:right;">×{r}</span><span style="{_OP_TD}flex:1.5;text-align:right;color:{GREEN};font-weight:600;">{rate:.2f} L/min</span><span style="{_OP_TD}flex:1.5;text-align:right;">{vol:.1f} L</span></div>', unsafe_allow_html=True)
                # Waste subtotal
                st.markdown(f'<div style="{_OP_ROW}display:flex;border-top:1px solid {BORDER};"><span style="{_OP_TD}flex:2;color:{TEXT_DIM};font-weight:600;">Total Waste</span><span style="{_OP_TD}flex:1;"></span><span style="{_OP_TD}flex:1.5;text-align:right;color:{TEXT_PRI};font-weight:700;">{ph.W:.2f} L/min</span><span style="{_OP_TD}flex:1.5;text-align:right;font-weight:600;">{ph.Q_phase:.1f} L</span></div>', unsafe_allow_html=True)

                # ── ② ADDITIVES table ──
                st.markdown(f'<div style="{_OP_ROW}margin-top:4px;"><span style="{_OP_LBL}">② ADDITIVES</span></div>', unsafe_allow_html=True)
                add_hdr = f'<div style="{_OP_ROW}display:flex;border-bottom:1px solid {BORDER};"><span style="{_OP_TH}flex:2;">Additive</span><span style="{_OP_TH}flex:1;text-align:right;">Ratio</span><span style="{_OP_TH}flex:1.5;text-align:right;">Pump Rate</span></div>'
                st.markdown(add_hdr, unsafe_allow_html=True)
                additives = [
                    ("DI Water", ph.r_water, ph.r_water * ph.W, BLUE),
                    ("Diesel", ph.r_diesel, ph.r_diesel * ph.W, RED),
                    ("NaOH (35%)", ph.r_naoh, ph.r_naoh * ph.W, PURPLE),
                ]
                for name, ratio, flow, clr in additives:
                    st.markdown(f'<div style="{_OP_ROW}display:flex;"><span style="{_OP_TD}flex:2;color:{clr};font-weight:600;">{name}</span><span style="{_OP_TD}flex:1;text-align:right;">{ratio:.4f}</span><span style="{_OP_TD}flex:1.5;text-align:right;color:{GREEN};font-weight:600;">{flow:.4f} L/min</span></div>', unsafe_allow_html=True)
                # Total flow
                total_flow = ph.W * (1 + ph.r_ext)
                st.markdown(f'<div style="{_OP_ROW}display:flex;border-top:1px solid {BORDER};"><span style="{_OP_TD}flex:2;color:{TEXT_DIM};font-weight:600;">Total Flow (waste + additives)</span><span style="{_OP_TD}flex:1;"></span><span style="{_OP_TD}flex:1.5;text-align:right;color:{ACCENT};font-weight:700;">{total_flow:.2f} L/min</span></div>', unsafe_allow_html=True)

                st.markdown("")

            # ── Summary ──
            st.markdown("---")
            total_rt = opt.total_runtime_min
            th = int(total_rt // 60)
            tm = int(total_rt % 60)
            total_vol = sum(ph.Q_phase for ph in opt.phases)
            s1, s2, s3 = st.columns(3)
            with s1: st.metric("TOTAL RUNTIME", f"{th}h {tm}m")
            with s2: st.metric("TOTAL VOLUME", f"{total_vol:,.0f} L")
            with s3: st.metric("TOTAL COST", f"${opt.total_cost:,.2f}")

    # ═══════════════════════════════════════════════════════════
    # TAB 4: PHASE DETAILS — full PhaseResult breakdowns
    # ═══════════════════════════════════════════════════════════
    with tab_phases:
        res = st.session_state.result
        if res is None or res.get("optimized") is None:
            st.info("Run optimization first.")
        else:
            bl = res["baseline"]
            opt = res["optimized"]

            # ── Helper: labeled section row ──
            _LBL = f"color:{ACCENT};font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;min-width:190px;display:inline-block;margin-right:12px;"
            _VAL = f"color:{TEXT_PRI};font-size:11px;"
            _NOTE = f"color:{TEXT_DIM};font-size:9px;font-style:italic;margin-top:2px;"

            # ── Baseline ──
            st.markdown(f'<div class="mono" style="font-size:12px;color:{RED};margin-bottom:12px;">◆ BASELINE — INDIVIDUAL PROCESSING</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="{_NOTE}">Each waste stream processed independently without blending — serves as cost benchmark.</div>', unsafe_allow_html=True)
            st.markdown("")
            for ph in bl.phases:
                sid = list(ph.streams.keys())[0]
                st.markdown(f'<div style="background:{PANEL_BG};border:1px solid {BORDER};border-radius:6px;padding:14px;margin-bottom:8px;"><span class="mono" style="color:{TEXT_PRI};font-size:13px;font-weight:700;">{sid}</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:{PANEL_BG};border-left:1px solid {BORDER};border-right:1px solid {BORDER};padding:4px 14px;"><span class="mono" style="{_LBL}">THROUGHPUT</span> <span class="mono" style="{_VAL}">{ph.W:.2f} L/min</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:{PANEL_BG};border-left:1px solid {BORDER};border-right:1px solid {BORDER};padding:4px 14px;"><span class="mono" style="{_LBL}">RUNTIME</span> <span class="mono" style="{_VAL}">{ph.runtime_min:.1f} min</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:{PANEL_BG};border:1px solid {BORDER};border-radius:0 0 6px 6px;padding:4px 14px 10px;margin-bottom:8px;"><span class="mono" style="{_LBL}">COST</span> <span class="mono" style="color:{ACCENT};font-size:12px;font-weight:700;">${ph.cost_total:,.2f}</span> <span class="mono" style="color:{TEXT_DIM};font-size:10px;"> — Diesel ${ph.cost_diesel:.2f} · NaOH ${ph.cost_naoh:.2f} · Water ${ph.cost_water:.2f} · Elec ${ph.cost_electricity:.2f} · Labor ${ph.cost_labor:.2f}</span></div>', unsafe_allow_html=True)

            st.markdown("---")

            # ── Optimized ──
            st.markdown(f'<div class="mono" style="font-size:12px;color:{GREEN};margin-bottom:12px;">◆ OPTIMIZED — MULTI-PHASE BLENDED FEED PLAN</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:{TEXT_DIM};font-size:9px;font-style:italic;">Waste streams blended in optimal ratios across multiple phases to minimize total operating cost.</div>', unsafe_allow_html=True)
            st.markdown("")
            for i, ph in enumerate(opt.phases):
                ratio_str = " + ".join(f"{sid} ×{r}" for sid, r in ph.streams.items())
                color = STREAM_COLORS[i % len(STREAM_COLORS)]
                b = ph.blend_props

                # Safety checks — effective values after ALL additives (water + diesel + NaOH)
                r_total = ph.r_water + ph.r_diesel + ph.r_naoh  # total external volume per unit waste
                dilution = 1.0 + r_total
                eff_solid = b.solid_pct / dilution
                eff_salt = b.salt_ppm / dilution
                # BTU after water dilution + diesel heat contribution
                btu_eff = b.btu_per_lb / (1.0 + ph.r_water) + ph.r_diesel * cfg.BTU_diesel * cfg.eta
                solid_ok = eff_solid <= cfg.solid_max_pct
                salt_ok = eff_salt <= cfg.salt_max_ppm
                w_ok = ph.W >= cfg.W_min
                all_ok = solid_ok and salt_ok and w_ok

                # ── Per-stream feed rates ──
                ratio_sum = sum(ph.streams.values())
                feed_details = " + ".join(
                    f"{sid} ×{r} ({r/ratio_sum*ph.W:.2f} L/min)"
                    for sid, r in ph.streams.items()
                )

                # ── Additive actual flow rates ──
                water_flow = ph.r_water * ph.W
                diesel_flow = ph.r_diesel * ph.W
                naoh_flow = ph.r_naoh * ph.W

                # ── Build rows as list of (label, value, note) ──
                _s = f"status-{'ok' if all_ok else 'warn'}"
                rows = [
                    ("FEED RECIPE", feed_details,
                     f"Blending ratio × (individual feed rate) · Total waste feed: {ph.W:.2f} L/min"),
                    ("BLEND PROPERTIES",
                     f"Heat Value: {b.btu_per_lb:.0f} BTU/lb · pH: {b.pH:.1f} · Fluoride: {b.f_ppm:.0f} ppm · Solids: {b.solid_pct:.1f}% · Salt: {b.salt_ppm:.0f} ppm",
                     "Combined properties of the blended mixture before entering the reactor"),
                    ("OPERATING CONDITIONS",
                     f"Feed Rate: {ph.W:.2f} L/min · Runtime: {ph.runtime_min:.1f} min · Volume Processed: {ph.Q_phase:.1f} L",
                     "Reactor throughput, processing time, and total volume for this phase"),
                    ("ADDITIVE RATIOS",
                     f"DI Water: {ph.r_water:.4f} ({water_flow:.3f} L/min) · Diesel: {ph.r_diesel:.4f} ({diesel_flow:.4f} L/min) · NaOH: {ph.r_naoh:.6f} ({naoh_flow:.5f} L/min)",
                     "Ratio = volume of additive per unit waste feed · (actual flow rate at current feed rate)"),
                    ("COST BREAKDOWN",
                     f"Diesel: ${ph.cost_diesel:.2f} · NaOH: ${ph.cost_naoh:.2f} · DI Water: ${ph.cost_water:.2f} · Electricity: ${ph.cost_electricity:.2f} · Labor: ${ph.cost_labor:.2f}",
                     "Itemized operating cost for each consumable and resource"),
                    ("SAFETY CHECK",
                     f'<span class="{_s}"></span> Eff. Heat Value: {btu_eff:.0f} BTU/lb · Eff. Solids: {eff_solid:.1f}% {"✓" if solid_ok else "⚠ EXCEEDS LIMIT"} · Eff. Salt: {eff_salt:.0f} ppm {"✓" if salt_ok else "⚠ EXCEEDS LIMIT"} · Feed Rate: {ph.W:.2f} L/min {"✓" if w_ok else "⚠ BELOW MINIMUM"}',
                     "Effective values after dilution — verifies reactor safety limits are met"),
                ]
                # Header
                st.markdown(f'<div style="background:{PANEL_BG};border:1px solid {BORDER};border-left:3px solid {color};border-radius:6px;padding:14px 14px 4px;margin-bottom:2px;display:flex;justify-content:space-between;align-items:center;"><span class="mono" style="color:{color};font-size:13px;font-weight:700;">Phase {i+1}</span><span class="mono" style="color:{ACCENT};font-size:15px;font-weight:800;">${ph.cost_total:,.2f}</span></div>', unsafe_allow_html=True)
                # Each labeled row
                for lbl, val, note in rows:
                    st.markdown(f'<div style="background:{PANEL_BG};border-left:1px solid {BORDER};border-right:1px solid {BORDER};padding:6px 14px;border-bottom:1px solid {BORDER};"><span class="mono" style="{_LBL}">{lbl}</span><span class="mono" style="{_VAL}">{val}</span><br><span style="{_NOTE}">{note}</span></div>', unsafe_allow_html=True)
                st.markdown("")

    # ── Footer ──
    st.markdown("---")
    st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:4px 0;">
        <span class="mono dim" style="font-size:9px;letter-spacing:0.1em;text-transform:uppercase;">
            AXNANO SMART-FEED v9 · LIVE ALGORITHM</span>
        <span class="mono dim" style="font-size:9px;letter-spacing:0.1em;">
            smart_feed_v9 · INDUSTRIAL CONTROL PANEL</span>
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

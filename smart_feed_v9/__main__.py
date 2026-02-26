#!/usr/bin/env python3
"""
AxNano Smart-Feed Algorithm v9 — Main Entry Point
===================================================

Usage:
  1. Use default input (input/example_input.json):
     python -m smart_feed_v9

  2. Specify a file in the input/ directory:
     python -m smart_feed_v9 --input my_waste.json

  3. Adjust parameters:
     python -m smart_feed_v9 --input my_waste.json --F_total 10.5 --eta 0.85

Input files should be placed in the input/ directory.
See input/example_input.json for format reference.
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime

from . import WasteStream, SystemConfig, run_optimization


# ═══════════════════════════════════════════════════════════════
# Input directory and default file
# ═══════════════════════════════════════════════════════════════

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PKG_DIR)
INPUT_DIR = os.path.join(_PROJECT_ROOT, "input")
DEFAULT_INPUT = "example_input.json"


def resolve_input_path(filename: str) -> str:
    """
    Resolve input file path.

    Priority:
    1. If absolute path and exists → use directly
    2. Look in input/ directory
    3. Look in current working directory
    """
    # Absolute path
    if os.path.isabs(filename) and os.path.isfile(filename):
        return filename

    # input/ directory
    in_input_dir = os.path.join(INPUT_DIR, filename)
    if os.path.isfile(in_input_dir):
        return in_input_dir

    # Current working directory
    if os.path.isfile(filename):
        return filename

    raise FileNotFoundError(
        f"Input file not found: {filename}\n"
        f"  Searched: {INPUT_DIR}/\n"
        f"  Please place JSON files in the input/ directory"
    )


def load_from_json(filepath: str) -> tuple:
    """
    Load waste stream inventory and optional config overrides from JSON.

    JSON format:
    {
      "streams": [
        {
          "stream_id": "Resin",
          "quantity_L": 200,
          "btu_per_lb": 12500,
          "pH": 3.0,
          "f_ppm": 15000,
          "solid_pct": 100,
          "salt_ppm": 500,
          "moisture_pct": 0
        },
        ...
      ],
      "config": {           // optional — only list parameters to override
        "F_total": 10.5,
        "eta": 0.85,
        "cost_diesel_per_L": 1.20
      }
    }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse waste streams
    streams = []
    for item in data["streams"]:
        streams.append(WasteStream(**item))

    # Parse config overrides
    cfg_overrides = data.get("config", {})

    return streams, cfg_overrides


def build_config(cli_args: dict, json_overrides: dict = None) -> SystemConfig:
    """
    Build configuration: defaults → JSON overrides → CLI overrides

    Priority: CLI > JSON > defaults
    """
    cfg = SystemConfig()
    overrides = {}

    # JSON overrides
    if json_overrides:
        overrides.update(json_overrides)

    # CLI overrides (only non-None values)
    config_fields = {f.name for f in SystemConfig.__dataclass_fields__.values()}
    for key, val in cli_args.items():
        if val is not None and key in config_fields:
            overrides[key] = val

    # Apply overrides
    for key, val in overrides.items():
        if hasattr(cfg, key):
            setattr(cfg, key, type(getattr(cfg, key))(val))

    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="AxNano Smart-Feed Algorithm v9 — SCWO Feed Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m smart_feed_v9                              # default: input/example_input.json
  python -m smart_feed_v9 --input my_waste.json        # specify: input/my_waste.json
  python -m smart_feed_v9 --input my_waste.json --eta 0.85  # specify file + tune params
        """,
    )

    # Input
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT,
                        help=f"JSON filename in input/ directory (default: {DEFAULT_INPUT})")

    # Tunable parameters (all optional, override defaults)
    g = parser.add_argument_group("Tunable parameters (all have defaults)")

    # Reactor
    g.add_argument("--F_total", type=float, default=None,
                   help="Total feed capacity L/min (default: 11.0)")
    g.add_argument("--P_system", type=float, default=None,
                   help="System power kW (default: 400)")

    # Boundaries
    g.add_argument("--BTU_target", type=float, default=None,
                   help="Target heat value BTU/lb (default: 2200)")
    g.add_argument("--solid_max_pct", type=float, default=None,
                   help="Max solid content %% (default: 15)")
    g.add_argument("--pH_min", type=float, default=None,
                   help="Min pH (default: 6)")
    g.add_argument("--pH_max", type=float, default=None,
                   help="Max pH (default: 9)")
    g.add_argument("--salt_max_ppm", type=float, default=None,
                   help="Max salt concentration ppm (default: 5000)")
    g.add_argument("--eta", type=float, default=None,
                   help="Thermal efficiency factor (default: 0.89)")

    # Chemical constants
    g.add_argument("--K_F_TO_ACID", type=float, default=None,
                   help="F ppm → acid equivalent coefficient (default: 0.053)")
    g.add_argument("--K_PH_TO_BASE", type=float, default=None,
                   help="pH base contribution coefficient (default: 50.0)")
    g.add_argument("--K_ACID_TO_NAOH_VOL", type=float, default=None,
                   help="Acid → NaOH volume coefficient (default: 8.28e-5)")

    # Costs
    g.add_argument("--cost_diesel_per_L", type=float, default=None,
                   help="Diesel $/L (default: 1.00)")
    g.add_argument("--cost_naoh_per_L", type=float, default=None,
                   help="NaOH $/L (default: 1.51)")
    g.add_argument("--cost_water_per_L", type=float, default=None,
                   help="DI Water $/L (default: 0.00199)")
    g.add_argument("--cost_electricity_per_kWh", type=float, default=None,
                   help="Electricity $/kWh (default: 0.12)")
    g.add_argument("--cost_labor_per_hr", type=float, default=None,
                   help="Labor $/hr (default: 100)")

    # Search
    g.add_argument("--ratio_sum_max", type=int, default=None,
                   help="Max ratio sum (default: 11)")
    g.add_argument("--W_min", type=float, default=None,
                   help="Min feasible throughput L/min (default: 0.5)")

    args = parser.parse_args()

    # ── Load data ──
    json_overrides = {}
    try:
        input_path = resolve_input_path(args.input)
        streams, json_overrides = load_from_json(input_path)
        print(f"✓ Loaded: {input_path} ({len(streams)} waste streams)")
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"✗ JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Build config ──
    cfg = build_config(vars(args), json_overrides)

    # ── Run optimization ──
    print(f"\n⏳ Optimizing feed plan for {len(streams)} waste streams...")
    t0 = time.time()

    # Tee: output to both terminal and buffer for saving report file
    report_buf = io.StringIO()
    _real_stdout = sys.stdout

    class _Tee:
        def __init__(self, *targets):
            self.targets = targets
        def write(self, data):
            for t in self.targets:
                t.write(data)
        def flush(self):
            for t in self.targets:
                t.flush()

    sys.stdout = _Tee(_real_stdout, report_buf)
    result = run_optimization(streams, cfg, verbose=True)
    elapsed = time.time() - t0
    print(f"\n  ⏱ Computation time: {elapsed:.2f}s")
    print(f"  💰 Cost savings: {result['savings_pct']:.1f}%")
    sys.stdout = _real_stdout

    # ── Save report to report/ directory ──
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    report_dir = os.path.join(project_root, "report")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"report_{timestamp}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_buf.getvalue())

    print(f"\n  📄 Report saved: {report_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AxNano Smart-Feed Algorithm v9 — 主入口
========================================

运行方式:
  1. 使用内置示例数据:
     python -m smart_feed_v9

  2. 从 JSON 文件加载:
     python -m smart_feed_v9 --input waste_manifest.json

  3. 调整参数:
     python -m smart_feed_v9 --input data.json --F_total 10.5 --eta 0.85

JSON 格式示例见 example_input.json
"""

import argparse
import json
import sys
import time

from . import WasteStream, SystemConfig, run_optimization


# ═══════════════════════════════════════════════════════════════
# 内置示例数据（基于 AxNano 典型废料）
# ═══════════════════════════════════════════════════════════════

EXAMPLE_STREAMS = [
    WasteStream(
        stream_id="Resin",
        quantity_L=200.0,
        btu_per_lb=12500.0,
        pH=3.0,
        f_ppm=15000.0,
        solid_pct=100.0,
        salt_ppm=500.0,
        moisture_pct=0.0,
    ),
    WasteStream(
        stream_id="AFFF",
        quantity_L=500.0,
        btu_per_lb=1.0,
        pH=7.5,
        f_ppm=5000.0,
        solid_pct=0.5,
        salt_ppm=200.0,
        moisture_pct=99.5,
    ),
    WasteStream(
        stream_id="Caustic",
        quantity_L=300.0,
        btu_per_lb=0.0,
        pH=13.5,
        f_ppm=0.0,
        solid_pct=0.0,
        salt_ppm=8000.0,
        moisture_pct=65.0,
    ),
]


def load_from_json(filepath: str) -> tuple:
    """
    从 JSON 文件加载废料清单和可选配置覆盖。

    JSON 格式:
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
      "config": {           // 可选 — 只需列出要修改的参数
        "F_total": 10.5,
        "eta": 0.85,
        "cost_diesel_per_L": 1.20
      }
    }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 解析废料流
    streams = []
    for item in data["streams"]:
        streams.append(WasteStream(**item))

    # 解析配置覆盖
    cfg_overrides = data.get("config", {})

    return streams, cfg_overrides


def build_config(cli_args: dict, json_overrides: dict = None) -> SystemConfig:
    """
    构建配置: 默认值 → JSON 覆盖 → CLI 覆盖

    优先级: CLI > JSON > 默认值
    """
    cfg = SystemConfig()
    overrides = {}

    # JSON 覆盖
    if json_overrides:
        overrides.update(json_overrides)

    # CLI 覆盖 (只取非 None 的)
    config_fields = {f.name for f in SystemConfig.__dataclass_fields__.values()}
    for key, val in cli_args.items():
        if val is not None and key in config_fields:
            overrides[key] = val

    # 应用覆盖
    for key, val in overrides.items():
        if hasattr(cfg, key):
            setattr(cfg, key, type(getattr(cfg, key))(val))

    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="AxNano Smart-Feed Algorithm v9 — SCWO 喂料优化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m smart_feed_v9                          # 内置示例数据
  python -m smart_feed_v9 --input manifest.json    # JSON 输入
  python -m smart_feed_v9 --F_total 10.5 --eta 0.85  # 调整参数
        """,
    )

    # 输入
    parser.add_argument("--input", "-i", type=str, default=None,
                        help="废料清单 JSON 文件路径")

    # 可调节参数 (全部可选，覆盖默认值)
    g = parser.add_argument_group("可调节参数 (均有默认值)")

    # 反应器
    g.add_argument("--F_total", type=float, default=None,
                   help="总进料容量 L/min (默认: 11.0)")
    g.add_argument("--P_system", type=float, default=None,
                   help="系统功率 kW (默认: 400)")

    # 边界
    g.add_argument("--BTU_target", type=float, default=None,
                   help="目标热值 BTU/lb (默认: 2200)")
    g.add_argument("--solid_max_pct", type=float, default=None,
                   help="最大固体含量 %% (默认: 15)")
    g.add_argument("--pH_min", type=float, default=None,
                   help="最低 pH (默认: 6)")
    g.add_argument("--pH_max", type=float, default=None,
                   help="最高 pH (默认: 9)")
    g.add_argument("--salt_max_ppm", type=float, default=None,
                   help="最大盐浓度 ppm (默认: 5000)")
    g.add_argument("--eta", type=float, default=None,
                   help="热效率因子 (默认: 0.89)")

    # 化学常数
    g.add_argument("--K_F_TO_ACID", type=float, default=None,
                   help="F ppm→酸当量系数 (默认: 0.053)")
    g.add_argument("--K_PH_TO_BASE", type=float, default=None,
                   help="pH碱贡献系数 (默认: 50.0)")
    g.add_argument("--K_ACID_TO_NAOH_VOL", type=float, default=None,
                   help="酸→NaOH体积系数 (默认: 8.28e-5)")

    # 成本
    g.add_argument("--cost_diesel_per_L", type=float, default=None,
                   help="柴油 $/L (默认: 1.00)")
    g.add_argument("--cost_naoh_per_L", type=float, default=None,
                   help="NaOH $/L (默认: 1.51)")
    g.add_argument("--cost_water_per_L", type=float, default=None,
                   help="DI Water $/L (默认: 0.00199)")
    g.add_argument("--cost_electricity_per_kWh", type=float, default=None,
                   help="电力 $/kWh (默认: 0.12)")
    g.add_argument("--cost_labor_per_hr", type=float, default=None,
                   help="人工 $/hr (默认: 100)")

    # 搜索
    g.add_argument("--ratio_sum_max", type=int, default=None,
                   help="配比总和上限 (默认: 11)")
    g.add_argument("--W_min", type=float, default=None,
                   help="最低可行吞吐量 L/min (默认: 0.5)")

    args = parser.parse_args()

    # ── 加载数据 ──
    json_overrides = {}
    if args.input:
        try:
            streams, json_overrides = load_from_json(args.input)
            print(f"✓ 已从 {args.input} 加载 {len(streams)} 条废料流")
        except FileNotFoundError:
            print(f"✗ 文件未找到: {args.input}", file=sys.stderr)
            sys.exit(1)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"✗ JSON 解析错误: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        streams = EXAMPLE_STREAMS
        print("ℹ 使用内置示例数据 (Resin + AFFF + Caustic)")
        print("  提示: 使用 --input manifest.json 加载自定义数据")

    # ── 构建配置 ──
    cfg = build_config(vars(args), json_overrides)

    # ── 运行优化 ──
    print(f"\n⏳ 正在优化 {len(streams)} 条废料流的喂料计划...")
    t0 = time.time()

    result = run_optimization(streams, cfg, verbose=True)

    elapsed = time.time() - t0
    print(f"\n  ⏱ 计算耗时: {elapsed:.2f}s")
    print(f"  💰 成本节省: {result['savings_pct']:.1f}%")


if __name__ == "__main__":
    main()

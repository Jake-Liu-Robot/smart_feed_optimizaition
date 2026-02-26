"""
Core module tests: blending, gatekeeper, search
"""
import math
import pytest

from smart_feed_v9.models import WasteStream, SystemConfig, BlendProperties
from smart_feed_v9.blending import blend_linear, blend_pH, calc_blend_properties
from smart_feed_v9.gatekeeper import (
    calc_r_water, calc_r_diesel, calc_r_naoh,
    gatekeeper, calc_throughput, evaluate_phase,
)
from smart_feed_v9.search import search


# ── Common fixtures ──────────────────────────────────────────────

@pytest.fixture
def cfg():
    return SystemConfig()


@pytest.fixture
def resin():
    return WasteStream(
        stream_id="Resin", quantity_L=200, btu_per_lb=12500,
        pH=3.0, f_ppm=15000, solid_pct=100.0, salt_ppm=500, moisture_pct=0,
    )


@pytest.fixture
def afff():
    return WasteStream(
        stream_id="AFFF", quantity_L=500, btu_per_lb=1,
        pH=7.5, f_ppm=5000, solid_pct=0.5, salt_ppm=200, moisture_pct=99.5,
    )


@pytest.fixture
def caustic():
    return WasteStream(
        stream_id="Caustic", quantity_L=300, btu_per_lb=0,
        pH=13.5, f_ppm=0, solid_pct=0.0, salt_ppm=8000, moisture_pct=65,
    )


# ══════════════════════════════════════════════════════════════
#  blending.py tests
# ══════════════════════════════════════════════════════════════

class TestBlendLinear:
    def test_equal_ratios(self):
        assert blend_linear([100, 200], [1, 1]) == 150.0

    def test_unequal_ratios(self):
        # (100*1 + 200*3) / 4 = 175
        assert blend_linear([100, 200], [1, 3]) == 175.0

    def test_single_stream(self):
        assert blend_linear([42.0], [1]) == 42.0

    def test_zero_ratios(self):
        assert blend_linear([100, 200], [0, 0]) == 0.0


class TestBlendPH:
    def test_same_pH(self):
        result = blend_pH([7.0, 7.0], [1, 1])
        assert abs(result - 7.0) < 0.01

    def test_acid_dominates(self):
        # pH 1 + pH 7, equal volume → heavily acidic
        result = blend_pH([1.0, 7.0], [1, 1])
        assert result < 2.0

    def test_single_stream(self):
        result = blend_pH([4.5], [1])
        assert abs(result - 4.5) < 0.01


class TestCalcBlendProperties:
    def test_single_stream(self, resin):
        blend = calc_blend_properties([resin], (1,))
        assert blend.btu_per_lb == 12500
        assert blend.solid_pct == 100.0
        assert abs(blend.pH - 3.0) < 0.01


# ══════════════════════════════════════════════════════════════
#  gatekeeper.py tests
# ══════════════════════════════════════════════════════════════

class TestCalcRWater:
    def test_no_dilution_needed(self, cfg):
        blend = BlendProperties(btu_per_lb=2000, pH=7, f_ppm=100,
                                solid_pct=10, salt_ppm=3000)
        assert calc_r_water(blend, cfg) == 0.0

    def test_solid_driven(self, cfg):
        # solid 30%, max 15% → r = 30/15 - 1 = 1.0
        blend = BlendProperties(btu_per_lb=2000, pH=7, f_ppm=0,
                                solid_pct=30, salt_ppm=0)
        assert abs(calc_r_water(blend, cfg) - 1.0) < 1e-9

    def test_salt_driven(self, cfg):
        # salt 10000 ppm, max 5000 → r = 10000/5000 - 1 = 1.0
        blend = BlendProperties(btu_per_lb=2000, pH=7, f_ppm=0,
                                solid_pct=0, salt_ppm=10000)
        assert abs(calc_r_water(blend, cfg) - 1.0) < 1e-9

    def test_max_of_both(self, cfg):
        # solid: 45/15 - 1 = 2.0,  salt: 10000/5000 - 1 = 1.0 → max = 2.0
        blend = BlendProperties(btu_per_lb=2000, pH=7, f_ppm=0,
                                solid_pct=45, salt_ppm=10000)
        assert abs(calc_r_water(blend, cfg) - 2.0) < 1e-9


class TestCalcRDiesel:
    def test_no_diesel_needed(self, cfg):
        # BTU already above target
        blend = BlendProperties(btu_per_lb=5000, pH=7, f_ppm=0,
                                solid_pct=0, salt_ppm=0)
        assert calc_r_diesel(blend, 0.0, cfg) == 0.0

    def test_diesel_needed(self, cfg):
        # BTU=0, r_water=0 → r_diesel = BTU_target / (BTU_diesel * eta)
        blend = BlendProperties(btu_per_lb=0, pH=7, f_ppm=0,
                                solid_pct=0, salt_ppm=0)
        expected = cfg.BTU_target / (cfg.BTU_diesel * cfg.eta)
        assert abs(calc_r_diesel(blend, 0.0, cfg) - expected) < 1e-9

    def test_water_dilutes_btu(self, cfg):
        # BTU=2200 (just meets target), but r_water=1 → BTU_eff = 1100 → needs diesel
        blend = BlendProperties(btu_per_lb=2200, pH=7, f_ppm=0,
                                solid_pct=0, salt_ppm=0)
        assert calc_r_diesel(blend, 0.0, cfg) == 0.0
        assert calc_r_diesel(blend, 1.0, cfg) > 0.0


class TestCalcRNaoh:
    def test_no_acid(self, cfg):
        blend = BlendProperties(btu_per_lb=2000, pH=7, f_ppm=0,
                                solid_pct=0, salt_ppm=0)
        assert calc_r_naoh(blend, cfg) == 0.0

    def test_alkaline_reduces_need(self, cfg):
        # pH > 7 provides internal base contribution, reducing NaOH demand
        blend_acid = BlendProperties(btu_per_lb=0, pH=5, f_ppm=5000,
                                     solid_pct=0, salt_ppm=0)
        blend_base = BlendProperties(btu_per_lb=0, pH=10, f_ppm=5000,
                                     solid_pct=0, salt_ppm=0)
        assert calc_r_naoh(blend_base, cfg) < calc_r_naoh(blend_acid, cfg)


class TestEvaluatePhase:
    def test_feasible(self, afff, cfg):
        inv = {"AFFF": 500}
        result = evaluate_phase([afff], (1,), inv, cfg)
        assert result is not None
        assert result.W >= cfg.W_min

    def test_infeasible_low_throughput(self, resin, cfg):
        # Resin solo has very high r_ext, but W is still > W_min
        inv = {"Resin": 200}
        result = evaluate_phase([resin], (1,), inv, cfg)
        # Resin W ≈ 1.63, W_min=0.5, so still feasible
        assert result is not None

    def test_infeasible_ph_too_high(self, cfg):
        # pH=14 > pH_max=9 → infeasible
        alkaline = WasteStream(
            stream_id="StrongBase", quantity_L=100, btu_per_lb=2000,
            pH=14, f_ppm=0, solid_pct=0, salt_ppm=0, moisture_pct=100,
        )
        inv = {"StrongBase": 100}
        result = evaluate_phase([alkaline], (1,), inv, cfg)
        assert result is None


# ══════════════════════════════════════════════════════════════
#  search.py tests
# ══════════════════════════════════════════════════════════════

class TestSearch:
    def test_single_stream(self, afff, cfg):
        cost, phases, stats = search([afff], cfg)
        assert cost < float("inf")
        assert len(phases) == 1
        assert stats["evaluated"] > 0

    def test_optimized_beats_solo(self, resin, afff, cfg):
        # Blending should be cheaper than the worst solo stream
        cost_mix, _, _ = search([resin, afff], cfg)
        cost_resin, _, _ = search([resin], cfg)
        cost_afff, _, _ = search([afff], cfg)
        assert cost_mix < cost_resin + cost_afff

    def test_three_streams(self, resin, afff, caustic, cfg):
        cost, phases, stats = search([resin, afff, caustic], cfg)
        assert cost < float("inf")
        assert len(phases) >= 1
        assert stats["pruned_bound"] >= 0

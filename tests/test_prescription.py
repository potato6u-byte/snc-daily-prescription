# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prescription as rx


def test_transport_drop_reproduces_consulting_report_table():
    expected = {10: 1.65, 11: 1.58, 12: 1.50, 13: 1.42, 14: 1.34, 15: 1.26,
                16: 1.18, 17: 1.11, 18: 1.03, 19: 0.95, 20: 0.87}
    for indoor, want in expected.items():
        got, _, _ = rx.predict_transport_drop(indoor)
        assert got == pytest.approx(want, abs=0.02), indoor


def test_transport_drop_matches_raw_data_fit():
    assert rx.TRANSPORT["intercept"] == pytest.approx(2.4385, abs=0.001)
    assert rx.TRANSPORT["slope_per_c"] == pytest.approx(-0.07842, abs=0.0001)
    assert rx.TRANSPORT["n"] == 277
    assert rx.TRANSPORT["r2"] == pytest.approx(0.614, abs=0.002)


def test_transport_interval_and_nan_safety():
    _, lo, hi = rx.predict_transport_drop(15.8)
    assert lo < rx.predict_transport_drop(15.8)[0] < hi
    assert hi - lo == pytest.approx(2 * rx.TRANSPORT["z95"] * rx.TRANSPORT["se"], abs=0.01)


def test_observed_drop_and_heat_loss():
    assert rx.observed_drop(38.5, 37.9) == pytest.approx(0.6)
    assert rx.heat_loss_kcal(1.0, 16500) == pytest.approx(16500.0)


def test_cooling_model_reproduces_baseline_and_golden():
    p = rx.predict_from_cooling(38.5)
    assert p["total_minutes"] == pytest.approx(379.9, abs=0.5)
    assert p["acidity_delta"] == pytest.approx(0.1153, abs=0.001)
    assert p["final_acidity"] == pytest.approx(0.9712, abs=0.001)
    assert p["acid_5h"] == pytest.approx(0.855, abs=0.002)


def test_cooling_model_matches_raw_coefficients():
    m = rx.COOLING_MODEL["total_minutes"]
    assert m["a"] == pytest.approx(795.263, abs=0.01)
    assert m["b"] == pytest.approx(-10.7878, abs=0.001)
    assert rx.COOLING_MODEL["acidity_delta"]["b"] == pytest.approx(-0.00692, abs=0.00001)
    assert rx.COOLING_MODEL["final_acidity"]["b"] == pytest.approx(0.0058, abs=0.0001)


def test_hotwater_regression_and_clamp():
    assert rx.predict_hotwater(20.0) == pytest.approx(38.6, abs=0.05)
    assert rx.predict_hotwater(35.0) == pytest.approx(38.3, abs=0.05)
    assert rx.predict_hotwater(-10.0) == rx.HOTWATER_MODEL["hi"]
    assert rx.predict_hotwater(80.0) == rx.HOTWATER_MODEL["lo"]


def test_tank_offset_303_is_the_outlier():
    assert rx.tank_offset("301") == 0.0
    assert rx.tank_offset("302") == pytest.approx(0.01)
    assert rx.tank_offset("303") == pytest.approx(0.51)
    assert rx.tank_offset("303호") == pytest.approx(0.51)


def test_prescribe_baseline_mode_holds_reference_setpoint():
    r = rx.prescribe(indoor_dawn_c=20.0, tank="301")
    assert r.mode == "baseline"
    assert r.cooling_set_c == pytest.approx(rx.BASELINE["cooling_set_c"], abs=0.05)
    assert r.predicted_minutes == pytest.approx(379.9, abs=0.5)


def test_prescribe_baseline_mode_is_season_independent():
    warm = rx.prescribe(indoor_dawn_c=36.0, tank="301")
    cold = rx.prescribe(indoor_dawn_c=16.0, tank="301")
    assert abs(warm.cooling_set_c - cold.cooling_set_c) < 0.05
    assert abs(warm.predicted_minutes - cold.predicted_minutes) < 0.5
    assert cold.predicted_inlet_c < warm.predicted_inlet_c


def test_prescribe_report_chain_mode_compensates_transport():
    cold = rx.prescribe(indoor_dawn_c=16.0, tank="301", mode="report_chain")
    warm = rx.prescribe(indoor_dawn_c=36.0, tank="301", mode="report_chain")
    assert cold.cooling_set_c > warm.cooling_set_c
    assert cold.predicted_inlet_c == pytest.approx(rx.BASELINE["inlet_tank_c"], abs=0.06)
    assert warm.predicted_inlet_c == pytest.approx(rx.BASELINE["inlet_tank_c"], abs=0.06)


def test_correction_shifts_cooling_in_both_modes():
    for mode in ("baseline", "report_chain"):
        base = rx.prescribe(indoor_dawn_c=16.0, tank="301", mode=mode)
        adj = rx.prescribe(indoor_dawn_c=16.0, tank="301", mode=mode, cooling_correction_c=0.4)
        assert adj.cooling_set_c == pytest.approx(base.cooling_set_c + 0.4, abs=0.051)


def test_prescribe_confidence_flags_extrapolation():
    assert "외삽" in rx.prescribe(indoor_dawn_c=9.0, tank="301").confidence
    assert "외삽" in rx.prescribe(indoor_dawn_c=40.0, tank="301").confidence
    assert rx.prescribe(indoor_dawn_c=25.0, tank="301").confidence == "보통"


def test_tank_303_note_is_surfaced():
    notes = rx.prescribe(indoor_dawn_c=25.0, tank="303").notes
    assert any("303호" in n for n in notes)


def test_prescribe_cooling_is_clamped_to_field_range():
    hi = rx.prescribe(indoor_dawn_c=20.0, tank="301", cooling_correction_c=2.0)
    lo = rx.prescribe(indoor_dawn_c=20.0, tank="301", cooling_correction_c=-2.0)
    assert 37.0 <= lo.cooling_set_c < 38.5 < hi.cooling_set_c <= 42.0
    assert rx.BASELINE["cooling_set_c"] + 2.0 == pytest.approx(hi.cooling_set_c, abs=0.06)


def test_indoor_to_outdoor_reference():
    assert rx.predict_outdoor_from_indoor(32.72) == pytest.approx(22.2, abs=0.3)


def test_ewma_prefers_recent_values():
    assert rx.ewma([1.0, 1.0, 3.0], alpha=0.5) == pytest.approx(2.0, abs=0.01)
    assert rx.ewma([]) == 0.0
    assert rx.ewma([0.5]) == 0.5


def test_review_lowers_cooling_when_fermentation_ran_long():
    rows = [{"cooling_set_c": 38.5, "inlet_tank_c": 37.9, "indoor_dawn_c": 33.0,
             "predicted_minutes": 380.0, "total_minutes": 400.0,
             "predicted_acidity_delta": 0.115, "acidity_delta": 0.125}]
    rev = rx.review(rows)
    assert rev["latest_minute_residual"] == pytest.approx(20.0, abs=0.1)
    assert rev["cooling_correction_c"] < 0


def test_review_raises_cooling_when_fermentation_ran_short():
    rows = [{"cooling_set_c": 38.5, "inlet_tank_c": 37.9, "indoor_dawn_c": 33.0,
             "predicted_minutes": 380.0, "total_minutes": 350.0,
             "predicted_acidity_delta": 0.115, "acidity_delta": 0.100}]
    rev = rx.review(rows)
    assert rev["cooling_correction_c"] > 0
    assert rev["latest_minute_residual"] == pytest.approx(-30.0, abs=0.1)


def test_review_correction_is_bounded():
    rows = [{"cooling_set_c": 38.5, "inlet_tank_c": 37.9, "indoor_dawn_c": 33.0,
             "predicted_minutes": 380.0, "total_minutes": 200.0,
             "predicted_acidity_delta": 0.115, "acidity_delta": 0.100}]
    assert rx.review(rows)["cooling_correction_c"] == pytest.approx(-0.5, abs=1e-6) or \
           rx.review(rows)["cooling_correction_c"] == pytest.approx(0.5, abs=1e-6)


def test_review_handles_empty_history():
    rev = rx.review([])
    assert rev["count"] == 0
    assert "message" in rev


def test_refit_returns_none_for_tiny_samples():
    rows = [{"cooling_set_c": 38.5, "total_minutes": 380} for _ in range(3)]
    out = rx.refit(rows)
    assert out["n_rows"] == 3
    assert "살균냉각 ↔ 종결분" not in out["fitted"]


def test_refit_recovers_known_slope():
    rows = [{"cooling_set_c": 38.0 + i * 0.05, "total_minutes": 800.0 - 10.0 * (38.0 + i * 0.05)}
            for i in range(30)]
    out = rx.refit(rows)
    f = out["fitted"]["살균냉각 ↔ 종결분"]
    assert f["b"] == pytest.approx(-10.0, abs=0.01)
    assert f["r2"] == pytest.approx(1.0, abs=1e-6)

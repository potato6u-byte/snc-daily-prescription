# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prescription as rx


def test_transport_drop_matches_report_table():
    expected = {10: 1.65, 11: 1.58, 12: 1.50, 13: 1.42, 14: 1.34, 15: 1.26,
                16: 1.18, 17: 1.11, 18: 1.03, 19: 0.95, 20: 0.87}
    for indoor, want in expected.items():
        got, _, _ = rx.predict_transport_drop(indoor)
        assert got == pytest.approx(want, abs=0.02), indoor


def test_transport_drop_interval_matches_report():
    _, lo, hi = rx.predict_transport_drop(10)
    assert lo == pytest.approx(0.95, abs=0.02)
    assert hi == pytest.approx(2.36, abs=0.02)


def test_transport_drop_is_clamped():
    hot, _, _ = rx.predict_transport_drop(-20)
    cold, _, _ = rx.predict_transport_drop(60)
    assert hot == rx.TRANSPORT["drop_max_c"]
    assert cold == rx.TRANSPORT["drop_min_c"]
    assert rx.predict_transport_drop(40)[0] == rx.TRANSPORT["drop_min_c"]


def test_observed_drop():
    assert rx.observed_drop(38.5, 37.2) == 1.3


def test_heat_loss_15t_and_16_5t():
    assert rx.heat_loss_kcal(1.34, 15000) == pytest.approx(20100.0, abs=1)
    assert rx.heat_loss_kcal(1.34, 16500) == pytest.approx(22110.0, abs=1)


def test_prescribe_inlets_land_on_golden_at_baseline_conditions():
    p = rx.prescribe(indoor_dawn_c=20.0, outdoor_c=27.6, tanks=["301호 탱크"])
    assert p.cooling_set_c == pytest.approx(
        rx.GOLDEN["pasteurize_cooling_set_c"] + p.transport_drop_c, abs=0.11
    )


def test_prescribe_raises_cooling_when_dawn_temp_drops():
    warm = rx.prescribe(indoor_dawn_c=22.0, outdoor_c=24.0, tanks=["301호 탱크"])
    cold = rx.prescribe(indoor_dawn_c=12.0, outdoor_c=6.0, tanks=["301호 탱크"])
    assert cold.cooling_set_c > warm.cooling_set_c
    assert cold.hotwater_set_c >= warm.hotwater_set_c


def test_prescribe_is_clamped_to_field_range():
    p = rx.prescribe(indoor_dawn_c=5.0, outdoor_c=-10.0, tanks=["302호 탱크"])
    assert 37.5 <= p.cooling_set_c <= 42.0
    assert 37.5 <= p.hotwater_set_c <= 39.5
    assert 300.0 <= p.predicted_minutes <= 460.0


def test_positive_residual_raises_cooling_setpoint():
    base = rx.prescribe(indoor_dawn_c=16.0, outdoor_c=12.0, tanks=["301호 탱크"])
    adj = rx.prescribe(indoor_dawn_c=16.0, outdoor_c=12.0, tanks=["301호 탱크"], cooling_residual_c=0.4)
    assert adj.cooling_set_c == pytest.approx(base.cooling_set_c + 0.4, abs=0.051)


def test_confidence_flags_extrapolation():
    p = rx.prescribe(indoor_dawn_c=9.0, outdoor_c=2.0, tanks=["301호 탱크"])
    assert "외삽" in p.confidence


def test_time_band_offset_crosses_midnight():
    bands = rx.DEFAULT_TIME_BANDS
    assert rx.time_band_offset(1.0, bands) == 0.3
    assert rx.time_band_offset(8.0, bands) == 0.1
    assert rx.time_band_offset(13.0, bands) == 0.0
    assert rx.time_band_offset(19.0, bands) == 0.2
    assert rx.time_band_offset(7.0, [{"시작": "00:00", "종료": "24:00", "보정dC": 0.5}]) == 0.5
    assert rx.time_band_offset(7.0, [{"시작": "08:00", "종료": "09:00", "보정dC": 0.5}]) == 0.0


def test_time_band_offset_feeds_cooling_not_hotwater_fully():
    bands = [{"시작": "00:00", "종료": "24:00", "보정dC": 0.2}]
    a = rx.prescribe(indoor_dawn_c=16.0, outdoor_c=12.0, tanks=["301호 탱크"])
    b = rx.prescribe(indoor_dawn_c=16.0, outdoor_c=12.0, tanks=["301호 탱크"], hour_float=1.0, time_bands=bands)
    assert b.cooling_set_c > a.cooling_set_c
    assert b.hotwater_set_c > a.hotwater_set_c


def test_ewma_prefers_recent_values():
    assert rx.ewma([1.0, 1.0, 3.0], alpha=0.5) == pytest.approx(2.0, abs=0.01)
    assert rx.ewma([]) == 0.0
    assert rx.ewma([0.5]) == 0.5


def test_residual_terms_sign():
    t = rx.residual_terms(1.30, 1.10, 380.0, 362.0)
    assert t["drop_residual_c"] == pytest.approx(-0.20)
    assert t["minute_residual"] == pytest.approx(-18.0)


def test_review_returns_ewma_correction_aligned_with_cooling_setpoint():
    rows = [
        {"predicted_drop_c": 1.30, "pasteurize_cooling_actual_c": 39.0, "inlet_tank_c": 38.0,
         "predicted_minutes": 380, "total_minutes": 362},
        {"predicted_drop_c": 1.26, "pasteurize_cooling_actual_c": 39.5, "inlet_tank_c": 38.4,
         "predicted_minutes": 380, "total_minutes": 371},
    ]
    rev = rx.review(rows)
    assert rev["count"] == 2
    assert rev["latest_drop_residual_c"] == pytest.approx(-0.30, abs=0.01)
    assert rev["drop_correction_c"] == pytest.approx(-0.23, abs=0.01)
    assert rev["latest_minute_residual"] == pytest.approx(-18.0, abs=0.1)
    assert rev["minute_correction"] == pytest.approx(-13.5, abs=0.1)


def test_review_correction_raises_cooling_when_actual_drop_was_larger():
    rows = [
        {"predicted_drop_c": 1.25, "pasteurize_cooling_actual_c": 40.2, "inlet_tank_c": 38.5,
         "predicted_minutes": 380, "total_minutes": 360},
    ]
    rev = rx.review(rows)
    assert rev["drop_correction_c"] == pytest.approx(0.45, abs=0.01)
    base = rx.prescribe(indoor_dawn_c=15.2, outdoor_c=11.4, tanks=["301호 탱크"])
    corrected = rx.prescribe(indoor_dawn_c=15.2, outdoor_c=11.4, tanks=["301호 탱크"],
                             cooling_residual_c=rev["drop_correction_c"])
    assert corrected.cooling_set_c > base.cooling_set_c


def test_review_handles_empty_history():
    rev = rx.review([])
    assert rev["count"] == 0
    assert "message" in rev


def test_kappa_of_picks_worst_tank():
    assert rx.kappa_of(["303호 탱크"]) == 0.90
    assert rx.kappa_of(["301호 탱크", "302호 탱크"]) == 1.15
    assert rx.kappa_of([]) == 1.00

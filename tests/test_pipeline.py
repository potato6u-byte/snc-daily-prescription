# -*- coding: utf-8 -*-
import os
import sys
import tempfile

import io

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP_DB = os.path.join(tempfile.mkdtemp(prefix="snc_test_"), "test.db")
os.environ["SNC_DB_PATH"] = TMP_DB

import data_store as ds
import excel_io as xio
import prescription as rx


def setup_module(module):
    ds.init_db()


def test_template_roundtrip_parses_all_rows():
    raw = xio.build_template_bytes()
    rows, errors = xio.parse_results_excel(raw)
    assert errors == []
    assert len(rows) == len(xio.SAMPLE_ROWS)
    first = max(rows, key=lambda r: r["batch_date"])
    assert first["batch_date"] == "2026-10-15"
    assert first["indoor_dawn_c"] == pytest.approx(15.2)
    assert first["pasteurize_cooling_actual_c"] == pytest.approx(39.8)
    assert first["inlet_tank_c"] == pytest.approx(38.6)
    assert first["total_minutes"] == pytest.approx(362)


def test_template_parses_real_xlsx_file():
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "t.xlsx")
    with open(path, "wb") as f:
        f.write(xio.build_template_bytes())
    rows, errors = xio.parse_results_excel(path)
    assert errors == []
    assert len(rows) == len(xio.SAMPLE_ROWS)


def test_english_headers_and_blank_rows_are_tolerated():
    df = pd.DataFrame(
        {
            "batch_date": ["2026-03-01", None, "2026-03-02"],
            "tanks": ["301호 탱크", None, "302호 탱크"],
            " indoor_dawn_c ": [12.0, None, 13.0],
            "pasteurize_cooling_actual_c": [39.8, None, 39.6],
            "inlet_tank_c": [38.6, None, 38.4],
            "total_minutes": [362, None, 371],
        }
    )
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "t.xlsx")
    df.to_excel(path, index=False)
    rows, errors = xio.parse_results_excel(path)
    assert errors == []
    assert len(rows) == 2
    assert rows[0]["batch_date"] == "2026-03-01"


def test_non_numeric_value_is_reported_not_crashed():
    df = pd.DataFrame({"일자": ["2026-03-03"], "새벽 실내온도(℃)": ["측정불가"], "이송후 탱크온도(℃)": [38.4]})
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "t.xlsx")
    df.to_excel(path, index=False)
    rows, errors = xio.parse_results_excel(path)
    assert rows
    assert any("측정불가" in e for e in errors)


def test_save_results_attaches_prescription_prediction():
    p = rx.prescribe(indoor_dawn_c=15.2, outdoor_c=11.4, tanks=["301호 탱크"], volume_l=16500.0,
                     rx_date="2026-10-15")
    ds.save_prescription(p.as_row())

    n = ds.save_batch_results(
        [{
            "batch_date": "2026-10-15", "tanks": "301호 탱크", "volume_l": 16500.0,
            "indoor_dawn_c": 15.2, "pasteurize_cooling_actual_c": 39.8,
            "inlet_tank_c": 38.6, "total_minutes": 362, "final_acidity": 0.982,
        }],
        source="test",
    )
    assert n == 1

    rows = ds.list_batch_results(10)
    top = rows[0]
    assert top["predicted_drop_c"] == pytest.approx(p.transport_drop_c)
    assert top["predicted_minutes"] == pytest.approx(p.predicted_minutes)

    rev = rx.review(rows)
    assert rev["count"] >= 1
    assert rev["latest_drop_residual_c"] == pytest.approx(
        (39.8 - 38.6) - p.transport_drop_c, abs=0.01
    )


def test_export_workbook_contains_both_sheets():
    buf = xio.results_to_bytes(ds.list_batch_results(10), ds.list_prescriptions(10))
    sheets = pd.read_excel(io.BytesIO(buf), sheet_name=None)
    assert "전일실적" in sheets
    assert "처방이력" in sheets
    assert len(sheets["처방이력"]) >= 1


def test_delete_and_clear():
    ds.save_batch_results([{"batch_date": "2026-01-01", "tanks": "301호 탱크"}], source="test")
    before = len(ds.list_batch_results(500))
    ds.delete_batch_result(ds.list_batch_results(500)[0]["id"])
    assert len(ds.list_batch_results(500)) == before - 1
    ds.clear_batch_results()
    assert ds.list_batch_results(500) == []

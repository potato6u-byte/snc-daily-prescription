# -*- coding: utf-8 -*-
import io
import os
import sys
import tempfile

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP_DB = os.path.join(tempfile.mkdtemp(prefix="snc_test_"), "test.db")
os.environ["SNC_DB_PATH"] = TMP_DB

import data_store as ds
import excel_io as xio
import prescription as rx

RAW_FILE = os.environ.get(
    "SNC_RAW_FILE",
    r"C:\Users\admin\Desktop\A300_App\로우\통합데이터.xlsx",
)


def setup_module(module):
    ds.init_db()


def test_template_has_field_form_layout():
    buf = xio.build_template_bytes(with_samples=True)
    workbook = pd.read_excel(io.BytesIO(buf), sheet_name=None, header=None)
    assert xio.SHEET_NAME in workbook
    grid = workbook[xio.SHEET_NAME]
    assert str(grid.iloc[0, 1]).startswith("♣A300")
    assert grid.iloc[xio.HDR_ROW - 1, 0] == "날짜"
    assert "작성안내" in workbook


def test_template_column_order_is_identical_to_field_form():
    assert len(xio.COLUMNS) == 62
    assert xio.COLUMNS[0][1] == "날짜"
    assert xio.COLUMNS[34][1] == "살균냉각온도"
    assert xio.COLUMNS[39][1] == "종결분"
    assert xio.COLUMNS[-1][1] == "완제품1"
    assert [c[1] for c in xio.COLUMNS[:6]] == [
        "날짜", "300 탱크", "제품 이송후 탱크 온도", "8시 300 탱크 온도",
        "11시 300 탱크 온도", "13시 300 탱크 온도",
    ]


def test_template_roundtrip_maps_every_sampled_field():
    rows, errors = xio.parse_results_excel(xio.build_template_bytes(with_samples=True))
    assert errors == []
    assert len(rows) == len(xio.SAMPLE_ROWS)
    r = {x["batch_date"]: x for x in rows}["2026-08-03"]
    assert r["tank"] == "301"
    assert r["inlet_tank_c"] == pytest.approx(38.9)
    assert r["indoor_dawn_c"] == pytest.approx(34.2)
    assert r["indoor_inoc_c"] == pytest.approx(36.5)
    assert r["cooling_set_c"] == pytest.approx(38.5)
    assert r["hotwater_set_c"] == pytest.approx(38.5)
    assert r["total_minutes"] == pytest.approx(372)
    assert r["final_acidity"] == pytest.approx(0.974)
    assert r["acidity_delta"] == pytest.approx(0.104)
    assert r["ph_end"] == pytest.approx(4.72)
    assert r["outdoor_inoc_c"] == pytest.approx(31.4)


def test_duplicate_headers_map_by_occurrence_order():
    rows, _ = xio.parse_results_excel(xio.build_template_bytes(with_samples=True))
    r = rows[0]
    assert r["final_acidity"] == pytest.approx(0.974)
    assert r["viscosity_end_cp"] == pytest.approx(648.0)
    assert r["ph_end"] == pytest.approx(4.72)
    assert r["brix_end"] == pytest.approx(11.80)


def test_blank_rows_and_guide_sheet_are_ignored():
    rows, errors = xio.parse_results_excel(xio.build_template_bytes(with_samples=False))
    assert rows == []
    assert errors and "읽을 수 있는" in errors[0]


def test_english_and_alias_headers_still_parse():
    df = pd.DataFrame({
        "일자": ["2026-03-01", "2026-03-02"],
        "탱크": ["301", "302"],
        "새벽 실내온도": [20.0, 21.0],
        "살균냉각온도": [38.5, 38.5],
        "제품 이송후 탱크 온도": [37.9, 37.8],
        "종결분": [380, 378],
        "산도차": [0.115, 0.116],
    })
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "alias.xlsx")
    df.to_excel(path, index=False)
    rows, errors = xio.parse_results_excel(path)
    assert errors == []
    assert len(rows) == 2
    assert rows[0]["cooling_set_c"] == pytest.approx(38.5)
    assert rows[0]["total_minutes"] == pytest.approx(380)


def test_non_numeric_value_is_reported_not_crashed():
    df = pd.DataFrame({
        "일자": ["2026-03-03"],
        "탱크": ["301"],
        "살균냉각온도": [38.5],
        "핫워터설정온도": [38.5],
        "새벽 실내온도": [20.0],
        "종결분": ["16..7"],
        "산도차": [0.115],
    })
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "bad.xlsx")
    df.to_excel(path, index=False)
    rows, errors = xio.parse_results_excel(path)
    assert rows
    assert any("16..7" in e for e in errors)
    assert "total_minutes" not in rows[0]
    assert rows[0]["cooling_set_c"] == pytest.approx(38.5)


def test_sentinel_strings_are_skipped_silently():
    df = pd.DataFrame({
        "일자": ["2026-03-04"],
        "탱크": ["302"],
        "살균냉각온도": [38.5],
        "핫워터설정온도": ["미측정"],
        "새벽 실내온도": [21.0],
        "종결분": ["-"],
        "산도차": [0.116],
    })
    path = os.path.join(tempfile.mkdtemp(prefix="snc_xlsx_"), "sent.xlsx")
    df.to_excel(path, index=False)
    rows, errors = xio.parse_results_excel(path)
    assert errors == []
    assert "hotwater_set_c" not in rows[0]
    assert "total_minutes" not in rows[0]


@pytest.mark.skipif(not os.path.exists(RAW_FILE), reason="로우데이터 원본 파일 없음")
def test_parses_real_field_workbook():
    rows, errors = xio.parse_results_excel(RAW_FILE)
    assert len(rows) == 278
    assert min(r["batch_date"] for r in rows) == "2025-07-01"
    assert max(r["batch_date"] for r in rows) == "2026-07-30"
    assert sorted({r["tank"] for r in rows}) == ["301", "302", "303"]
    assert all("숫자로 읽지 못했습니다" in e for e in errors)
    assert len(errors) <= 10


@pytest.mark.skipif(not os.path.exists(RAW_FILE), reason="로우데이터 원본 파일 없음")
def test_real_workbook_field_typos_are_surfaced_not_silently_dropped():
    _, errors = xio.parse_results_excel(RAW_FILE)
    joined = " ".join(errors)
    assert "16..7" in joined
    assert "비/맑음" in joined


@pytest.mark.skipif(not os.path.exists(RAW_FILE), reason="로우데이터 원본 파일 없음")
def test_refit_on_real_workbook_reproduces_embedded_coefficients():
    rows, _ = xio.parse_results_excel(RAW_FILE)
    out = rx.refit(rows)
    transport = out["fitted"]["이송하락 ↔ 새벽실내"]
    assert transport["n"] == 277
    assert transport["a"] == pytest.approx(rx.TRANSPORT["intercept"], abs=0.02)
    assert transport["b"] == pytest.approx(rx.TRANSPORT["slope_per_c"], abs=0.0005)
    assert transport["r2"] == pytest.approx(rx.TRANSPORT["r2"], abs=0.005)

    minutes = out["fitted"]["살균냉각 ↔ 종결분"]
    assert minutes["b"] == pytest.approx(rx.COOLING_MODEL["total_minutes"]["b"], abs=0.01)
    assert minutes["r2"] == pytest.approx(rx.COOLING_MODEL["total_minutes"]["r2"], abs=0.005)

    hot = out["fitted"]["핫워터 ↔ 새벽실내"]
    assert hot["b"] == pytest.approx(rx.HOTWATER_MODEL["b"], abs=0.001)


@pytest.mark.skipif(not os.path.exists(RAW_FILE), reason="로우데이터 원본 파일 없음")
def test_real_baseline_subset_matches_report():
    rows, _ = xio.parse_results_excel(RAW_FILE)
    base = [r for r in rows
            if r.get("cooling_set_c") == 38.5 and r.get("hotwater_set_c") == 38.5]
    assert len(base) == rx.BASELINE["n"]
    ad = sum(r["acidity_delta"] for r in base) / len(base)
    mins = sum(r["total_minutes"] for r in base) / len(base)
    assert ad == pytest.approx(rx.BASELINE["acidity_delta"], abs=0.0005)
    assert mins == pytest.approx(rx.BASELINE["total_minutes"], abs=0.05)


def test_save_results_attaches_prescription_predictions():
    p = rx.prescribe(indoor_dawn_c=34.2, tank="301", rx_date="2026-08-03")
    ds.save_prescription(p.as_row())
    n = ds.save_batch_results(
        [{"batch_date": "2026-08-03", "tank": "301", "indoor_dawn_c": 34.2,
          "cooling_set_c": 38.5, "inlet_tank_c": 38.2, "total_minutes": 372,
          "acidity_delta": 0.104, "final_acidity": 0.974}],
        source="test",
    )
    assert n == 1
    top = ds.list_batch_results(10)[0]
    assert top["predicted_minutes"] == pytest.approx(p.predicted_minutes)
    assert top["predicted_drop_c"] == pytest.approx(p.transport_drop_c)
    assert top["predicted_inlet_c"] == pytest.approx(p.predicted_inlet_c)


def test_save_keeps_full_row_in_raw_json():
    ds.save_batch_results([{"batch_date": "2026-08-06", "tank": "303", "brix_product": 13.19,
                            "hum_dawn": 49, "tank_temp_08": 38.4}], source="test")
    conn = ds._connect()
    try:
        row = conn.execute("SELECT raw_json FROM batch_result WHERE batch_date='2026-08-06'").fetchone()
    finally:
        conn.close()
    assert "brix_product" in row["raw_json"]
    assert "hum_dawn" in row["raw_json"]


def test_export_workbook_contains_both_sheets():
    buf = xio.results_to_bytes(ds.list_batch_results(10), ds.list_prescriptions(10))
    sheets = pd.read_excel(io.BytesIO(buf), sheet_name=None)
    assert "실적이력" in sheets
    assert "처방이력" in sheets
    assert "raw_json" not in sheets["실적이력"].columns


def test_delete_and_clear():
    ds.save_batch_results([{"batch_date": "2026-01-01", "tank": "301"}], source="test")
    before = len(ds.list_batch_results(1000))
    ds.delete_batch_result(ds.list_batch_results(1000)[0]["id"])
    assert len(ds.list_batch_results(1000)) == before - 1
    ds.clear_batch_results()
    assert ds.list_batch_results(1000) == []

# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from typing import Any, Sequence

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SHEET_NAME = "T300온도"
TITLE = "♣A300  온도 &  습 도  변화♣"
HDR_ROW = 6
DATA_ROW = 7

COLUMNS: list[tuple[str, str, str]] = [
    ("제품이송량", "날짜", "batch_date"),
    ("제품이송량", "300 탱크", "tank"),
    ("완료후", "제품 이송후 탱크 온도", "inlet_tank_c"),
    ("완료후", "8시 300 탱크 온도", "tank_temp_08"),
    ("완료후", "11시 300 탱크 온도", "tank_temp_11"),
    ("완료후", "13시 300 탱크 온도", "tank_temp_13"),
    ("", "200 살균 아웃 온도 (설정)", "pasteurize_out_set_c"),
    ("작업자 기록 데이터", "새벽A300     실내 온도", "indoor_dawn_c"),
    ("작업자 기록 데이터", "접종A300     실내 온도", "indoor_inoc_c"),
    ("작업자 기록 데이터", "9시A300     실내 온도", "indoor_09"),
    ("작업자 기록 데이터", "10시A300     실내 온도", "indoor_10"),
    ("작업자 기록 데이터", "11시A300     실내 온도", "indoor_11"),
    ("작업자 기록 데이터", "12시A300     실내 온도", "indoor_12"),
    ("작업자 기록 데이터", "13시A300     실내 온도", "indoor_13"),
    ("작업자 기록 데이터", "종결A300     실내 온도", "indoor_end"),
    ("작업자 기록 데이터", "새벽A300     실내 습도", "hum_dawn"),
    ("작업자 기록 데이터", "접종A300     실내 습도", "hum_inoc"),
    ("작업자 기록 데이터", "9시A300     실내 습도", "hum_09"),
    ("작업자 기록 데이터", "10시A300     실내 습도", "hum_10"),
    ("작업자 기록 데이터", "11시A300     실내 습도", "hum_11"),
    ("작업자 기록 데이터", "13시A300     실내 습도", "hum_13"),
    ("작업자 기록 데이터", "당일 날씨 온도", "weather_c"),
    ("작업자 기록 데이터", "종결A300     실내 습도", "hum_end"),
    ("작업자 기록 데이터", "새벽  실외 온도", "outdoor_dawn_c"),
    ("작업자 기록 데이터", "접종  실외 온도", "outdoor_inoc_c"),
    ("작업자 기록 데이터", "11시  실외 온도", "outdoor_11"),
    ("작업자 기록 데이터", "13시  실외 온도", "outdoor_13"),
    ("작업자 기록 데이터", "9시 300 탱크 온도", "tank_temp_09"),
    ("작업자 기록 데이터", "10시 300 탱크 온도", "tank_temp_10"),
    ("온도", "발효탱크TT", "ferment_tank_tt_c"),
    ("온도", "살균유 측정온도", "pasteurized_milk_c"),
    ("온도", "1H발효액 측정온도", "temp_1h_c"),
    ("온도", "5H발효액 측정온도", "temp_5h_c"),
    ("온도", "발효실 실내온도", "ferment_room_c"),
    ("온도", "살균냉각온도", "cooling_set_c"),
    ("온도", "핫워터설정온도", "hotwater_set_c"),
    ("산도", "살균후", "acid_after_pasteur"),
    ("산도", "접종후 (1H)", "acid_1h"),
    ("산도", "1차샘플 (5H)", "acid_5h"),
    ("산도", "종결분", "total_minutes"),
    ("산도", "종결", "final_acidity"),
    ("산도", "산도차", "acidity_delta"),
    ("산도", "분당산도", "acidity_per_min"),
    ("산도", "시간", "acid_time_min"),
    ("산도", "총이송(m)", "transport_m"),
    ("산도", "서지1", "surge_acidity"),
    ("산도", "완제품1", "product_acidity"),
    ("점도", "1차", "viscosity_1st"),
    ("점도", "종결", "viscosity_end_cp"),
    ("점도", "서지1", "viscosity_surge"),
    ("점도", "완제품1", "viscosity_product"),
    ("PH", "살균후", "ph_after_pasteur"),
    ("PH", "접종후 (1H)", "ph_1h"),
    ("PH", "1차", "ph_1st"),
    ("PH", "종결", "ph_end"),
    ("PH", "서지1", "ph_surge"),
    ("PH", "완제품1", "ph_product"),
    ("당도", "살균후", "brix_after_pasteur"),
    ("당도", "접종후 (1H)", "brix_1h"),
    ("당도", "종결", "brix_end"),
    ("당도", "서지1", "brix_surge"),
    ("당도", "완제품1", "brix_product"),
]

KEYS = [c[2] for c in COLUMNS]
SUBS = [c[1] for c in COLUMNS]
GROUPS = [c[0] for c in COLUMNS]

TEXT_KEYS = {"batch_date", "tank", "memo"}
NUMERIC_KEYS = [k for k in KEYS if k not in TEXT_KEYS]

ALIASES = {
    "일자": "batch_date", "날짜": "batch_date", "date": "batch_date", "batch_date": "batch_date",
    "탱크": "tank", "투입탱크": "tank", "tank": "tank",
    "제품이송후탱크온도": "inlet_tank_c", "이송후탱크온도": "inlet_tank_c", "inlet_tank_c": "inlet_tank_c",
    "새벽실내온도": "indoor_dawn_c", "새벽a300실내온도": "indoor_dawn_c", "indoor_dawn_c": "indoor_dawn_c",
    "살균냉각온도": "cooling_set_c", "살균냉각설정": "cooling_set_c", "cooling_set_c": "cooling_set_c",
    "핫워터설정온도": "hotwater_set_c", "핫워터설정": "hotwater_set_c", "hotwater_set_c": "hotwater_set_c",
    "종결분": "total_minutes", "종결시간": "total_minutes", "종결시간(분)": "total_minutes",
    "total_minutes": "total_minutes",
    "산도차": "acidity_delta", "acidity_delta": "acidity_delta",
    "종결산도": "final_acidity", "최종산도": "final_acidity", "final_acidity": "final_acidity",
    "최종ph": "ph_end", "ph": "ph_end", "final_ph": "ph_end", "ph_end": "ph_end",
    "1차샘플(5h)": "acid_5h", "5h산도": "acid_5h", "acid_5h": "acid_5h",
    "배치량(l)": "volume_l", "배치량": "volume_l", "volume_l": "volume_l",
    "비고": "memo", "메모": "memo", "memo": "memo",
    "새벽실외온도": "outdoor_dawn_c", "outdoor_c": "outdoor_dawn_c",
    "당일날씨온도": "weather_c",
}

SAMPLE_ROWS = [
    ["2026-08-03", 301, 38.9, 39.0, 39.2, 39.1, 38.5, 34.2, 36.5, None, None, 38.8, None, 38.6, 38.4, 51, 52, None, None, 49, 46, 29.5, 47, 28.9, 31.4, 32.8, 32.1, None, None, 38.6, 38.4, 38.3, 39.8, 38.1, 38.5, 38.5, 0.192, 0.216, 0.872, 372, 0.974, 0.104, 0.00140, 68, 56, 0.671, 0.671, 455.0, 648.0, 26.8, 28.4, 6.50, 6.38, 4.90, 4.72, 4.60, 4.60, 16.58, 16.66, 11.80, 13.05, 13.22],
    ["2026-08-04", 302, 38.7, 38.8, 39.0, 39.3, 38.5, 34.6, 36.8, None, None, 38.9, None, 38.9, 38.7, 50, 51, None, None, 51, 45, 30.2, 48, 29.4, 30.8, 31.6, 30.4, None, None, 38.7, 38.4, 38.2, 39.9, 38.3, 38.5, 38.5, 0.196, 0.219, 0.879, 368, 0.977, 0.100, 0.00138, 66, 54, 0.668, 0.668, 452.6, 653.4, 27.1, 28.9, 6.48, 6.36, 4.88, 4.70, 4.58, 4.59, 16.61, 16.70, 11.82, 13.10, 13.28],
    ["2026-08-05", 303, 38.2, 38.4, 38.9, 39.0, 38.5, 35.1, 37.2, None, None, 39.2, None, 39.1, 38.8, 49, 50, None, None, 48, 43, 31.0, 46, 30.1, 32.4, 33.0, 32.6, None, None, 38.4, 38.4, 38.5, 40.1, 38.0, 38.5, 38.5, 0.190, 0.214, 0.868, 376, 0.971, 0.107, 0.00143, 69, 57, 0.664, 0.664, 449.8, 651.2, 26.9, 28.6, 6.52, 6.40, 4.91, 4.73, 4.61, 4.60, 16.55, 16.63, 11.78, 13.01, 13.19],
]


def norm_header(h: Any) -> str:
    return str(h).strip().lower().replace(" ", "").replace("\u3000", "").replace("\n", "")


def build_template_bytes(with_samples: bool = True, extra_rows: int = 40) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.cell(row=1, column=2, value=TITLE).font = Font(size=13, bold=True, color="4C1D95")

    group_fill = PatternFill("solid", fgColor="EDE9FE")
    head_fill = PatternFill("solid", fgColor="DDD6FE")
    start = 0
    for i in range(len(COLUMNS) + 1):
        if i == len(COLUMNS) or (i > start and GROUPS[i] != GROUPS[start]):
            g = GROUPS[start]
            if g:
                c1, c2 = start + 1, i
                ws.merge_cells(start_row=5, start_column=c1, end_row=5, end_column=c2)
                cell = ws.cell(row=5, column=c1, value=g)
                cell.font = Font(bold=True, color="4C1D95")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                for cc in range(c1, c2 + 1):
                    ws.cell(row=5, column=cc).fill = group_fill
            start = i

    for j, (g, sub, key) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=HDR_ROW, column=j, value=sub)
        cell.font = Font(bold=True, size=9, color="4C1D95")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = head_fill
        cell.border = border
        ws.column_dimensions[get_column_letter(j)].width = 11 if j > 2 else 14

    if with_samples:
        for r, row in enumerate(SAMPLE_ROWS, start=DATA_ROW):
            for j, v in enumerate(row, start=1):
                c = ws.cell(row=r, column=j, value=v)
                c.border = border
                c.font = Font(size=9)
    n_first = DATA_ROW + (len(SAMPLE_ROWS) if with_samples else 0)
    for r in range(n_first, n_first + extra_rows):
        for j in range(1, len(COLUMNS) + 1):
            ws.cell(row=r, column=j).border = border
    ws.freeze_panes = ws.cell(row=DATA_ROW, column=3)

    guide = wb.create_sheet("작성안내")
    guide.column_dimensions["A"].width = 26
    guide.column_dimensions["B"].width = 12
    guide.column_dimensions["C"].width = 70
    guide.append(["항목", "필수", "설명"])
    for cell in guide[1]:
        cell.font = Font(bold=True, color="4C1D95")
    for row in [
        ("날짜", "필수", "제조일. 처방이력과 매칭되어 예측값·잔차가 자동 연결됩니다."),
        ("300 탱크", "필수", "301 / 302 / 303. 303호는 이송 온도차가 +0.51℃ 큼(센서·경로 점검 권고)."),
        ("제품 이송후 탱크 온도", "필수", "이송 후 발효탱크 유입 실측온도. 잔차 산출의 종속값."),
        ("새벽A300 실내 온도", "필수", "이송 열손실 회귀의 입력값(실측 최저 15.8℃, 최고 37.7℃)."),
        ("살균냉각온도", "필수", "P101 계열 살균냉각 설정·실측값. 처방의 실제 조작 변수."),
        ("핫워터설정온도", "필수", "재킷 온수 설정값. 실측 분포 38.0 / 38.5 / 39.0℃."),
        ("종결분", "필수", "접종 후 종결까지 소요 분. 종결시간 잔차 보정에 사용."),
        ("종결(산도)", "선택", "완제품 최종 적정산도(기준선 0.9734)."),
        ("산도차", "선택", "1차샘플(5H) 산도 − 초기 산도. 기준선 0.1162."),
        ("새벽/접종 실외 온도", "선택", "기입 시 이송 손실·계절 판정 정확도가 올라갑니다."),
        ("나머지 열", "선택", "기존 양식 그대로 기입하면 그대로 보관됩니다(변경 불필요)."),
    ]:
        guide.append(list(row))
    guide.freeze_panes = "A2"

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _resolve_keys(header_row: Sequence[Any]) -> dict[int, str]:
    counters: dict[str, int] = {}
    order: dict[str, list[str]] = {}
    for _, col, key in COLUMNS:
        order.setdefault(norm_header(col), []).append(key)
    assigned: dict[int, str] = {}
    for j, raw in enumerate(header_row):
        n = norm_header(raw)
        if not n:
            continue
        if n in order:
            idx = counters.get(n, 0)
            if idx < len(order[n]):
                assigned[j] = order[n][idx]
                counters[n] = idx + 1
        elif n in ALIASES:
            assigned[j] = ALIASES[n]
    return assigned


SENTINELS = {"미측정", "미기록", "미실시", "없음", "-", "--", "x", "n/a", "na", "nan", "null", ""}

GUIDE_SHEET = "작성안내"


def parse_results_excel(file_like: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if isinstance(file_like, (bytes, bytearray)):
        file_like = io.BytesIO(bytes(file_like))
    sheets = pd.read_excel(file_like, sheet_name=None, header=None, dtype=object)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for sheet_name, grid in sheets.items():
        if grid is None or grid.empty or str(sheet_name).strip() == GUIDE_SHEET:
            continue

        best_idx, best_keys = None, {}
        for i in range(min(len(grid), 20)):
            keys = _resolve_keys(grid.iloc[i].tolist())
            if "batch_date" in keys.values() and len(keys) > len(best_keys):
                best_idx, best_keys = i, keys
        if best_idx is None or len(best_keys) < 5:
            continue

        for i in range(best_idx + 1, len(grid)):
            raw = grid.iloc[i]
            rec: dict[str, Any] = {}
            for j, val in enumerate(raw.tolist()):
                key = best_keys.get(j)
                if not key or val is None or pd.isna(val):
                    continue
                if isinstance(val, str) and val.strip().lower() in SENTINELS:
                    continue
                if key in NUMERIC_KEYS:
                    try:
                        rec[key] = float(val)
                    except (TypeError, ValueError):
                        errors.append(f"[{sheet_name}] {i + 1}행 '{SUBS[j]}' 값 '{val}'을(를) 숫자로 읽지 못했습니다.")
                        continue
                elif key == "batch_date":
                    try:
                        rec[key] = pd.to_datetime(val).strftime("%Y-%m-%d")
                    except Exception:
                        rec[key] = str(val).strip()[:10]
                elif key == "tank":
                    s = str(val).strip().replace("호", "")
                    rec[key] = s if s else str(val).strip()
                else:
                    rec[key] = str(val).strip()
            if rec.get("batch_date"):
                rows.append(rec)

    if not rows:
        errors.append("읽을 수 있는 데이터 행이 없습니다. '날짜' 열이 있는 시트인지 확인하세요.")

    dedup: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        dedup[(r.get("batch_date"), str(r.get("tank")))] = r
    return list(dedup.values()), errors


def results_to_bytes(rows: Sequence[dict[str, Any]], prescriptions: Sequence[dict[str, Any]] | None = None) -> bytes:
    out = io.BytesIO()
    df = pd.DataFrame(list(rows))
    rx = pd.DataFrame(list(prescriptions or []))
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="실적이력", index=False)
        rx.to_excel(w, sheet_name="처방이력", index=False)
    return out.getvalue()

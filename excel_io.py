# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from typing import Any, Sequence

import pandas as pd

def norm_header(h: Any) -> str:
    return str(h).strip().lower().replace(" ", "").replace("\u3000", "")


_RAW_HEADER_MAP = {
    "일자": "batch_date",
    "날짜": "batch_date",
    "batch_date": "batch_date",
    "date": "batch_date",
    "투입탱크": "tanks",
    "탱크": "tanks",
    "tanks": "tanks",
    "배치량(l)": "volume_l",
    "배치량": "volume_l",
    "volume_l": "volume_l",
    "원료": "raw_material",
    "원유": "raw_material",
    "raw_material": "raw_material",
    "새벽 실내온도(℃)": "indoor_dawn_c",
    "새벽실내온도": "indoor_dawn_c",
    "실내온도": "indoor_dawn_c",
    "indoor_dawn_c": "indoor_dawn_c",
    "외기온도(℃)": "outdoor_c",
    "외기온도": "outdoor_c",
    "outdoor_c": "outdoor_c",
    "살균냉각 설정(℃)": "pasteurize_cooling_set_c",
    "살균냉각설정": "pasteurize_cooling_set_c",
    "pasteurize_cooling_set_c": "pasteurize_cooling_set_c",
    "살균냉각 실측(℃)": "pasteurize_cooling_actual_c",
    "살균냉각실측": "pasteurize_cooling_actual_c",
    "pasteurize_cooling_actual_c": "pasteurize_cooling_actual_c",
    "이송후 탱크온도(℃)": "inlet_tank_c",
    "이송후탱크온도": "inlet_tank_c",
    "inlet_tank_c": "inlet_tank_c",
    "핫워터 설정(℃)": "hotwater_set_c",
    "핫워터설정": "hotwater_set_c",
    "hotwater_set_c": "hotwater_set_c",
    "발효 5h 산도": "acid_5h",
    "5h산도": "acid_5h",
    "acid_5h": "acid_5h",
    "종결시간(분)": "total_minutes",
    "종결시간": "total_minutes",
    "total_minutes": "total_minutes",
    "최종 산도": "final_acidity",
    "final_acidity": "final_acidity",
    "최종 ph": "final_ph",
    "final_ph": "final_ph",
    "점도(cp)": "viscosity_cp",
    "점도": "viscosity_cp",
    "viscosity_cp": "viscosity_cp",
    "이슬분리(%)": "syneresis_pct",
    "유청분리(%)": "syneresis_pct",
    "syneresis_pct": "syneresis_pct",
    "관능점수": "taste_score",
    "taste_score": "taste_score",
    "비고": "memo",
    "메모": "memo",
    "memo": "memo",
}

HEADER_MAP = {norm_header(k): v for k, v in _RAW_HEADER_MAP.items()}

NUMERIC_KEYS = [
    "volume_l", "indoor_dawn_c", "outdoor_c", "pasteurize_cooling_set_c",
    "pasteurize_cooling_actual_c", "inlet_tank_c", "hotwater_set_c", "acid_5h",
    "total_minutes", "final_acidity", "final_ph", "viscosity_cp",
    "syneresis_pct", "taste_score", "predicted_drop_c", "predicted_minutes",
]

TEMPLATE_HEADERS = [
    "일자", "투입탱크", "배치량(L)", "원료", "새벽 실내온도(℃)", "외기온도(℃)",
    "살균냉각 설정(℃)", "살균냉각 실측(℃)", "이송후 탱크온도(℃)", "핫워터 설정(℃)",
    "발효 5H 산도", "종결시간(분)", "최종 산도", "최종 pH", "점도(cP)",
    "이슬분리(%)", "관능점수", "비고",
]

SAMPLE_ROWS = [
    ["2026-10-15", "301호 탱크, 302호 탱크", 16500, "국산 1등급A 원유 (표준)", 15.2, 11.4, 40.0, 39.8, 38.6, 38.7, 0.905, 362, 0.982, 4.62, 3410, 1.4, 4.6, "겨울 보정운전"],
    ["2026-10-14", "301호 탱크", 15000, "국산 1등급A 원유 (표준)", 16.1, 12.8, 39.6, 39.5, 38.4, 38.6, 0.898, 371, 0.974, 4.66, 3290, 1.2, 4.8, ""],
    ["2026-10-13", "302호 탱크", 16500, "무항생제/유기농 원유 (고단백)", 17.4, 14.2, 39.2, 39.3, 38.5, 38.6, 0.902, 376, 0.969, 4.68, 3220, 1.1, 5.0, ""],
    ["2026-10-12", "301호 탱크, 302호 탱크", 16500, "국산 1등급A 원유 (표준)", 19.8, 18.0, 38.8, 38.9, 38.5, 38.5, 0.908, 379, 0.967, 4.69, 3200, 1.1, 5.0, ""],
    ["2026-10-11", "303호 탱크", 15000, "저지방 배합원유 (고수분)", 20.6, 19.4, 38.6, 38.6, 38.5, 38.4, 0.910, 381, 0.965, 4.70, 3180, 1.0, 5.0, "골든 근접"],
]


def _norm(h: Any) -> str:
    return norm_header(h)


def build_template_bytes() -> bytes:
    out = io.BytesIO()
    guide = pd.DataFrame(
        {
            "항목": [
                "새벽 실내온도(℃)", "살균냉각 실측(℃)", "이송후 탱크온도(℃)",
                "종결시간(분)", "최종 산도",
            ],
            "필수": ["필수", "필수", "필수", "필수", "선택"],
            "설명": [
                "당일 새벽(착수 전) 공정 실내온도. 회귀식 입력값",
                "살균기 토출 실측 액온(P101TT02)",
                "이송 후 발효탱크 유입 실측온도. 이송 열손실 산출의 종속값",
                "접종 후 종결까지 총 소요 시간",
                "완제품 최종 적정산도(골든 0.965)",
            ],
        }
    )
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame(SAMPLE_ROWS, columns=TEMPLATE_HEADERS).to_excel(w, sheet_name="실적입력", index=False)
        guide.to_excel(w, sheet_name="작성안내", index=False)
    return out.getvalue()


def results_to_bytes(rows: Sequence[dict[str, Any]], prescriptions: Sequence[dict[str, Any]] | None = None) -> bytes:
    out = io.BytesIO()
    df = pd.DataFrame(list(rows))
    rx = pd.DataFrame(list(prescriptions or []))
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="전일실적", index=False)
        rx.to_excel(w, sheet_name="처방이력", index=False)
    return out.getvalue()


def parse_results_excel(file_like: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if isinstance(file_like, (bytes, bytearray)):
        file_like = io.BytesIO(bytes(file_like))
    sheets = pd.read_excel(file_like, sheet_name=None, dtype=object)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []

    for sheet_name, df in sheets.items():
        if df is None or df.empty:
            continue
        mapping: dict[str, str] = {}
        for col in df.columns:
            key = HEADER_MAP.get(_norm(col))
            if key:
                mapping[col] = key
        if not mapping:
            continue
        if "batch_date" not in mapping.values():
            errors.append(f"[{sheet_name}] 일자 열을 찾지 못해 건너뛰었습니다.")
            continue

        for idx, raw in df.iterrows():
            rec: dict[str, Any] = {}
            for col, key in mapping.items():
                val = raw[col]
                if pd.isna(val):
                    continue
                if key in NUMERIC_KEYS:
                    try:
                        rec[key] = float(val)
                    except (TypeError, ValueError):
                        errors.append(f"[{sheet_name}] {idx + 2}행 '{col}' 값 '{val}'을(를) 숫자로 읽지 못했습니다.")
                        continue
                elif key == "batch_date":
                    try:
                        rec[key] = pd.to_datetime(val).strftime("%Y-%m-%d")
                    except Exception:
                        rec[key] = str(val).strip()
                else:
                    rec[key] = str(val).strip()
            if rec.get("batch_date"):
                rows.append(rec)

    dedup: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        dedup[(r.get("batch_date"), r.get("tanks"))] = r
    return list(dedup.values()), errors

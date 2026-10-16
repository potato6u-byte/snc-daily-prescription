# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

import numpy as np

MODEL_VERSION = "v1.0"

GOLDEN = {
    "hotwater_set_c": 38.4,
    "pasteurize_cooling_set_c": 38.5,
    "inlet_target_c": 38.5,
    "total_minutes": 380.0,
    "final_acidity": 0.965,
    "final_ph": 4.70,
    "viscosity_cp": 3200.0,
}

BASELINE = {
    "outdoor_temp_c": 27.6,
    "pasteurize_cooling_set_c": 38.5,
    "hotwater_set_c": 38.5,
    "acidity_delta": 0.116,
    "total_minutes": 382.9,
    "batches": 278,
    "window": "2025-07 ~ 2026-07",
}

TRANSPORT = {
    "intercept": 2.44,
    "slope_per_c": -0.078,
    "se": 0.359,
    "r2": 0.61,
    "n": 277,
    "z95": 1.96,
    "drop_min_c": 0.2,
    "drop_max_c": 3.0,
}

SENSITIVITY = {
    "minutes_per_c": -8.5,
    "acidity_delta_per_c": -0.0051,
    "viscosity_cp_per_c": 220.0,
}

WINTER_DEVIATION = {
    "cooling_set_shift_c": (1.4, 3.0),
    "acidity_delta_pct": -9.6,
    "minutes": -19.0,
}

CORRELATIONS = {
    "실내온도↔살균냉각": -0.87,
    "살균냉각↔종결시간": -0.69,
    "살균냉각↔5H산도": 0.73,
    "살균냉각↔점도": 0.66,
}

TANK_SPECS = {
    "301호 탱크": {"kappa": 1.00, "desc": "표준형 단열 탱크 (중앙 구역)"},
    "302호 탱크": {"kappa": 1.15, "desc": "외벽 밀접 탱크 (방열 손실 15% 큼)"},
    "303호 탱크": {"kappa": 0.90, "desc": "고단열 보온 자켓 탱크 (방열 손실 10% 적음)"},
    "304호 탱크": {"kappa": 0.95, "desc": "대용량 5000L 탱크 (열용량 큼)"},
    "305호 탱크": {"kappa": 1.10, "desc": "소용량 3000L 탱크 (방열 빠름)"},
}

RAW_SPECS = {
    "국산 1등급A 원유 (표준)": {"cp_kj_kgk": 3930.0, "offset_c": 0.0, "chilling_target_c": 7.3},
    "무항생제/유기농 원유 (고단백)": {"cp_kj_kgk": 3890.0, "offset_c": 0.2, "chilling_target_c": 7.5},
    "저지방 배합원유 (고수분)": {"cp_kj_kgk": 4020.0, "offset_c": -0.1, "chilling_target_c": 7.1},
    "고형분 농축/환원 배합유": {"cp_kj_kgk": 3820.0, "offset_c": 0.1, "chilling_target_c": 7.3},
}

DEFAULT_TIME_BANDS = [
    {"시작": "22:00", "종료": "06:00", "보정dC": 0.3, "메모": "심야/새벽 착수 - 초기온도 확보"},
    {"시작": "06:00", "종료": "10:00", "보정dC": 0.1, "메모": "아침 착수 - 완만한 발효 유도"},
    {"시작": "10:00", "종료": "16:00", "보정dC": 0.0, "메모": "주간 착수 - 기준"},
    {"시작": "16:00", "종료": "22:00", "보정dC": 0.2, "메모": "저녁 착수 - 야간 방열 대비"},
]

EVIDENCE = {
    "transport": "2025.7~2026.7 품질관리일보 277배치 회귀, r2=0.61, p<0.001",
    "golden": "골든배치(2026-09-11 FermaAX 제어 기준), 불량률 16.9% -> 0% 목표",
    "baseline": "핫워터/살균냉각 38.5C 기준선, 외기 약 27.6C (278배치)",
    "winter": "겨울 보정운전 실측 이탈: 살균냉각 +1.4~3.0C, 산도차 -9.6%, 종결 -19.0분",
    "hotwater": "현장 경험식(ferma-ax 계승). 데이터 축적 후 3단계에서 규칙화 대상 - 미검증",
    "time_band": "착수 시간대별 야간 방열 대비 경험 보정 - 미검증",
    "heat_loss": "중량 x 물 등가 비열 1.0 kcal/kg.C x 온도하락폭 환산 참고값",
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return float(min(max(v, lo), hi))


def predict_transport_drop(indoor_dawn_c: float) -> tuple[float, float, float]:
    raw = TRANSPORT["intercept"] + TRANSPORT["slope_per_c"] * float(indoor_dawn_c)
    drop = _clamp(raw, TRANSPORT["drop_min_c"], TRANSPORT["drop_max_c"])
    half = TRANSPORT["z95"] * TRANSPORT["se"]
    return round(drop, 2), round(_clamp(drop - half, 0.0, 5.0), 2), round(drop + half, 2)


def observed_drop(pasteurize_cooling_actual_c: float, inlet_tank_c: float) -> float:
    return round(float(pasteurize_cooling_actual_c) - float(inlet_tank_c), 2)


def heat_loss_kcal(drop_c: float, volume_l: float) -> float:
    return round(float(volume_l) * 1.0 * float(drop_c), 1)


def kappa_of(tanks: Sequence[str]) -> float:
    ks = [TANK_SPECS[t]["kappa"] for t in tanks if t in TANK_SPECS]
    return max(ks) if ks else 1.00


def active_time_band(hour_float: float, bands: Sequence[dict]) -> dict | None:
    for b in bands:
        try:
            sh, sm = str(b["시작"]).split(":")
            eh, em = str(b["종료"]).split(":")
            s = int(sh) + int(sm) / 60.0
            e = int(eh) + int(em) / 60.0
        except Exception:
            continue
        inside = (s <= hour_float < e) if s <= e else (hour_float >= s or hour_float < e)
        if inside:
            return b
    return None


def time_band_offset(hour_float: float, bands: Sequence[dict]) -> float:
    b = active_time_band(hour_float, bands)
    try:
        return float(b["보정dC"]) if b else 0.0
    except Exception:
        return 0.0


def ewma(values: Sequence[float], alpha: float = 0.5) -> float:
    vals = [float(v) for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if not vals:
        return 0.0
    acc = vals[0]
    for v in vals[1:]:
        acc = alpha * v + (1 - alpha) * acc
    return round(acc, 3)


def residual_terms(
    predicted_drop_c: float,
    actual_drop_c: float,
    predicted_minutes: float | None = None,
    actual_minutes: float | None = None,
) -> dict[str, float]:
    drop_res = round(float(actual_drop_c) - float(predicted_drop_c), 2)
    minute_res = 0.0
    if predicted_minutes is not None and actual_minutes is not None:
        minute_res = round(float(actual_minutes) - float(predicted_minutes), 1)
    return {"drop_residual_c": drop_res, "minute_residual": minute_res}


@dataclass
class Prescription:
    rx_date: str
    indoor_dawn_c: float
    outdoor_c: float
    tanks: list[str]
    volume_l: float
    raw_material: str
    transport_drop_c: float
    transport_drop_lo_c: float
    transport_drop_hi_c: float
    inlet_target_c: float
    cooling_set_c: float
    hotwater_set_c: float
    cooling_residual_c: float
    minutes_residual: float
    time_offset_c: float
    predicted_minutes: float
    predicted_acidity_delta: float
    predicted_final_acidity: float
    predicted_final_ph: float
    predicted_viscosity_cp: float
    chilling_target_c: float
    heat_loss_kcal: float
    confidence: str
    basis: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION

    def as_row(self) -> dict[str, Any]:
        return {
            "rx_date": self.rx_date,
            "indoor_dawn_c": self.indoor_dawn_c,
            "outdoor_c": self.outdoor_c,
            "tanks": ", ".join(self.tanks),
            "volume_l": self.volume_l,
            "raw_material": self.raw_material,
            "transport_drop_c": self.transport_drop_c,
            "transport_drop_lo_c": self.transport_drop_lo_c,
            "transport_drop_hi_c": self.transport_drop_hi_c,
            "inlet_target_c": self.inlet_target_c,
            "cooling_set_c": self.cooling_set_c,
            "hotwater_set_c": self.hotwater_set_c,
            "cooling_residual_c": self.cooling_residual_c,
            "minutes_residual": self.minutes_residual,
            "time_offset_c": self.time_offset_c,
            "predicted_minutes": self.predicted_minutes,
            "predicted_acidity_delta": self.predicted_acidity_delta,
            "predicted_final_acidity": self.predicted_final_acidity,
            "predicted_final_ph": self.predicted_final_ph,
            "predicted_viscosity_cp": self.predicted_viscosity_cp,
            "chilling_target_c": self.chilling_target_c,
            "heat_loss_kcal": self.heat_loss_kcal,
            "confidence": self.confidence,
            "model_version": self.model_version,
        }


def prescribe(
    indoor_dawn_c: float,
    outdoor_c: float,
    tanks: Sequence[str] = ("301호 탱크",),
    volume_l: float = 15000.0,
    raw_material: str = "국산 1등급A 원유 (표준)",
    cooling_residual_c: float = 0.0,
    minutes_residual: float = 0.0,
    hour_float: float | None = None,
    time_bands: Sequence[dict] | None = None,
    rx_date: str | None = None,
) -> Prescription:
    bands = list(time_bands) if time_bands else DEFAULT_TIME_BANDS
    t_off = time_band_offset(hour_float, bands) if hour_float is not None else 0.0

    indoor = float(indoor_dawn_c)
    outdoor = float(outdoor_c)
    drop, lo, hi = predict_transport_drop(indoor)

    k = kappa_of(tanks)
    raw = RAW_SPECS.get(raw_material, {"cp_kj_kgk": 3930.0, "offset_c": 0.0, "chilling_target_c": 7.3})

    cooling = GOLDEN["pasteurize_cooling_set_c"] + drop + float(cooling_residual_c) + t_off
    cooling = _clamp(cooling, 37.5, 42.0)

    cold_drive = max(0.0, 25.0 - indoor)
    hotwater = GOLDEN["hotwater_set_c"] + cold_drive * 0.040 * k + raw["offset_c"] * 0.5 + t_off * 0.7
    hotwater = _clamp(hotwater, 37.5, 39.5)

    cooling_shift = cooling - BASELINE["pasteurize_cooling_set_c"]
    minutes = (
        GOLDEN["total_minutes"]
        + cooling_shift * SENSITIVITY["minutes_per_c"]
        + float(minutes_residual)
    )
    minutes = _clamp(minutes, 300.0, 460.0)

    acidity_delta = BASELINE["acidity_delta"] + cooling_shift * SENSITIVITY["acidity_delta_per_c"]
    acidity_delta = _clamp(acidity_delta, 0.06, 0.20)

    ph = GOLDEN["final_ph"] - (acidity_delta - BASELINE["acidity_delta"]) * 3.2
    viscosity = GOLDEN["viscosity_cp"] + cooling_shift * SENSITIVITY["viscosity_cp_per_c"]

    heat_loss = heat_loss_kcal(drop, volume_l)

    conf = "보통"
    notes: list[str] = []
    if indoor < 15.8:
        conf = "낮음 (외삽 구간)"
        notes.append("새벽 실내온도 15.8C 미만: 관측 최저치 이하 외삽 구간으로 실측 검증이 필요합니다.")
    elif indoor > 24.0:
        conf = "낮음 (관측 범위 밖)"
        notes.append("새벽 실내온도 24C 초과: 하절기 관측 밖 구간입니다.")
    if abs(cooling_residual_c) >= 0.5:
        conf = "보통 (잔차 보정 큼)"
        notes.append(f"전일 이송온도 잔차 {cooling_residual_c:+.2f}C가 반영되었습니다. 센서/배관 조건을 함께 확인하세요.")
    if abs(minutes_residual) >= 15:
        notes.append(f"전일 종결시간 잔차 {minutes_residual:+.1f}분이 반영되었습니다.")
    if t_off:
        notes.append(f"착수 시간대 보정 {t_off:+.1f}C 적용 (살균냉각 전량, 핫워터 70%).")

    return Prescription(
        rx_date=rx_date or date.today().isoformat(),
        indoor_dawn_c=round(indoor, 1),
        outdoor_c=round(outdoor, 1),
        tanks=list(tanks),
        volume_l=float(volume_l),
        raw_material=raw_material,
        transport_drop_c=drop,
        transport_drop_lo_c=lo,
        transport_drop_hi_c=hi,
        inlet_target_c=GOLDEN["inlet_target_c"],
        cooling_set_c=round(cooling, 1),
        hotwater_set_c=round(hotwater, 1),
        cooling_residual_c=round(float(cooling_residual_c), 2),
        minutes_residual=round(float(minutes_residual), 1),
        time_offset_c=round(float(t_off), 1),
        predicted_minutes=round(minutes, 1),
        predicted_acidity_delta=round(acidity_delta, 3),
        predicted_final_acidity=GOLDEN["final_acidity"],
        predicted_final_ph=round(ph, 2),
        predicted_viscosity_cp=round(viscosity, 0),
        chilling_target_c=raw["chilling_target_c"],
        heat_loss_kcal=heat_loss,
        confidence=conf,
        basis=dict(EVIDENCE),
        notes=notes,
    )


def review(actual_rows: Sequence[dict], prescription_row: dict | None = None) -> dict[str, Any]:
    rows = [r for r in actual_rows if r]
    if not rows:
        return {"count": 0, "message": "검토할 전일 실적이 없습니다."}

    latest = rows[0]
    pred_drop = float(latest.get("predicted_drop_c") or 0.0)
    act_drop = observed_drop(
        latest.get("pasteurize_cooling_actual_c", 0.0),
        latest.get("inlet_tank_c", 0.0),
    )
    terms = residual_terms(
        pred_drop,
        act_drop,
        latest.get("predicted_minutes"),
        latest.get("total_minutes"),
    )

    drops = []
    mins = []
    for r in rows[:7]:
        pd_ = float(r.get("predicted_drop_c") or 0.0)
        ad_ = observed_drop(r.get("pasteurize_cooling_actual_c", 0.0), r.get("inlet_tank_c", 0.0))
        drops.append(ad_ - pd_)
        if r.get("predicted_minutes") and r.get("total_minutes"):
            mins.append(float(r["total_minutes"]) - float(r["predicted_minutes"]))

    drop_correction = round(ewma(drops), 2)
    minute_correction = round(ewma(mins), 1)

    return {
        "count": len(rows),
        "latest": latest,
        "latest_drop_residual_c": terms["drop_residual_c"],
        "latest_minute_residual": terms["minute_residual"],
        "drop_correction_c": drop_correction,
        "minute_correction": minute_correction,
        "acidity_actual": latest.get("final_acidity"),
        "ph_actual": latest.get("final_ph"),
        "viscosity_actual": latest.get("viscosity_cp"),
        "message": "정상 범위" if abs(drop_correction) < 0.5 else "잔차 큼 - 보정 반영",
    }

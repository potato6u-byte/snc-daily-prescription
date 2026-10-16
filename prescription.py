# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

import numpy as np

MODEL_VERSION = "v2.0"
MODEL_SOURCE = "통합데이터.xlsx (T300온도) 278배치, 2025-07-01 ~ 2026-07-30 실측 재적합"

BASELINE = {
    "cooling_set_c": 38.5,
    "hotwater_set_c": 38.5,
    "inlet_tank_c": 38.75,
    "outdoor_c": 27.01,
    "indoor_dawn_c": 32.72,
    "acidity_delta": 0.1162,
    "total_minutes": 382.9,
    "final_acidity": 0.9734,
    "final_ph": 4.650,
    "n": 43,
}

GOLDEN = {
    "cooling_set_c": 38.95,
    "hotwater_set_c": 38.36,
    "inlet_tank_c": 38.94,
    "acidity_delta": 0.1162,
    "total_minutes": 379.5,
    "final_acidity": 0.9702,
    "final_ph": 4.699,
    "n": 48,
}

TANK_SPECS = {
    "301": {"transport_offset_c": 0.00, "n": 94},
    "302": {"transport_offset_c": 0.01, "n": 91},
    "303": {"transport_offset_c": 0.51, "n": 93},
}

TRANSPORT = {
    "intercept": 2.4385,
    "slope_per_c": -0.07842,
    "se": 0.3613,
    "r2": 0.614,
    "n": 277,
    "z95": 1.96,
    "drop_lo_obs": -0.60,
    "drop_hi_obs": 2.20,
}

COOLING_MODEL = {
    "total_minutes": {"a": 795.263, "b": -10.7878, "se": 14.11, "r2": 0.473},
    "acidity_delta": {"a": 0.3817, "b": -0.00692, "se": 0.01369, "r2": 0.282},
    "final_acidity": {"a": 0.7479, "b": 0.0058, "se": 0.0072, "r2": 0.497},
    "acid_5h": {"a": 0.3662, "b": 0.0127, "se": 0.0149, "r2": 0.528},
    "final_ph": {"a": 4.3773, "b": 0.0085, "se": 0.0474, "r2": 0.047},
}

HOTWATER_MODEL = {"a": 39.0351, "b": -0.0224, "se": 0.1732, "r2": 0.360, "n": 277, "lo": 38.0, "hi": 39.0}

INDOOR_TO_OUTDOOR = {"a": -27.8807, "b": 1.5307, "r2": 0.922, "n": 148}

CORRELATIONS = {
    "새벽실내 ↔ 살균냉각": -0.864,
    "살균냉각 ↔ 종결분": -0.688,
    "살균냉각 ↔ 5H산도": 0.726,
    "살균냉각 ↔ 종결산도": 0.705,
    "새벽실내 ↔ 종결분": 0.694,
    "살균냉각 ↔ 산도차": -0.531,
}

WINTER_PRACTICE = {
    "cooling_set_c": 40.69,
    "indoor_dawn_c": 22.76,
    "total_minutes": 355.59,
    "acidity_delta": 0.1005,
    "inlet_tank_c": 39.905,
    "n": 101,
}

EVIDENCE = {
    "transport": "살균냉각온도 − 이송후 탱크온도 ~ 새벽 실내온도 회귀 (n=277, r²=0.614, se 0.36℃) — 보고서 계수와 일치",
    "baseline": "핫워터 38.5 & 살균냉각 38.5 운전 배치 43건 실측 평균 — 보고서 기준선(0.116 / 382.9)과 일치",
    "golden": "종결분 375~385 & 산도차 0.110~0.120 구간 48건 실측 평균",
    "cooling_total_minutes": "종결분 ~ 살균냉각온도 회귀 (n=278, r²=0.473) — 살균냉각 38.5℃에서 379.9분",
    "cooling_acidity_delta": "산도차 ~ 살균냉각온도 회귀 (n=278, r²=0.282)",
    "cooling_final_acidity": "종결산도 ~ 살균냉각온도 회귀 (n=278, r²=0.497)",
    "cooling_acid_5h": "5H산도 ~ 살균냉각온도 회귀 (n=278, r²=0.528)",
    "hotwater": "핫워터설정온도 ~ 새벽 실내온도 회귀 (n=277, r²=0.360). 실측 분포 38.0/38.5/39.0℃",
    "inlet_target": "기준선 실측 이송후 탱크온도 38.75℃ (골든군 38.94℃)",
    "tank303": "303호 이송 온도차가 301/302 대비 +0.51℃ — 센서·이송경로 점검 권고",
    "indoor_outdoor": "접종 실외온도 ~ 새벽 실내온도 (n=148, r²=0.922) 참고용",
}

PRESCRIPTION_MODES = {
    "baseline": "기준선 고정 (살균냉각 38.5℃ 유지) — 데이터 회귀 기반, 권장",
    "report_chain": "이송 보상 (목표 유입온도 + 예상 하락폭) — 보고서 연쇄 방식",
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return float(min(max(v, lo), hi))


def predict_transport_drop(indoor_dawn_c: float) -> tuple[float, float, float]:
    raw = TRANSPORT["intercept"] + TRANSPORT["slope_per_c"] * float(indoor_dawn_c)
    drop = _clamp(raw, TRANSPORT["drop_lo_obs"] - 0.3, TRANSPORT["drop_hi_obs"] + 0.3)
    half = TRANSPORT["z95"] * TRANSPORT["se"]
    return round(drop, 2), round(drop - half, 2), round(drop + half, 2)


def observed_drop(cooling_set_c: float, inlet_tank_c: float) -> float:
    return round(float(cooling_set_c) - float(inlet_tank_c), 2)


def heat_loss_kcal(drop_c: float, volume_l: float) -> float:
    return round(float(volume_l) * 1.0 * float(drop_c), 1)


def predict_from_cooling(cooling_set_c: float) -> dict[str, float]:
    c = float(cooling_set_c)
    out: dict[str, float] = {}
    for key, m in COOLING_MODEL.items():
        out[key] = m["a"] + m["b"] * c
    out["total_minutes"] = round(out["total_minutes"], 1)
    out["final_acidity"] = round(out["final_acidity"], 4)
    out["final_ph"] = round(out["final_ph"], 2)
    out["acid_5h"] = round(out["acid_5h"], 3)
    out["acidity_delta"] = round(out["acidity_delta"], 4)
    return out


def predict_hotwater(indoor_dawn_c: float) -> float:
    v = HOTWATER_MODEL["a"] + HOTWATER_MODEL["b"] * float(indoor_dawn_c)
    return round(_clamp(v, HOTWATER_MODEL["lo"], HOTWATER_MODEL["hi"]), 1)


def predict_outdoor_from_indoor(indoor_dawn_c: float) -> float:
    return round(INDOOR_TO_OUTDOOR["a"] + INDOOR_TO_OUTDOOR["b"] * float(indoor_dawn_c), 1)


def tank_offset(tank: str) -> float:
    key = str(tank).replace("호", "").strip()
    return TANK_SPECS.get(key, {}).get("transport_offset_c", 0.0)


def ewma(values: Sequence[float], alpha: float = 0.5) -> float:
    vals = [float(v) for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if not vals:
        return 0.0
    acc = vals[0]
    for v in vals[1:]:
        acc = alpha * v + (1 - alpha) * acc
    return round(acc, 3)


@dataclass
class Prescription:
    rx_date: str
    mode: str
    tank: str
    volume_t: float
    indoor_dawn_c: float
    indoor_inoc_c: float
    outdoor_c: float
    cooling_set_c: float
    hotwater_set_c: float
    cooling_correction_c: float
    transport_drop_c: float
    transport_drop_lo_c: float
    transport_drop_hi_c: float
    predicted_inlet_c: float
    inlet_target_c: float
    predicted_minutes: float
    predicted_acidity_delta: float
    predicted_final_acidity: float
    predicted_final_ph: float
    predicted_acid_5h: float
    heat_loss_kcal: float
    practice_minutes: float
    practice_acidity_delta: float
    confidence: str
    basis: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION

    def as_row(self) -> dict[str, Any]:
        return {
            "rx_date": self.rx_date,
            "mode": self.mode,
            "tank": self.tank,
            "volume_t": self.volume_t,
            "indoor_dawn_c": self.indoor_dawn_c,
            "indoor_inoc_c": self.indoor_inoc_c,
            "outdoor_c": self.outdoor_c,
            "cooling_set_c": self.cooling_set_c,
            "hotwater_set_c": self.hotwater_set_c,
            "cooling_correction_c": self.cooling_correction_c,
            "transport_drop_c": self.transport_drop_c,
            "transport_drop_lo_c": self.transport_drop_lo_c,
            "transport_drop_hi_c": self.transport_drop_hi_c,
            "predicted_inlet_c": self.predicted_inlet_c,
            "inlet_target_c": self.inlet_target_c,
            "predicted_minutes": self.predicted_minutes,
            "predicted_acidity_delta": self.predicted_acidity_delta,
            "predicted_final_acidity": self.predicted_final_acidity,
            "predicted_final_ph": self.predicted_final_ph,
            "predicted_acid_5h": self.predicted_acid_5h,
            "heat_loss_kcal": self.heat_loss_kcal,
            "confidence": self.confidence,
            "model_version": self.model_version,
        }


def prescribe(
    indoor_dawn_c: float,
    tank: str = "301",
    volume_t: float = 16.5,
    indoor_inoc_c: float | None = None,
    outdoor_c: float | None = None,
    cooling_correction_c: float = 0.0,
    mode: str = "baseline",
    rx_date: str | None = None,
) -> Prescription:
    indoor = float(indoor_dawn_c)
    inoc = float(indoor_inoc_c) if indoor_inoc_c is not None else round(indoor + 3.0, 1)
    outdoor = float(outdoor_c) if outdoor_c is not None else predict_outdoor_from_indoor(indoor)

    drop, lo, hi = predict_transport_drop(indoor)
    off = tank_offset(tank)

    if mode == "report_chain":
        cooling = BASELINE["inlet_tank_c"] + drop + off + float(cooling_correction_c)
    else:
        cooling = BASELINE["cooling_set_c"] + float(cooling_correction_c)
    cooling = _clamp(cooling, 37.0, 42.0)
    cooling = round(cooling, 1)

    hotwater = predict_hotwater(indoor)
    pred = predict_from_cooling(cooling)
    inlet_pred = round(cooling - drop + off, 2)
    volume_l = float(volume_t) * 1000.0
    hl = heat_loss_kcal(drop, volume_l)

    practice_inlet = round(WINTER_PRACTICE["cooling_set_c"] - drop, 2)
    practice_minutes = round(COOLING_MODEL["total_minutes"]["a"] + COOLING_MODEL["total_minutes"]["b"] * WINTER_PRACTICE["cooling_set_c"], 1)
    practice_ad = round(COOLING_MODEL["acidity_delta"]["a"] + COOLING_MODEL["acidity_delta"]["b"] * WINTER_PRACTICE["cooling_set_c"], 4)

    conf = "보통"
    notes: list[str] = []
    if indoor < 15.8:
        conf = "낮음 (외삽)"
        notes.append("새벽 실내온도 15.8℃ 미만: 278배치 관측 최저치 이하 외삽 구간입니다.")
    elif indoor > 37.7:
        conf = "낮음 (외삽)"
        notes.append("새벽 실내온도 37.7℃ 초과: 278배치 관측 최고치 초과 구간입니다.")
    if abs(cooling_correction_c) >= 0.3:
        conf = "보통 (잔차 보정 큼)"
        notes.append(f"전일 실적 잔차 보정 {cooling_correction_c:+.2f}℃가 반영되었습니다.")
    if str(tank).replace("호", "").strip() == "303":
        notes.append(f"303호는 이송 온도차가 301/302 대비 +{off:.2f}℃ 큽니다. 센서·이송경로 점검 권고.")
    if mode == "report_chain":
        notes.append("이송 보상 모드는 보고서의 연쇄 구조를 따른 참고 처방입니다. 실측 회귀는 기준선 고정을 지지합니다.")
    if cooling >= WINTER_PRACTICE["cooling_set_c"] - 0.5:
        notes.append(
            f"현행 겨울 관행(살균냉각 {WINTER_PRACTICE['cooling_set_c']}℃)과 유사한 구간입니다. "
            f"관행 유지 시 예상 종결분 {practice_minutes:.0f}분 / 산도차 {practice_ad:.4f}로 기준선을 이탈합니다."
        )

    return Prescription(
        rx_date=rx_date or date.today().isoformat(),
        mode=mode,
        tank=str(tank),
        volume_t=round(float(volume_t), 2),
        indoor_dawn_c=round(indoor, 1),
        indoor_inoc_c=round(inoc, 1),
        outdoor_c=round(outdoor, 1),
        cooling_set_c=cooling,
        hotwater_set_c=hotwater,
        cooling_correction_c=round(float(cooling_correction_c), 2),
        transport_drop_c=drop,
        transport_drop_lo_c=lo,
        transport_drop_hi_c=hi,
        predicted_inlet_c=inlet_pred,
        inlet_target_c=BASELINE["inlet_tank_c"],
        predicted_minutes=pred["total_minutes"],
        predicted_acidity_delta=pred["acidity_delta"],
        predicted_final_acidity=pred["final_acidity"],
        predicted_final_ph=pred["final_ph"],
        predicted_acid_5h=pred["acid_5h"],
        heat_loss_kcal=hl,
        practice_minutes=practice_minutes,
        practice_acidity_delta=practice_ad,
        confidence=conf,
        basis=dict(EVIDENCE),
        notes=notes,
    )


def review(actual_rows: Sequence[dict], limit: int = 7) -> dict[str, Any]:
    rows = [r for r in actual_rows if r][: int(limit)]
    if not rows:
        return {"count": 0, "message": "검토할 전일 실적이 없습니다."}

    latest = rows[0]
    drops, min_res, ad_res, inl_res = [], [], [], []
    for r in rows:
        cool = r.get("cooling_set_c")
        inlet = r.get("inlet_tank_c")
        indoor = r.get("indoor_dawn_c")
        if cool is None or inlet is None or indoor is None:
            continue
        pred_drop = predict_transport_drop(float(indoor))[0]
        drops.append(observed_drop(cool, inlet) - pred_drop)
        if r.get("predicted_minutes") is not None and r.get("total_minutes") is not None:
            min_res.append(float(r["total_minutes"]) - float(r["predicted_minutes"]))
        if r.get("predicted_acidity_delta") is not None and r.get("acidity_delta") is not None:
            ad_res.append(float(r["acidity_delta"]) - float(r["predicted_acidity_delta"]))
        if r.get("predicted_inlet_c") is not None:
            inl_res.append(float(inlet) - float(r["predicted_inlet_c"]))

    ewma_min = ewma(min_res)
    gain = abs(COOLING_MODEL["total_minutes"]["b"]) or 10.79
    cooling_corr = _clamp(-ewma_min / gain, -0.5, 0.5)

    return {
        "count": len(rows),
        "latest": latest,
        "latest_drop_residual_c": round(drops[0], 2) if drops else 0.0,
        "latest_minute_residual": round(min_res[0], 1) if min_res else 0.0,
        "ewma_drop_residual_c": round(ewma(drops), 2),
        "ewma_minute_residual": ewma_min,
        "ewma_acidity_delta_residual": round(ewma(ad_res), 4),
        "ewma_inlet_residual_c": round(ewma(inl_res), 2),
        "cooling_correction_c": round(cooling_corr, 2),
        "final_acidity_actual": latest.get("final_acidity"),
        "final_ph_actual": latest.get("ph_end"),
        "message": "정상 범위" if abs(ewma_min) < 15 else "종결시간 잔차 큼 — 냉각 보정 반영",
    }


def _fit(xs: list[float], ys: list[float]) -> dict[str, float] | None:
    if len(xs) < 8:
        return None
    xv = np.asarray(xs, dtype=float)
    yv = np.asarray(ys, dtype=float)
    b, a = np.polyfit(xv, yv, 1)
    r = float(np.corrcoef(xv, yv)[0, 1])
    se = float((yv - (a + b * xv)).std(ddof=2))
    return {"a": round(float(a), 4), "b": round(float(b), 5), "r": round(r, 3),
            "r2": round(r * r, 3), "se": round(se, 4), "n": len(xs)}


def refit(rows: Sequence[dict]) -> dict[str, Any]:
    cols: dict[str, list[tuple[float, float]]] = {
        "살균냉각 ↔ 종결분": [], "살균냉각 ↔ 산도차": [], "살균냉각 ↔ 종결산도": [],
        "살균냉각 ↔ 5H산도": [], "새벽실내 ↔ 살균냉각": [], "핫워터 ↔ 새벽실내": [],
        "이송하락 ↔ 새벽실내": [],
    }
    for r in rows:
        try:
            cool = r.get("cooling_set_c")
            inlet = r.get("inlet_tank_c")
            indoor = r.get("indoor_dawn_c")
            mins = r.get("total_minutes")
            ad = r.get("acidity_delta")
            fin = r.get("final_acidity")
            a5 = r.get("acid_5h")
            hw = r.get("hotwater_set_c")

            def push(k, x, y):
                if x is None or y is None:
                    return
                cols[k].append((float(x), float(y)))

            push("살균냉각 ↔ 종결분", cool, mins)
            push("살균냉각 ↔ 산도차", cool, ad)
            push("살균냉각 ↔ 종결산도", cool, fin)
            push("살균냉각 ↔ 5H산도", cool, a5)
            push("새벽실내 ↔ 살균냉각", indoor, cool)
            push("핫워터 ↔ 새벽실내", indoor, hw)
            if cool is not None and inlet is not None and indoor is not None:
                cols["이송하락 ↔ 새벽실내"].append((float(indoor), float(cool) - float(inlet)))
        except (TypeError, ValueError):
            continue

    fitted: dict[str, Any] = {}
    for k, pairs in cols.items():
        if not pairs:
            continue
        f = _fit([p[0] for p in pairs], [p[1] for p in pairs])
        if f:
            fitted[k] = f

    builtin = {
        "이송하락 ↔ 새벽실내": TRANSPORT,
        "살균냉각 ↔ 종결분": COOLING_MODEL["total_minutes"],
        "살균냉각 ↔ 산도차": COOLING_MODEL["acidity_delta"],
        "살균냉각 ↔ 종결산도": COOLING_MODEL["final_acidity"],
        "살균냉각 ↔ 5H산도": COOLING_MODEL["acid_5h"],
        "핫워터 ↔ 새벽실내": {"a": HOTWATER_MODEL["a"], "b": HOTWATER_MODEL["b"],
                             "r2": HOTWATER_MODEL["r2"], "se": HOTWATER_MODEL["se"],
                             "n": HOTWATER_MODEL["n"]},
    }
    return {"fitted": fitted, "builtin": builtin, "n_rows": len(rows)}


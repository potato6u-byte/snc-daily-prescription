# -*- coding: utf-8 -*-
from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

import data_store as ds
import excel_io as xio
import prescription as rx

st.set_page_config(page_title="SNC 데일리 온도처방", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
    :root {
        --fp-900:#4c1d95; --fp-700:#6d28d9; --fp-600:#7c3aed; --fp-500:#8b5cf6;
        --fp-300:#c4b5fd; --fp-200:#ddd6fe; --fp-100:#ede9fe; --fp-50:#f5f3ff;
        --ok:#059669; --warn:#d97706; --bad:#dc2626;
    }
    .stApp { background:#fbfaff; }
    h1,h2,h3 { color:var(--fp-900) !important; letter-spacing:-0.3px; }
    .stButton button { font-size:1.05rem !important; font-weight:700 !important; border-radius:10px !important; }
    .stButton button[kind="primary"] {
        background:linear-gradient(90deg,var(--fp-700),var(--fp-500)) !important;
        border:none !important; color:#fff !important;
        box-shadow:0 3px 10px rgba(124,58,237,.35) !important;
    }
    .stDownloadButton button {
        background:var(--fp-100) !important; color:var(--fp-900) !important;
        border:1.5px solid var(--fp-500) !important; border-radius:10px !important; font-weight:700 !important;
    }
    div[data-testid="stInfo"] { background:var(--fp-100) !important; border-left:5px solid var(--fp-600) !important; border-radius:10px !important; }
    hr { border-color:var(--fp-200) !important; }

    .rx-head {
        background:linear-gradient(135deg,var(--fp-700),var(--fp-500));
        border-radius:16px; padding:16px 20px; color:#fff; margin-bottom:14px;
        box-shadow:0 6px 20px rgba(109,40,217,.30);
    }
    .rx-head .t { font-size:1.35rem; font-weight:800; }
    .rx-head .s { font-size:.85rem; opacity:.92; margin-top:2px; }
    .rx-head .pill {
        display:inline-block; background:rgba(255,255,255,.22); border-radius:999px;
        padding:3px 12px; font-size:.8rem; font-weight:700; margin-right:6px; margin-top:8px;
    }
    .rx-grid { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:10px; }
    .rx-card {
        flex:1 1 190px; background:#fff; border:1px solid var(--fp-200); border-radius:14px;
        padding:14px 16px; box-shadow:0 2px 10px rgba(109,40,217,.08);
    }
    .rx-card.main { border:2px solid var(--fp-600); background:linear-gradient(180deg,#fff,var(--fp-50)); }
    .rx-card .k { font-size:.8rem; font-weight:700; color:var(--fp-600); }
    .rx-card .v { font-size:1.9rem; font-weight:800; color:var(--fp-900); line-height:1.15; }
    .rx-card .v small { font-size:.95rem; font-weight:700; color:var(--fp-700); }
    .rx-card .d { font-size:.78rem; color:#64748b; margin-top:4px; }
    .rx-basis { font-size:.82rem; color:#475569; }

    .dev-row { display:flex; flex-wrap:wrap; gap:10px; }
    .dev {
        flex:1 1 150px; border-radius:12px; padding:10px 12px; background:#fff;
        border:1px solid var(--fp-200); border-left-width:5px;
    }
    .dev.ok { border-left-color:var(--ok); }
    .dev.warn { border-left-color:var(--warn); }
    .dev.bad { border-left-color:var(--bad); }
    .dev .k { font-size:.78rem; font-weight:700; color:#475569; }
    .dev .v { font-size:1.25rem; font-weight:800; color:#0f172a; }
    .dev .d { font-size:.74rem; color:#64748b; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

GJANG_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=35.2447&longitude=129.2226"
    "&current=temperature_2m&hourly=temperature_2m"
    "&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul&forecast_days=2"
)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_gijang_weather():
    try:
        res = requests.get(GJANG_URL, timeout=5)
        res.raise_for_status()
        d = res.json()
        cur = float(d["current"]["temperature_2m"])
        tmin = float(d["daily"]["temperature_2m_min"][0])
        tmax = float(d["daily"]["temperature_2m_max"][0])
        nmin = float(d["daily"]["temperature_2m_min"][1]) if len(d["daily"]["temperature_2m_min"]) > 1 else tmin
        hours = d.get("hourly", {})
        dawn = tmin
        if hours.get("time"):
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            idxs = [i for i, t in enumerate(hours["time"]) if t.startswith(tomorrow) and int(t[11:13]) in range(3, 7)]
            vals = [float(hours["temperature_2m"][i]) for i in idxs] if idxs else []
            if vals:
                dawn = min(vals)
        return {"ok": True, "cur": cur, "min": tmin, "max": tmax, "tomorrow_min": nmin, "tomorrow_dawn": dawn}
    except Exception as e:
        return {"ok": False, "error": str(e)[:60], "cur": 15.0, "min": 10.0, "max": 20.0, "tomorrow_min": 10.0, "tomorrow_dawn": 7.0}


def fmt(v, unit="", digits=1):
    if v is None:
        return "-"
    try:
        return f"{float(v):.{digits}f}{unit}"
    except (TypeError, ValueError):
        return str(v)


def badge_class(delta, warn=0.5, bad=1.2):
    a = abs(delta)
    if a < warn:
        return "ok"
    if a < bad:
        return "warn"
    return "bad"


ds.init_db()
w = fetch_gijang_weather()

if "results" not in st.session_state:
    st.session_state.results = []
if "manual_rows" not in st.session_state:
    st.session_state.manual_rows = []
if "time_bands" not in st.session_state:
    st.session_state.time_bands = [dict(b) for b in rx.DEFAULT_TIME_BANDS]
if "rx" not in st.session_state:
    st.session_state.rx = None

with st.sidebar:
    st.markdown("### 연동 상태")
    if w["ok"]:
        st.success(f"기장군 기상 정상 ({w['cur']:.1f}℃)")
    else:
        st.warning(f"기상 지연 ({w['error']})")
    st.caption(
        f"현재 {w['cur']:.1f}℃ · 오늘 {w['min']:.1f}~{w['max']:.1f}℃ · "
        f"내일 최저 {w['tomorrow_min']:.1f}℃"
    )
    if st.button("기상 새로고침", width="stretch"):
        fetch_gijang_weather.clear()
        st.rerun()

    st.divider()
    st.markdown("### 착수 시간대 보정")
    st.caption("시간대별 보정 Δ℃. 자정을 넘는 구간도 지원합니다.")
    edited_bands = st.data_editor(
        pd.DataFrame(st.session_state.time_bands),
        num_rows="dynamic", width="stretch", key="band_editor",
        column_config={
            "시작": st.column_config.TextColumn("시작", required=True),
            "종료": st.column_config.TextColumn("종료", required=True),
            "보정dC": st.column_config.NumberColumn("보정 Δ℃", min_value=-1.0, max_value=1.0, step=0.1, format="%.1f"),
            "메모": st.column_config.TextColumn("메모"),
        },
    )
    if st.button("보정값 저장", width="stretch"):
        st.session_state.time_bands = edited_bands.to_dict("records")
        st.success("저장되었습니다.")

    st.divider()
    counts = ds.count_rows()
    st.markdown("### 데이터")
    st.caption(f"처방 {counts['prescriptions']}건 · 실적 {counts['batch_results']}건")

st.markdown(
    "<h1 style='margin-bottom:2px;'>신앙촌 발효유 · 데일리 온도처방</h1>"
    "<div style='color:#6d28d9;font-weight:700;margin-bottom:6px;'>전일 공정결과 확인 → 오늘 온도처방 자동 산출</div>"
    f"<div style='font-size:.82rem;color:#64748b;'>처방모델 {rx.MODEL_VERSION} · 근거: 부산 신앙촌 허브 데이터 관리 컨설팅 최종보고서(278배치) 및 FermaAX 작업</div>",
    unsafe_allow_html=True,
)
st.divider()

tab_review, tab_rx, tab_hist = st.tabs(["① 전날 공정결과 확인", "② 오늘의 온도처방", "③ 이력 · 통계"])

with tab_review:
    st.subheader("전날 공정결과 입력")
    st.caption("엑셀 업로드 또는 표에 직접 입력하세요. 필수 항목: 새벽 실내온도 · 살균냉각 실측 · 이송후 탱크온도 · 종결시간")

    c1, c2 = st.columns([1, 1])
    with c1:
        up = st.file_uploader("실적 엑셀(.xlsx / .csv)", type=["xlsx", "xls", "csv"])
        if up is not None:
            try:
                if st.button("업로드 파일 읽기 및 저장", type="primary", width="stretch"):
                    data = up
                    rows, errs = xio.parse_results_excel(data)
                    if rows:
                        n = ds.save_batch_results(rows, source="excel")
                        st.success(f"{n}건 저장 완료 (중복 일자·탱크는 마지막 값 유지)")
                    for e in errs[:5]:
                        st.warning(e)
                    if not rows:
                        st.error("읽을 수 있는 행이 없습니다. 양식의 열 이름을 확인하세요.")
            except Exception as e:
                st.error(f"파일을 읽지 못했습니다: {e}")
        st.download_button(
            "실적 입력 양식(.xlsx) 내려받기",
            data=xio.build_template_bytes(),
            file_name="SNC_실적입력_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with c2:
        st.info(
            "**이송 열손실 회귀식**\n\n"
            "온도하락폭(℃) = 2.44 − 0.078 × 새벽실내온도\n\n"
            f"n={rx.TRANSPORT['n']} 배치 · r²={rx.TRANSPORT['r2']} · 95% 예측범위 ±{rx.TRANSPORT['z95'] * rx.TRANSPORT['se']:.2f}℃\n\n"
            "실측 이송후 온도와 회귀 예측의 차이가 다음 처방의 잔차 보정으로 이어집니다."
        )

    st.markdown("#### 수동 입력")
    base = pd.DataFrame(
        [
            {
                "일자": (date.today() - timedelta(days=1)).isoformat(),
                "투입탱크": "301호 탱크",
                "배치량(L)": 15000,
                "새벽 실내온도(℃)": w["tomorrow_dawn"] if w["ok"] else 15.0,
                "외기온도(℃)": w["cur"],
                "살균냉각 설정(℃)": 38.5,
                "살균냉각 실측(℃)": 38.5,
                "이송후 탱크온도(℃)": 37.2,
                "종결시간(분)": 380,
                "최종 산도": 0.965,
                "최종 pH": 4.70,
                "점도(cP)": 3200,
                "비고": "",
            }
        ]
    )
    edited = st.data_editor(base, num_rows="dynamic", width="stretch", key="manual_editor")
    if st.button("입력값 저장", type="primary", width="stretch"):
        recs = []
        for _, r in edited.iterrows():
            rec = {}
            for col, val in r.items():
                key = xio.HEADER_MAP.get(xio.norm_header(col))
                if not key or pd.isna(val):
                    continue
                rec[key] = float(val) if key in xio.NUMERIC_KEYS else (pd.to_datetime(val).strftime("%Y-%m-%d") if key == "batch_date" else str(val))
            if rec.get("batch_date"):
                recs.append(rec)
        if recs:
            st.success(f"{ds.save_batch_results(recs, source='manual')}건 저장 완료")
        else:
            st.warning("저장할 행이 없습니다.")

    st.divider()
    st.subheader("저장된 실적 (최근 60일)")
    hist = ds.list_batch_results(limit=200)
    if hist:
        dfh = pd.DataFrame(hist)
        cols = [
            "batch_date", "tanks", "volume_l", "indoor_dawn_c", "pasteurize_cooling_actual_c",
            "inlet_tank_c", "predicted_drop_c", "total_minutes", "final_acidity", "final_ph",
            "viscosity_cp", "source",
        ]
        show = dfh[[c for c in cols if c in dfh.columns]]
        st.dataframe(show, width="stretch", hide_index=True)

        if st.button("전체 실적 삭제"):
            ds.clear_batch_results()
            st.rerun()
    else:
        st.info("아직 저장된 실적이 없습니다. 위에서 업로드하거나 직접 입력하세요.")

with tab_rx:
    st.subheader("오늘의 온도처방")

    rev = rx.review(hist or [])
    auto_adj = float(rev.get("drop_correction_c", 0.0)) if rev.get("count") else 0.0
    auto_min = float(rev.get("minute_correction", 0.0)) if rev.get("count") else 0.0

    if rev.get("count"):
        devs = [
            ("전일 이송온도 잔차", rev["latest_drop_residual_c"], "℃", "실측 이송후온도 − 처방 예측"),
            ("최근 EWMA 보정", auto_adj, "℃", "이송 열손실 잔차 보정 (= 살균냉각 상향량)"),
            ("전일 종결시간 잔차", rev["latest_minute_residual"], "분", "실측 − 처방 예측"),
        ]
        cards = "".join(
            f"<div class='dev {badge_class(d, 0.5, 1.2)}'><div class='k'>{html.escape(k)}</div>"
            f"<div class='v'>{d:+.2f}{u}</div><div class='d'>{html.escape(note)}</div></div>"
            for k, d, u, note in devs
        )
        st.markdown(f"<div class='dev-row'>{cards}</div>", unsafe_allow_html=True)
        st.caption(f"최근 {rev['count']}일 실적 기준 · {rev['message']}")
    else:
        st.info("전일 실적이 없어 잔차 보정 없이 기준 처방만 계산합니다.")

    st.divider()
    f1, f2, f3 = st.columns(3)
    with f1:
        dawn_default = float(hist[0].get("indoor_dawn_c") or 15.0) if hist else (w["tomorrow_dawn"] if w["ok"] else 15.0)
        indoor = st.number_input("오늘 새벽 실내온도 (℃)", 5.0, 35.0, float(round(dawn_default, 1)), 0.1, format="%.1f")
        if w["ok"]:
            st.caption(f"기상 내일 새벽 외기 {w['tomorrow_dawn']:.1f}℃ · 실내 추정 {w['tomorrow_dawn'] + 4.0:.1f}℃ (참고)")
    with f2:
        outdoor = st.number_input("오늘 외기온도 (℃)", -15.0, 40.0, float(w["cur"] if w["ok"] else 15.0), 0.1, format="%.1f")
    with f3:
        start_t = st.time_input("오늘 착수 시각", value=datetime.now().replace(microsecond=0).time())

    g1, g2, g3 = st.columns(3)
    with g1:
        tanks = st.multiselect("투입 발효탱크", list(rx.TANK_SPECS.keys()), default=["301호 탱크"])
    with g2:
        volume = st.number_input("배치량 (L)", 1000, 20000, 15000, 500)
    with g3:
        raw = st.selectbox("원료", list(rx.RAW_SPECS.keys()), index=0)

    use_auto = st.checkbox("전일 실적 잔차 자동 반영", value=True)
    adj = st.number_input(
        "이송 잔차 보정 (℃, + = 살균냉각 상향)",
        -2.0, 2.0, float(round(auto_adj, 2)) if use_auto else 0.0, 0.05, format="%.2f",
        disabled=use_auto,
    )
    min_adj = st.number_input(
        "종결시간 잔차 보정 (분)",
        -60.0, 60.0, float(round(auto_min, 1)) if use_auto else 0.0, 1.0,
        disabled=use_auto,
    )

    hour_float = start_t.hour + start_t.minute / 60.0
    band = rx.active_time_band(hour_float, st.session_state.time_bands)
    if band:
        st.caption(f"착수 시각 활성 시간밴드: {band['시작']}~{band['종료']} (Δ{band['보정dC']:+.1f}℃)")

    if st.button("오늘 온도처방 계산", type="primary", width="stretch"):
        if not tanks:
            st.error("투입 탱크를 1개 이상 선택하세요.")
        else:
            st.session_state.rx = rx.prescribe(
                indoor_dawn_c=indoor,
                outdoor_c=outdoor,
                tanks=tanks,
                volume_l=volume,
                raw_material=raw,
                cooling_residual_c=float(adj),
                minutes_residual=float(min_adj),
                hour_float=hour_float,
                time_bands=st.session_state.time_bands,
                rx_date=date.today().isoformat(),
            )

    rx_ = st.session_state.rx
    if rx_ is not None:
        st.divider()
        st.markdown(
            f"<div class='rx-head'><div class='t'>오늘의 온도처방 · {html.escape(rx_.rx_date)}</div>"
            f"<div class='s'>새벽 실내 {rx_.indoor_dawn_c:.1f}℃ · 외기 {rx_.outdoor_c:.1f}℃ · "
            f"{', '.join(rx_.tanks)} · {rx_.volume_l:,.0f}L</div>"
            f"<div class='pill'>신뢰도 {html.escape(rx_.confidence)}</div>"
            f"<div class='pill'>모델 {rx_.model_version}</div></div>",
            unsafe_allow_html=True,
        )

        cards = [
            ("살균냉각 설정 (P101TC02.SP)", f"{rx_.cooling_set_c:.1f}", "℃",
             f"기준 {rx.GOLDEN['pasteurize_cooling_set_c']:.1f} + 이송하락 {rx_.transport_drop_c:.2f} + 잔차 {rx_.cooling_residual_c:+.2f}", True),
            ("핫워터 설정 (재킷)", f"{rx_.hotwater_set_c:.1f}", "℃",
             "골든 38.4 + 실내온도 보정 (현장 경험식)", False),
            ("목표 이송후 유입온도", f"{rx_.inlet_target_c:.1f}", "℃",
             f"예상 하락폭 {rx_.transport_drop_c:.2f}℃ (95% {rx_.transport_drop_lo_c:.2f}~{rx_.transport_drop_hi_c:.2f})", False),
            ("예상 종결시간", f"{rx_.predicted_minutes:.0f}", "분",
             f"골든 380 · 시간보정 {rx_.minutes_residual:+.1f}분", False),
            ("예상 산도차 (5H−초기)", f"{rx_.predicted_acidity_delta:.3f}", "",
             f"기준선 {rx.BASELINE['acidity_delta']:.3f} 대비", False),
            ("예상 열손실량", f"{rx_.heat_loss_kcal / 1000:,.1f}", "×10³ kcal",
             f"{rx_.volume_l:,.0f}L × 하락폭", False),
            ("예상 최종 pH", f"{rx_.predicted_final_ph:.2f}", "", "골든 4.70 기준 추정", False),
            ("예상 점도", f"{rx_.predicted_viscosity_cp:,.0f}", "cP", "골든 3,200 기준 추정", False),
            ("급속칠링 목표", f"{rx_.chilling_target_c:.1f}", "℃", "원료별 목표", False),
            ("골든 최종산도", f"{rx.GOLDEN['final_acidity']:.3f}", "", "사계절 유지 목표", False),
        ]
        grid = "".join(
            f"<div class='rx-card{' main' if main else ''}'><div class='k'>{html.escape(k)}</div>"
            f"<div class='v'>{v} <small>{u}</small></div><div class='d'>{html.escape(d)}</div></div>"
            for k, v, u, d, main in cards
        )
        st.markdown(f"<div class='rx-grid'>{grid}</div>", unsafe_allow_html=True)

        for n in rx_.notes:
            st.warning(n)

        with st.expander("처방 근거 · 산출식", expanded=False):
            st.markdown(
                f"""
| 항목 | 값 | 근거 |
|---|---|---|
| 이송 온도하락 | `{rx.TRANSPORT['intercept']} − {abs(rx.TRANSPORT['slope_per_c'])} × 새벽실내` | {rx.EVIDENCE['transport']} |
| 골든 배치 | 핫워터 {rx.GOLDEN['hotwater_set_c']}℃ / 종결 {rx.GOLDEN['total_minutes']:.0f}분 / 산도 {rx.GOLDEN['final_acidity']} | {rx.EVIDENCE['golden']} |
| 기준선 | 핫워터·살균냉각 {rx.BASELINE['pasteurize_cooling_set_c']}℃, 외기 {rx.BASELINE['outdoor_temp_c']}℃ | {rx.EVIDENCE['baseline']} |
| 겨울 이탈 | 살균냉각 +{rx.WINTER_DEVIATION['cooling_set_shift_c'][0]}~+{rx.WINTER_DEVIATION['cooling_set_shift_c'][1]}℃, 산도차 {rx.WINTER_DEVIATION['acidity_delta_pct']}%, 종결 {rx.WINTER_DEVIATION['minutes']}분 | {rx.EVIDENCE['winter']} |
| 핫워터 보정 | 실내 {rx_.indoor_dawn_c:.1f}℃ → {rx_.hotwater_set_c:.1f}℃ | {rx.EVIDENCE['hotwater']} |
| 시간대 보정 | {rx_.time_offset_c:+.1f}℃ (살균냉각 전량 · 핫워터 70%) | {rx.EVIDENCE['time_band']} |
| 열손실 환산 | {rx_.heat_loss_kcal:,.0f} kcal | {rx.EVIDENCE['heat_loss']} |
| 상관계수 | 실내온도↔냉각 {rx.CORRELATIONS['실내온도↔살균냉각']}, 냉각↔종결 {rx.CORRELATIONS['살균냉각↔종결시간']} | 278배치 상관분석 |
"""
            )

        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("이 처방 저장", type="primary", width="stretch"):
                ds.save_prescription(rx_.as_row())
                st.success(f"{rx_.rx_date} 처방 저장 완료")
        with cc2:
            st.download_button(
                "처방서(.xlsx) 내려받기",
                data=xio.results_to_bytes([rx_.as_row()], ds.list_prescriptions(50)),
                file_name=f"SNC_처방_{rx_.rx_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

with tab_hist:
    st.subheader("처방 이력")
    rxs = ds.list_prescriptions(limit=200)
    if rxs:
        dfr = pd.DataFrame(rxs)
        st.dataframe(dfr, width="stretch", hide_index=True)
        st.download_button(
            "처방·실적 통합(.xlsx) 내려받기",
            data=xio.results_to_bytes(ds.list_batch_results(500), rxs),
            file_name=f"SNC_처방실적_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.info("저장된 처방이 없습니다.")

    st.divider()
    st.subheader("처방 정확도 추이")
    rr = ds.list_batch_results(200)
    pairs = []
    for r in rr:
        if r.get("predicted_drop_c") and r.get("pasteurize_cooling_actual_c") and r.get("inlet_tank_c"):
            pred = float(r["predicted_drop_c"])
            act = float(r["pasteurize_cooling_actual_c"]) - float(r["inlet_tank_c"])
            pairs.append({"일자": r["batch_date"], "예측 하락폭": pred, "실측 하락폭": round(act, 2), "오차": round(act - pred, 2)})
    if pairs:
        dfp = pd.DataFrame(pairs).sort_values("일자")
        st.line_chart(dfp.set_index("일자")[["예측 하락폭", "실측 하락폭"]])
        st.dataframe(dfp.sort_values("일자", ascending=False), width="stretch", hide_index=True)
        err = dfp["오차"]
        m1, m2, m3 = st.columns(3)
        m1.metric("평균 오차 (ME)", f"{err.mean():+.2f}℃")
        m2.metric("평균 절대오차 (MAE)", f"{err.abs().mean():.2f}℃")
        m3.metric("표준편차 (SD)", f"{err.std(ddof=0):.2f}℃")
    else:
        st.info("실적에 예측값이 함께 기록되면 정확도 추이가 표시됩니다.")

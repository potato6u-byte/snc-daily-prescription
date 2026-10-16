# -*- coding: utf-8 -*-
from __future__ import annotations

import html
from datetime import date, datetime

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
    .rx-head .pill { display:inline-block; background:rgba(255,255,255,.22); border-radius:999px;
        padding:3px 12px; font-size:.8rem; font-weight:700; margin-right:6px; margin-top:8px; }
    .rx-grid { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:10px; }
    .rx-card { flex:1 1 190px; background:#fff; border:1px solid var(--fp-200); border-radius:14px;
        padding:14px 16px; box-shadow:0 2px 10px rgba(109,40,217,.08); }
    .rx-card.main { border:2px solid var(--fp-600); background:linear-gradient(180deg,#fff,var(--fp-50)); }
    .rx-card .k { font-size:.8rem; font-weight:700; color:var(--fp-600); }
    .rx-card .v { font-size:1.9rem; font-weight:800; color:var(--fp-900); line-height:1.15; }
    .rx-card .v small { font-size:.95rem; font-weight:700; color:var(--fp-700); }
    .rx-card .d { font-size:.78rem; color:#64748b; margin-top:4px; }
    .dev-row { display:flex; flex-wrap:wrap; gap:10px; }
    .dev { flex:1 1 150px; border-radius:12px; padding:10px 12px; background:#fff;
        border:1px solid var(--fp-200); border-left-width:5px; }
    .dev.ok { border-left-color:var(--ok); } .dev.warn { border-left-color:var(--warn); } .dev.bad { border-left-color:var(--bad); }
    .dev .k { font-size:.78rem; font-weight:700; color:#475569; }
    .dev .v { font-size:1.25rem; font-weight:800; color:#0f172a; }
    .dev .d { font-size:.74rem; color:#64748b; }
    .cmp { display:flex; flex-wrap:wrap; gap:12px; }
    .cmp > div { flex:1 1 200px; border-radius:12px; padding:12px 14px; }
    .cmp .now { background:#fef2f2; border:1px solid #fecaca; }
    .cmp .rx { background:#f0fdf4; border:1px solid #bbf7d0; }
    .cmp .k { font-size:.78rem; font-weight:800; }
    .cmp .now .k { color:#b91c1c; } .cmp .rx .k { color:#15803d; }
    .cmp .v { font-size:1.05rem; font-weight:700; color:#0f172a; margin-top:4px; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

GJANG_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=35.2447&longitude=129.2226"
    "&current=temperature_2m&daily=temperature_2m_min,temperature_2m_max&timezone=Asia%2FSeoul&forecast_days=2"
)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_weather():
    try:
        res = requests.get(GJANG_URL, timeout=5)
        res.raise_for_status()
        d = res.json()
        return {
            "ok": True,
            "cur": float(d["current"]["temperature_2m"]),
            "min": float(d["daily"]["temperature_2m_min"][0]),
            "max": float(d["daily"]["temperature_2m_max"][0]),
            "tomorrow_min": float(d["daily"]["temperature_2m_min"][1]),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:60], "cur": 20.0, "min": 15.0, "max": 25.0, "tomorrow_min": 15.0}


def badge(delta, warn=0.5, bad=1.2):
    a = abs(delta)
    return "ok" if a < warn else ("warn" if a < bad else "bad")


ds.init_db()
w = fetch_weather()

if "rx" not in st.session_state:
    st.session_state.rx = None
if "verify" not in st.session_state:
    st.session_state.verify = None

with st.sidebar:
    st.markdown("### 연동 상태")
    if w["ok"]:
        st.success(f"기장군 기상 정상 ({w['cur']:.1f}℃)")
    else:
        st.warning(f"기상 지연 ({w['error']})")
    st.caption(f"현재 {w['cur']:.1f}℃ · 오늘 {w['min']:.1f}~{w['max']:.1f}℃ · 내일 최저 {w['tomorrow_min']:.1f}℃")
    if st.button("기상 새로고침", width="stretch"):
        fetch_weather.clear()
        st.rerun()

    st.divider()
    st.markdown("### 처방모델")
    st.caption(
        f"{rx.MODEL_VERSION} · {rx.MODEL_SOURCE}\n\n"
        f"기준선 살균냉각 {rx.BASELINE['cooling_set_c']}℃ / 핫워터 {rx.BASELINE['hotwater_set_c']}℃\n\n"
        f"종결분 380분 · 산도차 0.116 사계절 유지"
    )
    counts = ds.count_rows()
    st.caption(f"처방 {counts['prescriptions']}건 · 실적 {counts['batch_results']}건")

st.markdown(
    "<h1 style='margin-bottom:2px;'>신앙촌 발효유 · 데일리 온도처방</h1>"
    "<div style='color:#6d28d9;font-weight:700;margin-bottom:6px;'>전일 공정결과 확인 → 오늘 온도처방 자동 산출</div>"
    f"<div style='font-size:.82rem;color:#64748b;'>처방모델 {rx.MODEL_VERSION} · 근거: 로우데이터(통합데이터.xlsx) 278배치 실측 재적합 + 부산 신앙촌 허브 컨설팅 보고서</div>",
    unsafe_allow_html=True,
)
st.divider()

tab_review, tab_rx, tab_hist = st.tabs(["① 전날 공정결과 확인", "② 오늘의 온도처방", "③ 이력 · 모델검증"])

with tab_review:
    st.subheader("전날 공정결과 입력")
    st.caption("현장에서 쓰던 양식 그대로 올리면 됩니다. 열 이름·열 순서가 같으면 자동 인식합니다.")

    c1, c2 = st.columns([1.15, 1])
    with c1:
        up = st.file_uploader("실적 엑셀 (.xlsx / .xls / .csv)", type=["xlsx", "xls", "csv"])
        if up is not None and st.button("업로드 파일 읽기 및 저장", type="primary", width="stretch"):
            try:
                rows, errs = xio.parse_results_excel(up)
                if rows:
                    st.success(f"{len(rows)}건 저장 완료 (동일 날짜·탱크는 마지막 값 유지)")
                for e in errs[:6]:
                    st.warning(e)
            except Exception as e:
                st.error(f"파일을 읽지 못했습니다: {e}")
        st.download_button(
            "빈 입력 양식(.xlsx) 내려받기",
            data=xio.build_template_bytes(with_samples=False),
            file_name="SANC_A300_온도_입력양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with c2:
        st.info(
            "**모델 근거 (원본 278배치 실측)**\n\n"
            f"이송 하락폭 = {rx.TRANSPORT['intercept']} − {abs(rx.TRANSPORT['slope_per_c'])} × 새벽 실내온도 "
            f"(n={rx.TRANSPORT['n']}, r²={rx.TRANSPORT['r2']})\n\n"
            f"종결분 = {rx.COOLING_MODEL['total_minutes']['a']} − {abs(rx.COOLING_MODEL['total_minutes']['b'])} × 살균냉각온도 "
            f"(r²={rx.COOLING_MODEL['total_minutes']['r2']})\n\n"
            "기준선(38.5/38.5, 43건) 실측: 산도차 0.1162 · 종결분 382.9분"
        )

    st.markdown("#### 수동 입력 (핵심 항목)")
    base = pd.DataFrame([{
        "날짜": (date.today()).isoformat(),
        "300 탱크": "301",
        "제품 이송후 탱크 온도": 38.9,
        "새벽A300 실내 온도": round(float(w["tomorrow_min"]) + 15.0, 1) if w["ok"] else 33.0,
        "접종A300 실내 온도": round(float(w["tomorrow_min"]) + 17.0, 1) if w["ok"] else 35.0,
        "접종 실외 온도": w["cur"] if w["ok"] else 20.0,
        "살균냉각온도": 38.5,
        "핫워터설정온도": 38.5,
        "종결분": 380,
        "종결(산도)": 0.970,
        "산도차": 0.116,
    }])
    edited = st.data_editor(base, num_rows="dynamic", width="stretch", key="manual_editor")
    if st.button("입력값 저장", type="primary", width="stretch"):
        manual_map = {
            "날짜": "batch_date", "300 탱크": "tank", "제품 이송후 탱크 온도": "inlet_tank_c",
            "새벽A300 실내 온도": "indoor_dawn_c", "접종A300 실내 온도": "indoor_inoc_c",
            "접종 실외 온도": "outdoor_inoc_c", "살균냉각온도": "cooling_set_c",
            "핫워터설정온도": "hotwater_set_c", "종결분": "total_minutes",
            "종결(산도)": "final_acidity", "산도차": "acidity_delta",
        }
        recs = []
        for _, r in edited.iterrows():
            rec = {}
            for col, val in r.items():
                key = manual_map.get(str(col).strip())
                if not key or val is None or pd.isna(val) or str(val).strip() == "":
                    continue
                if key == "batch_date":
                    rec[key] = pd.to_datetime(val).strftime("%Y-%m-%d")
                elif key == "tank":
                    rec[key] = str(val).strip().replace("호", "")
                else:
                    try:
                        rec[key] = float(val)
                    except (TypeError, ValueError):
                        st.warning(f"'{col}' 값 '{val}'을(를) 숫자로 읽지 못했습니다.")
            if rec.get("batch_date"):
                recs.append(rec)
        st.success(f"{ds.save_batch_results(recs, source='manual')}건 저장 완료") if recs else st.warning("저장할 행이 없습니다.")

    st.divider()
    st.subheader("저장된 실적")
    hist = ds.list_batch_results(limit=400)
    if hist:
        dfh = pd.DataFrame(hist)
        cols = ["batch_date", "tank", "indoor_dawn_c", "cooling_set_c", "hotwater_set_c",
                "inlet_tank_c", "total_minutes", "acidity_delta", "final_acidity", "ph_end",
                "predicted_minutes", "predicted_acidity_delta", "source"]
        st.dataframe(dfh[[c for c in cols if c in dfh.columns]], width="stretch", hide_index=True)
        if st.button("전체 실적 삭제"):
            ds.clear_batch_results()
            st.rerun()
    else:
        st.info("저장된 실적이 없습니다. 위에서 업로드하거나 직접 입력하세요.")

with tab_rx:
    st.subheader("오늘의 온도처방")
    hist = ds.list_batch_results(limit=400)

    rev = rx.review(hist or [])
    auto_corr = float(rev.get("cooling_correction_c", 0.0)) if rev.get("count") else 0.0

    if rev.get("count"):
        cards = "".join(
            f"<div class='dev {badge(d, 0.5, 1.2)}'><div class='k'>{html.escape(k)}</div>"
            f"<div class='v'>{d:+.2f}{u}</div><div class='d'>{html.escape(note)}</div></div>"
            for k, d, u, note in [
                ("전일 이송온도 잔차", rev["latest_drop_residual_c"], "℃", "실측 이송하락 − 회귀 예측"),
                ("최근 EWMA 이송잔차", rev["ewma_drop_residual_c"], "℃", "센서·배관 추세 (감시용)"),
                ("전일 종결시간 잔차", rev["latest_minute_residual"], "분", "실측 − 처방 예측"),
                ("핫워터 설정", float(rev["latest"].get("hotwater_set_c") or 0), "℃", "실측 최근값"),
            ]
        )
        st.markdown(f"<div class='dev-row'>{cards}</div>", unsafe_allow_html=True)
        st.caption(f"최근 {rev['count']}일 실적 · {rev['message']} · 종결잔차 기반 냉각보정 {auto_corr:+.2f}℃")
    else:
        st.info("전일 실적이 없어 잔차 보정 없이 기준선 처방만 계산합니다.")

    st.divider()
    f1, f2, f3 = st.columns(3)
    with f1:
        default_indoor = float(hist[0].get("indoor_dawn_c")) if hist and hist[0].get("indoor_dawn_c") else 33.0
        indoor = st.number_input("오늘 새벽 실내온도 (℃)", 5.0, 45.0, round(default_indoor, 1), 0.1, format="%.1f")
        if w["ok"]:
            st.caption(f"기상 내일 최저 외기 {w['tomorrow_min']:.1f}℃ (참고)")
    with f2:
        inoc_default = float(hist[0].get("indoor_inoc_c")) if hist and hist[0].get("indoor_inoc_c") else round(indoor + 3.0, 1)
        inoc = st.number_input("오늘 접종 실내온도 (℃)", 5.0, 45.0, round(inoc_default, 1), 0.1, format="%.1f")
    with f3:
        od_default = float(hist[0].get("outdoor_inoc_c")) if hist and hist[0].get("outdoor_inoc_c") else (w["cur"] if w["ok"] else 20.0)
        outdoor = st.number_input("오늘 실외온도 (℃)", -20.0, 45.0, round(od_default, 1), 0.1, format="%.1f")

    g1, g2, g3 = st.columns(3)
    with g1:
        tank = st.selectbox("투입 발효탱크", list(rx.TANK_SPECS.keys()), index=0)
    with g2:
        volume_t = st.number_input("배치량 (톤)", 1.0, 30.0, 16.5, 0.5, format="%.1f")
    with g3:
        mode = st.radio("처방 방식", list(rx.PRESCRIPTION_MODES.keys()),
                        format_func=lambda k: rx.PRESCRIPTION_MODES[k], index=0)

    use_auto = st.checkbox("전일 실적 잔차 자동 반영", value=True)
    corr = st.number_input("살균냉각 보정 (℃, + = 상향)", -2.0, 2.0,
                           float(round(auto_corr, 2)) if use_auto else 0.0, 0.05,
                           format="%.2f", disabled=use_auto)

    if st.button("오늘 온도처방 계산", type="primary", width="stretch"):
        st.session_state.rx = rx.prescribe(
            indoor_dawn_c=indoor, tank=tank, volume_t=volume_t, indoor_inoc_c=inoc,
            outdoor_c=outdoor, cooling_correction_c=float(corr), mode=mode,
            rx_date=date.today().isoformat(),
        )

    r = st.session_state.rx
    if r is not None:
        st.divider()
        st.markdown(
            f"<div class='rx-head'><div class='t'>오늘의 온도처방 · {html.escape(r.rx_date)}</div>"
            f"<div class='s'>{r.tank}호 탱크 · {r.volume_t}톤 · 새벽 실내 {r.indoor_dawn_c:.1f}℃ · "
            f"접종 실내 {r.indoor_inoc_c:.1f}℃ · 실외 {r.outdoor_c:.1f}℃</div>"
            f"<div class='pill'>신뢰도 {html.escape(r.confidence)}</div>"
            f"<div class='pill'>{html.escape(rx.PRESCRIPTION_MODES[r.mode].split(' —')[0])}</div></div>",
            unsafe_allow_html=True,
        )
        cards = [
            ("살균냉각 설정", f"{r.cooling_set_c:.1f}", "℃",
             f"기준선 {rx.BASELINE['cooling_set_c']}℃ + 잔차보정 {r.cooling_correction_c:+.2f}", True),
            ("핫워터 설정", f"{r.hotwater_set_c:.1f}", "℃", "실내온도 회귀식", False),
            ("예상 이송후 유입온도", f"{r.predicted_inlet_c:.2f}", "℃",
             f"이송 하락 {r.transport_drop_c:+.2f}℃ (95% {r.transport_drop_lo_c:.2f}~{r.transport_drop_hi_c:.2f})", False),
            ("예상 종결분", f"{r.predicted_minutes:.0f}", "분", "목표 380분 (기준선 382.9)", False),
            ("예상 산도차", f"{r.predicted_acidity_delta:.4f}", "", "기준선 0.1162", False),
            ("예상 종결산도", f"{r.predicted_final_acidity:.4f}", "", "골든군 0.9702", False),
            ("예상 5H 산도", f"{r.predicted_acid_5h:.3f}", "", "1차샘플(5H)", False),
            ("예상 종결 pH", f"{r.predicted_final_ph:.2f}", "", "골든군 4.70", False),
            ("예상 이송 열손실", f"{r.heat_loss_kcal / 1000:,.1f}", "×10³ kcal", f"{r.volume_t}톤 × 하락폭", False),
            ("예상 접종 실외온도", f"{rx.predict_outdoor_from_indoor(r.indoor_dawn_c):.1f}", "℃", "실내→실외 참고 회귀", False),
        ]
        grid = "".join(
            f"<div class='rx-card{' main' if m else ''}'><div class='k'>{html.escape(k)}</div>"
            f"<div class='v'>{v} <small>{u}</small></div><div class='d'>{html.escape(d)}</div></div>"
            for k, v, u, d, m in cards
        )
        st.markdown(f"<div class='rx-grid'>{grid}</div>", unsafe_allow_html=True)

        st.markdown("##### 현행 겨울 관행과 비교")
        st.markdown(
            "<div class='cmp'>"
            f"<div class='now'><div class='k'>현행 관행 (겨울 상향)</div>"
            f"<div class='v'>살균냉각 {rx.WINTER_PRACTICE['cooling_set_c']}℃ → 종결분 {r.practice_minutes:.0f}분 / 산도차 {r.practice_acidity_delta:.4f}</div></div>"
            f"<div class='rx'><div class='k'>처방</div>"
            f"<div class='v'>살균냉각 {r.cooling_set_c}℃ → 종결분 {r.predicted_minutes:.0f}분 / 산도차 {r.predicted_acidity_delta:.4f}</div></div>"
            f"<div class='rx'><div class='k'>기대 개선</div>"
            f"<div class='v'>종결분 {r.predicted_minutes - r.practice_minutes:+.0f}분 / 산도차 {r.predicted_acidity_delta - r.practice_acidity_delta:+.4f}</div></div>"
            "</div>", unsafe_allow_html=True,
        )
        for n in r.notes:
            st.warning(n)

        with st.expander("처방 근거 · 회귀식 (원본 278배치 재적합)", expanded=False):
            spec = [
                ("이송 하락폭", "살균냉각 − 이송후 ~ 새벽 실내온도",
                 rx.TRANSPORT["intercept"], rx.TRANSPORT["slope_per_c"],
                 rx.TRANSPORT["n"], rx.TRANSPORT["r2"], rx.TRANSPORT["se"]),
                ("종결분", "발효 종결 소요시간", rx.COOLING_MODEL["total_minutes"]["a"],
                 rx.COOLING_MODEL["total_minutes"]["b"], 278, rx.COOLING_MODEL["total_minutes"]["r2"],
                 rx.COOLING_MODEL["total_minutes"]["se"]),
                ("산도차", "1차샘플(5H) − 초기 산도", rx.COOLING_MODEL["acidity_delta"]["a"],
                 rx.COOLING_MODEL["acidity_delta"]["b"], 278, rx.COOLING_MODEL["acidity_delta"]["r2"],
                 rx.COOLING_MODEL["acidity_delta"]["se"]),
                ("종결산도", "완제품 적정산도", rx.COOLING_MODEL["final_acidity"]["a"],
                 rx.COOLING_MODEL["final_acidity"]["b"], 278, rx.COOLING_MODEL["final_acidity"]["r2"],
                 rx.COOLING_MODEL["final_acidity"]["se"]),
                ("5H 산도", "1차샘플(5H) 산도", rx.COOLING_MODEL["acid_5h"]["a"],
                 rx.COOLING_MODEL["acid_5h"]["b"], 278, rx.COOLING_MODEL["acid_5h"]["r2"],
                 rx.COOLING_MODEL["acid_5h"]["se"]),
                ("핫워터", "재킷 온수 설정값", rx.HOTWATER_MODEL["a"], rx.HOTWATER_MODEL["b"],
                 rx.HOTWATER_MODEL["n"], rx.HOTWATER_MODEL["r2"], rx.HOTWATER_MODEL["se"]),
            ]
            md = ["| 항목 | 회귀식 (y ~ x) | n | r² | se | 대상 |", "|---|---|---|---|---|---|"]
            for label, desc, a, b, n, r2, se in spec:
                md.append(f"| {label} | `y = {a} + ({b}) × x` | {n} | {r2} | {se} | {desc} |")
            st.markdown("\n".join(md))
            st.caption(rx.EVIDENCE["baseline"] + " · " + rx.EVIDENCE["tank303"])

        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("이 처방 저장", type="primary", width="stretch"):
                ds.save_prescription(r.as_row())
                st.success(f"{r.rx_date} 처방 저장 완료")
        with cc2:
            st.download_button(
                "처방서(.xlsx) 내려받기",
                data=xio.results_to_bytes([r.as_row()], ds.list_prescriptions(50)),
                file_name=f"SNC_처방_{r.rx_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

with tab_hist:
    st.subheader("처방 이력")
    rxs = ds.list_prescriptions(limit=200)
    if rxs:
        st.dataframe(pd.DataFrame(rxs), width="stretch", hide_index=True)
        st.download_button(
            "처방 + 실적 통합(.xlsx) 내려받기",
            data=xio.results_to_bytes(ds.list_batch_results(500), rxs),
            file_name=f"SNC_처방실적_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.info("저장된 처방이 없습니다.")

    st.divider()
    st.subheader("처방 정확도 추이")
    rr = ds.list_batch_results(400)
    pairs = []
    for x in rr:
        if x.get("predicted_minutes") and x.get("total_minutes"):
            pairs.append({"일자": x["batch_date"],
                          "종결분 오차": round(float(x["total_minutes"]) - float(x["predicted_minutes"]), 1)})
    if pairs:
        dfp = pd.DataFrame(pairs).sort_values("일자")
        st.line_chart(dfp.set_index("일자"))
        e = dfp["종결분 오차"]
        m1, m2, m3 = st.columns(3)
        m1.metric("평균 오차 (ME)", f"{e.mean():+.1f}분")
        m2.metric("평균 절대오차 (MAE)", f"{e.abs().mean():.1f}분")
        m3.metric("표본 수", f"{len(e)}건")
    else:
        st.info("처방과 실적이 같은 날짜로 쌓이면 종결시간 오차 추이가 표시됩니다.")

    st.divider()
    st.subheader("모델 검증 — 원본 로우데이터로 재적합")
    st.caption(
        "로우데이터 원본(통합데이터.xlsx 등)을 올리면 계수를 다시 계산해 내장 값과 대조합니다. "
        "내장 계수는 이 파일 278배치에서 산출된 값입니다."
    )
    up2 = st.file_uploader("로우데이터 (.xlsx)", type=["xlsx", "xls"], key="verify_file")
    if up2 is not None and st.button("재적합 실행", type="primary", width="stretch"):
        try:
            rows, errs = xio.parse_results_excel(up2)
            st.session_state.verify = rx.refit(rows)
            st.caption(f"파싱 {len(rows)}건 · 오류 {len(errs)}건")
            for e in errs[:5]:
                st.warning(e)
        except Exception as e:
            st.error(f"재적합 실패: {e}")

    v = st.session_state.verify
    if v:
        t = []
        for k, f in v["fitted"].items():
            b = v["builtin"].get(k)
            t.append({
                "관계": k,
                "원본 재적합": f"{f['a']} + ({f['b']})x",
                "내장 계수": f"{b['a']} + ({b['b']})x" if b else "-",
                "n": f["n"],
                "재적합 r²": f["r2"],
                "내장 r²": b.get("r2") if b else None,
            })
        st.dataframe(pd.DataFrame(t), width="stretch", hide_index=True)
        st.caption(f"재적합 행 수: {v['n_rows']}건")

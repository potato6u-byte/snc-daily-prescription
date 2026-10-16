# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Sequence

DB_PATH = os.environ.get("SNC_DB_PATH", "snc_prescription_history.db")

PRESCRIPTION_COLUMNS = [
    "rx_date", "mode", "tank", "volume_t", "indoor_dawn_c", "indoor_inoc_c", "outdoor_c",
    "cooling_set_c", "hotwater_set_c", "cooling_correction_c",
    "transport_drop_c", "transport_drop_lo_c", "transport_drop_hi_c",
    "predicted_inlet_c", "inlet_target_c", "predicted_minutes",
    "predicted_acidity_delta", "predicted_final_acidity", "predicted_final_ph",
    "predicted_acid_5h", "heat_loss_kcal", "confidence", "model_version",
]

RESULT_STORED = [
    "batch_date", "tank", "indoor_dawn_c", "indoor_inoc_c", "outdoor_dawn_c",
    "cooling_set_c", "hotwater_set_c", "pasteurize_out_set_c", "inlet_tank_c",
    "ferment_tank_tt_c", "temp_1h_c", "temp_5h_c", "ferment_room_c",
    "acid_after_pasteur", "acid_1h", "acid_5h", "total_minutes", "final_acidity",
    "acidity_delta", "acidity_per_min", "transport_m", "surge_acidity", "product_acidity",
    "viscosity_end_cp", "viscosity_product", "ph_end", "ph_product",
    "brix_end", "brix_product", "weather_c",
    "predicted_drop_c", "predicted_inlet_c", "predicted_minutes",
    "predicted_acidity_delta", "predicted_final_acidity",
    "source",
]

RESULT_NUMERIC = [c for c in RESULT_STORED if c not in {"batch_date", "tank", "source"}]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prescription (
                rx_date TEXT PRIMARY KEY,
                mode TEXT, tank TEXT, volume_t REAL,
                indoor_dawn_c REAL, indoor_inoc_c REAL, outdoor_c REAL,
                cooling_set_c REAL, hotwater_set_c REAL, cooling_correction_c REAL,
                transport_drop_c REAL, transport_drop_lo_c REAL, transport_drop_hi_c REAL,
                predicted_inlet_c REAL, inlet_target_c REAL, predicted_minutes REAL,
                predicted_acidity_delta REAL, predicted_final_acidity REAL,
                predicted_final_ph REAL, predicted_acid_5h REAL, heat_loss_kcal REAL,
                confidence TEXT, model_version TEXT, created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_date TEXT NOT NULL,
                tank TEXT,
                indoor_dawn_c REAL, indoor_inoc_c REAL, outdoor_dawn_c REAL,
                cooling_set_c REAL, hotwater_set_c REAL, pasteurize_out_set_c REAL,
                inlet_tank_c REAL, ferment_tank_tt_c REAL, temp_1h_c REAL, temp_5h_c REAL,
                ferment_room_c REAL,
                acid_after_pasteur REAL, acid_1h REAL, acid_5h REAL, total_minutes REAL,
                final_acidity REAL, acidity_delta REAL, acidity_per_min REAL,
                transport_m REAL, surge_acidity REAL, product_acidity REAL,
                viscosity_end_cp REAL, viscosity_product REAL,
                ph_end REAL, ph_product REAL, brix_end REAL, brix_product REAL, weather_c REAL,
                predicted_drop_c REAL, predicted_inlet_c REAL, predicted_minutes REAL,
                predicted_acidity_delta REAL, predicted_final_acidity REAL,
                source TEXT, raw_json TEXT, created_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_result_date ON batch_result(batch_date DESC)")
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


EXPORT_IGNORED = {"raw_json", "created_at"}


def save_prescription(row: dict[str, Any]) -> None:
    data = {c: row.get(c) for c in PRESCRIPTION_COLUMNS}
    data["created_at"] = _now()
    cols = ", ".join(data.keys())
    ph = ", ".join("?" for _ in data)
    conn = _connect()
    try:
        conn.execute(f"INSERT OR REPLACE INTO prescription ({cols}) VALUES ({ph})", list(data.values()))
        conn.commit()
    finally:
        conn.close()


def latest_prescription() -> dict[str, Any] | None:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM prescription ORDER BY rx_date DESC LIMIT 1").fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def list_prescriptions(limit: int = 60, drop_raw: bool = True) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM prescription ORDER BY rx_date DESC LIMIT ?", (int(limit),))
        out = [dict(r) for r in cur.fetchall()]
        return [{k: v for k, v in d.items() if k not in EXPORT_IGNORED} for d in out] if drop_raw else out
    finally:
        conn.close()


def get_prescription(rx_date: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM prescription WHERE rx_date = ?", (str(rx_date),)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def attach_predictions(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    cache: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        rec = dict(row)
        d = rec.get("batch_date")
        if d and any(rec.get(k) is None for k in ("predicted_drop_c", "predicted_minutes", "predicted_acidity_delta")):
            if d not in cache:
                cache[d] = get_prescription(d)
            pr = cache[d]
            if pr:
                if rec.get("predicted_drop_c") is None:
                    rec["predicted_drop_c"] = pr.get("transport_drop_c")
                if rec.get("predicted_inlet_c") is None:
                    rec["predicted_inlet_c"] = pr.get("predicted_inlet_c")
                if rec.get("predicted_minutes") is None:
                    rec["predicted_minutes"] = pr.get("predicted_minutes")
                if rec.get("predicted_acidity_delta") is None:
                    rec["predicted_acidity_delta"] = pr.get("predicted_acidity_delta")
                if rec.get("predicted_final_acidity") is None:
                    rec["predicted_final_acidity"] = pr.get("predicted_final_acidity")
        enriched.append(rec)
    return enriched


def save_batch_results(rows: Sequence[dict[str, Any]], source: str = "manual") -> int:
    if not rows:
        return 0
    rows = attach_predictions(rows)
    conn = _connect()
    n = 0
    try:
        for row in rows:
            data = {c: row.get(c) for c in RESULT_STORED if c != "source"}
            data["tank"] = str(data.get("tank")) if data.get("tank") is not None else None
            data["source"] = source
            data["raw_json"] = json.dumps({k: row.get(k) for k in row if row.get(k) is not None}, ensure_ascii=False)
            data["created_at"] = _now()
            cols = ", ".join(data.keys())
            ph = ", ".join("?" for _ in data)
            conn.execute(f"INSERT INTO batch_result ({cols}) VALUES ({ph})", list(data.values()))
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def _clean(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if k not in EXPORT_IGNORED} for r in rows]


def list_batch_results(limit: int = 200) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM batch_result ORDER BY batch_date DESC, id DESC LIMIT ?", (int(limit),))
        return _clean([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


def recent_batch_results(days: int = 7) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT * FROM batch_result WHERE date(batch_date) >= date('now', ?) ORDER BY batch_date DESC, id DESC",
            (f"-{int(days)} day",),
        )
        return _clean([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


def delete_batch_result(row_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM batch_result WHERE id = ?", (int(row_id),))
        conn.commit()
    finally:
        conn.close()


def clear_batch_results() -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM batch_result")
        conn.commit()
    finally:
        conn.close()


def count_rows() -> dict[str, int]:
    conn = _connect()
    try:
        return {
            "prescriptions": conn.execute("SELECT COUNT(*) FROM prescription").fetchone()[0],
            "batch_results": conn.execute("SELECT COUNT(*) FROM batch_result").fetchone()[0],
        }
    finally:
        conn.close()

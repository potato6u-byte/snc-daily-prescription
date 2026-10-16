# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Iterable, Sequence

DB_PATH = os.environ.get("SNC_DB_PATH", "snc_prescription_history.db")

PRESCRIPTION_COLUMNS = [
    "rx_date", "indoor_dawn_c", "outdoor_c", "tanks", "volume_l", "raw_material",
    "transport_drop_c", "transport_drop_lo_c", "transport_drop_hi_c", "inlet_target_c",
    "cooling_set_c", "hotwater_set_c", "cooling_residual_c", "minutes_residual",
    "time_offset_c", "predicted_minutes", "predicted_acidity_delta",
    "predicted_final_acidity", "predicted_final_ph", "predicted_viscosity_cp",
    "chilling_target_c", "heat_loss_kcal", "confidence", "model_version",
]

RESULT_COLUMNS = [
    "batch_date", "tanks", "volume_l", "raw_material", "indoor_dawn_c", "outdoor_c",
    "pasteurize_cooling_set_c", "pasteurize_cooling_actual_c", "inlet_tank_c",
    "hotwater_set_c", "acid_5h", "total_minutes", "final_acidity", "final_ph",
    "viscosity_cp", "syneresis_pct", "taste_score",
    "predicted_drop_c", "predicted_minutes", "memo",
]


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
                indoor_dawn_c REAL, outdoor_c REAL, tanks TEXT, volume_l REAL,
                raw_material TEXT, transport_drop_c REAL, transport_drop_lo_c REAL,
                transport_drop_hi_c REAL, inlet_target_c REAL, cooling_set_c REAL,
                hotwater_set_c REAL, cooling_residual_c REAL, minutes_residual REAL,
                time_offset_c REAL, predicted_minutes REAL, predicted_acidity_delta REAL,
                predicted_final_acidity REAL, predicted_final_ph REAL,
                predicted_viscosity_cp REAL, chilling_target_c REAL, heat_loss_kcal REAL,
                confidence TEXT, model_version TEXT, created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_date TEXT NOT NULL,
                tanks TEXT, volume_l REAL, raw_material TEXT,
                indoor_dawn_c REAL, outdoor_c REAL,
                pasteurize_cooling_set_c REAL, pasteurize_cooling_actual_c REAL,
                inlet_tank_c REAL, hotwater_set_c REAL, acid_5h REAL,
                total_minutes REAL, final_acidity REAL, final_ph REAL,
                viscosity_cp REAL, syneresis_pct REAL, taste_score REAL,
                predicted_drop_c REAL, predicted_minutes REAL,
                memo TEXT, source TEXT, created_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_result_date ON batch_result(batch_date DESC)")
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
        cur = conn.execute("SELECT * FROM prescription ORDER BY rx_date DESC LIMIT 1")
        r = cur.fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def list_prescriptions(limit: int = 60) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM prescription ORDER BY rx_date DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_prescription(rx_date: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM prescription WHERE rx_date = ?", (str(rx_date),))
        r = cur.fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def attach_predictions(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    cache: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        rec = dict(row)
        d = rec.get("batch_date")
        if d and (rec.get("predicted_drop_c") is None or rec.get("predicted_minutes") is None):
            if d not in cache:
                cache[d] = get_prescription(d)
            pr = cache[d]
            if pr:
                if rec.get("predicted_drop_c") is None:
                    rec["predicted_drop_c"] = pr.get("transport_drop_c")
                if rec.get("predicted_minutes") is None:
                    rec["predicted_minutes"] = pr.get("predicted_minutes")
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
            data = {c: row.get(c) for c in RESULT_COLUMNS}
            data["source"] = source
            data["created_at"] = _now()
            cols = ", ".join(data.keys())
            ph = ", ".join("?" for _ in data)
            conn.execute(f"INSERT INTO batch_result ({cols}) VALUES ({ph})", list(data.values()))
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def list_batch_results(limit: int = 120) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT * FROM batch_result ORDER BY batch_date DESC, id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def recent_batch_results(days: int = 7) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT * FROM batch_result
            WHERE date(batch_date) >= date('now', ?)
            ORDER BY batch_date DESC, id DESC
            """,
            (f"-{int(days)} day",),
        )
        return [dict(r) for r in cur.fetchall()]
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
        p = conn.execute("SELECT COUNT(*) FROM prescription").fetchone()[0]
        b = conn.execute("SELECT COUNT(*) FROM batch_result").fetchone()[0]
        return {"prescriptions": p, "batch_results": b}
    finally:
        conn.close()

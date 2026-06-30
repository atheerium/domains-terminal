"""SQLite storage layer — single source of truth.

Purpose: Persist all domain data, scores, appraisals, sales cache, and audit events
to a local SQLite database. This is the single source of truth — no in-memory state.

Input: Domain / Score / Appraisal / Sale / Event models
Output: Same models read back from database
Dependencies: stdlib: sqlite3, pathlib
Side effects: Creates/reads/writes ~/.domains-terminal/domains.db"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

DB_PATH = Path.home() / ".domains-terminal" / "domains.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    domain TEXT PRIMARY KEY,
    source TEXT,
    tld TEXT,
    length INTEGER,
    word_count INTEGER,
    contains_numbers INTEGER,
    seen_at TEXT,
    drop_at TEXT,
    current_price REAL,
    end_time TEXT,
    auction_id TEXT,
    is_available INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    raw_data TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    metric_type TEXT,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    rule TEXT,
    score INTEGER,
    confidence REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appraisals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    retail_min INTEGER,
    retail_max INTEGER,
    wholesale_min INTEGER,
    wholesale_max INTEGER,
    buy_recommendation INTEGER,
    confidence REAL,
    reason TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT,
    domain TEXT,
    sale_price INTEGER,
    sale_date TEXT,
    venue TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT,
    event_type TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Storage:
    """SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        with self._conn() as conn:
            cur = conn.execute(sql, params or ())
            return cur.fetchall()

    def insert_domain(self, data: Dict[str, Any]) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT OR REPLACE INTO domains ({cols}) VALUES ({placeholders})"
        with self._conn() as conn:
            conn.execute(sql, tuple(data.values()))

    def insert_metric(self, data: Dict[str, Any]) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO metrics ({cols}) VALUES ({placeholders})"
        with self._conn() as conn:
            conn.execute(sql, tuple(data.values()))

    def insert_score(self, data: Dict[str, Any]) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO scores ({cols}) VALUES ({placeholders})"
        with self._conn() as conn:
            conn.execute(sql, tuple(data.values()))

    def insert_appraisal(self, data: Dict[str, Any]) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO appraisals ({cols}) VALUES ({placeholders})"
        with self._conn() as conn:
            conn.execute(sql, tuple(data.values()))

    def insert_event(self, domain: str, event_type: str, details: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (domain, event_type, details) VALUES (?, ?, ?)",
                (domain, event_type, details),
            )

    def get_domains(self, where: str = "", params: tuple = ()) -> List[Dict[str, Any]]:
        sql = f"SELECT * FROM domains {where}"
        with self._conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def get_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM domains WHERE domain = ?", (domain,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_metrics(self, domain: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM metrics WHERE domain = ?", (domain,))
            return [dict(row) for row in cur.fetchall()]

    def get_scores(self, domain: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM scores WHERE domain = ?", (domain,))
            return [dict(row) for row in cur.fetchall()]

    def get_appraisals(self, domain: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM appraisals WHERE domain = ?", (domain,))
            return [dict(row) for row in cur.fetchall()]

    def get_top_scores(self, limit: int = 10, min_score: int = 0) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT s.*, d.current_price, d.end_time
                FROM scores s
                JOIN domains d ON s.domain = d.domain
                WHERE s.score >= ?
                ORDER BY s.score DESC
                LIMIT ?""",
                (min_score, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def recommended_domains(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT a.*, d.current_price
                FROM appraisals a
                JOIN domains d ON a.domain = d.domain
                WHERE a.buy_recommendation = 1
                ORDER BY a.confidence DESC
                LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
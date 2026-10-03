from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    search TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    data TEXT NOT NULL,
    first_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    # ---- anuncios ----
    def seen(self, uid: str) -> bool:
        return self.db.execute("SELECT 1 FROM listings WHERE uid=?", (uid,)).fetchone() is not None

    def has_search(self, search: str) -> bool:
        return self.db.execute("SELECT 1 FROM listings WHERE search=? LIMIT 1", (search,)).fetchone() is not None

    def add(self, l: Listing, search: str, status: str) -> int:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO listings (uid, search, status, score, data, first_seen) VALUES (?,?,?,?,?,?)",
            (l.uid, search, status, l.score, json.dumps(asdict(l), ensure_ascii=False), time.time()),
        )
        self.db.commit()
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        return self.db.execute("SELECT id FROM listings WHERE uid=?", (l.uid,)).fetchone()[0]

    def set_status(self, row_id: int, status: str) -> None:
        self.db.execute("UPDATE listings SET status=? WHERE id=?", (status, row_id))
        self.db.commit()

    def get(self, row_id: int) -> Listing | None:
        row = self.db.execute("SELECT data FROM listings WHERE id=?", (row_id,)).fetchone()
        return Listing(**json.loads(row[0])) if row else None

    def counts(self) -> dict[str, int]:
        rows = self.db.execute("SELECT status, COUNT(*) FROM listings GROUP BY status").fetchall()
        return {s: n for s, n in rows}

    # ---- clave/valor ----
    def kv_get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def kv_set(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, value))
        self.db.commit()

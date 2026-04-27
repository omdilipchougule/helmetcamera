"""
SQLite database — stores every violation locally.
No server or internet needed.
"""

import sqlite3
from pathlib import Path
from detection.rules_engine import Violation
from utils.logger import setup_logger

logger = setup_logger("database")
DB_PATH = Path("./violations.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                violation_type TEXT,
                timestamp_sec  REAL,
                confidence     REAL,
                source_video   TEXT,
                detected_at    TEXT,
                evidence_clip  TEXT,
                snapshot_path  TEXT,
                notes          TEXT,
                reported       INTEGER DEFAULT 0,
                report_path    TEXT
            )""")
        self.conn.commit()
        logger.info(f"Database: {DB_PATH.resolve()}")

    def save(self, v: Violation) -> int:
        cur = self.conn.execute(
            "INSERT INTO violations (violation_type,timestamp_sec,confidence,"
            "source_video,detected_at,evidence_clip,snapshot_path,notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (v.violation_type, v.timestamp_sec, v.confidence,
             v.source_video, v.detected_at, v.evidence_clip,
             v.snapshot_path, v.notes))
        self.conn.commit()
        return cur.lastrowid

    def mark_reported(self, vid: int, report_path: str):
        self.conn.execute("UPDATE violations SET reported=1,report_path=? WHERE id=?",
                          (report_path, vid))
        self.conn.commit()

    def all(self):
        cur = self.conn.execute("SELECT * FROM violations ORDER BY detected_at DESC")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols,r)) for r in cur.fetchall()]

    def unreported(self):
        cur = self.conn.execute("SELECT * FROM violations WHERE reported=0")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols,r)) for r in cur.fetchall()]

    def summary(self):
        cur = self.conn.execute(
            "SELECT violation_type, COUNT(*) FROM violations GROUP BY violation_type ORDER BY 2 DESC")
        return {r[0]:r[1] for r in cur.fetchall()}

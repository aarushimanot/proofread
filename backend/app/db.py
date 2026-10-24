"""
SQLite database for Proofread (a single file: backend/data/proofread.db).

SQLite ships with Python, needs no server and stores everything in one file,
so the whole project stays "clone and run".

Tables
  passages     the curated reference passages (the ONLY evidence verdicts may use)
  test_claims  labelled claims used by evaluate.py and the "Load example" dropdown
  reviews      human reviewer decisions (Step 3 in the UI)
  checks       history of every /verify call (claim, verdict, confidence, time)

Source of truth: the curated corpus is written by hand in data/references.json and
data/test_claims.json because JSON is easy to edit and review. On every startup
`sync_seed_data()` copies those files into the database, so an edit to the JSON shows
up after a restart. Reviews and check history exist only in the database.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS passages (
    id      TEXT PRIMARY KEY,
    title   TEXT NOT NULL,
    source  TEXT NOT NULL,
    url     TEXT NOT NULL,
    date    TEXT NOT NULL,
    text    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS test_claims (
    id                TEXT PRIMARY KEY,
    post_text         TEXT NOT NULL,
    claim             TEXT NOT NULL,
    expected_verdict  TEXT NOT NULL,
    note              TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    claim             TEXT NOT NULL,
    model_verdict     TEXT NOT NULL,
    reviewer_verdict  TEXT NOT NULL,
    note              TEXT NOT NULL DEFAULT '',
    agreed            INTEGER NOT NULL,           -- 1 if reviewer agreed with the model
    timestamp         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    claim             TEXT NOT NULL,
    verdict           TEXT NOT NULL,
    confidence        REAL,                       -- NULL when no passage was relevant
    confidence_label  TEXT NOT NULL,
    top_passage_id    TEXT,
    timestamp         TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    """Open a connection, commit on success, always close. Rows behave like dicts."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if needed and load the curated JSON seed files."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
    sync_seed_data()
    _import_legacy_review_log()


def _sync_table(conn, table: str, columns: list[str], rows: list[dict]) -> None:
    """Make `table` match `rows` exactly: insert/update every row, delete the rest."""
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c != "id")
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        [tuple(row.get(c, "") for c in columns) for row in rows],
    )
    ids = [row["id"] for row in rows]
    conn.execute(f"DELETE FROM {table} WHERE id NOT IN ({', '.join('?' for _ in ids)})", ids)


def sync_seed_data() -> None:
    """Copy references.json and test_claims.json into the database."""
    with open(config.REFERENCES_PATH, encoding="utf-8") as f:
        passages = json.load(f)
    with open(config.TEST_CLAIMS_PATH, encoding="utf-8") as f:
        tests = json.load(f)
    with connect() as conn:
        _sync_table(conn, "passages", ["id", "title", "source", "url", "date", "text"], passages)
        _sync_table(conn, "test_claims", ["id", "post_text", "claim", "expected_verdict", "note"], tests)


def _import_legacy_review_log() -> None:
    """One-off migration: earlier versions stored reviews in data/review_log.json."""
    legacy = config.DATA_DIR / "review_log.json"
    if not legacy.exists():
        return
    with open(legacy, encoding="utf-8") as f:
        entries = json.load(f)
    for e in entries:
        add_review(e["claim"], e["model_verdict"], e["reviewer_verdict"], e.get("note", ""),
                   timestamp=e.get("timestamp"))
    legacy.rename(legacy.with_suffix(".json.imported"))


# ------------------------------------------------------------------ passages & test claims
def get_passages() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM passages ORDER BY id")]


def get_test_claims() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM test_claims ORDER BY id")]


# ------------------------------------------------------------------ reviews
def add_review(claim: str, model_verdict: str, reviewer_verdict: str, note: str,
               timestamp: str | None = None) -> dict:
    entry = {
        "claim": claim, "model_verdict": model_verdict, "reviewer_verdict": reviewer_verdict,
        "note": note, "agreed": model_verdict == reviewer_verdict, "timestamp": timestamp or now(),
    }
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reviews (claim, model_verdict, reviewer_verdict, note, agreed, timestamp) "
            "VALUES (:claim, :model_verdict, :reviewer_verdict, :note, :agreed, :timestamp)", entry)
        entry["id"] = cur.lastrowid
    return entry


def get_reviews() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reviews ORDER BY id").fetchall()
    return [{**dict(r), "agreed": bool(r["agreed"])} for r in rows]


# ------------------------------------------------------------------ check history
def add_check(result: dict) -> None:
    top = result["evidence"][0]["id"] if result["evidence"] else None
    with connect() as conn:
        conn.execute(
            "INSERT INTO checks (claim, verdict, confidence, confidence_label, top_passage_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (result["claim"], result["verdict"], result["confidence"], result["confidence_label"], top, now()))


def get_checks(limit: int = 50) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM checks ORDER BY id DESC LIMIT ?", (limit,))]


def stats() -> dict:
    """Counts shown on /health and in the UI."""
    with connect() as conn:
        count = lambda table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: E731
        agreed = conn.execute("SELECT COUNT(*) FROM reviews WHERE agreed = 1").fetchone()[0]
        return {"passages": count("passages"), "test_claims": count("test_claims"),
                "reviews": count("reviews"), "reviews_agreed": agreed, "checks": count("checks")}

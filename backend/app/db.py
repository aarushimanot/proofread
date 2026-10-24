"""
SQLite database for Proofread (a single file: backend/data/proofread.db).

SQLite ships with Python, needs no server and stores everything in one file,
so the whole project stays "clone and run".

Tables
  collections  topics, e.g. "Chandrayaan-3" or "Climate change"; each has its own passages
  passages     the reference passages (the ONLY evidence verdicts may use)
  test_claims  labelled claims used by evaluate.py and the "Load example" dropdown
  reviews      human reviewer decisions (Step 3 in the UI)
  checks       history of every /verify call (claim, verdict, confidence, time)

Where passages come from (the `origin` column)
  "seed"  the built-in topics (Chandrayaan-3, Constitution of India, Cricket World Cup 2023),
          written by hand in data/topics/*.json. On every startup `sync_seed_data()`
          copies those files into the database, so seed passages are read-only in the
          app: change them by editing the JSON.
  "user"  passages added in the app (typed, pasted or imported from a link). They live
          only in the database and can be edited or deleted in the Lie-brary tab.
"""
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SEED_COLLECTION_ID = "chandrayaan-3"   # default topic for older rows and the UI


def load_seed_topics() -> list[dict]:
    """Every built-in topic file in data/topics/ ({id, name, description, passages})."""
    return [json.load(open(f, encoding="utf-8")) for f in sorted(config.TOPICS_DIR.glob("*.json"))]


SCHEMA = """
CREATE TABLE IF NOT EXISTS collections (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT NOT NULL DEFAULT '',
    origin       TEXT NOT NULL DEFAULT 'user',     -- 'seed' or 'user'
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passages (
    id             TEXT PRIMARY KEY,
    collection_id  TEXT NOT NULL DEFAULT 'chandrayaan-3' REFERENCES collections(id),
    title          TEXT NOT NULL,
    source         TEXT NOT NULL,
    url            TEXT NOT NULL,
    date           TEXT NOT NULL,
    text           TEXT NOT NULL,
    origin         TEXT NOT NULL DEFAULT 'seed'    -- 'seed' or 'user'
);
CREATE TABLE IF NOT EXISTS test_claims (
    id                TEXT PRIMARY KEY,
    collection_id     TEXT NOT NULL DEFAULT 'chandrayaan-3',
    post_text         TEXT NOT NULL,
    claim             TEXT NOT NULL,
    expected_verdict  TEXT NOT NULL,
    note              TEXT NOT NULL DEFAULT '',
    origin            TEXT NOT NULL DEFAULT 'seed'    -- 'seed' (hand-written) or 'auto' (generated)
);
CREATE TABLE IF NOT EXISTS reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id     TEXT,                       -- NULL = checked against all topics
    claim             TEXT NOT NULL,
    model_verdict     TEXT NOT NULL,
    reviewer_verdict  TEXT NOT NULL,
    note              TEXT NOT NULL DEFAULT '',
    agreed            INTEGER NOT NULL,           -- 1 if reviewer agreed with the model
    timestamp         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id     TEXT,                       -- NULL = checked against all topics
    claim             TEXT NOT NULL,
    verdict           TEXT NOT NULL,
    confidence        REAL,                       -- NULL when no passage was relevant
    confidence_label  TEXT NOT NULL,
    top_passage_id    TEXT,
    timestamp         TEXT NOT NULL
);
"""

# Columns added after the first version; added automatically to older database files.
MIGRATIONS = {
    "passages": {"collection_id": "TEXT NOT NULL DEFAULT 'chandrayaan-3'", "origin": "TEXT NOT NULL DEFAULT 'seed'"},
    "test_claims": {"collection_id": "TEXT NOT NULL DEFAULT 'chandrayaan-3'", "origin": "TEXT NOT NULL DEFAULT 'seed'"},
    "reviews": {"collection_id": "TEXT"},
    "checks": {"collection_id": "TEXT"},
}

PASSAGE_FIELDS = ["id", "collection_id", "title", "source", "url", "date", "text", "origin"]


class NotFound(Exception):
    pass


class ReadOnly(Exception):
    pass


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
    """Create tables if needed, upgrade older files, and load the built-in seed data."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, columns in MIGRATIONS.items():
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    sync_seed_data()
    _import_legacy_review_log()


def sync_seed_data() -> None:
    """
    Copy the built-in topic files and test_claims.json into the database.
    Only rows with origin='seed' are touched, so topics and passages added in the app are never lost.
    """
    topics = load_seed_topics()
    with open(config.TEST_CLAIMS_PATH, encoding="utf-8") as f:
        tests = json.load(f)
    with connect() as conn:
        for t in topics:
            conn.execute(
                "INSERT INTO collections (id, name, description, origin, created_at) VALUES (?, ?, ?, 'seed', ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description, origin='seed'",
                (t["id"], t["name"], t.get("description", ""), now()))
            conn.executemany(
                "INSERT INTO passages (id, collection_id, title, source, url, date, text, origin) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'seed') ON CONFLICT(id) DO UPDATE SET "
                "collection_id=excluded.collection_id, title=excluded.title, source=excluded.source, "
                "url=excluded.url, date=excluded.date, text=excluded.text, origin='seed'",
                [(p["id"], t["id"], p["title"], p["source"], p["url"], p["date"], p["text"]) for p in t["passages"]])
        # Remove built-in passages/topics whose files or entries were deleted.
        seed_ids = [p["id"] for t in topics for p in t["passages"]]
        conn.execute(f"DELETE FROM passages WHERE origin = 'seed' AND id NOT IN ({', '.join('?' * len(seed_ids))})",
                     seed_ids)
        topic_ids = [t["id"] for t in topics]
        conn.execute(f"DELETE FROM collections WHERE origin = 'seed' AND id NOT IN ({', '.join('?' * len(topic_ids))}) "
                     "AND id NOT IN (SELECT collection_id FROM passages)", topic_ids)
        conn.executemany(
            "INSERT INTO test_claims (id, collection_id, post_text, claim, expected_verdict, note) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET collection_id=excluded.collection_id, "
            "post_text=excluded.post_text, claim=excluded.claim, "
            "expected_verdict=excluded.expected_verdict, note=excluded.note",
            [(t["id"], t["collection_id"], t["post_text"], t["claim"], t["expected_verdict"],
              t.get("note", "")) for t in tests])
        test_ids = [t["id"] for t in tests]
        conn.execute(f"DELETE FROM test_claims WHERE origin = 'seed' AND id NOT IN ({', '.join('?' * len(test_ids))})",
                     test_ids)


def _import_legacy_review_log() -> None:
    """One-off migration: earlier versions stored reviews in data/review_log.json."""
    legacy = config.DATA_DIR / "review_log.json"
    if not legacy.exists():
        return
    with open(legacy, encoding="utf-8") as f:
        entries = json.load(f)
    for e in entries:
        add_review(e["claim"], e["model_verdict"], e["reviewer_verdict"], e.get("note", ""),
                   collection_id=SEED_COLLECTION_ID, timestamp=e.get("timestamp"))
    legacy.rename(legacy.with_suffix(".json.imported"))


# ------------------------------------------------------------------ collections (topics)
def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "topic"


def get_collections() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, COUNT(p.id) AS passage_count FROM collections c "
            "LEFT JOIN passages p ON p.collection_id = c.id "
            "GROUP BY c.id ORDER BY c.origin = 'seed' DESC, c.created_at").fetchall()
    return [dict(r) for r in rows]


def get_collection(collection_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if row is None:
        raise NotFound(f"Topic '{collection_id}' does not exist.")
    return dict(row)


def create_collection(name: str, description: str = "") -> dict:
    name = name.strip()
    with connect() as conn:
        if conn.execute("SELECT 1 FROM collections WHERE lower(name) = lower(?)", (name,)).fetchone():
            raise ValueError(f"A topic called '{name}' already exists.")
        base = cid = _slug(name)
        n = 2
        while conn.execute("SELECT 1 FROM collections WHERE id = ?", (cid,)).fetchone():
            cid, n = f"{base}-{n}", n + 1
        conn.execute("INSERT INTO collections (id, name, description, origin, created_at) "
                     "VALUES (?, ?, ?, 'user', ?)", (cid, name, description.strip(), now()))
    return get_collection(cid)


def delete_collection(collection_id: str) -> None:
    """Delete a user topic and all of its passages."""
    if get_collection(collection_id)["origin"] == "seed":
        raise ReadOnly("Built-in topics can't be deleted. Remove their file from data/topics/ instead.")
    with connect() as conn:
        conn.execute("DELETE FROM passages WHERE collection_id = ?", (collection_id,))
        conn.execute("DELETE FROM test_claims WHERE collection_id = ?", (collection_id,))
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))


# ------------------------------------------------------------------ passages
def get_passages(collection_id: str | None = None) -> list[dict]:
    """All passages, or only those of one topic."""
    with connect() as conn:
        if collection_id:
            rows = conn.execute("SELECT * FROM passages WHERE collection_id = ? ORDER BY origin, rowid",
                                (collection_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM passages ORDER BY collection_id, origin, rowid").fetchall()
    return [dict(r) for r in rows]


def get_passage(passage_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM passages WHERE id = ?", (passage_id,)).fetchone()
    if row is None:
        raise NotFound(f"Passage '{passage_id}' does not exist.")
    return dict(row)


def add_passages(collection_id: str, items: list[dict]) -> list[dict]:
    """Add one or more user passages to a topic. Each item: title, source, url, date, text."""
    get_collection(collection_id)  # raises NotFound
    rows = []
    for item in items:
        rows.append({
            "id": f"P-{uuid.uuid4().hex[:8]}", "collection_id": collection_id, "origin": "user",
            "title": item["title"].strip(), "source": item["source"].strip(), "url": item.get("url", "").strip(),
            "date": item.get("date", "").strip(), "text": item["text"].strip(),
        })
    with connect() as conn:
        conn.executemany(f"INSERT INTO passages ({', '.join(PASSAGE_FIELDS)}) "
                         f"VALUES ({', '.join(':' + f for f in PASSAGE_FIELDS)})", rows)
    return rows


def update_passage(passage_id: str, fields: dict) -> dict:
    if get_passage(passage_id)["origin"] == "seed":
        raise ReadOnly("Built-in passages are read-only. Edit data/references.json instead.")
    allowed = {k: v.strip() for k, v in fields.items() if k in {"title", "source", "url", "date", "text"}}
    if allowed:
        with connect() as conn:
            conn.execute(f"UPDATE passages SET {', '.join(f'{k} = :{k}' for k in allowed)} WHERE id = :id",
                         {**allowed, "id": passage_id})
    return get_passage(passage_id)


def delete_passage(passage_id: str) -> None:
    if get_passage(passage_id)["origin"] == "seed":
        raise ReadOnly("Built-in passages are read-only. Edit data/references.json instead.")
    with connect() as conn:
        conn.execute("DELETE FROM passages WHERE id = ?", (passage_id,))


# ------------------------------------------------------------------ test claims
def get_test_claims(collection_id: str | None = None, origin: str | None = None) -> list[dict]:
    """Test claims, optionally only one topic's and/or only 'seed' (hand-written) or 'auto' ones."""
    where, args = [], []
    if collection_id:
        where.append("collection_id = ?")
        args.append(collection_id)
    if origin:
        where.append("origin = ?")
        args.append(origin)
    sql = "SELECT * FROM test_claims" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY rowid"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def replace_auto_test_claims(collection_id: str, items: list[dict]) -> None:
    """Swap a topic's auto-generated test claims for a new set (hand-written ones are untouched)."""
    with connect() as conn:
        conn.execute("DELETE FROM test_claims WHERE collection_id = ? AND origin = 'auto'", (collection_id,))
        conn.executemany(
            "INSERT OR REPLACE INTO test_claims (id, collection_id, post_text, claim, expected_verdict, note, origin) "
            "VALUES (:id, :collection_id, :post_text, :claim, :expected_verdict, :note, 'auto')", items)


def update_test_claim(claim_id: str, claim: str, expected_verdict: str, note: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE test_claims SET claim = ?, expected_verdict = ?, note = ? WHERE id = ? AND origin = 'auto'",
                     (claim.strip(), expected_verdict, note.strip(), claim_id))


def delete_test_claim(claim_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM test_claims WHERE id = ? AND origin = 'auto'", (claim_id,))


# ------------------------------------------------------------------ reviews
def add_review(claim: str, model_verdict: str, reviewer_verdict: str, note: str,
               collection_id: str | None = None, timestamp: str | None = None) -> dict:
    entry = {
        "collection_id": collection_id, "claim": claim, "model_verdict": model_verdict,
        "reviewer_verdict": reviewer_verdict, "note": note,
        "agreed": model_verdict == reviewer_verdict, "timestamp": timestamp or now(),
    }
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reviews (collection_id, claim, model_verdict, reviewer_verdict, note, agreed, timestamp) "
            "VALUES (:collection_id, :claim, :model_verdict, :reviewer_verdict, :note, :agreed, :timestamp)", entry)
        entry["id"] = cur.lastrowid
    return entry


def get_reviews() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reviews ORDER BY id").fetchall()
    return [{**dict(r), "agreed": bool(r["agreed"])} for r in rows]


# ------------------------------------------------------------------ check history
def add_check(result: dict, collection_id: str | None = None) -> None:
    top = result["evidence"][0]["id"] if result["evidence"] else None
    with connect() as conn:
        conn.execute(
            "INSERT INTO checks (collection_id, claim, verdict, confidence, confidence_label, top_passage_id, "
            "timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (collection_id, result["claim"], result["verdict"], result["confidence"],
             result["confidence_label"], top, now()))


def get_checks(limit: int = 50) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT k.*, c.name AS collection_name FROM checks k "
            "LEFT JOIN collections c ON c.id = k.collection_id ORDER BY k.id DESC LIMIT ?", (limit,))]


def stats() -> dict:
    """Counts shown on /health and in the UI."""
    with connect() as conn:
        count = lambda table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: E731
        agreed = conn.execute("SELECT COUNT(*) FROM reviews WHERE agreed = 1").fetchone()[0]
        return {"collections": count("collections"), "passages": count("passages"),
                "test_claims": count("test_claims"), "reviews": count("reviews"),
                "reviews_agreed": agreed, "checks": count("checks")}

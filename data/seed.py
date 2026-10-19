"""Build data/incidents.db with a planted incident.

Deterministic (fixed random seed). Timestamps are generated relative to "now"
so the server's since_hours queries always line up.

The story: a deploy to `checkout` ~6 hours ago starts a PaymentTimeoutError
spike (roughly 20x the baseline error rate, ramping up over the first hour).
The deploy row's commit_sha is read from data/demo_sha.txt (or the DEMO_SHA
env var), so it points at the real "culprit" commit in the demo GitHub repo.
"""

from __future__ import annotations

import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "data" / "incidents.db"))
SHA_FILE = ROOT / "data" / "demo_sha.txt"

RNG_SEED = 42
WINDOW_HOURS = 72
INCIDENT_HOURS_AGO = 6

SERVICES = ("checkout", "auth", "search")

BASELINE = {
    "checkout": (
        ("CacheMissWarning", "cache miss for cart:{id}"),
        ("SlowQueryWarning", "query took {ms}ms on products table"),
    ),
    "auth": (
        ("AuthTokenExpired", "access token expired for session {id}"),
        ("CacheMissWarning", "cache miss for token:{id}"),
    ),
    "search": (
        ("SlowQueryWarning", "query took {ms}ms on search_index"),
        ("CacheMissWarning", "cache miss for query:{id}"),
    ),
}

INCIDENT_SERVICE = "checkout"
INCIDENT_SIGNATURE = "PaymentTimeoutError"
INCIDENT_MESSAGE = "payment-gateway request exceeded 3000ms"

SCHEMA = """
CREATE TABLE IF NOT EXISTS error_logs (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  service TEXT NOT NULL,
  level TEXT NOT NULL,
  signature TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deploys (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  service TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_service_ts ON error_logs(service, ts);
"""


def culprit_sha() -> str:
    """The commit SHA the planted deploy points at."""
    if SHA_FILE.exists():
        sha = SHA_FILE.read_text(encoding="utf-8").strip()
        if sha:
            return sha
    return os.environ.get("DEMO_SHA", "0" * 40)


def _rand_ts(rng: random.Random, hour_start: datetime) -> str:
    ts = hour_start + timedelta(
        minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
    )
    return ts.astimezone(timezone.utc).isoformat()


def build_rows() -> tuple[list[tuple], list[tuple]]:
    rng = random.Random(RNG_SEED)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    incident_time = now - timedelta(hours=INCIDENT_HOURS_AGO)

    logs: list[tuple] = []
    for h in range(WINDOW_HOURS, 0, -1):
        hour_start = now - timedelta(hours=h)

        for service in SERVICES:
            for _ in range(rng.randint(0, 2)):
                signature, template = rng.choice(BASELINE[service])
                message = template.format(id=rng.randint(1000, 9999), ms=rng.randint(500, 2500))
                logs.append((_rand_ts(rng, hour_start), service, "WARN", signature, message))

        if hour_start >= incident_time:
            hours_since = (hour_start - incident_time) // timedelta(hours=1)
            factor = 0.4 if hours_since < 1 else 1.0
            for _ in range(rng.randint(int(15 * factor), int(20 * factor) + 2)):
                logs.append(
                    (_rand_ts(rng, hour_start), INCIDENT_SERVICE, "ERROR",
                     INCIDENT_SIGNATURE, INCIDENT_MESSAGE)
                )

    culprit = culprit_sha()
    deploys: list[tuple] = [
        (
            (now - timedelta(hours=40)).astimezone(timezone.utc).isoformat(),
            "auth", f"{rng.randrange(16**40):040x}", "Bump jwt library to 2.9.1",
        ),
        (
            incident_time.astimezone(timezone.utc).isoformat(),
            INCIDENT_SERVICE, culprit, "Reduce payment client timeout from 30s to 3s",
        ),
        (
            (now - timedelta(hours=20)).astimezone(timezone.utc).isoformat(),
            "search", f"{rng.randrange(16**40):040x}", "Tune search relevance weights",
        ),
    ]
    return logs, deploys


def main() -> None:
    logs, deploys = build_rows()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO error_logs (ts, service, level, signature, message) VALUES (?, ?, ?, ?, ?)",
            logs,
        )
        conn.executemany(
            "INSERT INTO deploys (ts, service, commit_sha, notes) VALUES (?, ?, ?, ?)",
            deploys,
        )
        conn.commit()

        print(f"Wrote {len(logs)} log rows and {len(deploys)} deploys to {DB_PATH}")
        print(f"Planted culprit deploy: {culprit_sha()} at {deploys[1][0]}")
        print("\nCounts per service / signature:")
        rows = conn.execute(
            "SELECT service, signature, COUNT(*) FROM error_logs "
            "GROUP BY service, signature ORDER BY service, COUNT(*) DESC"
        ).fetchall()
        for service, signature, count in rows:
            print(f"  {service:9s} {signature:20s} {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)

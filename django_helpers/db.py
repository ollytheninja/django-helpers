from pathlib import Path

SQLITE_INIT_COMMAND = (
    "PRAGMA foreign_keys=ON;"
    "PRAGMA journal_mode=WAL;"
    "PRAGMA synchronous=NORMAL;"
    "PRAGMA busy_timeout=5000;"
    "PRAGMA temp_store=MEMORY;"
    "PRAGMA mmap_size=134217728;"
    "PRAGMA journal_size_limit=67108864;"
    "PRAGMA cache_size=2000;"
)


def sqlite_database(path: str | Path, *, test_name: str = ":memory:") -> dict:
    """Return a tuned SQLite database config suitable for a small deployed app."""

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(path),
        "OPTIONS": {
            "init_command": SQLITE_INIT_COMMAND,
            "transaction_mode": "IMMEDIATE",
        },
        "TEST": {"NAME": test_name},
    }

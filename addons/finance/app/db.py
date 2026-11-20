"""SQLite-Verbindungen, Migrationen und Transaktionskontext.

Eine Datei, ein Prozess, keine externe Datenbank. Der Pfad lässt sich über
FINANCE_DB_PATH überschreiben (lokale Entwicklung und Tests).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = "/data/finance.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_db_path() -> Path:
    """Datenbankpfad ermitteln.

    In Home Assistant ist /data immer gemountet. Außerhalb (lokale Entwicklung)
    wird eine Datei im aktuellen Verzeichnis verwendet.
    """
    override = os.environ.get("FINANCE_DB_PATH")
    if override:
        return Path(override)

    default = Path(DEFAULT_DB_PATH)
    if default.parent.is_dir() and os.access(default.parent, os.W_OK):
        return default
    return Path.cwd() / "finance.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Eine Verbindung mit den für uns wichtigen PRAGMAs öffnen."""
    connection = sqlite3.connect(path or get_db_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def transaction(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Verbindung mit automatischem Commit/Rollback und Close."""
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(path: Path | None = None) -> None:
    """Alle noch nicht angewendeten Migrationen der Reihe nach ausführen."""
    db_path = path or get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with transaction(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            number = int(migration.stem.split("_", 1)[0])
            if number > version:
                connection.executescript(migration.read_text(encoding="utf-8"))
                version = number

    # executescript committet implizit, daher user_version danach separat setzen.
    with transaction(db_path) as connection:
        connection.execute(f"PRAGMA user_version = {version}")

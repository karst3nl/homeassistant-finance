"""Konsistenten SQLite-Snapshot für Home-Assistant-Backups erzeugen.

Der Supervisor ruft vor einem Backup ``backup_pre`` und danach ``backup_post``
auf. Während die Anwendung läuft, dürfen die WAL-Dateien nicht einfach
kopiert werden; ``sqlite3.Connection.backup()`` erzeugt dagegen einen
sauberen Snapshot, der mitgesichert wird.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from db import get_db_path

SUFFIX = ".snapshot"


def snapshot_path(db_path: Path) -> Path:
    """Pfad des Snapshots neben der lebenden Datenbank."""
    return db_path.with_name(db_path.name + SUFFIX)


def create_snapshot() -> None:
    """Snapshot aus der laufenden Datenbank schreiben (idempotent)."""
    db_path = get_db_path()
    if not db_path.exists():
        return
    target = snapshot_path(db_path)
    target.unlink(missing_ok=True)

    # Normal öffnen: eine WAL-Datenbank lässt sich ohne vorhandene -shm-Datei
    # nicht zuverlässig read-only öffnen. Es werden keine Daten verändert.
    source = sqlite3.connect(db_path)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def remove_snapshot() -> None:
    """Snapshot nach dem Backup wieder entfernen."""
    snapshot_path(get_db_path()).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["pre"]:
        create_snapshot()
    elif args == ["post"]:
        remove_snapshot()
    else:
        print("Aufruf: backup.py pre|post", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

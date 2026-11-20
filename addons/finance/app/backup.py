"""Konsistente SQLite-Kopien: HA-Snapshot und herunterladbare Backups.

Der Supervisor ruft vor einem Backup ``backup_pre`` und danach ``backup_post``
auf. Während die Anwendung läuft, dürfen die WAL-Dateien nicht einfach
kopiert werden; ``sqlite3.Connection.backup()`` erzeugt dagegen einen
sauberen Snapshot. Die gleiche Funktion schreibt auch die Backups, die in
der Oberfläche heruntergeladen werden können.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from db import get_db_path

SUFFIX = ".snapshot"
BACKUP_DIR_NAME = "backups"
BACKUP_NAME_RE = re.compile(r"^finance-(\d{8})-(\d{6})-[0-9a-f]{8}\.db$")


def snapshot_path(db_path: Path) -> Path:
    """Pfad des Snapshots neben der lebenden Datenbank."""
    return db_path.with_name(db_path.name + SUFFIX)


def backup_dir(db_path: Path | None = None) -> Path:
    """Verzeichnis der herunterladbaren Backups (in HA: /data/backups)."""
    return (db_path or get_db_path()).parent / BACKUP_DIR_NAME


def export_database(target: Path, db_path: Path | None = None) -> None:
    """Konsistente Kopie der Datenbank nach `target` schreiben.

    Über eine temporäre Datei, damit eine fehlgeschlagene Kopie kein halbes
    Backup zurücklässt.
    """
    source_path = db_path or get_db_path()
    if not source_path.exists():
        raise FileNotFoundError(f"Datenbank {source_path} existiert nicht")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        # Normal öffnen: eine WAL-Datenbank lässt sich ohne vorhandene -shm-Datei
        # nicht zuverlässig read-only öffnen. Es werden keine Daten verändert.
        source = sqlite3.connect(source_path)
        try:
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def create_snapshot() -> None:
    """Snapshot aus der laufenden Datenbank schreiben (idempotent)."""
    db_path = get_db_path()
    if not db_path.exists():
        return
    export_database(snapshot_path(db_path), db_path)


def remove_snapshot() -> None:
    """Snapshot nach dem Backup wieder entfernen."""
    snapshot_path(get_db_path()).unlink(missing_ok=True)


def create_backup(db_path: Path | None = None) -> Path:
    """Neues herunterladbares Backup anlegen und seinen Pfad zurückgeben."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = backup_dir(db_path) / f"finance-{stamp}-{uuid4().hex[:8]}.db"
    export_database(target, db_path)
    return target


def list_backups(db_path: Path | None = None) -> list[dict]:
    """Gespeicherte Backups, neuestes zuerst."""
    directory = backup_dir(db_path)
    if not directory.is_dir():
        return []

    items: list[dict] = []
    for path in directory.iterdir():
        match = BACKUP_NAME_RE.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        created = datetime.strptime(f"{match.group(1)}-{match.group(2)}", "%Y%m%d-%H%M%S")
        items.append(
            {
                "name": path.name,
                "created": created.strftime("%d.%m.%Y %H:%M") + " UTC",
                "size_bytes": path.stat().st_size,
            }
        )
    return sorted(items, key=lambda item: item["name"], reverse=True)


def backup_path(name: str, db_path: Path | None = None) -> Path | None:
    """Nur Dateien mit einem von uns erzeugten Namen freigeben."""
    if not BACKUP_NAME_RE.fullmatch(name):
        return None
    candidate = backup_dir(db_path) / name
    return candidate if candidate.is_file() else None


def delete_backup(name: str, db_path: Path | None = None) -> bool:
    path = backup_path(name, db_path)
    if path is None:
        return False
    path.unlink()
    return True


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

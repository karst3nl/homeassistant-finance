"""Prüft die Mindestanforderungen an die Add-on-Konfiguration.

Läuft in CI und lokal: python scripts/validate_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "finance"
REQUIRED_KEYS = (
    "name",
    "version",
    "slug",
    "description",
    "url",
    "arch",
    "init",
    "ingress",
    "ingress_port",
)


def main() -> int:
    errors: list[str] = []

    configs = [path for path in ROOT.rglob("config.yaml") if ".git" not in path.parts]
    if len(configs) != 1:
        errors.append(f"Erwartet genau eine config.yaml, gefunden: {len(configs)}")

    config_path = ADDON / "config.yaml"
    if not config_path.is_file():
        errors.append(f"Fehlt: {config_path.relative_to(ROOT)}")
        return report(errors)

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for key in REQUIRED_KEYS:
        if key not in config:
            errors.append(f"config.yaml: fehlt '{key}'")

    if not isinstance(config.get("version"), str):
        errors.append("config.yaml: 'version' muss ein String sein (z. B. \"0.0.1\")")
    if config.get("init") is not False:
        errors.append("config.yaml: 'init' muss false sein (S6-Overlay im Base-Image)")
    if config.get("ingress") is not True:
        errors.append("config.yaml: 'ingress' muss true sein")
    if config.get("ingress_port") != 8099:
        errors.append("config.yaml: 'ingress_port' muss 8099 sein")
    if config.get("homeassistant_api") is True or config.get("hassio_api") is True:
        errors.append("config.yaml: keine HA-/Supervisor-API-Rechte in dieser Phase")
    if config.get("ports"):
        errors.append("config.yaml: keine Ports veröffentlichen (Ingress-only)")
    image = config.get("image")
    if not isinstance(image, str) or not image.startswith("ghcr.io/"):
        errors.append("config.yaml: 'image' muss auf ghcr.io/ verweisen")
    elif "YOUR_GITHUB_USER" in image:
        print("Hinweis: YOUR_GITHUB_USER muss vor dem Release ersetzt werden.")
    if config.get("backup_pre") != "python3 /app/backup.py pre":
        errors.append("config.yaml: 'backup_pre' muss den SQLite-Snapshot erzeugen")
    if config.get("backup_post") != "python3 /app/backup.py post":
        errors.append("config.yaml: 'backup_post' muss den Snapshot entfernen")

    arch = config.get("arch")
    if not isinstance(arch, list) or set(arch) != {"aarch64", "amd64"}:
        errors.append("config.yaml: 'arch' muss [aarch64, amd64] sein")

    repo_path = ROOT / "repository.yaml"
    if not repo_path.is_file():
        errors.append("Fehlt: repository.yaml")
    else:
        repository = yaml.safe_load(repo_path.read_text(encoding="utf-8")) or {}
        if "name" not in repository:
            errors.append("repository.yaml: fehlt 'name'")

    for filename in ("Dockerfile", "README.md", "icon.png"):
        if not (ADDON / filename).is_file():
            errors.append(f"Fehlt: addons/finance/{filename}")
    for language in ("de", "en"):
        if not (ADDON / "translations" / f"{language}.yaml").is_file():
            errors.append(f"Fehlt: addons/finance/translations/{language}.yaml")

    return report(errors)


def report(errors: list[str]) -> int:
    if errors:
        print("Validierung fehlgeschlagen:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Konfiguration gültig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

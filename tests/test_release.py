"""Konsistenzprüfung der Release-Metadaten.

Verhindert, dass Version, Image, Repository-URL, Übersetzungen und Doku
auseinanderlaufen – gerade wenn der Release später von Hand vorbereitet wird.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "finance"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_version_ist_in_config_und_pyproject_gleich() -> None:
    config = load_yaml(ADDON / "config.yaml")
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    assert config["version"] == pyproject["project"]["version"]


def test_image_passt_zur_repository_url() -> None:
    config = load_yaml(ADDON / "config.yaml")
    repository = load_yaml(ROOT / "repository.yaml")

    url = repository["url"].rstrip("/")
    prefix, owner, repo = url.split("/")[-3:]
    assert prefix == "https:" or prefix == "github.com"
    assert owner == repository["maintainer"]
    assert config["url"] == url
    assert config["image"] == f"ghcr.io/{owner}/finance"
    assert repo == "homeassistant-finance"


def test_badge_enthält_die_repository_url() -> None:
    repository = load_yaml(ROOT / "repository.yaml")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    encoded = quote(repository["url"].rstrip("/"), safe="")
    assert f"repository_url={encoded}" in readme


def test_changelog_enthält_die_aktuelle_version() -> None:
    config = load_yaml(ADDON / "config.yaml")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{config['version']}]" in changelog


def test_übersetzungen_decken_alle_optionen_ab() -> None:
    config = load_yaml(ADDON / "config.yaml")
    options = set(config.get("options", {}))

    for language in ("de", "en"):
        translations = load_yaml(ADDON / "translations" / f"{language}.yaml")
        configuration = translations.get("configuration", {})
        assert set(configuration) == options, language
        for value in configuration.values():
            assert value.get("name"), language
            assert value.get("description"), language


def test_dockerfile_ist_gepinnt_und_startet_ueber_run_sh() -> None:
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM ghcr.io/home-assistant/base-python:3.14-alpine3.24" in dockerfile
    assert ":latest" not in dockerfile
    assert "RUN chmod +x /app/run.sh" in dockerfile
    assert 'CMD ["/app/run.sh"]' in dockerfile

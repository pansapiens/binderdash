import os
from pathlib import Path

from backend.runtime_paths import static_root


def test_static_root_default(monkeypatch):
    monkeypatch.delenv("BINDERDASH_STATIC_ROOT", raising=False)
    root = static_root()
    assert root.name == "static"
    assert root.parent.name == "backend"


def test_static_root_override(monkeypatch, tmp_path: Path):
    override = tmp_path / "custom-static"
    override.mkdir()
    monkeypatch.setenv("BINDERDASH_STATIC_ROOT", str(override))
    assert static_root() == override

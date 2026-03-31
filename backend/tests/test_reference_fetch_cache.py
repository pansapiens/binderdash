"""In-process LRU cache for fetch_reference_structure (RCSB / PDBTM / URL)."""

import json
from unittest.mock import MagicMock

import pytest

import backend.util.superpose as superpose

_MIN_PDBTM_ENTRY = {
    "additional_entry_annotations": {
        "membrane": {
            "radius": 12.0,
            "transformation_matrix": {
                "rowx": {"x": 1, "y": 0, "z": 0, "t": 0},
                "rowy": {"x": 0, "y": 1, "z": 0, "t": 0},
                "rowz": {"x": 0, "y": 0, "z": 1, "t": 0},
            },
        }
    }
}


@pytest.fixture(autouse=True)
def clear_reference_fetch_cache() -> None:
    superpose._REFERENCE_FETCH_CACHE.clear()
    yield
    superpose._REFERENCE_FETCH_CACHE.clear()


def test_pdb_id_fetch_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_get(url: str, timeout: int) -> MagicMock:
        urls.append(url)
        r = MagicMock()
        r.content = b"mmcif-bytes"
        r.raise_for_status = MagicMock()
        return r

    monkeypatch.setattr(superpose.requests, "get", fake_get)
    b1, fmt1, m1 = superpose.fetch_reference_structure("1crn")
    b2, fmt2, m2 = superpose.fetch_reference_structure("1crn")
    assert len(urls) == 1
    assert "1crn" in urls[0].lower()
    assert b1 == b2 == b"mmcif-bytes"
    assert fmt1 == fmt2 == "mmcif"
    assert m1 is None and m2 is None


def test_pdbtm_entry_and_json_url_share_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []
    payload = json.dumps(_MIN_PDBTM_ENTRY).encode("utf-8")

    def fake_get(url: str, timeout: int) -> MagicMock:
        urls.append(url)
        r = MagicMock()
        if "pdbtm" in url and url.endswith(".json"):
            r.content = payload
        elif "files.rcsb.org" in url:
            r.content = b"cif-bytes"
        else:
            r.content = b""
        r.raise_for_status = MagicMock()
        return r

    monkeypatch.setattr(superpose.requests, "get", fake_get)
    superpose.fetch_reference_structure("https://pdbtm.unitmp.org/entry/6lfl")
    superpose.fetch_reference_structure(
        "https://pdbtm.unitmp.org/api/v1/entry/6lfl.json"
    )
    json_calls = [u for u in urls if u.endswith(".json")]
    cif_calls = [u for u in urls if "files.rcsb.org" in u]
    assert len(json_calls) == 1
    assert len(cif_calls) == 1


def test_arbitrary_url_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = "https://example.org/ref.cif"
    urls: list[str] = []

    def fake_get(url: str, timeout: int) -> MagicMock:
        urls.append(url)
        r = MagicMock()
        r.content = b"cif-data"
        r.raise_for_status = MagicMock()
        return r

    monkeypatch.setattr(superpose.requests, "get", fake_get)
    superpose.fetch_reference_structure(ref)
    superpose.fetch_reference_structure(ref)
    assert urls == [ref]

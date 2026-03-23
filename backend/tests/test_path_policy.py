from pathlib import Path

from backend.path_policy import is_allowed_path, resolved_base_dirs


def test_resolved_base_dirs_skips_empty(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    bases = resolved_base_dirs(["", "  ", str(tmp_path / "data")])
    assert len(bases) == 1
    assert bases[0] == (tmp_path / "data").resolve()


def test_is_allowed_path_relative_base_absolute_candidate(tmp_path: Path) -> None:
    run_root = tmp_path / "example_runs" / "boltzgen-nanobody"
    run_root.mkdir(parents=True)
    rel_base = str(tmp_path / "example_runs")
    abs_candidate = str(run_root.resolve())
    assert is_allowed_path(abs_candidate, [rel_base])


def test_is_allowed_path_rejects_outside(tmp_path: Path) -> None:
    allowed = tmp_path / "a"
    other = tmp_path / "b"
    allowed.mkdir()
    other.mkdir()
    assert is_allowed_path(str(other / "x"), [str(allowed)]) is False

from pathlib import Path

from desktop.config import DesktopConfig, load_config, save_config, update_run_base_dirs_in_file


def test_desktop_config_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "desktop.json"
    config = DesktopConfig(run_base_dirs=["/data/runs"])
    save_config(config, cfg_path)
    loaded = load_config(cfg_path)
    assert loaded.run_base_dirs == ["/data/runs"]


def test_update_run_base_dirs_in_file(tmp_path: Path):
    cfg_path = tmp_path / "desktop.json"
    update_run_base_dirs_in_file(["/a", "/b"], cfg_path)
    loaded = load_config(cfg_path)
    assert loaded.run_base_dirs == ["/a", "/b"]

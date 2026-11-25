from pathlib import Path, PureWindowsPath

from app.config import Settings


def test_browser_channel_default():
    assert Settings(_platform="darwin").browser_channel == "chrome"
    assert Settings(_platform="win32").browser_channel == "msedge"


def test_data_dir_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings(data_dir=Path("rel/dir"), _platform="darwin")
    assert s.data_dir.is_absolute()
    assert s.data_dir == (tmp_path / "rel/dir").resolve()


def test_data_dir_default_windows(monkeypatch):
    monkeypatch.delenv("DD_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\X")
    s = Settings(_platform="win32")
    assert PureWindowsPath(str(s.data_dir)) == PureWindowsPath("C:\\X\\doudian-multishop")


def test_data_dir_default_non_windows_is_repo_data(monkeypatch):
    monkeypatch.delenv("DD_DATA_DIR", raising=False)
    s = Settings(_platform="darwin")
    assert s.data_dir.name == "data"
    assert s.data_dir.is_absolute()


def test_defaults():
    s = Settings(_platform="darwin")
    assert (s.host, s.port) == ("127.0.0.1", 8787)
    assert s.egress_echo_url == "https://ifconfig.me/ip"
    assert s.dev_mode is False and s.dry_run is False

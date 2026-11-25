"""curl_cffi 的 CA 证书路径适配：中文目录会让 libcurl 报 error 77。"""

import os
from pathlib import Path

from app.shared.curl_ca import ENV_KEY, install_ca_bundle


def test_copies_bundle_and_points_env(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    target = install_ca_bundle(tmp_path)

    assert target == tmp_path / "cacert.pem"
    assert target.is_file() and target.stat().st_size > 0
    assert os.environ[ENV_KEY] == str(target)


def test_reuses_same_size_copy(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    first = install_ca_bundle(tmp_path)
    stamp = first.stat().st_mtime_ns
    install_ca_bundle(tmp_path)

    assert first.stat().st_mtime_ns == stamp  # 未重写


def test_returns_none_for_non_ascii_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    chinese = tmp_path / "抖店"

    assert install_ca_bundle(chinese) is None
    assert ENV_KEY not in os.environ
    assert not (chinese / "cacert.pem").exists()


def test_keeps_usable_existing_env(tmp_path, monkeypatch):
    existing = tmp_path / "mine.pem"
    existing.write_text("x", encoding="ascii")
    monkeypatch.setenv(ENV_KEY, str(existing))

    assert install_ca_bundle(tmp_path) == existing
    assert not (tmp_path / "cacert.pem").exists()


def test_rebuilds_source_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    target = Path(install_ca_bundle(tmp_path))
    target.write_text("stale", encoding="ascii")
    install_ca_bundle(tmp_path)

    assert target.stat().st_size > len("stale")

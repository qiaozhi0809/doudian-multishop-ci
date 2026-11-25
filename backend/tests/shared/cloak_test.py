"""CloakBrowser 指纹种子：每店固定、越界重建、不可写时抛错。"""

import sys

import pytest

from app.shared.cloak import SEED_MAX, SEED_MIN, apply_env, cloak_launch_args, get_or_create_seed


def test_creates_seed_once_and_reuses_it(tmp_path):
    first = get_or_create_seed(tmp_path)
    second = get_or_create_seed(tmp_path)

    assert first == second
    assert SEED_MIN <= first <= SEED_MAX


def test_rebuilds_out_of_range_seed(tmp_path):
    (tmp_path / ".cloak-seed").write_text("5", encoding="ascii")

    seed = get_or_create_seed(tmp_path)

    assert SEED_MIN <= seed <= SEED_MAX
    assert (tmp_path / ".cloak-seed").read_text(encoding="ascii").strip() == str(seed)


def test_rebuilds_garbage_seed(tmp_path):
    (tmp_path / ".cloak-seed").write_text("not-a-number", encoding="ascii")

    seed = get_or_create_seed(tmp_path)

    assert SEED_MIN <= seed <= SEED_MAX


def test_two_profiles_get_different_seeds(tmp_path):
    a = get_or_create_seed(tmp_path / "1")
    b = get_or_create_seed(tmp_path / "2")

    assert a != b


def test_launch_args_contains_fixed_fingerprint():
    assert cloak_launch_args(12345) == [
        "--fingerprint=12345",
        "--fingerprint-platform=windows",
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows 目录只读语义不同于 POSIX")
def test_raises_when_profile_not_writable(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)

    try:
        with pytest.raises(OSError):
            get_or_create_seed(ro)
    finally:
        ro.chmod(0o700)


def test_new_seed_avoids_sibling_collision(tmp_path, monkeypatch):
    import random

    sibling = tmp_path / "1"
    sibling.mkdir()
    (sibling / ".cloak-seed").write_text("12345", encoding="ascii")

    calls = iter([12345, 54321])
    monkeypatch.setattr(random, "randint", lambda a, b: next(calls))

    seed = get_or_create_seed(tmp_path / "2")

    assert seed == 54321


def test_copied_profile_gets_a_different_seed(tmp_path):
    import shutil

    source = tmp_path / "1"
    source.mkdir()
    original = get_or_create_seed(source)

    copy = tmp_path / "2"
    shutil.copytree(source, copy)

    assert get_or_create_seed(copy) != original


def test_apply_env_pins_cache_dir_and_disables_auto_update(monkeypatch, tmp_path):
    import os

    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_AUTO_UPDATE", raising=False)

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_CACHE_DIR"] == str(tmp_path)
    assert os.environ["CLOAKBROWSER_AUTO_UPDATE"] == "false"


def test_apply_env_forces_auto_update_off_even_if_preset(monkeypatch, tmp_path):
    """禁用自动更新是硬约束：外部把它设成 true，调用后也必须变 false。"""
    import os

    monkeypatch.setenv("CLOAKBROWSER_AUTO_UPDATE", "true")

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_AUTO_UPDATE"] == "false"


def test_apply_env_keeps_explicit_cache_dir(monkeypatch, tmp_path):
    """缓存目录是用户可配置项，显式设置必须被尊重。"""
    import os

    custom = str(tmp_path / "custom")
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", custom)

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_CACHE_DIR"] == custom

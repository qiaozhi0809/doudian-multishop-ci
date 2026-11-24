import stat
import sys

import pytest

from app.shared.secret_box import DevKeyBox, DpapiBox, make_secret_box

PLAIN = b"cookie-blob-" + b"x" * 8


def test_dev_box_roundtrip(tmp_path):
    box = DevKeyBox(tmp_path / "dev.key")
    blob = box.encrypt(PLAIN)
    assert PLAIN not in blob
    assert box.decrypt(blob) == PLAIN


def test_dev_box_reuses_key(tmp_path):
    key_file = tmp_path / "dev.key"
    blob = DevKeyBox(key_file).encrypt(PLAIN)
    assert DevKeyBox(key_file).decrypt(blob) == PLAIN


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX 权限位")
def test_dev_key_file_mode_0600(tmp_path):
    DevKeyBox(tmp_path / "dev.key")
    mode = stat.S_IMODE((tmp_path / "dev.key").stat().st_mode)
    assert mode == 0o600


def test_factory_non_windows(tmp_path):
    box = make_secret_box(tmp_path, platform="darwin")
    assert isinstance(box, DevKeyBox)
    assert (tmp_path / "dev.key").exists()
    assert box.decrypt(box.encrypt(PLAIN)) == PLAIN


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI 仅 Windows，由 CI windows job 覆盖")
def test_dpapi_roundtrip(tmp_path):
    box = make_secret_box(tmp_path, platform="win32")
    assert isinstance(box, DpapiBox)
    blob = box.encrypt(PLAIN)
    assert PLAIN not in blob
    assert box.decrypt(blob) == PLAIN

import pytest

from app.cli import main
from app.config import Settings
from app.service.auth import AuthService
from app.store.db import make_engine
from app.store.migrate import upgrade_to_head
from tests.conftest import FAST_HASHER

OLD = "old_" + "p" * 8
NEW = "new_" + "q" * 8


@pytest.fixture
def settings(tmp_path):
    s = Settings(data_dir=tmp_path / "data")
    s.data_dir.mkdir()
    upgrade_to_head(s.data_dir / "app.db")
    engine = make_engine(s.data_dir / "app.db")
    AuthService(engine, hasher=FAST_HASHER).setup("admin", OLD)
    engine.dispose()
    return s


def _prompt(*answers):
    it = iter(answers)
    return lambda _label: next(it)


def _login(settings, password):
    engine = make_engine(settings.data_dir / "app.db")
    try:
        return AuthService(engine, hasher=FAST_HASHER).login("admin", password)
    finally:
        engine.dispose()


def test_reset_admin_changes_password_and_revokes_sessions(settings):
    token = _login(settings, OLD)
    code = main(["reset-admin", "--username", "admin"], settings=settings, prompt=_prompt(NEW, NEW))
    assert code == 0
    assert _login(settings, NEW)
    engine = make_engine(settings.data_dir / "app.db")
    assert AuthService(engine).current_user(token) is None
    engine.dispose()


def test_reset_admin_rejects_mismatch_short_and_unknown(settings, capsys):
    argv = ["reset-admin", "--username", "admin"]
    assert main(argv, settings=settings, prompt=_prompt(NEW, "other_" + "z" * 4)) == 1
    assert main(argv, settings=settings, prompt=_prompt("short", "short")) == 1
    assert main(["reset-admin", "--username", "ghost"], settings=settings,
                prompt=_prompt(NEW, NEW)) == 1
    assert NEW not in capsys.readouterr().err
    assert _login(settings, OLD)  # 没改动


def test_reset_admin_requires_initialized_db(tmp_path):
    s = Settings(data_dir=tmp_path / "empty")
    assert main(["reset-admin", "--username", "a"], settings=s, prompt=_prompt(NEW, NEW)) == 1

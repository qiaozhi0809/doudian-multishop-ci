"""本机命令行：忘记管理员密码时在出单机上重置。

用法：python -m app.cli reset-admin --username <name>
"""

import argparse
import getpass
import sys
from collections.abc import Callable

from app.config import Settings
from app.service.auth import AuthService, PasswordRejected
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import upgrade_to_head


def reset_admin(username: str, settings: Settings, prompt: Callable[[str], str]) -> int:
    new = prompt("新密码: ")
    if new != prompt("再输入一次: "):
        print("两次输入不一致", file=sys.stderr)
        return 1
    db_path = settings.data_dir / DB_FILE_NAME
    if not db_path.exists():
        print("尚未初始化：请先启动后台并创建管理员", file=sys.stderr)
        return 1
    upgrade_to_head(db_path)
    engine = make_engine(db_path)
    try:
        AuthService(engine).reset_password(username, new)
    except PasswordRejected as e:
        print(str(e), file=sys.stderr)
        return 1
    except LookupError as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print("已重置，该账号的所有登录会话已失效")
    return 0


def main(
    argv: list[str] | None = None, *, settings: Settings | None = None,
    prompt: Callable[[str], str] = getpass.getpass,
) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="command", required=True)
    reset = sub.add_parser("reset-admin", help="重置管理员密码")
    reset.add_argument("--username", required=True)
    args = ap.parse_args(argv)
    return reset_admin(args.username, settings or Settings(), prompt)


if __name__ == "__main__":
    sys.exit(main())

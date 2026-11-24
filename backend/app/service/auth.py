"""本机管理员登录（backend 5.16）：argon2id 口令、令牌只存 SHA-256、失败锁定、审计。"""

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import Engine

from app.domain.audit import CallRecord
from app.domain.auth_rules import (
    SESSION_ABSOLUTE_LIMIT,
    after_failure,
    session_alive,
    validate_password,
)
from app.domain.errors import NotFound
from app.store import admin_store, audit_store

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
TOKEN_BYTES = 32
UNKNOWN_ACTOR = "unknown"


class AuthError(Exception):
    """登录相关错误的基类。"""


class NotAuthenticated(AuthError):
    pass


class InvalidCredentials(AuthError):
    """账号或密码错误（两种情况对外不作区分）。"""


class AccountLocked(AuthError):
    pass


class AlreadyInitialized(AuthError):
    pass


class PasswordRejected(AuthError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("；".join(problems))
        self.problems = problems


def _utc_now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(
        self, engine: Engine, clock: Callable[[], datetime] = _utc_now,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._hasher = hasher or PasswordHasher()
        self._dummy_hash = self._hasher.hash("dummy-password-for-timing")

    # ---- 状态 ----

    def is_initialized(self) -> bool:
        with self._engine.connect() as conn:
            return admin_store.count_users(conn) > 0

    def current_user(self, token: str | None) -> str | None:
        """校验会话并刷新最近活动时间；无效或过期返回 None（过期会话顺带删除）。"""
        if not token:
            return None
        now = self._clock()
        key = hash_token(token)
        with self._engine.begin() as conn:
            session = admin_store.get_session(conn, key)
            if session is None:
                return None
            if not session_alive(session["created_at"], session["last_seen_at"], now):
                admin_store.delete_session(conn, key)
                return None
            admin_store.touch_session(conn, key, now.strftime(_ISO_FMT))
            user = admin_store.get_user(conn, session["user_id"])
        return user["username"] if user else None

    # ---- 创建 / 登录 / 登出 ----

    def setup(self, username: str, password: str) -> None:
        problems = validate_password(password)
        if problems:
            raise PasswordRejected(problems)
        now = self._now_iso()
        with self._engine.begin() as conn:
            if admin_store.count_users(conn) > 0:
                raise AlreadyInitialized("管理员账号已创建")
            admin_store.create_user(conn, username, self._hasher.hash(password), now)

    def login(self, username: str, password: str) -> str:
        now = self._clock()
        error: AuthError | None = None
        token = ""
        # 失败计数与审计必须先提交再抛异常，否则会随事务回滚
        with self._engine.begin() as conn:
            user = admin_store.get_user_by_name(conn, username)
            if user is None:
                self._verify(self._dummy_hash, password)  # 不存在时也做一次校验，抹平耗时差
                self._audit(conn, "auth.login_failed", UNKNOWN_ACTOR, now, "failed")
                error = InvalidCredentials("账号或密码错误")
            elif user["locked_until"] and user["locked_until"] > now.strftime(_ISO_FMT):
                self._audit(conn, "auth.login_failed", username, now, "failed", "locked")
                error = AccountLocked("尝试次数过多，账号已锁定，请 5 分钟后再试")
            elif not self._verify(user["password_hash"], password):
                count, locked_until = after_failure(user["failed_attempts"], now)
                admin_store.set_failures(conn, user["id"], count, locked_until)
                self._audit(conn, "auth.login_failed", username, now, "failed")
                error = InvalidCredentials("账号或密码错误")
            else:
                admin_store.set_failures(conn, user["id"], 0, None)
                token = self._new_session(conn, user["id"], now)
                self._audit(conn, "auth.login_ok", username, now)
        if error is not None:
            raise error
        return token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        now = self._clock()
        with self._engine.begin() as conn:
            session = admin_store.get_session(conn, hash_token(token))
            if session is None:
                return
            user = admin_store.get_user(conn, session["user_id"])
            admin_store.delete_session(conn, hash_token(token))
            self._audit(conn, "auth.logout", user["username"] if user else UNKNOWN_ACTOR, now)

    # ---- 改密 / 重置 ----

    def change_password(self, token: str, old_password: str, new_password: str) -> None:
        """校验旧密码；改完后该账号的其他会话全部失效，当前会话保留。"""
        now = self._clock()
        with self._engine.begin() as conn:
            session = admin_store.get_session(conn, hash_token(token))
            user = admin_store.get_user(conn, session["user_id"]) if session else None
            if user is None:
                raise NotAuthenticated("未登录")
            if not self._verify(user["password_hash"], old_password):
                raise InvalidCredentials("旧密码错误")
            problems = validate_password(new_password)
            if problems:
                raise PasswordRejected(problems)
            admin_store.set_password(
                conn, user["id"], self._hasher.hash(new_password), now.strftime(_ISO_FMT))
            admin_store.delete_user_sessions(conn, user["id"], except_token_hash=hash_token(token))
            self._audit(conn, "auth.password_changed", user["username"], now)

    def reset_password(self, username: str, new_password: str) -> None:
        """命令行重置：设新密码、解锁、使该账号全部会话失效。"""
        problems = validate_password(new_password)
        if problems:
            raise PasswordRejected(problems)
        now = self._clock()
        with self._engine.begin() as conn:
            user = admin_store.get_user_by_name(conn, username)
            if user is None:
                raise NotFound(f"管理员账号不存在: {username}")
            admin_store.set_password(
                conn, user["id"], self._hasher.hash(new_password), now.strftime(_ISO_FMT))
            admin_store.delete_user_sessions(conn, user["id"])
            self._audit(conn, "auth.password_reset", username, now)

    # ---- 内部 ----

    def _now_iso(self) -> str:
        return self._clock().strftime(_ISO_FMT)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def _new_session(self, conn, user_id: int, now: datetime) -> str:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        admin_store.create_session(
            conn, hash_token(token), user_id, now.strftime(_ISO_FMT),
            (now + SESSION_ABSOLUTE_LIMIT).strftime(_ISO_FMT),
        )
        return token

    def _audit(
        self, conn, action: str, actor: str, now: datetime, result: str = "ok", detail: str = ""
    ) -> None:
        # 只记动作与账号，不记任何口令
        audit_store.insert(conn, CallRecord(
            shop_id=None, action=action, actor=actor, req_summary={},
            resp_summary={"detail": detail} if detail else {}, result=result, duration_ms=0,
        ), now.strftime(_ISO_FMT))


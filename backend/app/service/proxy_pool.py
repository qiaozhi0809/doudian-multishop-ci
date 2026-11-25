"""代理池：列表、批量导入、删除、旧数据补算。

代理 URL（含账号密码）只以 SecretBox 密文落库；响应、日志、审计只出现 主机:端口 与行号，
导入失败不回显原文。与 EgressService 互不依赖（共用 egress 模块级名字）。
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import Engine

from app.domain.audit import CallRecord
from app.domain.egress_rules import (
    display_proxy,
    expiry_state,
    join_proxy_url,
    parse_provider_line,
    proxy_identity,
    split_proxy_url,
    validate_proxy_url,
)
from app.domain.errors import NotFound
from app.service.egress import ProxyPoolInUse, reset_shop_egress
from app.service.egress_probe import Probe, ProbeReason
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.shared.secret_box import SecretBox
from app.store import audit_store, proxy_pool_store, shop_store

log = structlog.get_logger()

MAX_IMPORT_LINES = 500
MAX_PORT = 65535
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class ImportSummary:
    added: int
    skipped: int
    failed: int
    failures: list[tuple[int, str]]  # (行号, 原因)；不含原文


@dataclass(frozen=True)
class CheckResult:
    ip: str | None
    reason: ProbeReason | None
    elapsed_ms: int
    ip_in_use_by: dict | None  # {"shop_id", "shop_name"}：该 IP 已被另一家启用店铺使用


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProxyPoolService:
    def __init__(
        self, engine: Engine, box: SecretBox, events: EventBus, probe: Probe,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._box = box
        self._events = events
        self._probe = probe
        self._clock = clock

    def list_view(self) -> list[dict[str, Any]]:
        now = self._clock()
        with self._engine.connect() as conn:
            rows = proxy_pool_store.list_with_usage(conn)
        return [{
            "id": r["id"],
            "proxy_display": r["proxy_display"],
            "expires_at": r["expires_at"],
            "expiry_state": expiry_state(r["expires_at"], now),
            "in_use_by": (
                {"shop_id": r["in_use_shop_id"], "shop_name": r["in_use_shop_name"]}
                if r["in_use_shop_id"] is not None else None
            ),
            "last_checked_at": r["last_checked_at"],
            "last_check_ip": r["last_check_ip"],
        } for r in rows]

    def import_text(self, text: str, actor: str) -> ImportSummary:
        """逐行尽力导入；空行跳过；重复（库内或同批）计为 skipped。"""
        # 只按 \n 切分、每行去掉 \r：行号与编辑器所见一致（splitlines 会多切 \x0b \x0c 等）
        lines = [
            (n, raw.rstrip("\r")) for n, raw in enumerate(text.split("\n"), start=1)
            if raw.strip()
        ]
        if len(lines) > MAX_IMPORT_LINES:
            raise ValueError(f"单次最多导入 {MAX_IMPORT_LINES} 行")
        now = self._clock().strftime(_ISO_FMT)
        added = skipped = 0
        failures: list[tuple[int, str]] = []
        with self._engine.begin() as conn:
            for n, raw in lines:
                try:
                    url, expiry = parse_provider_line(raw)
                except ValueError as e:  # 消息不含账号密码
                    failures.append((n, str(e)))
                    continue
                identity = proxy_identity(url)
                if proxy_pool_store.get_by_identity(conn, identity) is not None:
                    skipped += 1  # 库内已有，或同批更早的行刚插入
                    continue
                proxy_pool_store.upsert(
                    conn, identity=identity, proxy_url=self._box.encrypt(url.encode()),
                    proxy_display=display_proxy(url), expires_at=expiry, now=now)
                added += 1
            audit_store.insert(conn, CallRecord(
                None, "proxy_pool.import", actor, {"lines": len(lines)},
                {"added": added, "skipped": skipped, "failed": len(failures),
                 "failed_lines": [n for n, _ in failures]},
                "ok", 0), now)
        return ImportSummary(added, skipped, len(failures), failures)

    def delete(self, pool_id: int, actor: str) -> None:
        """被启用店铺占用则拒绝；只剩停用引用者时先解绑再删（同一事务）。"""
        now = self._clock().strftime(_ISO_FMT)
        with self._engine.begin() as conn:
            item = proxy_pool_store.get(conn, pool_id)
            if item is None:
                raise NotFound(f"代理池项不存在: {pool_id}")
            referrers = proxy_pool_store.referrers(conn, pool_id)
            for r in referrers:
                if r["status"] != "disabled":
                    raise ProxyPoolInUse(r["name"])
            for r in referrers:
                shop_store.set_egress(conn, r["id"], now, proxy_pool_id=None)
            proxy_pool_store.delete(conn, pool_id)
            audit_store.insert(conn, CallRecord(
                None, "proxy_pool.delete", actor,
                {"pool_id": pool_id, "proxy_display": item["proxy_display"]},
                {"unbound_shops": [r["id"] for r in referrers]}, "ok", 0), now)

    def rehash_legacy(self) -> int:
        """把迁移留下的 legacy:* 池项改成真实 identity；撞车则保留占位并告警。返回补算条数。"""
        now = self._clock().strftime(_ISO_FMT)
        done = 0
        with self._engine.begin() as conn:
            for item in proxy_pool_store.list_legacy(conn):
                try:
                    url = self._box.decrypt(item["proxy_url"]).decode()
                except Exception:  # noqa: BLE001 单项解密失败不得拖垮启动；日志只记 pool_id
                    log.warning("proxy_pool.rehash_decrypt_failed", pool_id=item["id"])
                    continue
                identity = proxy_identity(url)
                if proxy_pool_store.get_by_identity(conn, identity) is not None:
                    log.warning(
                        "proxy_pool.rehash_clash", pool_id=item["id"],
                        proxy_display=item["proxy_display"])
                    continue
                proxy_pool_store.update(conn, item["id"], now, identity=identity)
                done += 1
        return done

    def update(
        self, pool_id: int, *, host: str | None = None, port: int | None = None,
        username: str | None = None, password: str | None = None,
        expires_at: str | None = None, actor: str,
    ) -> None:
        """改池项；None 表示不改。出口身份变了则复位所有引用店铺，提交后发事件。"""
        if port is not None and not 1 <= port <= MAX_PORT:
            raise ValueError("端口必须在 1-65535 之间")
        if expires_at is not None:
            try:
                datetime.strptime(expires_at, "%Y-%m-%d")
            except ValueError:
                raise ValueError("到期日格式应为 YYYY-MM-DD") from None
        now = self._clock().strftime(_ISO_FMT)
        changed: list[tuple[int, str]] = []  # (shop_id, 新状态)
        with self._engine.begin() as conn:
            item = proxy_pool_store.get(conn, pool_id)
            if item is None:
                raise NotFound(f"代理池项不存在: {pool_id}")
            old_url = self._box.decrypt(item["proxy_url"]).decode()
            parts = split_proxy_url(old_url)
            new_parts = replace(
                parts,
                host=parts.host if host is None else host.strip(),
                port=parts.port if port is None else port,
                username=parts.username if username is None else username,
                password=parts.password if password is None else password,
            )
            new_url = join_proxy_url(new_parts)
            if errors := validate_proxy_url(new_url):
                raise ValueError(errors[0])
            fields: dict[str, Any] = {}
            if expires_at is not None:
                fields["expires_at"] = expires_at
            new_identity = proxy_identity(new_url)
            egress_changed = new_identity != proxy_identity(old_url)
            if egress_changed:
                clash = proxy_pool_store.get_by_identity(conn, new_identity)
                if clash is not None and clash["id"] != pool_id:
                    holder = next((
                        r for r in proxy_pool_store.referrers(conn, clash["id"])
                        if r["status"] != "disabled"), None)
                    raise ProxyPoolInUse(
                        holder["name"] if holder else f"池项 {clash['proxy_display']}")
                fields.update(
                    identity=new_identity, proxy_url=self._box.encrypt(new_url.encode()),
                    proxy_display=display_proxy(new_url))
            proxy_pool_store.update(conn, pool_id, now, **fields)
            if egress_changed:
                for r in proxy_pool_store.referrers(conn, pool_id):
                    shop = shop_store.get(conn, r["id"])
                    new_status = reset_shop_egress(conn, shop, now)
                    if shop["status"] != "disabled" and (
                        new_status != shop["status"] or shop["egress_ip"] is not None
                        or shop["egress_status"] != "unchecked"
                    ):
                        changed.append((r["id"], new_status))
            audit_store.insert(conn, CallRecord(
                None, "proxy_pool.update", actor,
                {"pool_id": pool_id, "proxy_display": item["proxy_display"]},
                {"fields": sorted(k for k in fields if k != "proxy_url"),
                 "reset_shops": [sid for sid, _ in changed]}, "ok", 0), now)
        for sid, status in changed:
            self._events.publish(SHOP_STATUS_CHANGED, {
                "shop_id": sid, "status": status, "egress_status": "unchecked"})

    async def check(self, pool_id: int, actor: str) -> CheckResult:
        """经该代理取出口 IP 并记录；只读，不改任何店铺。"""
        with self._engine.connect() as conn:
            item = proxy_pool_store.get(conn, pool_id)
        if item is None:
            raise NotFound(f"代理池项不存在: {pool_id}")
        url = self._box.decrypt(item["proxy_url"]).decode()
        started = time.monotonic()
        result = await self._probe(url)  # 事务外做网络请求
        elapsed_ms = int((time.monotonic() - started) * 1000)
        now = self._clock().strftime(_ISO_FMT)
        in_use_by = None
        with self._engine.begin() as conn:
            if proxy_pool_store.get(conn, pool_id) is None:  # 检测期间被删
                raise NotFound(f"代理池项不存在: {pool_id}")
            proxy_pool_store.update(
                conn, pool_id, now, last_checked_at=now, last_check_ip=result.ip)
            if result.ip is not None:
                own = {r["id"] for r in proxy_pool_store.referrers(conn, pool_id)}
                other = next((
                    o for o in shop_store.list(conn)
                    if o["id"] not in own and o["status"] != "disabled"
                    and o["egress_ip"] == result.ip), None)
                if other is not None:
                    in_use_by = {"shop_id": other["id"], "shop_name": other["name"]}
            audit_store.insert(conn, CallRecord(
                None, "proxy_pool.check", actor,
                {"pool_id": pool_id, "proxy_display": item["proxy_display"]},
                {"reason": result.reason}, "ok" if result.ip else "error", elapsed_ms), now)
        return CheckResult(result.ip, result.reason, elapsed_ms, in_use_by)

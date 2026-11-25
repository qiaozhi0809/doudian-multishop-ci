"""运行配置（环境变量前缀 DD_）。"""

import os
import sys
from pathlib import Path, PureWindowsPath

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR_NAME = "doudian-multishop"
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DD_", extra="ignore")

    data_dir: Path = Path()
    host: str = "127.0.0.1"
    port: int = 8787
    browser_channel: str = "chrome"
    use_cloak: bool = True
    cloak_cache_dir: Path = Path()
    egress_echo_url: str = "https://ifconfig.me/ip"
    dev_mode: bool = False
    dry_run: bool = False
    max_concurrent_shops: int = 3
    printer_name: str = ""  # 取号请求的 printer 字段；M3 接打印组件前默认不传
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # ---- M7 打磨：每日定时对账 / 备份 / 临近超时告警（overview 13、gaps ENG-04/06/07）----
    reconcile_daily: bool = True
    reconcile_hour: int = Field(3, ge=0, le=23)  # 每天本地时间几点跑全店对账
    reconcile_window_days: int = Field(30, ge=1, le=90)
    backup_daily: bool = True
    backup_hour: int = Field(4, ge=0, le=23)  # 与对账错开一小时
    backup_keep: int = Field(7, ge=1, le=365)  # 保留最近 N 份快照
    ship_deadline_warn_hours: int = Field(6, ge=1, le=72)  # 剩余发货时间 < N 小时告警
    ship_deadline_scan_interval_s: int = Field(1800, ge=60)

    @property
    def profiles_dir(self) -> Path:
        """每店一个持久化浏览器用户目录：profiles/<shop_id>/。"""
        return self.data_dir / "profiles"

    @property
    def backups_dir(self) -> Path:
        """SQLite 每日快照目录：backups/（ENG-06）。"""
        return self.data_dir / "backups"

    def __init__(self, _platform: str | None = None, **values):
        super().__init__(**values)
        platform = _platform or sys.platform
        if "browser_channel" not in self.model_fields_set:
            self.browser_channel = "msedge" if platform == "win32" else "chrome"
        if "data_dir" not in self.model_fields_set:
            self.data_dir = _default_data_dir(platform)
        if not _is_absolute(self.data_dir, platform):
            self.data_dir = self.data_dir.resolve()
        if "cloak_cache_dir" not in self.model_fields_set:
            self.cloak_cache_dir = self.data_dir / "browser"


def _default_data_dir(platform: str) -> Path:
    if platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(str(PureWindowsPath(base) / APP_DIR_NAME))
    return REPO_ROOT / "data"


def _is_absolute(path: Path, platform: str) -> bool:
    if platform == "win32":
        return PureWindowsPath(str(path)).is_absolute()
    return path.is_absolute()

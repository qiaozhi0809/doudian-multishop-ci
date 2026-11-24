"""运行配置（环境变量前缀 DD_）。"""

import os
import sys
from pathlib import Path, PureWindowsPath

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR_NAME = "doudian-multishop"
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DD_", extra="ignore")

    data_dir: Path = Path()
    host: str = "127.0.0.1"
    port: int = 8787
    browser_channel: str = "chrome"
    egress_echo_url: str = "https://api.ipify.org"
    dev_mode: bool = False
    dry_run: bool = False

    def __init__(self, _platform: str | None = None, **values):
        super().__init__(**values)
        platform = _platform or sys.platform
        if "browser_channel" not in self.model_fields_set:
            self.browser_channel = "msedge" if platform == "win32" else "chrome"
        if "data_dir" not in self.model_fields_set:
            self.data_dir = _default_data_dir(platform)
        if not _is_absolute(self.data_dir, platform):
            self.data_dir = self.data_dir.resolve()


def _default_data_dir(platform: str) -> Path:
    if platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(str(PureWindowsPath(base) / APP_DIR_NAME))
    return REPO_ROOT / "data"


def _is_absolute(path: Path, platform: str) -> bool:
    if platform == "win32":
        return PureWindowsPath(str(path)).is_absolute()
    return path.is_absolute()

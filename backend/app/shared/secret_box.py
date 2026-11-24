"""凭证加密：Windows 用 DPAPI（绑定当前用户），开发机用本地密钥文件的 Fernet。"""

import os
import sys
from pathlib import Path
from typing import Protocol

import structlog
from cryptography.fernet import Fernet

log = structlog.get_logger()


class SecretBox(Protocol):
    def encrypt(self, data: bytes) -> bytes: ...

    def decrypt(self, data: bytes) -> bytes: ...


class DpapiBox:
    """Windows DPAPI（CryptProtectData）。pywin32 仅在 Windows 安装，故延迟导入。"""

    def __init__(self) -> None:
        import win32crypt  # type: ignore[import-not-found]

        self._crypt = win32crypt

    def encrypt(self, data: bytes) -> bytes:
        return self._crypt.CryptProtectData(data, None, None, None, None, 0)

    def decrypt(self, data: bytes) -> bytes:
        return self._crypt.CryptUnprotectData(data, None, None, None, 0)[1]


class DevKeyBox:
    """开发机用：密钥文件不存在时生成，权限 0600。"""

    def __init__(self, key_file: Path) -> None:
        key_file = Path(key_file)
        if not key_file.exists():
            key_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        key_file.chmod(0o600)
        self._fernet = Fernet(key_file.read_bytes())

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)


def make_secret_box(data_dir: Path, platform: str = sys.platform) -> SecretBox:
    if platform == "win32":
        return DpapiBox()
    log.warning("secret_box.dev_key", reason="非 Windows 平台，使用开发机密钥文件加密")
    return DevKeyBox(Path(data_dir) / "dev.key")

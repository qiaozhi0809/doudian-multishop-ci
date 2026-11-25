"""把 certifi 的 CA 证书落到纯 ASCII 目录，规避 libcurl 的 Windows 中文路径问题。

libcurl 在 Windows 上按 ANSI 代码页解释文件路径。证书位于含非 ASCII 字符的目录时
（例如仓库放在「E:\\项目\\...」下面），加载会失败并让**所有** HTTPS 请求报
`curl: (77) error adding trust anchors`。启动时复制一份到数据目录，用 CURL_CA_BUNDLE 指过去。
"""

import os
import shutil
from pathlib import Path

import certifi

ENV_KEY = "CURL_CA_BUNDLE"
CA_FILE_NAME = "cacert.pem"


def install_ca_bundle(data_dir: Path) -> Path | None:
    """确保 CA 证书位于可被 libcurl 打开的路径，并设置 CURL_CA_BUNDLE。

    已有可用的 ASCII 路径设置时不改动；data_dir 自身含非 ASCII 字符时返回 None
    （调用方保持原状，让 HTTP 层自己报错，而不是给出看似成功的假象）。
    """
    target = data_dir / CA_FILE_NAME
    existing = os.environ.get(ENV_KEY)
    if existing and str(existing).isascii():
        path = Path(existing)
        # 调用方自带可用的 ASCII 证书就不动；指向本函数目标文件时仍要校验其内容
        if path.is_file() and path != target:
            return path
    if not str(data_dir).isascii():
        return None

    source = Path(certifi.where())
    try:
        source_size = source.stat().st_size
        if not target.is_file() or target.stat().st_size != source_size:
            data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    except OSError:
        return None
    os.environ[ENV_KEY] = str(target)
    return target

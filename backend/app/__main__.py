"""python -m app：启动本机服务。"""

import asyncio
import sys

import uvicorn

from app.config import Settings
from app.main import create_app
from app.shared.curl_ca import install_ca_bundle


def main() -> None:
    if sys.platform == "win32":
        # Playwright 需要子进程支持
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    settings = Settings()
    install_ca_bundle(settings.data_dir)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()

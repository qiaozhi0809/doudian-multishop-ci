"""系统信息：演练模式标识、版本号等界面全局状态（M7）。"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.shared.version import APP_VERSION

router = APIRouter(prefix="/api/system", tags=["system"])


class SystemInfo(BaseModel):
    dry_run: bool
    version: str
    reconcile_daily: bool
    reconcile_hour: int
    backup_daily: bool
    backup_keep: int
    ship_deadline_warn_hours: int


@router.get("/info", response_model=SystemInfo)
def info(request: Request) -> SystemInfo:
    settings = request.app.state.settings
    return SystemInfo(
        dry_run=settings.dry_run,
        version=APP_VERSION,
        reconcile_daily=settings.reconcile_daily,
        reconcile_hour=settings.reconcile_hour,
        backup_daily=settings.backup_daily,
        backup_keep=settings.backup_keep,
        ship_deadline_warn_hours=settings.ship_deadline_warn_hours,
    )

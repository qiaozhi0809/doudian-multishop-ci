"""备份接口：查看快照、手动触发（ENG-06）。恢复是停服后的手工步骤，不提供在线接口。"""

from fastapi import APIRouter, Depends, Request

from app.api.backup_schemas import BackupCreated, BackupSnapshot, BackupSnapshotList
from app.api.deps import require_admin

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/snapshots", response_model=BackupSnapshotList)
def snapshots(request: Request) -> BackupSnapshotList:
    state = request.app.state
    return BackupSnapshotList(
        items=[BackupSnapshot(**row) for row in state.backup.snapshots()],
        backups_dir=str(state.settings.backups_dir),
        keep=state.settings.backup_keep,
    )


@router.post("/run", response_model=BackupCreated, status_code=201)
def run(request: Request, admin: str = Depends(require_admin)) -> BackupCreated:
    # 同步端点：FastAPI 在线程池里执行，sqlite3 备份不会阻塞事件循环
    return BackupCreated(**request.app.state.backup.create(actor=admin, trigger="manual"))

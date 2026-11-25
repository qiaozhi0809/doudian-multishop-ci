"""备份接口的请求 / 响应模型（ENG-06）。"""

from pydantic import BaseModel


class BackupSnapshot(BaseModel):
    file_name: str
    size_bytes: int
    trigger: str
    actor: str | None
    created_at: str
    exists: bool = True


class BackupSnapshotList(BaseModel):
    items: list[BackupSnapshot]
    backups_dir: str
    keep: int


class BackupCreated(BaseModel):
    file_name: str
    size_bytes: int
    trigger: str
    actor: str | None
    created_at: str
    pruned: list[str]

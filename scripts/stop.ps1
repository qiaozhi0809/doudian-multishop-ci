# 停止通过 start.ps1 启动的本机服务
param([string]$InstallRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"

$pidFile = Join-Path $InstallRoot "run\app.pid"
if (-not (Test-Path $pidFile)) {
    Write-Host "没有 PID 文件：服务未通过 start.ps1 启动，或已停止"
    exit 0
}

$appPid = Get-Content $pidFile | Select-Object -First 1
$proc = Get-Process -Id $appPid -ErrorAction SilentlyContinue
if ($proc) {
    Stop-Process -Id $appPid -Force
    Write-Host "已停止（PID $appPid）"
} else {
    Write-Host "进程 $appPid 已不存在，清理 PID 文件"
}
Remove-Item $pidFile -Force

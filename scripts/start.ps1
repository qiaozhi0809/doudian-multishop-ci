# 启动本机服务（Windows 出单机）
# 生成 PID 文件与日志；重复运行会被拒绝。
param([string]$InstallRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"

$backend = Join-Path $InstallRoot "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "未找到虚拟环境：先按 docs/design/deployment.md 第 2 节安装依赖"
    exit 1
}

$runDir = Join-Path $InstallRoot "run"
$logDir = Join-Path $InstallRoot "logs"
New-Item -ItemType Directory -Force -Path $runDir, $logDir | Out-Null
$pidFile = Join-Path $runDir "app.pid"

if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile | Select-Object -First 1
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "服务已在运行（PID $oldPid）"
        exit 0
    }
    Remove-Item $pidFile -Force
}

# 可选：scripts\config.env 每行 KEY=VALUE（# 开头为注释），覆盖 DD_* 配置
$envFile = Join-Path $PSScriptRoot "config.env"
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match "^\s*[^#].*=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

$outLog = Join-Path $logDir "app.out.log"
$errLog = Join-Path $logDir "app.err.log"
$proc = Start-Process -FilePath $python -ArgumentList "-m", "app" `
    -WorkingDirectory $backend -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Set-Content -Path $pidFile -Value $proc.Id -Encoding ascii

$appHost = if ($env:DD_HOST) { $env:DD_HOST } else { "127.0.0.1" }
$appPort = if ($env:DD_PORT) { $env:DD_PORT } else { "8787" }
Write-Host "已启动（PID $($proc.Id)）"
Write-Host "打开 http://${appHost}:${appPort} 使用；日志见 logs\app.out.log / app.err.log"

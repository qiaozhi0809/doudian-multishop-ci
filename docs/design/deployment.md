# 出单机部署与运维

> M7 / gaps ENG-04（打包与安装）、ENG-06（备份与恢复）、ENG-07（通知通道）。
> 目标：在出单机上**双击即可使用**（overview 14 第 7 条），升级、备份、回滚都有明确步骤。
> 2026-11-25 初版。

## 1. 运行形态

单机、单进程、只监听 `127.0.0.1`（backend 4.1）。安装包 = 「源码 + 前端构建产物 + 启动脚本」，
用 **zip 包 + 本机 venv** 部署；Python 侧不打包成 exe（PyInstaller 方案见 §9，尚未验证）。

```
D:\doudian-multishop\            ← 安装目录（可任意）
├── backend\app\ ...             ← 后端源码
├── backend\.venv\               ← 本机虚拟环境（安装时创建）
├── frontend\dist\               ← 前端构建产物，由后端托管
├── scripts\start.bat            ← 双击启动
├── scripts\stop.bat             ← 双击停止
├── logs\                        ← 运行日志（start.ps1 写到这里）
├── run\app.pid                  ← 启动脚本维护的 PID
└── %LOCALAPPDATA%\doudian-multishop\   ← 数据目录（不在安装目录里）
    ├── app.db                   ← SQLite 主库（WAL）
    ├── backups\app-*.db         ← 每日快照（ENG-06）
    └── profiles\<shop_id>\      ← 每店浏览器用户目录（登录态）
```

数据目录默认放在 `%LOCALAPPDATA%`，避免被 OneDrive 同步；可用 `DD_DATA_DIR` 改到别的磁盘。

## 2. 出单机前置条件（安装前逐项确认）

| 检查项 | 要求 | 怎么确认 |
|---|---|---|
| 操作系统 | Windows 10/11 x64 | `winver` |
| Python | 3.12.x（64 位） | `python --version`；安装时勾选 Add to PATH |
| 磁盘 | ≥ 5 GB 可用（数据库 + 浏览器 profile + 备份） | 资源管理器 |
| 网络 | 能访问 `fxg.jinritemai.com`；代理出口按店准备 | 浏览器打开抖店后台 |
| 下载源可达 | 能直连 `https://cloakbrowser.dev`（失败会自动回退 GitHub Releases）下载约 200MB；或已预置 `<安装目录>\backend\browser\chromium-146.*\` | 第 3 节步骤 2 的预下载命令成功输出二进制路径 |
| 抖店官方打印组件 | 已安装并**保持运行**（`wss://localhost:13999`） | `netstat -ano \| findstr 13999` 有 LISTENING |
| 打印机 | 系统打印机已添加、能打测试页 | 打印机设置 |
| 时间 | 与网络时间同步（对账 / 超时告警依赖系统时间） | `w32tm /query /status` |

> 打印组件未启动时界面会明确提示，且**不会**把订单标记为已打印（overview 14 第 10 条）。

## 3. 首次安装

1. 解压 zip 到 `D:\doudian-multishop`（路径不要含空格以外的特殊字符）。
2. 打开 PowerShell（在该目录）创建虚拟环境并安装依赖：

   ```powershell
   cd D:\doudian-multishop\backend
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   # 预下载 CloakBrowser 定制浏览器（约 200MB，直连下载，不走店铺代理）
   # 必须关闭自动更新：否则库会在后台下载新版并写 latest_version_* 标记，运行时改用未验证的新版
   $env:CLOAKBROWSER_AUTO_UPDATE = "false"
   $env:CLOAKBROWSER_CACHE_DIR = "$PWD\browser"
   .\.venv\Scripts\python.exe -c "import cloakbrowser; print(cloakbrowser.ensure_binary())"
   ```

   `requirements.txt` 是 `uv export` 生成的**锁定版本**清单，不安装开发依赖。
   开发机也可以用 `uv sync`，见 [engineering-rules.md](../engineering-rules.md)。

   预下载输出应为 `...\browser\chromium-146.*\chrome.exe`。这一步失败说明出单机无法直连外网——请在能联网的机器上执行同样命令，再把整个 `browser` 目录拷过来。程序运行时**不会**自动下载浏览器：二进制不在时扫码与同步收款信息直接提示「浏览器未预下载」。

3. 前端产物：发布包里已带 `frontend\dist\`。若没有（例如只拿了源码），在开发机执行
   `cd frontend && pnpm install && pnpm build`，再把 `frontend\dist` 整个拷过来。
   后端启动时检测到 `frontend\dist\index.html` 就托管静态页面，否则只提供 `/api/*`。

4. （可选）复制 `scripts\config.env.example` 为 `scripts\config.env`，按需改配置（§4）。

5. 双击 `scripts\start.bat`，浏览器打开 <http://127.0.0.1:8787>。
   首次启动会自动建库并执行迁移（0001~0007），页面引导创建管理员账号。

6. 建议**第一天用演练模式**（§5）走一遍：添加店铺 → 扫码登录 → 同步基础数据 →
   预览取号 / 发货，确认界面与审计记录符合预期后再关闭演练模式真实操作。

7. 逐店配置：店铺页添加店铺 → 设置出口（直连或独享静态代理）→ 扫码登录 →
   基础数据同步（地址 / 模板 / 快递 / 面单账户）→ 确认默认发货地址与面单账户。

## 4. 配置项

全部通过环境变量（前缀 `DD_`）配置，写在 `scripts\config.env` 里由启动脚本加载；
不写在文件里时也可以用系统环境变量。改完重启生效。

| 变量 | 默认 | 说明 |
|---|---|---|
| `DD_DATA_DIR` | `%LOCALAPPDATA%\doudian-multishop` | 数据目录（库、备份、浏览器 profile） |
| `DD_HOST` / `DD_PORT` | `127.0.0.1` / `8787` | 监听地址与端口（不要改成 0.0.0.0） |
| `DD_DRY_RUN` | `false` | 演练模式，见 §5 |
| `DD_USE_CLOAK` | `true` | 是否使用 CloakBrowser 定制 Chromium；设为 `false` 时回退系统浏览器 |
| `DD_CLOAK_CACHE_DIR` | `<安装目录>\backend\browser` | CloakBrowser 二进制缓存目录。**不要指到 `%LOCALAPPDATA%`**：Windows 下该目录中的 exe 无法生成 SxS 激活上下文，浏览器起不来（`spawn UNKNOWN`） |
| `DD_BROWSER_CHANNEL` | `msedge`（Windows） | 仅 `DD_USE_CLOAK=false` 时生效的兜底通道。**应急专用**：此时所有店铺共用本机真实 Edge 指纹，多店同时使用会破坏「每店固定指纹」的隔离目标 |
| `DD_PRINTER_NAME` | 空 | 取号请求的 printer 字段 / 默认打印机名 |
| `DD_MAX_CONCURRENT_SHOPS` | `3` | 同时执行的店铺数上限 |
| `DD_RECONCILE_DAILY` | `true` | 每日定时全店对账开关 |
| `DD_RECONCILE_HOUR` | `3` | 对账时间（本地时间 0-23 点，错峰用） |
| `DD_RECONCILE_WINDOW_DAYS` | `30` | 对账时间窗（天，1~90） |
| `DD_BACKUP_DAILY` | `true` | 每日自动备份开关 |
| `DD_BACKUP_HOUR` | `4` | 备份时间（与对账错开） |
| `DD_BACKUP_KEEP` | `7` | 保留最近 N 份快照 |
| `DD_SHIP_DEADLINE_WARN_HOURS` | `6` | 剩余发货时间不足 N 小时时告警 |
| `DD_SHIP_DEADLINE_SCAN_INTERVAL_S` | `1800` | 超时告警扫描间隔（秒） |

## 5. 演练模式（dry run）

`DD_DRY_RUN=true` 重启后：

- 顶部显示**醒目横幅**；取号 / 一体 / 作废 / 发货 / 打印的确认按钮标注「（演练）」。
- 所有写操作**不调用**抖店写接口、不连打印组件、不推进本地状态：
  只把「将发出的请求」写进 `audit_log`（`action` 以 `dry_run_` 开头，`result='dry_run'`），
  界面显示模拟结果。
- 只读请求（拉单、发货前检查、对账、聚合）照常执行，可用真实数据预览。
- **不会**产生假面单或「已发货」状态——关掉演练模式后真单不会被幂等键误跳过。

售后处理动作属于阶段二（overview 2.2），当前版本没有任何售后写接口；
实现时同样在 service 入口复用 `service/dry_run.py` 的拦截（记录 `dry_run_*` 审计、不发请求）。

这是新店 / 新版本上线前的标准预演流程，也是验收标准第 11 条（不产生真实写请求）的实现。

## 6. 每日自动任务

| 任务 | 默认时间 / 间隔 | 说明 |
|---|---|---|
| 订单同步 | 每 5 分钟 | 所有可用店铺的待发货订单 |
| 会话探测 | 每 30 分钟 | `tabcnt`，掉线标记 `needs_login` 并在顶栏提示 |
| 全店对账 | 每天 03:00 | 结果见「对账」页；也可手动触发 |
| 数据库快照 | 每天 04:00 | 保留 `DD_BACKUP_KEEP` 份（§7） |
| 临近超时发货告警 | 每 30 分钟 | 剩余时间 < `DD_SHIP_DEADLINE_WARN_HOURS` 的单在任务中心提示 |

通知走界面内 SSE（任务中心 / 会话健康指示），不接外部 IM（ENG-07：掉线、打印失败、
临近超时均可在界面看到；打印失败在任务中心与打单发货页都可见）。

## 7. 备份与恢复（ENG-06）

### 7.1 每日快照

- 位置：`<数据目录>\backups\app-YYYYMMDD-HHMMSS.db`，用 SQLite 在线备份 API
  （`Connection.backup`，等价 `.backup` / `VACUUM INTO`），WAL 模式下包含全部已提交事务。
- 每个快照在 `backup_run` 表里有一条记录（文件、体积、触发方式、时间），
  界面 / API 可查：`GET /api/backup/snapshots`。
- 保留策略：只保留最近 `DD_BACKUP_KEEP` 份（默认 7），超出的文件与记录一起删除。
- 手动触发：店铺管理页「数据备份 → 查看快照 → 立即备份」，
  或调用 `POST /api/backup/run`（需管理员登录），返回文件名与清理掉的旧快照。

### 7.2 恢复步骤（必须停服操作）

1. 双击 `scripts\stop.bat` 停止服务（确认 `run\app.pid` 进程已退出）。
2. 把当前库留档：把 `<数据目录>\app.db` 复制成 `app.db.before-restore`。
3. 删除 `app.db-wal` / `app.db-shm`（如果存在）——WAL 里可能有未合并的事务。
4. 从 `backups\` 选一个快照，复制为 `<数据目录>\app.db`。
5. 双击 `scripts\start.bat`。启动时会自动把库结构迁移到当前版本（向前迁移）。
6. 登录后抽查：店铺列表、最近订单、当天对账批次是否与快照时间相符。

> 备份文件是完整独立 SQLite 库，可以直接用 DB Browser for SQLite 打开核对。
> 恢复演练一年至少一次（用一台非生产机验证备份能打开、能登录）。

## 8. 升级与回滚

### 8.1 升级

1. 停止服务（`scripts\stop.bat`）。
2. 手动备份一次：启动服务 → 设置页「立即备份」→ 再停止；或直接复制 `app.db` 留档。
3. 用新版本覆盖 `backend\app`、`backend\migrations`、`backend\requirements.txt`、
   `frontend\dist`、`scripts`；**保留** `.venv` 之外的目录结构、`data\`（数据目录不在安装目录）。
4. `backend\.venv\Scripts\python.exe -m pip install -r requirements.txt`（依赖可能变化）。
5. 启动：数据库迁移在启动时自动执行（`upgrade_to_head`）。
6. 先开 `DD_DRY_RUN=true` 验证一遍，再关闭。

### 8.2 回滚

- 保留上一版安装目录（如 `D:\doudian-multishop-0.6`），回滚时停止服务、切回旧目录、启动。
- **数据库不向下迁移**：如果新版本已执行新迁移，旧版本可能读不了新库。
  因此回滚前用升级前的备份恢复数据库（§7.2）。

## 9. 备选打包方式（PyInstaller，未验证）

`PyInstaller --onedir` 可以把 Python 运行时打进目录，出单机无需装 Python。
需要额外处理 Playwright / 浏览器 profile / 静态资源路径（`REPO_ROOT` 计算），
目前**没有**验证通过，暂不作为交付方式；zip + venv 是经过测试的路径。

## 10. 排障

| 现象 | 排查 |
|---|---|
| 双击 start.bat 没反应 | 看 `logs\app.err.log`；多半是没建 venv（§3）或端口被占 |
| 打印按钮置灰 | 打印组件未启动或没有默认打印机；`netstat -ano \| findstr 13999` |
| 扫码登录打不开浏览器 | CloakBrowser 二进制未预下载（提示「浏览器未预下载」；检查 `<安装目录>\backend\browser\`）；或该店 profile 目录被占用（先停止其他实例）；若 `DD_USE_CLOAK=false` 则检查系统 Edge 是否安装 |
| 所有店都提示出口不通 | 代理失效（`DD_EGRESS_ECHO_URL` 不可达）；恢复后重新「出口检查」 |
| 某店提示需要重新登录 | 会话过期（约 60 天）或平台踢出；顶栏「重登」重新扫码即可，其他店不受影响 |
| 任务中心一直「进行中」 | 看日志；进程重启后未完成的写任务会转「待核实」，到单据里核对后重试 |
| 忘记管理员密码 | `backend\.venv\Scripts\python.exe -m app.cli reset-admin --username admin` |

日志：`logs\app.out.log`（业务日志，已脱敏）与 `logs\app.err.log`（uvicorn 错误）。
外部调用统一在 `audit_log`，可按店铺和动作追溯（overview 14 第 6 条）。

## 11. 首次交付验收清单

- [ ] 前置条件表全过（§2）
- [ ] 双击启动即可用，浏览器不再需要命令行（overview 14 第 7 条）
- [ ] 演练模式下取号 / 发货 / 打印 / 作废都只产生审计记录，无真实请求（第 11 条）
- [ ] 关闭演练模式，2 个不同主体店铺各完成 1 单全流程
- [ ] 手动制造一次会话失效：5 分钟内标记 `needs_login`，其他店不受影响（第 4 条）
- [ ] 对账页能看到三类异常（第 5 条）
- [ ] 手动备份一次，并按 §7.2 在非生产库上演练恢复
- [ ] 升级流程按 §8.1 走一遍，回滚流程按 §8.2 走一遍

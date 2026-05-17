# 在本地 Windows 机器上运行一次，生成专用同步密钥并打印服务器端需要添加的 authorized_keys 行。
# 公司和家的机器分别运行一次，各自生成独立密钥。
# 运行方式：在项目根目录执行  powershell -ExecutionPolicy Bypass -File scripts\setup_sync_key.ps1

$ErrorActionPreference = "Stop"

$RootDir     = Split-Path $PSScriptRoot -Parent
$SyncEnvPath = Join-Path $RootDir ".sync.env"

if (-not (Test-Path $SyncEnvPath)) {
    Write-Error "缺少 .sync.env，请先复制 .sync.env.example 并填入服务器信息"
    exit 1
}

# 解析 .sync.env
$SyncEnv = @{}
Get-Content $SyncEnvPath | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $parts = $_ -split '=', 2
    $SyncEnv[$parts[0].Trim()] = $parts[1].Trim()
}

$SyncHost    = $SyncEnv['SYNC_HOST']
$SyncUser    = $SyncEnv['SYNC_USER']
$SyncPort    = if ($SyncEnv['SYNC_PORT']) { $SyncEnv['SYNC_PORT'] } else { "22" }
$SyncAppDir  = $SyncEnv['SYNC_APP_DIR']
$SyncUsername = $SyncEnv['SYNC_USERNAME']
$KeyPathRaw  = if ($SyncEnv['SYNC_KEY_PATH']) { $SyncEnv['SYNC_KEY_PATH'] } else { "~/.ssh/mypresent_sync" }
$KeyPath     = $KeyPathRaw -replace '^~', $HOME

# 检查 ssh-keygen 是否可用
if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 ssh-keygen。请确认已安装 Windows OpenSSH（Windows 10/11 内置，在「可选功能」中启用）"
    exit 1
}

$KeyDir = Split-Path $KeyPath -Parent
if (-not (Test-Path $KeyDir)) {
    New-Item -ItemType Directory -Force -Path $KeyDir | Out-Null
}

if (Test-Path $KeyPath) {
    Write-Host "密钥已存在：$KeyPath，跳过生成。"
} else {
    $Comment = "mypresent-sync-readonly-$env:COMPUTERNAME"
    # 注意：-N '""' 才能在 PowerShell 下把"空密码"正确传给 ssh-keygen
    # 直接写 '' 会被 PowerShell 吞掉，导致 ssh-keygen 报 "option requires an argument -- N"
    ssh-keygen -t ed25519 -f $KeyPath -C $Comment -N '""'
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ssh-keygen 执行失败（退出码 $LASTEXITCODE）。请检查上面输出。"
        exit 1
    }
    if (-not (Test-Path "$KeyPath.pub")) {
        Write-Error "ssh-keygen 看似成功但未生成 .pub 文件。请删除 $KeyPath 后重试。"
        exit 1
    }
    Write-Host "密钥已生成：$KeyPath"
}

$PubKey   = (Get-Content "$KeyPath.pub").Trim()
$DataDir  = "$SyncAppDir/data/users/$SyncUsername"

# 用单引号 + 字符串拼接构造，避开 PowerShell 双引号转义嵌套地狱
$AuthLine = 'command="internal-sftp -R",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ' + $PubKey
$InnerEcho = "echo '" + $AuthLine + "' >> ~/.ssh/authorized_keys"
$SshCmd    = '  ssh -p ' + $SyncPort + ' ' + $SyncUser + '@' + $SyncHost + ' "' + $InnerEcho + '"'

Write-Host ""
Write-Host "========================================================="
Write-Host "请将以下内容追加到服务器 ~/.ssh/authorized_keys："
Write-Host "========================================================="
Write-Host $AuthLine
Write-Host "========================================================="
Write-Host ""
Write-Host "可在本机 PowerShell 运行以下命令一步完成（需要能正常 SSH 登录服务器）："
Write-Host ""
Write-Host $SshCmd
Write-Host ""
Write-Host "完成后可用以下命令拉取数据："
Write-Host "  MyPresent 项目数据（含媒体文件）：python D:\MyPresent\scripts\pull_data.py"
Write-Host "  自媒体素材分析（仅数据库）：     python E:\个人\自媒体\scripts\pull_db.py"

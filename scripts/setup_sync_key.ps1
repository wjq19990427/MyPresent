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
    ssh-keygen -t ed25519 -f $KeyPath -C $Comment -N ''
    Write-Host "密钥已生成：$KeyPath"
}

$PubKey     = (Get-Content "$KeyPath.pub").Trim()
$DataDir    = "$SyncAppDir/data/users/$SyncUsername"

Write-Host ""
Write-Host "========================================================="
Write-Host "请将以下内容追加到服务器 ~/.ssh/authorized_keys："
Write-Host "========================================================="
Write-Host "command=`"internal-sftp -R`",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding $PubKey"
Write-Host "========================================================="
Write-Host ""
Write-Host "可在本机 PowerShell 运行以下命令一步完成（需要能正常 SSH 登录服务器）："
Write-Host ""
Write-Host "  ssh -p $SyncPort ${SyncUser}@${SyncHost} `"echo 'command=\`"internal-sftp -R\`",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding $PubKey' >> ~/.ssh/authorized_keys`""
Write-Host ""
Write-Host "完成后运行以下命令拉取数据："
Write-Host "  python scripts\pull_data.py"

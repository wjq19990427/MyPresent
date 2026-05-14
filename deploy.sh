#!/usr/bin/env bash
# MyPresent 标准部署脚本。
# 在服务器项目根目录执行：备份数据库 -> 拉取 main -> 更新依赖 -> 重启 systemd 服务。

set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ENV_FILE="$APP_DIR/.env"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少必要命令：$1" >&2
    exit 1
  fi
}

backup_database() {
  mkdir -p "$BACKUP_DIR"

  if [[ "$DEPLOY_MODE" == "cloud" ]]; then
    if [[ ! -d "$APP_DIR/data/users" ]]; then
      log "cloud 模式未发现 data/users 目录，跳过用户库备份。"
      return
    fi
    while IFS= read -r db_path; do
      username="$(basename "$(dirname "$db_path")")"
      cp "$db_path" "$BACKUP_DIR/${username}_${TIMESTAMP}.db"
      log "已备份用户数据库：$username"
    done < <(find "$APP_DIR/data/users" -type f -name "database.db")
  else
    local_db="$APP_DIR/data/database.db"
    if [[ -f "$local_db" ]]; then
      cp "$local_db" "$BACKUP_DIR/database_${TIMESTAMP}.db"
      log "已备份本地数据库。"
    else
      log "未发现 data/database.db，跳过本地数据库备份。"
    fi
  fi

  find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
  log "已清理 7 天前的数据库备份。"
}

log "步骤 1：环境检查"
require_command python3
require_command pip
require_command git

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 .env 文件：$ENV_FILE。请先在服务器项目目录创建部署环境配置。" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

SERVICE_NAME="${SERVICE_NAME:-mypresent}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
DEPLOY_MODE="${DEPLOY_MODE:-local}"

if [[ ! -f "$SERVICE_FILE" ]]; then
  echo "缺少 systemd 服务单元：$SERVICE_FILE。请参考 infra/mypresent.service 安装。" >&2
  exit 1
fi

cd "$APP_DIR"

log "步骤 2：备份数据库"
backup_database

log "步骤 3：拉取最新代码"
git pull origin main

log "步骤 4：更新 Python 依赖"
pip install -r requirements.txt --quiet

log "步骤 5：重启 systemd 服务"
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"

log "步骤 6：部署完成"
log "服务 ${SERVICE_NAME} 已运行，部署时间：$(date '+%Y-%m-%d %H:%M:%S')"

#!/usr/bin/env bash
# 从云端拉取指定用户的数据库和媒体文件到本地 data/
# 安全策略：拉前备份 → 下载到临时文件 → integrity_check → 通过后替换，失败自动回滚
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SYNC_ENV="$ROOT_DIR/.sync.env"

if [[ ! -f "$SYNC_ENV" ]]; then
  echo "缺少 .sync.env，请复制 .sync.env.example 并填入服务器信息" >&2
  exit 1
fi

source "$SYNC_ENV"
: "${SYNC_HOST:?}" "${SYNC_USER:?}" "${SYNC_PORT:=22}" "${SYNC_APP_DIR:?}" "${SYNC_USERNAME:?}"

KEY_PATH="${SYNC_KEY_PATH:-$HOME/.ssh/mypresent_sync}"
KEY_PATH="${KEY_PATH/#\~/$HOME}"

if [[ ! -f "$KEY_PATH" ]]; then
  echo "未找到同步密钥 $KEY_PATH，请先运行 scripts/setup-sync-key.sh" >&2
  exit 1
fi

SSH_OPT="ssh -p ${SYNC_PORT} -i ${KEY_PATH} -o StrictHostKeyChecking=yes"
# rrsync 已将根目录锁定为 data/users/SYNC_USERNAME，这里只写相对路径
REMOTE="${SYNC_USER}@${SYNC_HOST}:"
LOCAL="$ROOT_DIR/data"
BACKUP_DIR="$ROOT_DIR/backups/sync"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TMP_DB="$LOCAL/database.db.tmp"

mkdir -p "$LOCAL/final" "$LOCAL/pending" "$BACKUP_DIR"

# ── 1. 备份当前本地数据库 ──────────────────────────────────────────────────────
if [[ -f "$LOCAL/database.db" ]]; then
  cp "$LOCAL/database.db" "$BACKUP_DIR/database_${TIMESTAMP}.db"
  echo "已备份本地数据库 → backups/sync/database_${TIMESTAMP}.db"
fi

# 保留最近 10 份备份，删除更早的
ls -t "$BACKUP_DIR"/database_*.db 2>/dev/null | tail -n +11 | xargs rm -f --

# ── 2. 拉取数据库到临时文件 ───────────────────────────────────────────────────
echo ">>> 拉取数据库..."
rsync -az --progress -e "$SSH_OPT" "${REMOTE}database.db" "$TMP_DB"

# ── 3. SQLite 完整性校验 ──────────────────────────────────────────────────────
echo ">>> 校验数据库完整性..."
CHECK="$(python3 -c "
import sqlite3, sys
try:
    result = sqlite3.connect('$TMP_DB').execute('PRAGMA integrity_check').fetchone()[0]
    print(result)
    sys.exit(0 if result == 'ok' else 1)
except Exception as e:
    print(f'error: {e}')
    sys.exit(1)
")"

if [[ "$CHECK" != "ok" ]]; then
  rm -f "$TMP_DB"
  echo "完整性校验失败（$CHECK），已中止并保留原本地数据库" >&2
  exit 1
fi

# ── 4. 替换本地数据库 ─────────────────────────────────────────────────────────
mv "$TMP_DB" "$LOCAL/database.db"
echo "数据库替换完成（integrity_check: ok）"

# ── 5. 拉取媒体文件（不加 --delete，只增不删） ──────────────────────────────
echo ">>> 拉取 final/..."
rsync -az --progress -e "$SSH_OPT" "${REMOTE}final/" "$LOCAL/final/"

echo ">>> 拉取 pending/..."
rsync -az --progress -e "$SSH_OPT" "${REMOTE}pending/" "$LOCAL/pending/"

echo "同步完成：$(date '+%Y-%m-%d %H:%M:%S')"

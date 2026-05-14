#!/usr/bin/env bash
# 在本地机器上运行一次，生成专用同步密钥并打印服务器端需要添加的 authorized_keys 行。
# 公司和家的机器分别运行一次，各自生成独立密钥。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SYNC_ENV="$ROOT_DIR/.sync.env"

if [[ ! -f "$SYNC_ENV" ]]; then
  echo "缺少 .sync.env，请先复制 .sync.env.example 并填入服务器信息" >&2
  exit 1
fi

source "$SYNC_ENV"
: "${SYNC_HOST:?}" "${SYNC_USER:?}" "${SYNC_PORT:=22}" "${SYNC_APP_DIR:?}" "${SYNC_USERNAME:?}"

KEY_PATH="${SYNC_KEY_PATH:-$HOME/.ssh/mypresent_sync}"
KEY_PATH="${KEY_PATH/#\~/$HOME}"

if [[ -f "$KEY_PATH" ]]; then
  echo "密钥已存在：$KEY_PATH，跳过生成。"
else
  ssh-keygen -t ed25519 -f "$KEY_PATH" -C "mypresent-sync-readonly-$(hostname)" -N ""
  echo "密钥已生成：$KEY_PATH"
fi

PUBKEY="$(cat "${KEY_PATH}.pub")"
RRSYNC_PATH="/usr/bin/rrsync"
DATA_DIR="${SYNC_APP_DIR}/data/users/${SYNC_USERNAME}"

echo ""
echo "========================================================="
echo "请将以下内容追加到服务器 ~/.ssh/authorized_keys："
echo "========================================================="
echo "command=\"${RRSYNC_PATH} -ro ${DATA_DIR}\",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ${PUBKEY}"
echo "========================================================="
echo ""
echo "可用此命令一步完成（需要有 SSH 登录权限）："
echo "  ssh -p ${SYNC_PORT} ${SYNC_USER}@${SYNC_HOST} \\"
echo "    \"echo 'command=\\\"${RRSYNC_PATH} -ro ${DATA_DIR}\\\",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ${PUBKEY}' >> ~/.ssh/authorized_keys\""

"""从云端拉取指定用户的数据库和媒体文件到本地 data/

安全策略：拉前备份 → 下载到临时文件 → integrity_check → 通过后替换，失败自动回滚
依赖：pip install paramiko
"""
from __future__ import annotations

import shutil
import sqlite3
import stat
import sys
from datetime import datetime
from pathlib import Path

try:
    import paramiko
except ImportError:
    sys.exit("缺少依赖：请先执行  pip install paramiko")


def _load_sync_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def _sync_dir(sftp: paramiko.SFTPClient, remote: str, local: Path) -> None:
    """递归同步目录，只增不删。"""
    print(f">>> 拉取 {remote.split('/')[-1]}/...")
    local.mkdir(parents=True, exist_ok=True)
    try:
        entries = sftp.listdir_attr(remote)
    except FileNotFoundError:
        print(f"    远端目录不存在，跳过：{remote}")
        return
    for entry in entries:
        remote_path = f"{remote}/{entry.filename}"
        local_path = local / entry.filename
        if stat.S_ISDIR(entry.st_mode):
            _sync_dir(sftp, remote_path, local_path)
        else:
            local_size = local_path.stat().st_size if local_path.exists() else -1
            if local_size != entry.st_size:
                sftp.get(remote_path, str(local_path))


def main() -> None:
    root = Path(__file__).parent.parent
    sync_env_path = root / ".sync.env"

    if not sync_env_path.exists():
        sys.exit("缺少 .sync.env，请复制 .sync.env.example 并填入服务器信息")

    env = _load_sync_env(sync_env_path)

    host     = env.get("SYNC_HOST", "")
    user     = env.get("SYNC_USER", "")
    port     = int(env.get("SYNC_PORT", "22"))
    app_dir  = env.get("SYNC_APP_DIR", "")
    username = env.get("SYNC_USERNAME", "")
    key_path = Path(env.get("SYNC_KEY_PATH", "~/.ssh/mypresent_sync").replace("~", str(Path.home())))

    missing = [k for k, v in [("SYNC_HOST", host), ("SYNC_USER", user),
                                ("SYNC_APP_DIR", app_dir), ("SYNC_USERNAME", username)] if not v]
    if missing:
        sys.exit(f"缺少配置项：{', '.join(missing)}")

    if not key_path.exists():
        sys.exit(f"未找到同步密钥 {key_path}\n请先运行 scripts\\setup_sync_key.ps1（Windows）或 scripts/setup-sync-key.sh（Mac/Linux）")

    local_data = root / "data"
    backup_dir = root / "backups" / "sync"
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_db     = local_data / "database.db.tmp"
    local_db   = local_data / "database.db"

    for d in ("final", "pending"):
        (local_data / d).mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. 备份当前本地数据库 ────────────────────────────────────────────────
    if local_db.exists():
        backup_path = backup_dir / f"database_{timestamp}.db"
        shutil.copy2(local_db, backup_path)
        print(f"已备份本地数据库 → backups/sync/database_{timestamp}.db")

    old_backups = sorted(backup_dir.glob("database_*.db"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    for old in old_backups[10:]:
        old.unlink()

    # ── 2. 建立 SSH 连接 ─────────────────────────────────────────────────────
    print(f"连接 {user}@{host}:{port} ...")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        client.connect(hostname=host, port=port, username=user, key_filename=str(key_path))
    except paramiko.ssh_exception.NoValidConnectionsError:
        sys.exit(f"无法连接到服务器 {host}:{port}，请检查网络和 SYNC_HOST 配置")
    except paramiko.ssh_exception.AuthenticationException:
        sys.exit("SSH 认证失败，请检查密钥是否已添加到服务器 authorized_keys")
    except paramiko.ssh_exception.SSHException as e:
        sys.exit(f"SSH 错误：{e}\n提示：请先用主密钥 ssh {user}@{host} 登录一次以接受服务器指纹")

    sftp = client.open_sftp()
    remote_base = f"{app_dir}/data/users/{username}"

    try:
        # ── 3. 拉取数据库到临时文件 ──────────────────────────────────────────
        print(">>> 拉取数据库...")
        sftp.get(f"{remote_base}/database.db", str(tmp_db))

        # ── 4. SQLite 完整性校验 ─────────────────────────────────────────────
        print(">>> 校验数据库完整性...")
        try:
            result = sqlite3.connect(str(tmp_db)).execute("PRAGMA integrity_check").fetchone()[0]
        except Exception as e:
            tmp_db.unlink(missing_ok=True)
            sys.exit(f"校验异常（{e}），已中止")

        if result != "ok":
            tmp_db.unlink(missing_ok=True)
            sys.exit(f"完整性校验失败（{result}），已中止并保留原本地数据库")

        # ── 5. 替换本地数据库 ────────────────────────────────────────────────
        shutil.move(str(tmp_db), str(local_db))
        print("数据库替换完成（integrity_check: ok）")

        # ── 6. 拉取媒体文件（只增不删） ──────────────────────────────────────
        _sync_dir(sftp, f"{remote_base}/final", local_data / "final")
        _sync_dir(sftp, f"{remote_base}/pending", local_data / "pending")

    finally:
        tmp_db.unlink(missing_ok=True)
        sftp.close()
        client.close()

    print(f"同步完成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

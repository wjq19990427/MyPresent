# MyPresent 远端开发指南

> 适用场景：Windows 本地开发（公司 / 家），云端 Linux 服务器运行生产环境。

---

## 架构概览

```
本地 Windows（公司 / 家）              云端服务器（Linux）
──────────────────────────             ──────────────────────────────
DEPLOY_MODE=local                      DEPLOY_MODE=cloud
data\database.db                       data/users/plus7/database.db
data\final\                            data/users/plus7/final/
data\pending\                          data/users/plus7/pending/

代码修改 ──git push──▶ GitHub Actions ──SSH──▶ deploy.sh ──▶ 服务重启
真实数据 ◀──python scripts\pull_data.py（SFTP，专用只读密钥）─────────
```

- **代码**：通过 Git 同步，push 后自动部署到服务器
- **数据**：单向从云端拉取到本地，本地数据不上传服务器
- **`.env` / `.sync.env`**：各机器独立维护，不进 Git

---

## 前置要求

| 工具 | 说明 | 检查命令 |
|------|------|---------|
| Git | 代码管理 | `git --version` |
| Python 3.10+ | 运行项目 | `python --version` |
| OpenSSH | Windows 10/11 内置 | `ssh -V` |
| paramiko | SSH/SFTP 库 | `pip install paramiko` |

> OpenSSH 若未安装：系统设置 → 可选功能 → 添加"OpenSSH 客户端"

---

## 一、首次配置（每台新机器操作一次）

### 1. 克隆项目

```powershell
git clone <repo-url> MyPresent
cd MyPresent
```

### 2. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
```

### 3. 配置本地运行环境

在项目根目录新建 `.env` 文件，内容固定为：

```
DEPLOY_MODE=local
EMBEDDING_ENABLED=false
```

### 4. 配置数据同步信息

```powershell
copy .sync.env.example .sync.env
```

用记事本打开 `.sync.env`，填入实际值：

```
SYNC_HOST=your-server.com       # 服务器 IP 或域名
SYNC_USER=root                  # SSH 登录用户名
SYNC_PORT=22                    # SSH 端口
SYNC_APP_DIR=/root/MyPresent    # 服务器上的项目路径
SYNC_USERNAME=plus7             # 云端数据用户名
SYNC_KEY_PATH=~/.ssh/mypresent_sync   # 专用只读密钥（自动展开为 C:\Users\你的用户名\.ssh\...）
```

### 5. 生成专用同步密钥

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_sync_key.ps1
```

脚本会：
1. 在 `C:\Users\你的用户名\.ssh\mypresent_sync` 生成专用 ed25519 密钥
2. 打印出需要添加到服务器的 `authorized_keys` 行

**将脚本输出的那一行**追加到服务器 `~/.ssh/authorized_keys`，可用脚本末尾提示的 ssh 命令一步完成。

> **为什么要专用密钥？**
> 该密钥在服务器端被限制为只读 SFTP（`internal-sftp -R`），即使泄露也无法登录 shell、无法写入任何文件，和部署用的主密钥完全隔离。

### 6. 拉取云端数据

**首次连接前**，先用主密钥登录一次服务器，让 Windows 记住服务器指纹：

```powershell
ssh -p 22 root@your-server.com
# 输入 yes 确认指纹后退出即可
exit
```

然后拉取数据：

```powershell
python scripts\pull_data.py
```

---

## 二、日常开发流程

```
1. python scripts\pull_data.py          # 需要真实数据时执行，不需要可跳过
2. .venv\Scripts\streamlit run app.py   # 本地启动
3. 浏览器访问 http://localhost:8501，本地模式无需登录
4. 修改代码，本地验证
5. git add、git commit、git push        # 推送后自动部署到云端
```

---

## 三、pull_data.py 安全机制

每次执行时按以下顺序操作：

| 步骤 | 说明 |
|------|------|
| 备份 | 将当前本地 `data\database.db` 备份到 `backups\sync\`，自动保留最近 10 份 |
| 下载 | 通过 SFTP 将服务器数据库下载到临时文件 `database.db.tmp` |
| 校验 | 对临时文件执行 `PRAGMA integrity_check`，确认 SQLite 完整性 |
| 替换 | 校验通过后才替换本地数据库；失败则中止，原文件不受影响 |
| 媒体 | `final\` 和 `pending\` 按文件大小判断差异，只增不删 |

---

## 四、代码部署流程（自动）

push 到 `main` 分支后，GitHub Actions 自动：

1. SSH 连接到服务器
2. 执行 `deploy.sh`：备份数据库 → `git pull` → 更新依赖 → 重启 systemd 服务

GitHub 仓库需要配置以下 Secrets：

| Secret | 说明 |
|--------|------|
| `SSH_HOST` | 服务器 IP 或域名 |
| `SSH_USER` | SSH 用户名 |
| `SSH_PRIVATE_KEY` | 部署用主密钥（私钥内容） |
| `SSH_PORT` | SSH 端口，默认 22 |
| `APP_DIR` | 服务器上的项目目录 |

---

## 五、常见问题

**Q：`pull_data.py` 提示"请先用主密钥登录一次"**
执行 `ssh root@your-server.com`，输入 `yes` 接受服务器指纹后退出，再重新运行脚本。

**Q：`pull_data.py` 提示 SSH 认证失败**
检查脚本第 5 步的 `authorized_keys` 行是否已正确追加到服务器，密钥文件路径是否与 `.sync.env` 中一致。

**Q：本地不需要真实数据，只想跑起来测试**
跳过 `pull_data.py`，直接启动，`init_db()` 会自动建空库。

**Q：公司和家需要分别操作吗？**
是的，两台机器分别执行一次「首次配置」的全部步骤，各自生成独立密钥，服务器 `authorized_keys` 里会有两行记录，互不影响。

**Q：push 后云端服务没有更新**
检查 GitHub Actions 运行日志，确认以上五个 Secrets 均已在仓库 Settings → Secrets 中配置。

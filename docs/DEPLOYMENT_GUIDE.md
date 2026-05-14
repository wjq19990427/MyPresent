# MyPresent 云端部署指南

> **前提**：task-46 ～ task-50 已全部完成并 merge 到 main 分支。

本指南描述如何将本地 MyPresent 项目**首次迁移到云服务器**，并配置好自动化 CI/CD 流水线，使后续的日常开发只需 `git push` 即可自动上线。

---

## 目录

1. [服务器环境要求](#1-服务器环境要求)
2. [一次性服务器配置](#2-一次性服务器配置)
3. [首次数据迁移（复制本地数据库）](#3-首次数据迁移)
4. [配置 systemd 服务](#4-配置-systemd-服务)
5. [配置 Nginx 反向代理](#5-配置-nginx-反向代理)
6. [配置 GitHub Actions 自动部署](#6-配置-github-actions-自动部署)
7. [验证部署](#7-验证部署)
8. [日常开发工作流](#8-日常开发工作流)
9. [运维手册](#9-运维手册)
10. [常见问题排查](#10-常见问题排查)

---

## 1. 服务器环境要求

| 项目 | 最低要求 | 备注 |
|------|---------|------|
| OS | Ubuntu 22.04 LTS | 其他 Linux 发行版理论可用，未测试 |
| CPU | 2 核 | |
| 内存 | 2 GB（推荐 4 GB） | 启用本地 Embedding 需 4 GB+，强烈不推荐 |
| 磁盘 | 20 GB+ | 媒体文件会持续增长 |
| Python | 3.10+ | `python3 --version` 验证 |
| 公网 IP | 必须 | 或通过 Cloudflare Tunnel 暴露 |
| 域名 | 推荐 | 无域名可用 IP 直接访问 |

---

## 2. 一次性服务器配置

### 2.1 登录服务器，安装依赖

```bash
ssh your_user@your_server_ip

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip git nginx

# 验证
python3 --version
git --version
nginx -v
```

### 2.2 克隆代码仓库

```bash
cd /home/your_user   # 或你偏好的目录，下文以 /home/your_user/mypresent 为例
git clone https://github.com/your_username/mypresent.git
cd mypresent
```

### 2.3 创建 Python 虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.4 配置 `.env`

```bash
cp .env.example .env
nano .env
```

修改以下内容：

```env
DEPLOY_MODE=cloud
EMBEDDING_ENABLED=false    # 2C2G 服务器强烈建议关闭，改用 API
```

其他 API Key（LLM 等）也在此文件配置。

### 2.5 创建必要目录

```bash
mkdir -p data/users backups

# cloud 模式不需要手动建用户子目录，app 首次运行时自动创建
```

---

## 3. 首次数据迁移

将本地数据库**一次性 copy** 到服务器。此后数据只在服务器上增长，不再有回传需求。

### 3.1 本地执行（从你的 Windows 机器）

```powershell
# 将本地 SQLite 数据库上传到服务器
# local 模式数据库路径：data/database.db
scp data/database.db your_user@your_server_ip:/home/your_user/mypresent/data/database.db

# 如果有媒体文件（pending / final）
scp -r data/pending your_user@your_server_ip:/home/your_user/mypresent/data/pending
scp -r data/final   your_user@your_server_ip:/home/your_user/mypresent/data/final
```

> **注意**：迁移到 cloud 模式后，若你是第一个（也是唯一的）用户，可以先以 local 模式启动服务验证数据完整性，确认无误后再切换 `DEPLOY_MODE=cloud` 并进行用户账号体系的 Phase B 开发。

### 3.2 验证数据完整性（服务器上）

```bash
cd /home/your_user/mypresent
source venv/bin/activate

# 临时以 local 模式启动，检查数据是否正常
DEPLOY_MODE=local streamlit run app.py --server.port=8501 --server.headless=true &
# 浏览 http://your_server_ip:8501 验证
# Ctrl+C 停止
```

---

## 4. 配置 systemd 服务

```bash
# 编辑服务模板（替换占位符）
sudo cp infra/mypresent.service /etc/systemd/system/mypresent.service
sudo nano /etc/systemd/system/mypresent.service
```

将模板中的占位符替换为实际值：

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `{YOUR_USER}` | 系统用户名 | `ubuntu` |
| `{APP_DIR}` | 项目绝对路径 | `/home/ubuntu/mypresent` |
| `{PYTHON_PATH}` | venv 中的 python 路径 | `/home/ubuntu/mypresent/venv/bin/python` |

```bash
# 重新加载 systemd，启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable mypresent
sudo systemctl start mypresent

# 验证
sudo systemctl status mypresent
```

常用命令：

```bash
sudo systemctl restart mypresent   # 重启
sudo systemctl stop mypresent      # 停止
journalctl -u mypresent -f         # 实时查看日志
```

---

## 5. 配置 Nginx 反向代理

```bash
# 复制模板
sudo cp infra/nginx.conf.example /etc/nginx/sites-available/mypresent
sudo nano /etc/nginx/sites-available/mypresent
```

将 `{YOUR_DOMAIN}` 替换为你的域名（无域名则填 `_`）。

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/mypresent /etc/nginx/sites-enabled/
sudo nginx -t          # 测试配置语法
sudo systemctl reload nginx
```

### 5.1 配置 HTTPS（推荐）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

certbot 会自动修改 nginx 配置，添加 SSL 证书并设置 HTTP → HTTPS 重定向，WebSocket 配置保持不变。

> ⚠️ **重要**：若不配置 `Upgrade $http_upgrade` 和 `Connection "upgrade"`，Streamlit 前端无法建立 WebSocket 连接，表现为页面无限转圈。`infra/nginx.conf.example` 已包含此配置，不要删除。

---

## 6. 配置 GitHub Actions 自动部署

### 6.1 生成专用部署 SSH 密钥

在**本地**或服务器上生成一对专用密钥（不要复用登录密钥）：

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/mypresent_deploy
# 生成两个文件：mypresent_deploy（私钥）和 mypresent_deploy.pub（公钥）
```

将公钥加入服务器的授权列表：

```bash
# 在服务器上执行
echo "$(cat mypresent_deploy.pub)" >> ~/.ssh/authorized_keys
```

### 6.2 在 GitHub 仓库中配置 Secrets

进入 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加：

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `SSH_HOST` | 服务器 IP 或域名 | 如 `123.45.67.89` |
| `SSH_USER` | 服务器用户名 | 如 `ubuntu` |
| `SSH_PRIVATE_KEY` | 私钥文件全文 | `cat mypresent_deploy` 的输出 |
| `SSH_PORT` | SSH 端口 | 默认 `22` |
| `APP_DIR` | 项目绝对路径 | 如 `/home/ubuntu/mypresent` |

### 6.3 验证 Actions 配置

查看 `.github/workflows/deploy.yml`，确认 `SSH_HOST` 等 Secret 名称与上一步一致，然后：

```bash
git add .
git commit -m "ci: 配置 GitHub Actions 自动部署"
git push origin main
```

在 GitHub → **Actions** 标签页查看运行状态。首次应能看到完整的部署日志。

---

## 7. 验证部署

```bash
# 服务器上
sudo systemctl status mypresent        # 服务应为 active (running)
curl -I http://127.0.0.1:8501          # 应返回 200
curl -I http://your_domain.com         # 通过 Nginx 访问
```

浏览器打开 `http://your_domain.com`，确认：
- 页面正常加载（不转圈）
- 数据完整（之前 copy 的记录可见）
- 功能正常（上传、归档、搜索）

---

## 8. 日常开发工作流

完成上述一次性配置后，日常开发只需：

```
1. 本地编写代码，本地测试（DEPLOY_MODE=local）
2. git add / git commit
3. git push origin main
      ↓ 自动触发
4. GitHub Actions SSH 连接服务器
5. deploy.sh 执行：
   - 备份当前数据库（backups/ 目录，保留 7 天）
   - git pull origin main
   - pip install -r requirements.txt
   - systemctl restart mypresent
6. 部署完成，服务自动恢复
```

> **注意**：若修改涉及数据库 schema 变更，`init_db()` 会在服务重启时自动执行 `ALTER TABLE` 迁移，无需手动操作。

---

## 9. 运维手册

### 查看实时日志

```bash
journalctl -u mypresent -f
```

### 手动触发部署（不推 git 的情况）

```bash
cd /home/your_user/mypresent
bash deploy.sh
```

### 手动备份数据库

```bash
cp data/database.db backups/database_manual_$(date +%Y%m%d_%H%M%S).db
# cloud 模式备份特定用户
cp data/users/alice/database.db backups/alice_manual_$(date +%Y%m%d_%H%M%S).db
```

### 查看备份列表

```bash
ls -lh backups/
```

### 磁盘使用检查

```bash
du -sh data/ backups/ vector_db/
df -h
```

### 更新 .env 配置后重启服务

```bash
nano .env                          # 编辑配置
sudo systemctl restart mypresent   # 重启使配置生效
```

---

## 10. 常见问题排查

### 页面无限转圈 / 组件无响应

**原因**：Nginx 未配置 WebSocket 支持。

**解决**：检查 `/etc/nginx/sites-available/mypresent`，确认存在：
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```
然后 `sudo systemctl reload nginx`。

---

### 服务启动后立即退出

```bash
journalctl -u mypresent -n 50      # 查看最近 50 行日志
```

常见原因：
- `.env` 文件路径错误或缺少必要变量
- Python 依赖未安装完整（`pip install -r requirements.txt`）
- 端口 8501 被占用（`ss -tlnp | grep 8501`）

---

### OOM / 服务器内存不足

```bash
free -h                            # 查看内存使用
```

若内存不足，首先检查 `.env`：

```env
EMBEDDING_ENABLED=false            # 关闭本地 Embedding（最有效）
```

然后重启服务。如需 Embedding 功能，配置外部 API（后续 Phase 中实现）。

---

### GitHub Actions 部署失败

1. 检查 Actions 日志：GitHub → Actions → 对应 workflow 运行记录
2. 验证 Secrets 配置：SSH_HOST / SSH_USER / SSH_PRIVATE_KEY / SSH_PORT
3. 手动测试 SSH 连接：`ssh -i ~/.ssh/mypresent_deploy your_user@your_server_ip`
4. 检查服务器防火墙是否放行 SSH 端口

---

### deploy.sh 执行失败：备份目录不存在

```bash
mkdir -p backups
```

首次运行前需手动创建 `backups/` 目录（deploy.sh 不会自动创建）。

---

*最后更新：配合 task-46 ～ task-50 编写*

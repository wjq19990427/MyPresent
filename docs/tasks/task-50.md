# Task #50 — CI/CD 基础设施：GitHub Actions + deploy.sh + Nginx + systemd

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：基础设施（新建）

搭建从代码提交到云端自动部署的完整流水线。推送代码到 GitHub main 分支后，Actions 自动 SSH 连接服务器执行部署脚本。部署脚本内置数据库备份（保留 7 天）、依赖更新、服务重启。同时提供 Nginx（含 WebSocket 支持）和 systemd 的配置模板。

---

## 目标

完成后，开发者只需 `git push`，云端即自动完成"备份 → 拉取代码 → 更新依赖 → 重启服务"的完整流程，且每次部署前数据库均有快照保护。

## 必读契约

无需读代码契约，本卡只创建基础设施配置文件，不修改任何 Python 代码。

## 改动范围

- **新建**：`.github/workflows/deploy.yml`
- **新建**：`deploy.sh`
- **新建**：`infra/mypresent.service`（systemd 服务单元模板）
- **新建**：`infra/nginx.conf.example`（Nginx 配置模板，含 WebSocket）
- **不许碰**：所有 Python 源代码、`core/`、`components/`、`skills/`

## 接口约定

### 一、`deploy.sh` — 标准部署工作流

脚本位于项目根目录，服务器上执行，需具备可执行权限（`chmod +x deploy.sh`）。

**严格按以下顺序执行，任意步骤失败立即退出（`set -euo pipefail`）：**

```
步骤 1：环境检查
  - 确认 Python3、pip、git 可用
  - 确认 .env 文件存在（不存在则打印提示并退出）
  - 确认 systemd 服务单元文件存在

步骤 2：备份数据库
  - 目标：data/ 目录下所有 database.db（local 模式：data/database.db；
    cloud 模式：data/users/*/database.db）
  - 命名格式：backups/database_YYYYMMDD_HHMMSS.db（local）
             backups/{username}_YYYYMMDD_HHMMSS.db（cloud）
  - 清理策略：删除 backups/ 下超过 7 天的 .db 文件（find + mtime +7 + rm）

步骤 3：拉取最新代码
  - git pull origin main

步骤 4：更新 Python 依赖
  - pip install -r requirements.txt --quiet

步骤 5：重启 systemd 服务
  - systemctl restart mypresent
  - systemctl is-active --quiet mypresent（验证服务正常运行）

步骤 6：部署完成提示
  - 打印部署时间戳和服务状态
```

脚本顶部用变量声明可配置项：`SERVICE_NAME`、`APP_DIR`、`BACKUP_DIR`、`DEPLOY_MODE`（从 .env 读取）。

### 二、`.github/workflows/deploy.yml`

触发条件：`push` 到 `main` 分支。

步骤：
1. 通过 SSH 连接云服务器（使用 GitHub Secrets：`SSH_HOST`、`SSH_USER`、`SSH_PRIVATE_KEY`、`SSH_PORT`）
2. 进入应用目录（路径通过 Secret `APP_DIR` 或硬编码）
3. 执行 `bash deploy.sh`

使用 `appleboy/ssh-action` 或等价的 SSH action。无需 checkout 代码（服务器上直接 git pull）。

workflow 文件需包含注释说明每个 Secret 的用途和设置方式。

### 三、`infra/mypresent.service` — systemd 单元模板

关键配置项（用占位符，部署时替换）：
```
[Unit]
Description=MyPresent Streamlit App
After=network.target

[Service]
Type=simple
User={YOUR_USER}
WorkingDirectory={APP_DIR}
EnvironmentFile={APP_DIR}/.env
ExecStart={PYTHON_PATH} -m streamlit run app.py --server.port=8501 --server.address=127.0.0.1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 四、`infra/nginx.conf.example` — 含 WebSocket 支持

**必须包含以下关键配置，否则 Streamlit 无法正常工作：**

```nginx
server {
    listen 80;
    server_name {YOUR_DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;

        # WebSocket 支持（Streamlit 必需，缺少此配置页面将无限加载）
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
```

注释中标注 HTTPS/SSL 扩展方式（certbot 命令）。

## 不要做

- 不要在 `deploy.sh` 中执行任何数据库 schema 变更（schema 迁移由应用启动时的 `init_db()` 完成）
- 不要在 `deploy.sh` 中 `git reset --hard` 或强制覆盖本地改动
- 不要将真实的服务器 IP、密钥、密码写入任何提交的文件
- 不要修改任何 Python 源代码

## 验收清单

- [ ] `deploy.sh` 语法检查：`bash -n deploy.sh` 无报错
- [ ] `deploy.sh` 包含 `set -euo pipefail`
- [ ] `deploy.sh` 备份逻辑覆盖 local 和 cloud 两种路径模式
- [ ] `deploy.sh` 7 天清理逻辑存在（`find backups/ -name "*.db" -mtime +7 -delete`）
- [ ] `.github/workflows/deploy.yml` 触发条件为 `push: branches: [main]`
- [ ] workflow 文件包含所有必需 Secret 的注释说明
- [ ] `infra/mypresent.service` 包含 `EnvironmentFile` 指向 `.env`
- [ ] `infra/nginx.conf.example` 包含 `Upgrade $http_upgrade` 和 `Connection "upgrade"` 配置
- [ ] `infra/` 目录下的文件均包含中文注释说明占位符的替换方式
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`deploy.sh` 备份的 cloud 模式路径用 `find data/users -name "database.db"` 遍历，每个用户库单独备份，文件名前缀用父目录名（即 username）区分。

Nginx WebSocket 配置是 Streamlit 最常见的部署踩坑点：Streamlit 前端通过 WebSocket 与后端保持长连接，若 Nginx 未配置 `Upgrade` 头，连接会被降级为 HTTP 轮询或直接断开，表现为页面转圈或组件无响应。`proxy_read_timeout 86400` 防止长时间空闲连接被 Nginx 断开。

GitHub Actions 使用 Secrets 存储 SSH 私钥，私钥对应公钥需提前加入服务器的 `~/.ssh/authorized_keys`。

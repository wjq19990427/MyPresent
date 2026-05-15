# Patches — 版本升级补丁

每个补丁脚本负责将数据库从上一个版本迁移到指定版本。

## 说明

- 补丁脚本**幂等**：重复执行不会损坏数据
- 启动 `streamlit run app.py` 时 `init_db()` 会自动完成同样的迁移，补丁脚本是手动验证/执行的备用方式
- 补丁只处理 Schema 变更，不修改业务数据（除非有明确的数据回填逻辑）

## 使用方法

```bash
# 确认当前版本（查看 docs/STATUS.md）
# 按版本顺序依次执行所需的补丁

python patches/patch_v5.1.0.py
python patches/patch_v5.2.0.py
```

## 补丁列表

| 补丁 | 从版本 | 到版本 | 变更内容 |
|------|--------|--------|----------|
| `patch_v5.1.0.py` | v5.0.0 | v5.1.0 | 新增 `emotion_scores` 表；`daily_activities` 加 `start_time/end_time`；`calendar_todos` 加 `postponed_months` |
| `patch_v5.2.0.py` | v5.1.0 | v5.2.0 | `calendar_todos` 加 `parent_id/todo_state`，支持树形待办与三态完成 |

---

## 远程访问部署指南（Cloudflare Tunnel）

### 前提条件

- 域名已托管到 Cloudflare（在阿里云/其他注册商修改 Nameserver 指向 Cloudflare）
- 已安装 cloudflared（下载地址：https://github.com/cloudflare/cloudflared/releases）

### 一次性配置步骤

```bash
# 1. 登录 Cloudflare（会打开浏览器，选择你的域名授权）
cloudflared tunnel login

# 2. 创建 tunnel
cloudflared tunnel create mypresent

# 3. 添加 DNS 记录（将域名指向 tunnel）
cloudflared tunnel route dns mypresent your.domain.com

# 4. 编辑 ~/.cloudflared/config.yml（参考下方模板）
```

**config.yml 模板**：

```yaml
tunnel: <tunnel-id>
credentials-file: C:\Users\<用户名>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: your.domain.com
    service: http://127.0.0.1:8501
  - service: http_status:404
```

### 每次启动

```bash
# 方式一：双击项目根目录的 start.bat（Windows）

# 方式二：手动启动两个进程
python -m streamlit run app.py                    # 窗口1
cloudflared tunnel run mypresent                  # 窗口2
```

### 配置访问密码

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 编辑 secrets.toml，设置 app_password
```

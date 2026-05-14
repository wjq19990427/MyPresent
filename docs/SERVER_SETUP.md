# 云端服务器初始化手册

> 给云端 Claude 的执行指南。当前状态：git clone 完成、database.db 已上传至 `data/`。

---

## 你需要完成的事

1. 创建 Python 虚拟环境并安装依赖
2. 创建 Streamlit 配置文件
3. 配置 systemd 服务
4. 配置 Nginx 反向代理
5. 启动并验证

执行过程中遇到报错立即停下，不要绕过，报告给用户。

---

## 第一步：确认环境与目录结构

```bash
# 确认当前在项目根目录
pwd   # 应输出类似 /home/xxx/mypresent

# 确认数据库已就位
ls data/database.db   # 必须存在，否则停下告知用户

# 确认 Python 版本
python3 --version   # 需要 3.10+
```

---

## 第二步：创建虚拟环境，安装依赖

```bash
python3 -m venv venv
source venv/bin/activate

# 安装依赖（sentence-transformers 较大，耐心等待）
pip install -r requirements.txt
```

> ⚠️ **内存警告**：安装完成后首次启动，应用会尝试加载向量 Embedding 模型，可能导致 2G 内存服务器 OOM。
> 第三步的 systemd 配置中已通过环境变量临时关闭此功能，**务必完整执行第三步再启动服务**。

---

## 第三步：创建配置文件

### 3a. Streamlit 服务器配置

```bash
mkdir -p .streamlit
```

创建文件 `.streamlit/config.toml`，内容如下：

```toml
[server]
headless = true
address = "127.0.0.1"
port = 8501
```

### 3b. 访问密码配置

创建文件 `.streamlit/secrets.toml`，内容如下（**替换为你想设置的密码**）：

```toml
app_password = "your_password_here"
```

此文件已在 `.gitignore` 中忽略，不会被提交。

---

## 第四步：配置 systemd 服务

```bash
# 确认项目绝对路径，后续需要填入
pwd
# 确认 venv 中 python 的绝对路径
which python   # 在 venv 激活状态下执行，形如 /home/xxx/mypresent/venv/bin/python
```

创建文件 `/etc/systemd/system/mypresent.service`（需要 sudo）：

```ini
[Unit]
Description=MyPresent Streamlit App
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/YOUR/APP/PATH
Environment="EMBEDDING_ENABLED=false"
ExecStart=/YOUR/APP/PATH/venv/bin/python -m streamlit run app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**替换三处占位符**：
- `YOUR_USERNAME` → 当前系统用户名（`whoami` 查询）
- `/YOUR/APP/PATH` → 项目绝对路径（两处，`pwd` 查询）

```bash
# 加载并启动服务
sudo systemctl daemon-reload
sudo systemctl enable mypresent
sudo systemctl start mypresent

# 确认运行状态（应显示 active (running)）
sudo systemctl status mypresent
```

如果状态不是 running，执行 `journalctl -u mypresent -n 30` 查看日志并报告给用户。

---

## 第五步：配置 Nginx

```bash
sudo nano /etc/nginx/sites-available/mypresent
```

写入以下内容（**替换 `YOUR_DOMAIN_OR_IP`**）：

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;

        # Streamlit WebSocket 必需，缺少此配置页面将无限转圈
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
```

```bash
# 启用配置
sudo ln -s /etc/nginx/sites-available/mypresent /etc/nginx/sites-enabled/
sudo nginx -t          # 测试语法，必须显示 ok
sudo systemctl reload nginx
```

---

## 第六步：验证

```bash
# 本地验证服务正在监听
curl -I http://127.0.0.1:8501
# 应返回 HTTP 200

# 查看服务日志（有无报错）
journalctl -u mypresent -n 20
```

浏览器访问 `http://YOUR_DOMAIN_OR_IP`，应看到密码输入界面，输入第三步配置的密码后进入应用，确认历史数据可见。

---

## 完成后告知用户

报告以下信息：
- 各步骤是否顺利完成
- `systemctl status mypresent` 的输出
- 访问地址
- 遇到的任何报错或警告

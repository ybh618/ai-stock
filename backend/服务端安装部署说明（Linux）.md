# 服务端安装部署说明（Linux）

本文档用于在 Linux 服务器上部署本项目后端（FastAPI + SQLite + WebSocket + 定时推荐扫描）。

## 1. 环境要求

- 操作系统：Ubuntu 22.04+ / Debian 12+ / CentOS Stream 9+（任一 Linux 发行版均可）
- Python：3.11 或更高
- 网络：可访问 LLM 服务地址、行情/资讯数据源

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

如果是 CentOS/RHEL：

```bash
sudo dnf install -y python3 python3-pip
```

## 3. 拉取代码并创建虚拟环境

```bash
cd /opt
sudo git clone <你的仓库地址> stock-ai
sudo chown -R $USER:$USER /opt/stock-ai
cd /opt/stock-ai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

## 4. 配置环境变量

建议在 `backend/.env` 或 systemd 中配置，关键变量如下：

- `SERVER_HOST`：默认 `0.0.0.0`
- `SERVER_PORT`：默认 `3005`

- `DB_URL`：默认 `sqlite:///./stock_ai.db`
- `LLM_BASE_URL`：如 `https://api.openai.com/v1`
- `LLM_API_KEY`：你的密钥（必填）
- `LLM_MODEL`：如 `gpt-4.1-mini`
- `LLM_MAX_CONCURRENCY`：固定为 `20`
- `SCAN_INTERVAL_MINUTES`：默认 `15`
- `SCHEDULER_ENABLED`：默认 `true`

示例（临时导出）：

```bash
export SERVER_HOST="0.0.0.0"
export SERVER_PORT="3005"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="sk-xxx"
export LLM_MODEL="gpt-4.1-mini"
export LLM_MAX_CONCURRENCY="20"
export SCAN_INTERVAL_MINUTES="15"
```

也可以直接使用样例配置：

```bash
cd /opt/stock-ai/backend
cp .env.example .env
```

## 5. 启动服务（开发/验证）

推荐使用一键脚本（无需手动进入虚拟环境）：

```bash
cd /opt/stock-ai/backend
chmod +x run_server.sh
./run_server.sh
```

验证：

```bash
curl http://127.0.0.1:3005/healthz
```

返回 `{"status":"ok"}` 表示正常。

## 6. 使用 systemd 常驻（生产建议）

创建文件 `/etc/systemd/system/stock-ai-backend.service`：

```ini
[Unit]
Description=Stock AI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/stock-ai/backend
ExecStart=/bin/bash /opt/stock-ai/backend/run_server.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

加载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-ai-backend
sudo systemctl start stock-ai-backend
sudo systemctl status stock-ai-backend
```

查看日志：

```bash
journalctl -u stock-ai-backend -f
```

## 7. 可选：Nginx 反向代理（含 WebSocket）

`/etc/nginx/sites-available/stock-ai-backend` 示例：

```nginx
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:3005;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

生效：

```bash
sudo ln -s /etc/nginx/sites-available/stock-ai-backend /etc/nginx/sites-enabled/stock-ai-backend
sudo nginx -t
sudo systemctl reload nginx
```

## 8. 运行与安全说明

- 当前版本为 MVP：**无鉴权**，依赖 `client_id` 进行匿名归属；不适合直接公网开放给未知用户。
- 建议通过防火墙、白名单或内网网关限制访问来源。
- SQLite 适合 MVP；若并发和数据量增长，建议迁移到 Postgres。
- 资讯抓取与 AkShare 接口可能因外部变更失效，需做持续监控。

## 9. 常见问题

- 启动报错缺少依赖：确认已激活 `.venv` 且执行 `pip install -e .[dev]`
- WebSocket 连接不上：检查反向代理 `Upgrade/Connection` 头是否配置
- 没有推荐产出：检查行情/资讯拉取是否成功、`LLM_API_KEY` 是否有效、日志中是否频繁校验失败

## 10. 调试模式（debug.sh）

`debug.sh` 会执行以下流程：

1. 启动后端服务（读取 `.env`）
2. 向 LLM 发送内容为 `test` 的请求
3. 检查 AkShare 行情接口、资讯抓取接口、数据库、服务状态
4. 将结果输出到服务器日志，并通过 WebSocket 推送 `server.debug.result` 给客户端

使用方式：

```bash
cd /opt/stock-ai/backend
chmod +x run_server.sh debug.sh
./debug.sh
```

可选：只推送给指定客户端（避免广播）：

```bash
export DEBUG_CLIENT_ID="你的client_id"
./debug.sh
```

## 11. 一键更新脚本（update.sh）

项目根目录提供 `update.sh`，可自动从 GitHub 拉取最新代码：

```bash
cd /opt/stock-ai
chmod +x update.sh
./update.sh
```

可选参数（环境变量）：

- `UPDATE_REMOTE`：默认 `origin`
- `UPDATE_BRANCH`：默认 `main`

# ============================================
# 多Agent协同平台 - 后端镜像 (main + worker 共用)
# ============================================
FROM docker:27 AS docker-cli

FROM python:3.11-slim

LABEL app="hh-agent-hub"
LABEL description="Multi-Agent Collaboration Platform Backend"

# 从 docker 镜像复制 CLI（用于启动 claudecode/reasonix 容器）
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

# 创建非 root 用户（Claude Code SDK 要求非 root 才能使用 --dangerously-skip-permissions）
# 添加 docker 组以便访问 Docker socket
RUN groupadd -f docker && useradd -m -s /bin/bash -G docker appuser

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码
COPY backend/ ./backend/
COPY worker/ ./worker/

# 创建数据和日志目录，设置权限（main 以 root 创建目录，worker 以 appuser 需要写权限）
RUN mkdir -p /data /logs && chmod -R 777 /data /logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

EXPOSE 8000

# 默认启动 main 服务（main 以 root 运行，worker 以 appuser 运行）
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# 多Agent协同平台 - 后端镜像 (main + worker 共用)
# ============================================
FROM python:3.11-slim

LABEL app="hh-agent-hub"
LABEL description="Multi-Agent Collaboration Platform Backend"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码
COPY backend/ ./backend/

# 创建数据和日志目录
RUN mkdir -p /data /logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

EXPOSE 8000

# 默认启动 main 服务
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

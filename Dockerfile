# Text-to-SQL Data Analysis Agent Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_ENDPOINT=https://hf-mirror.com

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码与测试数据
COPY app/ ./app/
COPY data/ ./data/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY .env.example .env.example

# 暴露 FastAPI (8000) 与 Streamlit (8501) 端口
EXPOSE 8000 8501

# 默认启动 FastAPI 后端服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

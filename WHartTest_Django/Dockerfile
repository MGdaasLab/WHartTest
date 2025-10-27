# 使用 Python 3.11 官方镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 复制 requirements 文件
COPY requirements.txt .

# 使用 uv 安装 Python 依赖
RUN uv pip install --system -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p media static nltk_data

# 暴露端口
EXPOSE 8000

# 启动命令 - 使用 uvicorn ASGI 服务器支持异步接口
CMD ["bash", "-c", "mkdir -p /app/data/media && python manage.py migrate --noinput && python manage.py init_admin && uvicorn wharttest_django.asgi:application --host 0.0.0.0 --port 8000"]
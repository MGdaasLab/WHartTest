FROM python:3.12-slim

WORKDIR /app

# 设置Hugging Face缓存目录
ENV HF_HOME=/app/.cache/huggingface \
    HF_HUB_CACHE=/app/.cache/huggingface/hub

# 使用国内镜像源加速
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（SQLite开发库）
RUN apt-get update && apt-get install -y libsqlite3-dev

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制项目文件
COPY . .

# 复制已有的模型缓存目录（如果存在）
COPY .cache/huggingface /app/.cache/huggingface

EXPOSE 8000

# 设置默认超级用户环境变量
ENV DJANGO_SUPERUSER_USERNAME=admin \
    DJANGO_SUPERUSER_PASSWORD=123456 \
    DJANGO_SUPERUSER_EMAIL=admin@qq.com

CMD ["sh", "-c", "python manage.py migrate && python manage.py createsuperuser --noinput || true && python manage.py runserver 0.0.0.0:8000"]
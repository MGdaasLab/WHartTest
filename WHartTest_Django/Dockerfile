# ============================================
# 多阶段构建 - 优化后的Dockerfile
# 镜像大小：~1.1GB（从1.74GB减少36.8%）
# ============================================

ARG PYTHON_BASE_IMAGE=python:3.11-slim

# ============================================
# 第一阶段：构建阶段（包含编译工具）
# ============================================
FROM ${PYTHON_BASE_IMAGE} AS builder

ARG APT_BASE_URL=http://deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_FALLBACKS=
ARG HF_ENDPOINT=https://huggingface.co

WORKDIR /build

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_FALLBACKS=${PIP_INDEX_FALLBACKS} \
    FASTEMBED_CACHE_PATH=/root/.cache/fastembed \
    HF_ENDPOINT=${HF_ENDPOINT}

# 安装构建依赖（仅在构建阶段需要）
RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（主镜像失败时自动切换到后备源）
RUN set -eux; \
    install_uv() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "pip install uv via $index"; \
        if python -m pip install --no-cache-dir --retries 5 --timeout 30 -i "$index" uv; then \
          return 0; \
        fi; \
        echo "pip install uv failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_uv

# 复制requirements并安装依赖到虚拟环境
COPY requirements.txt .

# 使用 uv 直接安装到虚拟环境（主镜像失败时自动切换到后备源）
RUN set -eux; \
    uv venv /opt/venv; \
    install_requirements() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "uv pip install via $index"; \
        if uv pip install --python /opt/venv/bin/python --no-cache \
          --default-index "$index" \
          -r requirements.txt; then \
          return 0; \
        fi; \
        echo "uv pip install failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_requirements

# 预下载 BM25 稀疏编码模型（用于混合检索）
# 使用 FASTEMBED_CACHE_PATH 环境变量强制指定缓存路径
# 运行时会继承当前选择的 Hugging Face 下载地址
ENV HOME=/root
RUN mkdir -p /root/.cache/fastembed && \
    /opt/venv/bin/python -c "\
import os; \
os.environ['FASTEMBED_CACHE_PATH'] = '/root/.cache/fastembed'; \
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://huggingface.co'); \
from fastembed import SparseTextEmbedding; \
m = SparseTextEmbedding('Qdrant/bm25'); \
print('BM25 model downloaded to:', os.environ.get('FASTEMBED_CACHE_PATH')); \
" && ls -la /root/.cache/fastembed/

# ============================================
# 第二阶段：运行阶段（仅包含运行时依赖）
# ============================================
FROM ${PYTHON_BASE_IMAGE}

ARG APT_BASE_URL=http://deb.debian.org
ARG HF_ENDPOINT=https://huggingface.co
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG PLAYWRIGHT_DOWNLOAD_HOST=

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    FASTEMBED_CACHE_PATH=/root/.cache/fastembed \
    HF_ENDPOINT=${HF_ENDPOINT} \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST}

# 仅安装运行时必需的系统依赖
RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    supervisor \
    curl \
    git \
    nodejs \
    npm \
    # Playwright 所需的系统依赖
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    # 中文字体支持（解决截图乱码问题）
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    # 旧版Word文档(.doc)解析支持
    antiword \
    catdoc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && fc-cache -fv

# 从构建阶段复制虚拟环境（不包含构建工具）
COPY --from=builder /opt/venv /opt/venv

# 复制第三方许可证声明文件（用于对外分发合规）
COPY THIRD_PARTY_NOTICES.md /app/THIRD_PARTY_NOTICES.md

# 安装 Playwright 浏览器（Chromium）—— 镜像源失败时自动回退官方源
RUN set -eux; \
    if /opt/venv/bin/playwright install chromium; then \
      echo "Playwright chromium installed successfully"; \
    elif [ -n "${PLAYWRIGHT_DOWNLOAD_HOST:-}" ]; then \
      echo "Mirror download failed, retrying with official source..."; \
      PLAYWRIGHT_DOWNLOAD_HOST= /opt/venv/bin/playwright install chromium; \
    else \
      exit 1; \
    fi

# 收集第三方许可证文件（Playwright/Pillow/Chromium/FFmpeg）
RUN set -eux; \
    mkdir -p /app/third_party_licenses/python /app/third_party_licenses/playwright-browsers; \
    cp /app/THIRD_PARTY_NOTICES.md /app/third_party_licenses/THIRD_PARTY_NOTICES.md; \
    site_pkgs="$(/opt/venv/bin/python -c 'import site; print(next(p for p in site.getsitepackages() if p.endswith("site-packages")))')"; \
    copy_python_licenses() { \
      src="$1"; \
      dst="$2"; \
      depth="$3"; \
      [ -d "$src" ] || return 0; \
      mkdir -p "$dst"; \
      find "$src" -maxdepth "$depth" -type f \( -name "LICENSE*" -o -name "COPYING*" -o -name "NOTICE*" \) -exec cp -f {} "$dst"/ \; ; \
    }; \
    for pattern in "playwright-*.dist-info" "pillow-*.dist-info" "Pillow-*.dist-info"; do \
      for dir in "$site_pkgs"/$pattern; do \
        [ -d "$dir" ] || continue; \
        copy_python_licenses "$dir" "/app/third_party_licenses/python/$(basename "$dir")" 2; \
      done; \
    done; \
    for dir in "$site_pkgs"/playwright "$site_pkgs"/PIL; do \
      [ -d "$dir" ] || continue; \
      copy_python_licenses "$dir" "/app/third_party_licenses/python/$(basename "$dir")" 2; \
    done; \
    browser_root="${PLAYWRIGHT_BROWSERS_PATH:-/root/.cache/ms-playwright}"; \
    if [ -d "$browser_root" ]; then \
      find "$browser_root" -maxdepth 4 -type f \( -name "LICENSE*" -o -name "COPYING*" -o -name "NOTICE*" -o -name "ABOUT" \) -exec cp --parents -f {} /app/third_party_licenses/playwright-browsers/ \; ; \
    fi

# 安装 agent-browser CLI 工具及其浏览器
# agent-browser 是 AI Agent 专用的浏览器自动化工具
RUN npm config set registry "${NPM_REGISTRY}" && \
    npm install -g agent-browser && \
    agent-browser install

# 从构建阶段复制预下载的 BM25 模型缓存
COPY --from=builder /root/.cache/fastembed /root/.cache/fastembed

# 复制启动脚本和配置文件
COPY entrypoint.sh /app/entrypoint.sh
COPY supervisord.conf /app/supervisord.conf

# 转换换行符并添加执行权限
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 复制Django项目代码（仅复制必要的Python代码）
COPY manage.py /app/
COPY accounts/ /app/accounts/
COPY api_keys/ /app/api_keys/
COPY knowledge/ /app/knowledge/
COPY langgraph_integration/ /app/langgraph_integration/
COPY mcp_tools/ /app/mcp_tools/
COPY orchestrator_integration/ /app/orchestrator_integration/
COPY projects/ /app/projects/
COPY prompts/ /app/prompts/
COPY requirements/ /app/requirements/
COPY skills/ /app/skills/
COPY task_center/ /app/task_center/
COPY ui_automation/ /app/ui_automation/
COPY testcase_templates/ /app/testcase_templates/
COPY testcases/ /app/testcases/
COPY wharttest_django/ /app/wharttest_django/

# 清理不必要的文件
RUN find /app -type f \( -name "*.sqlite*" -o -name "*.db" -o -name "*.sql" \) -delete && \
    find /app -type d \( -name ".venv" -o -name "venv" -o -name "__pycache__" -o -name ".git" -o -name "*.egg-info" \) -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true

# 创建必要的目录
RUN mkdir -p media static nltk_data /var/log

# 暴露端口
EXPOSE 8000

# 设置启动脚本为入口点
ENTRYPOINT ["/app/entrypoint.sh"]

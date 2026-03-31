"""
wharttest_django 项目的 Django 配置。

由 Django 5.2.1 的 'django-admin startproject' 生成。

本文件更多说明见：
https://docs.djangoproject.com/en/5.2/topics/settings/

完整配置项与取值说明见：
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

# 导入 Path，用于跨平台路径拼接与解析。
from pathlib import Path



# 导入 os，用于读取和写入环境变量。
import os

# 导入 dotenv 加载器，用于读取 .env 配置。
from dotenv import load_dotenv

# 在项目内构建路径时可使用：BASE_DIR / 'subdir'。
# 计算项目根目录（settings.py 的上两级目录）。
BASE_DIR = Path(__file__).resolve().parent.parent

# 从 .env 文件加载环境变量
# 从项目根目录的 .env 文件加载环境变量到进程环境。
load_dotenv(BASE_DIR / ".env")


# 处理HuggingFace环境变量的相对路径
# 将.env文件中的相对路径转换为绝对路径
# 定义 HuggingFace 路径变量标准化函数。
def setup_huggingface_env():
    """设置HuggingFace环境变量，处理相对路径"""
    hf_vars = [
        "HF_HOME",
        "HF_HUB_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
    ]

    for var in hf_vars:
        # 读取当前变量值。
        value = os.environ.get(var)
        if value and not os.path.isabs(value):
            # 如果是相对路径，转换为绝对路径
            # 基于 BASE_DIR 计算绝对路径。
            abs_path = str(BASE_DIR / value)
            # 回写环境变量，统一后续依赖读取结果。
            os.environ[var] = abs_path


# 设置HuggingFace环境变量
# 启动时立即执行路径标准化，避免运行期路径歧义。
setup_huggingface_env()


# 开发环境快速启动配置（不适用于生产）
# 参考：https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# 安全警告：生产环境必须妥善保管密钥！
# 从环境变量加载 SECRET_KEY。
# 开发环境下若未配置环境变量，会使用默认（不安全）密钥。
# 生产环境必须显式设置强随机且唯一的 DJANGO_SECRET_KEY。
# 优先从环境变量读取 Django 密钥。
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-jsto-5oth_9(a_xfy#zg@$i$0w47h9a$rw0s&(v#1o5t+s-!*7",  # 开发环境兜底值
)

# 安全警告：生产环境禁止开启 DEBUG！
# 从环境变量加载 DEBUG 开关；生产环境默认应为 False。
# 开发环境可设置 DJANGO_DEBUG=True。
# 将字符串环境变量转换为布尔调试开关。
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# ALLOWED_HOSTS 配置
# 从环境变量读取允许主机（逗号分隔）。
# 生产环境应通过 DJANGO_ALLOWED_HOSTS 配置正式域名。
# 读取允许主机列表原始字符串。
ALLOWED_HOSTS_ENV = os.environ.get("DJANGO_ALLOWED_HOSTS")
if ALLOWED_HOSTS_ENV:
    # 解析逗号分隔主机并去除空白。
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(",")]
elif DEBUG:
    # Django 测试客户端默认会使用 testserver 主机名。
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "testserver",
    ]
else:
    # 生产环境必须通过 DJANGO_ALLOWED_HOSTS 显式配置允许主机。
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
    ]


# 应用定义

# 注册 Django/第三方/业务应用。
INSTALLED_APPS = [
    "daphne",  # Channels 的 ASGI server，需优先加载。
    "django.contrib.admin",  # Django 管理后台。
    "django.contrib.auth",  # 用户认证与权限系统。
    "django.contrib.contenttypes",  # 通用内容类型框架（权限/通用关系依赖）。
    "django.contrib.sessions",  # 会话管理。
    "django.contrib.messages",  # 消息提示框架。
    "django.contrib.staticfiles",  # 静态资源管理。
    "rest_framework",  # Django REST Framework 核心。
    "rest_framework_simplejwt",  # JWT 认证实现。
    "django_filters",  # 启用 django-filter。
    "channels",  # 启用 Django Channels。
    "accounts",  # 账户与认证应用。
    "projects",  # 项目管理应用。
    "testcases",  # 测试用例管理应用。
    "drf_spectacular",  # OpenAPI Schema 生成与文档支持。
    "corsheaders",  # CORS 跨域支持。
    "langgraph_integration",  # LangGraph 集成应用。
    "mcp_tools",  # MCP 工具应用。
    "api_keys",  # API Key 管理应用。
    "knowledge",  # 知识库应用。
    "prompts",  # 提示词管理应用。
    "requirements",  # 需求评审应用。
    "orchestrator_integration",  # 智能编排应用。
    "skills",  # Skill 管理应用。
    "testcase_templates",  # 用例模板应用。
    "ui_automation",  # UI 自动化应用。
    'task_center', # 任务中心应用
    'django_celery_beat', # Celery Beat 数据库调度器
]

# ASGI 配置（用于 Channels WebSocket）
# 指定 ASGI 入口，支持 WebSocket。
ASGI_APPLICATION = "wharttest_django.asgi.application"

# Channels Layer 配置（使用内存后端，生产环境建议使用 Redis）
# 配置 Channels 通道层后端。
CHANNEL_LAYERS = {
    "default": {
        # 使用内存通道层（适合开发/单进程场景）。
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# 配置请求处理中间件执行链。
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # 安全增强中间件（HTTPS 重定向、安全头等）。
    "django.contrib.sessions.middleware.SessionMiddleware",  # 会话读写中间件。
    "corsheaders.middleware.CorsMiddleware",  # CORS 中间件需放在 CommonMiddleware 前。
    "django.middleware.common.CommonMiddleware",  # 通用请求处理（URL 规范化等）。
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF 防护中间件。
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # 将用户对象绑定到 request。
    "django.contrib.messages.middleware.MessageMiddleware",  # 消息框架中间件。
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # 防点击劫持响应头。
]

# 指定项目根路由模块。
ROOT_URLCONF = "wharttest_django.urls"

# 配置模板引擎与上下文处理器。
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# 指定 WSGI 入口（传统同步部署场景）。
WSGI_APPLICATION = "wharttest_django.wsgi.application"


# 数据库配置
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# 生产环境建议使用 PostgreSQL 或 MySQL，并通过环境变量配置。
# PostgreSQL 示例（需安装 psycopg2-binary）：
# 可按需基于 DATABASE_URL 与 dj_database_url 扩展此处配置。

# 数据库配置
# 支持通过环境变量配置数据库类型和连接参数
# DATABASE_TYPE: sqlite (默认) 或 postgres
# DATABASE_PATH: SQLite 文件路径（仅 sqlite 模式）
# POSTGRES_*: PostgreSQL 连接参数（仅 postgres 模式）

# 读取数据库类型（默认 postgres）。
DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "postgres")

if DATABASE_TYPE == "postgres":
    # PostgreSQL 配置
    # 构建 Django 数据库连接配置。
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "wharttest"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "8919"),
            "OPTIONS": {
                "connect_timeout": 5,
            },
            # 连接保持 600 秒（10 分钟），减少频繁建连开销。
            "CONN_MAX_AGE": 600,
            # 启用连接健康检查。
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    # SQLite 配置（默认，用于本地开发）
    # 读取可选 SQLite 文件路径。
    DATABASE_PATH = os.environ.get("DATABASE_PATH")
    if DATABASE_PATH:
        # 使用环境变量指定的路径（Docker部署）
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": DATABASE_PATH,
            }
        }
    else:
        # 使用默认路径（本地开发）
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }


# 密码校验
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    # 校验密码与用户属性相似度，防止弱口令。
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    # 最小密码长度校验。
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    # 常见弱密码黑名单校验。
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    # 纯数字密码校验。
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# 国际化
# https://docs.djangoproject.com/en/5.2/topics/i18n/

# 默认语言为简体中文。
LANGUAGE_CODE = "zh-Hans"

# 默认时区为亚洲/上海。
TIME_ZONE = "Asia/Shanghai"

# 启用 Django 国际化。
USE_I18N = True

# 启用时区感知时间处理。
USE_TZ = True


# 静态文件（CSS、JavaScript、图片）
# https://docs.djangoproject.com/en/5.2/howto/static-files/

# 静态资源访问前缀。
STATIC_URL = "static/"
# 生产环境可配置 STATIC_ROOT 以支持 collectstatic
# 例如：可将 STATIC_ROOT 设为 BASE_DIR / "staticfiles"

# 媒体文件（用户上传）
# https://docs.djangoproject.com/en/5.2/topics/files/
# 用户上传文件访问前缀。
MEDIA_URL = "/media/"
# 支持通过环境变量配置 MEDIA_ROOT，用于 Docker 部署
# 相对路径会基于 BASE_DIR 解析，绝对路径直接使用
# 读取 MEDIA_ROOT 环境变量。
_media_root_env = os.environ.get("MEDIA_ROOT", "")
if _media_root_env:
    _media_path = Path(_media_root_env)
    # 如果是相对路径，基于 BASE_DIR 解析（确保路径一致性，不依赖工作目录）
    if not _media_path.is_absolute():
        MEDIA_ROOT = str((BASE_DIR / _media_root_env).resolve())
    else:
        MEDIA_ROOT = str(_media_path)
else:
    # 默认使用 BASE_DIR/media
    MEDIA_ROOT = str(BASE_DIR / "media")


# 默认主键字段类型
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF 全局配置。
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",  # 优先使用 JWT 认证。
        "api_keys.authentication.APIKeyAuthentication",  # 回退到 API Key 认证。
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",  # 默认要求用户已认证。
        "wharttest_django.permissions.DjangoModelPermissions",  # 使用扩展后的模型权限控制。
    ],
    # 默认过滤后端列表。
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",  # 字段过滤后端。
        "rest_framework.filters.SearchFilter",  # 关键字搜索后端。
        "rest_framework.filters.OrderingFilter",  # 排序后端。
    ],
    # OpenAPI Schema 生成类。
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "wharttest_django.renderers.UnifiedResponseRenderer",
        # 如果你仍然希望在浏览器中看到 DRF 的可浏览 API 界面进行调试，
        # 可以取消下面这行注释。但请注意，它的输出不会经过 UnifiedResponseRenderer。
        # 可按需启用 BrowsableAPIRenderer。
    ),
    # 'DEFAULT_PARSER_CLASSES': [ # 如需显式声明，可保留 JSONParser
    #     # 可按需显式启用 JSONParser。
    # ],
    # 'EXCEPTION_HANDLER': 'your_project_name.utils.custom_exception_handler', # 如果需要更细致的异常处理
}

# CORS 配置
# 生产环境应设置 DJANGO_CORS_ALLOWED_ORIGINS（逗号分隔）。
# 读取 CORS 允许来源环境变量。
CORS_ALLOWED_ORIGINS_ENV = os.environ.get("DJANGO_CORS_ALLOWED_ORIGINS")
if CORS_ALLOWED_ORIGINS_ENV:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(",")
    ]
elif DEBUG:
    # 开发环境默认值：允许前端常见端口跨域访问
    CORS_ALLOWED_ORIGINS = [
        # Nginx 默认 80 端口。
        "http://localhost",
        "http://127.0.0.1",
        # React 默认端口。
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Vite 默认端口。
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Vue/Angular 常用端口。
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        # Django 开发服务器端口。
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
else:
    # 生产环境需通过 DJANGO_CORS_ALLOWED_ORIGINS 显式配置。
    CORS_ALLOWED_ORIGINS = []

# 生产环境默认不允许任意来源。
CORS_ALLOW_ALL_ORIGINS = False

# 允许发送认证信息（Cookie、Authorization 等）。
CORS_ALLOW_CREDENTIALS = True

# 允许的HTTP方法
CORS_ALLOW_METHODS = [
    "DELETE",  # 删除资源。
    "GET",  # 获取资源。
    "OPTIONS",  # 预检请求。
    "PATCH",  # 局部更新。
    "POST",  # 创建资源。
    "PUT",  # 全量更新。
]

# 允许的请求头
CORS_ALLOW_HEADERS = [
    "accept",  # 可接受的响应类型声明。
    "authorization",  # 认证信息头。
    "content-type",  # 请求体类型声明。
    "user-agent",  # 客户端标识头。
    "x-csrftoken",  # CSRF Token 头。
    "x-requested-with",  # AJAX 请求标识头。
]

# CSRF 可信来源：当前后端位于不同子域/端口，且使用会话认证或 CSRF 保护时尤为重要。
# 若主要使用 JWT（如 /api/token/），该项影响相对较小，但仍建议规范配置。
# 生产环境建议从 DJANGO_CSRF_TRUSTED_ORIGINS 读取。
# 读取 CSRF 可信来源环境变量。
CSRF_TRUSTED_ORIGINS_ENV = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS")
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in CSRF_TRUSTED_ORIGINS_ENV.split(",")
    ]
elif DEBUG:
    # 开发环境默认可信来源列表。
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost",  # 本地域名。
        "http://127.0.0.1",  # 本地回环地址。
        "http://localhost:3000",  # React 常用端口。
        "http://127.0.0.1:3000",  # React 回环地址。
        "http://localhost:8080",  # Vue/Angular 常用端口。
        "http://127.0.0.1:8080",  # Vue/Angular 回环地址。
        "http://localhost:8000",  # Django 本地服务地址。
        "http://127.0.0.1:8000",  # Django 回环服务地址。
    ]
else:
    CSRF_TRUSTED_ORIGINS = []


# CORS配置已在上面设置

# Simple JWT 配置
# 导入时间间隔类型，用于 JWT 有效期配置。
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),  # 访问令牌有效期 12 小时。
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # 刷新令牌有效期 7 天。
    "ROTATE_REFRESH_TOKENS": True,  # 刷新时轮换刷新令牌。
    "BLACKLIST_AFTER_ROTATION": False,  # 不启用黑名单机制。
    "UPDATE_LAST_LOGIN": False,  # 不更新最后登录时间。
    "ALGORITHM": "HS256",  # 使用 HS256 签名算法。
    "SIGNING_KEY": SECRET_KEY,  # 使用 Django SECRET_KEY 作为签名密钥。
    "AUTH_HEADER_TYPES": ("Bearer",),  # 认证头类型。
    "USER_ID_FIELD": "id",  # 用户 ID 字段名。
    "USER_ID_CLAIM": "user_id",  # token 中用户 ID claim 名称。
}

# 日志输出目录
LOGS_DIR = BASE_DIR / "data" / "logs"
# 自动创建日志目录。
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
# Python logging 全局配置。
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}:{lineno} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "detailed": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        # 控制台输出
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # 应用总日志文件 - 使用安全的时间轮转处理器
        "app_file": {
            "level": "INFO",
            "class": "wharttest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "when": "midnight",
            "interval": 1,
            # 保留 30 天归档。
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        # 错误日志文件 - 只记录ERROR及以上
        "error_file": {
            "level": "ERROR",
            "class": "wharttest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "error.log"),
            "when": "midnight",
            "interval": 1,
            # 错误日志保留 60 天。
            "backupCount": 60,
            "formatter": "detailed",
            "encoding": "utf-8",
        },
        # Requirements应用专用日志
        "requirements_file": {
            "level": "DEBUG",
            "class": "wharttest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "requirements.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        # Celery任务日志
        "celery_file": {
            "level": "INFO",
            "class": "wharttest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "celery.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        # Django核心日志
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Requirements应用日志
        "requirements": {
            "handlers": ["console", "requirements_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "requirements.services": {
            "handlers": ["console", "requirements_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "requirements.tasks": {
            "handlers": ["console", "celery_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Celery日志
        "celery": {
            "handlers": ["console", "celery_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # MCP工具日志
        "mcp_tools": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Knowledge应用日志
        "knowledge": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "knowledge.services": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Testcases应用日志
        "testcases": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "testcases.views": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "testcases.serializers": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Orchestrator集成应用日志(Agent Loop压缩调试)
        "orchestrator_integration": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # LangGraph集成日志
        "langgraph_integration": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 三方AI框架与SDK日志（排查模型调用失败）
        "langchain": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langchain_core": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langchain_openai": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langgraph": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "openai": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "httpx": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Celery配置
# Celery使用Redis作为broker和backend
# Celery Broker 连接地址。
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "redis://localhost:6379/0"
)  # Broker 连接地址。
# Celery 结果后端连接地址。
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)  # 任务结果后端连接地址。

# Celery 6.0+ 启动时重试连接
# Worker 启动时若 broker 不可用则自动重试。
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True  # 启动时若 broker 暂不可用则自动重试。

# Celery时区设置
# Celery 使用与 Django 一致的时区。
CELERY_TIMEZONE = TIME_ZONE  # 任务调度时区。
# Celery 内部启用 UTC 时间基准。
CELERY_ENABLE_UTC = True  # 内部时间统一按 UTC 处理。

# Celery任务结果配置
CELERY_RESULT_EXTENDED = True  # 返回扩展任务元信息。
CELERY_RESULT_EXPIRES = 3600  # 结果过期时间（秒）。

# Celery任务序列化
CELERY_TASK_SERIALIZER = "json"  # 任务消息序列化格式。
CELERY_RESULT_SERIALIZER = "json"  # 任务结果序列化格式。
CELERY_ACCEPT_CONTENT = ["json"]  # Worker 允许接收的消息内容类型。

# Celery任务路由 - task_center 使用独立队列，避免被其他 worker 误消费
CELERY_TASK_ROUTES = {
    'task_center.tasks.*': {'queue': 'task_center'},
}

# Celery Beat 调度器配置
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery任务配置
CELERY_TASK_TRACK_STARTED = True  # 追踪任务开始状态。
CELERY_TASK_TIME_LIMIT = 30 * 60  # 任务硬超时（秒，30 分钟）。
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 任务软超时（秒，25 分钟）。

# Celery Worker配置
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Worker 预取任务数量。
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Worker 子进程处理任务上限后重启。

# Celery日志配置
# Celery Worker 日志格式。
CELERY_WORKER_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
# Celery 任务级日志格式。
CELERY_WORKER_TASK_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# 内部API基础URL配置 - 用于Celery任务等内部服务调用
# 在Docker环境中应设置为 http://backend:8000
# 在本地开发环境中可以使用 http://localhost:8000
# 内部服务调用基础地址。
BASE_URL = os.environ.get("DJANGO_BASE_URL", "http://localhost:8000")

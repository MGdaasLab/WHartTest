"""媒体文件访问视图（/media/）。

生产/容器部署会设置 DJANGO_DEBUG=False，而前端 nginx 仍把 /media/ 反代到后端，
因此媒体路由不能依赖 DEBUG（原 django.conf.urls.static.static() 只在 DEBUG=True
时注册路由，导致上传文件在生产环境全部 404）。

访问控制与响应头统一在本模块处理：
- 请求路径规范化后按真实路径（realpath）收敛，软链逃逸、.. 越界一律 404；
- 不应对浏览器公开的敏感目录（需求文档原件、技能登录态快照、技能包）一律 404；
- 仅栅格图片与 PDF 允许内联展示，其余强制作为附件下载，避免上传目录里的
  .html/.svg/.xml 等文件形成同源存储型 XSS；所有媒体响应带 nosniff 与
  default-src 'none' 的 CSP。

安全边界说明：realpath 收敛只能识别路径与软链层面的越界，硬链接（同一文件系统内
对源文件有权限才能创建）在文件系统层面就是普通文件，无法通过路径判定拦截。因此
deny-list 的定位是“阻止未认证外部直读”，不是“防御已取得 data 目录写权限的进程”；
容器化部署下应把敏感数据与沙箱可写目录彻底隔离。
"""

import logging
import mimetypes
import posixpath
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.http import (
    FileResponse,
    Http404,
    HttpResponseNotAllowed,
    HttpResponseNotModified,
)
from django.utils.http import http_date
from django.views.static import was_modified_since

logger = logging.getLogger(__name__)

# 不允许通过 /media/ 对外公开的目录（内部数据：已有鉴权接口或仅供服务内部读取）。
_DENIED_PREFIXES = (
    # 需求文档原件：前端统一走 /api/requirements/documents/<id>/download-file/ 鉴权下载。
    "requirement_documents/",
    # Playwright 登录态快照：包含 Cookie / Token，仅服务内部注入使用。
    "skill_runtime/ui-auth-state/",
    # 技能包：安装时会注入平台 API Key（skills/platform_skills.py），仅供 skill-runner
    # 通过共享卷读取，对外下载走 /api/v1/skills/... 鉴权接口。
    "skills/",
)

# 允许浏览器内联打开的响应类型；其余一律作为附件下载。
_INLINE_CONTENT_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "application/pdf",
    }
)

_ALLOWED_METHODS = ("GET", "HEAD")


def build_media_url_pattern(media_url):
    """由 MEDIA_URL 生成媒体路由正则；无效前缀返回 None（不注册路由）。

    前缀要求边界匹配：MEDIA_URL="/media" 时不能把 "/mediafoo" 也识别成媒体路径。
    MEDIA_URL 带域名（如 CDN 地址）时由外部服务提供文件，这里不注册路由。
    """
    if not media_url:
        return None
    parsed = urlsplit(str(media_url))
    if parsed.netloc:
        logger.warning("MEDIA_URL 包含域名，媒体路由不由 Django 提供：%s", media_url)
        return None
    prefix = parsed.path.strip("/")
    if not prefix:
        return None
    return r"^%s(?:/(?P<path>.*))?$" % re.escape(prefix)


def _resolve_media_file(path):
    """把请求路径收敛为 MEDIA_ROOT 内的真实文件；越界/缺失/敏感目录返回 None。"""
    normalised = posixpath.normpath(path or "")
    if (
        normalised in ("", ".")
        or normalised == ".."
        or normalised.startswith("../")
        or posixpath.isabs(normalised)
    ):
        return None

    try:
        media_root = Path(settings.MEDIA_ROOT).resolve()
        resolved = (media_root / normalised).resolve()
        if not resolved.is_relative_to(media_root) or not resolved.is_file():
            return None
    except (OSError, ValueError, RuntimeError):
        # 软链指环（RuntimeError）、路径含 NUL（ValueError）、路径过长（OSError）等
        # 异常路径统一按“不存在”处理，避免未认证请求触发 500 与异常栈。
        return None

    # 敏感目录判定要用解析后的相对路径，防止通过软链映射到被禁目录。
    relative = resolved.relative_to(media_root).as_posix()
    if any(relative.startswith(prefix) for prefix in _DENIED_PREFIXES):
        return None
    return resolved


def _build_response(request, fullpath):
    content_type = mimetypes.guess_type(str(fullpath))[0] or "application/octet-stream"
    try:
        stat = fullpath.stat()
    except OSError:
        raise Http404("媒体文件不存在")

    if not was_modified_since(
        request.META.get("HTTP_IF_MODIFIED_SINCE"), stat.st_mtime
    ):
        response = HttpResponseNotModified()
        response["X-Content-Type-Options"] = "nosniff"
        return response

    response = FileResponse(
        open(fullpath, "rb"),
        content_type=content_type,
        as_attachment=content_type not in _INLINE_CONTENT_TYPES,
        filename=fullpath.name,
    )
    response["Last-Modified"] = http_date(stat.st_mtime)
    response["X-Content-Type-Options"] = "nosniff"
    # 与 file_management 的预览/下载一致：媒体内容不允许加载任何子资源。
    response["Content-Security-Policy"] = "default-src 'none';"
    return response


def serve_media(request, path=None):
    """按当前 settings.MEDIA_ROOT 返回媒体文件。"""
    if request.method not in _ALLOWED_METHODS:
        return HttpResponseNotAllowed(_ALLOWED_METHODS)
    fullpath = _resolve_media_file(path)
    if fullpath is None:
        raise Http404("媒体文件不存在")
    try:
        return _build_response(request, fullpath)
    except OSError:
        raise Http404("媒体文件不存在")

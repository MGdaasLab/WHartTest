import os
from pathlib import Path, PurePosixPath


TRUE_VALUES = {'1', 'true', 'yes', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'off'}


def parse_bool_env(value: str | None) -> bool | None:
    """解析环境变量中的布尔值。"""
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def is_running_in_container() -> bool:
    """检测当前是否运行在容器环境中。"""
    explicit = parse_bool_env(os.environ.get('WHARTTEST_ACTUATOR_DOCKER'))
    if explicit is not None:
        return explicit

    return (
        Path('/.dockerenv').exists()
        or os.environ.get('container') == 'docker'
        or bool(os.environ.get('KUBERNETES_SERVICE_HOST'))
    )


def has_display_server() -> bool:
    """检测是否存在可用的图形显示环境。"""
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


def should_force_headless() -> bool:
    """在容器内且无显示服务时，应强制使用无头模式。"""
    return is_running_in_container() and not has_display_server()


def _normalize_posix_path(value: str) -> str:
    return value.replace('\\', '/')


def _is_relative_to(path: PurePosixPath, parent: PurePosixPath) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_runtime_file_path(file_path: str) -> str:
    """将后端下发的文件路径转换为当前执行器可访问的路径。

    后端本地运行、执行器容器运行时，FileField.path 会是宿主机/WSL
    绝对路径，例如 /home/.../wharttest/data/media/xxx；容器内同一目录
    通过 compose 挂载在 /app/data。这里仅在容器模式下做路径映射。
    """
    if not file_path or not is_running_in_container():
        return file_path

    if os.path.exists(file_path):
        return file_path

    container_data_dir = os.environ.get('WHARTTEST_ACTUATOR_CONTAINER_DATA_DIR', '/app/data')
    host_data_dir = os.environ.get('WHARTTEST_ACTUATOR_HOST_DATA_DIR', '')

    normalized = _normalize_posix_path(file_path)
    source = PurePosixPath(normalized)
    target_root = PurePosixPath(_normalize_posix_path(container_data_dir))

    if host_data_dir:
        host_root = PurePosixPath(_normalize_posix_path(host_data_dir))
        if _is_relative_to(source, host_root):
            return str(target_root / source.relative_to(host_root))

    parts = source.parts
    if 'data' in parts:
        data_index = parts.index('data')
        suffix_parts = parts[data_index + 1:]
        if not suffix_parts:
            return str(target_root)
        return str(target_root / PurePosixPath(*suffix_parts))

    return file_path


def trusted_upload_roots() -> list[Path]:
    """允许平台下发路径落点的可信根目录列表。

    默认信任两类目录：
    1. 上传缓存目录（平台按 file_id 拉取后的落地处）
    2. 平台数据目录（容器挂载的 media，对应后端 FileField 路径映射目标）
    运维可用 ``WHARTTEST_ACTUATOR_TRUSTED_UPLOAD_ROOTS`` 追加（逗号分隔绝对路径）。
    """
    roots: list[Path] = []

    upload_cache = os.environ.get(
        'WHARTTEST_ACTUATOR_UPLOAD_CACHE_DIR', './data/runtime_uploads'
    )
    roots.append(Path(upload_cache).resolve())

    container_data = os.environ.get(
        'WHARTTEST_ACTUATOR_CONTAINER_DATA_DIR', '/app/data'
    )
    roots.append(Path(container_data).resolve())

    # 非容器部署（后端与执行器同机）时，后端下发的是本机 MEDIA_ROOT 绝对路径
    # （默认 <BASE_DIR>/media，配置 MEDIA_ROOT=../data/media 时为 <repo>/data/media），
    # 因此把本机 media 目录也纳入可信根，否则平台文件会被误拒。
    media_root = os.environ.get('WHARTTEST_ACTUATOR_MEDIA_ROOT', '')
    if media_root:
        roots.append(Path(media_root).resolve())

    extra = os.environ.get('WHARTTEST_ACTUATOR_TRUSTED_UPLOAD_ROOTS', '')
    for item in extra.split(','):
        item = item.strip()
        if item:
            roots.append(Path(item).resolve())

    return roots


def is_path_within(file_path: str | os.PathLike, root: str | os.PathLike) -> bool:
    """判断真实路径是否位于 root 之内（两侧都过 realpath，防符号链接逃逸）。"""
    try:
        resolved = Path(file_path).resolve()
        root_resolved = Path(root).resolve()
        resolved.relative_to(root_resolved)
        return True
    except (ValueError, OSError):
        return False


def is_trusted_upload_path(file_path: str | os.PathLike) -> bool:
    """路径是否落在任一可信根内。

    平台任务数据（用例步骤）属于不可信输入：不限定落点的话，
    ``upload`` 步骤可让执行器读取其所在机器上的任意文件并上传到被测页面。
    """
    return any(is_path_within(file_path, root) for root in trusted_upload_roots())

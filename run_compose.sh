#!/usr/bin/env bash
set -euo pipefail

# 统一 Docker 启动脚本。
# 用法：
#   ./run_compose.sh                 # 交互选择远程镜像 / 本地构建
#   ./run_compose.sh remote         # 使用远程预构建镜像
#   ./run_compose.sh local          # 使用本地源码构建镜像
#   ./run_compose.sh local docker-compose.local.yml

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="$SCRIPT_DIR"

cd "$REPO_ROOT"

LOG_DIR="data/docker-logs"
ENV_FILE=${DOCKER_ENV_FILE:-.env}
DEPLOY_MODE=""
COMPOSE_FILE=""
COMPOSE_CMD=()
_RANKED_DIR=""
mkdir -p "$LOG_DIR"

usage() {
  cat <<'USAGE'
用法:
  ./run_compose.sh [remote|local] [compose-file]

模式:
  remote   远程拉取预构建镜像（默认 compose: docker-compose.yml）
  local    本地源码构建镜像（默认 compose: docker-compose.local.yml）

环境变量:
  DOCKER_DEPLOY_MODE=remote|local
  DOCKER_SOURCE_PROFILE=auto|native|mirror
  DOCKER_BUILD_NO_CACHE=1
  DOCKER_BUILD_PULL=1
  DOCKER_REMOTE_PULL=0|1
  DOCKER_PIP_INDEX_FALLBACKS="url1 url2"
  DOCKER_*_CANDIDATES_EXTRA="name|base_url|probe_url;name2|base_url|probe_url"
USAGE
}

load_env_file() {
  if [ -f "$ENV_FILE" ]; then
    echo "检测到环境文件: $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source <(sed 's/\r$//' "$ENV_FILE")
    set +a
  fi
}

prompt_deploy_mode() {
  local choice=""

  echo "请选择部署方式："
  echo "  1) 远程镜像下载（不本地构建，自动选择更快镜像仓库，如 1Panel/1MS/轩辕/DaoCloud/NJU/Azure China）"
  echo "  2) 本地构建镜像（使用 docker-compose.local.yml，并自动选最快下载源）"

  while true; do
    read -r -p "请输入 1 或 2（默认 1）: " choice
    choice=${choice:-1}

    case "$choice" in
      1|remote)
        DEPLOY_MODE="remote"
        return 0
        ;;
      2|local)
        DEPLOY_MODE="local"
        return 0
        ;;
      *)
        echo "输入无效，请输入 1 或 2。"
        ;;
    esac
  done
}

resolve_mode_and_compose() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      remote|local)
        DEPLOY_MODE="$1"
        ;;
      *.yml|*.yaml)
        COMPOSE_FILE="$1"
        ;;
      *)
        echo "错误：无法识别参数 '$1'" >&2
        usage >&2
        exit 1
        ;;
    esac
    shift
  done

  if [ -z "$DEPLOY_MODE" ] && [ -n "${DOCKER_DEPLOY_MODE:-}" ]; then
    DEPLOY_MODE="$DOCKER_DEPLOY_MODE"
  fi

  if [ -z "$DEPLOY_MODE" ]; then
    if [ -t 0 ] && [ -t 1 ]; then
      prompt_deploy_mode
    else
      DEPLOY_MODE="local"
      echo "未指定部署方式，非交互环境下默认使用本地构建模式。"
    fi
  fi

  case "$DEPLOY_MODE" in
    remote)
      COMPOSE_FILE=${COMPOSE_FILE:-${DOCKER_REMOTE_COMPOSE_FILE:-docker-compose.yml}}
      ;;
    local)
      COMPOSE_FILE=${COMPOSE_FILE:-${DOCKER_LOCAL_COMPOSE_FILE:-docker-compose.local.yml}}
      ;;
    *)
      echo "错误：DOCKER_DEPLOY_MODE 仅支持 remote 或 local，当前值为 '$DEPLOY_MODE'" >&2
      exit 1
      ;;
  esac

  if [ ! -f "$COMPOSE_FILE" ]; then
    echo "错误：compose 文件不存在: $COMPOSE_FILE" >&2
    exit 1
  fi

  echo "部署模式: $DEPLOY_MODE"
  echo "使用的 compose 文件: $COMPOSE_FILE"
}

probe_url() {
  local url="$1"
  local timeout="${2:-3}"

  if command -v curl >/dev/null 2>&1; then
    curl -fsS -o /dev/null -w '%{time_total}' \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      "$url" 2>/dev/null || return 1
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" "$timeout" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
timeout = float(sys.argv[2])
start = time.perf_counter()
with urllib.request.urlopen(url, timeout=timeout) as response:
    response.read(1)
print(f"{time.perf_counter() - start:.3f}")
PY
    return $?
  fi

  return 1
}

probe_url_relaxed() {
  local url="$1"
  local timeout="${2:-3}"
  local result=""
  local code=""
  local time_total=""

  if command -v curl >/dev/null 2>&1; then
    result=$(curl -L -s -o /dev/null -w '%{http_code} %{time_total}' \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      "$url" 2>/dev/null || true)
    code=${result%% *}
    time_total=${result#* }

    case "$code" in
      200|204|301|302|307|308|401|403|404)
        printf '%s' "$time_total"
        return 0
        ;;
      *)
        return 1
        ;;
    esac
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" "$timeout" <<'PY'
import sys
import time
import urllib.request
import urllib.error

url = sys.argv[1]
timeout = float(sys.argv[2])
start = time.perf_counter()
try:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        response.read(1)
except urllib.error.HTTPError as exc:
    if exc.code not in {401, 403, 404}:
        raise
print(f"{time.perf_counter() - start:.3f}")
PY
    return $?
  fi

  return 1
}

is_faster() {
  local left="$1"
  local right="$2"

  if [ -z "$right" ]; then
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$left" "$right" <<'PY'
import sys
left = float(sys.argv[1])
right = float(sys.argv[2])
sys.exit(0 if left < right else 1)
PY
    return $?
  fi

  awk -v left="$left" -v right="$right" 'BEGIN { exit !(left < right) }'
}

format_speed() {
  local speed_kbps="$1"
  awk -v s="$speed_kbps" 'BEGIN { if (s >= 1024) printf "%.2f MB/s", s/1024; else printf "%.1f KB/s", s }'
}

probe_url_speed() {
  local url="$1"
  local timeout="${2:-5}"
  local max_bytes="${3:-1048576}"

  if command -v curl >/dev/null 2>&1; then
    curl -sS -o /dev/null \
      -H "User-Agent: Mozilla/5.0" \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      -r "0-$((max_bytes - 1))" \
      -w '%{speed_download}' \
      "$url" 2>/dev/null | awk '{
        speed_bytes = $1
        if (speed_bytes > 0) {
          printf "%.1f", speed_bytes / 1024
        } else {
          exit 1
        }
      }'
    return "${PIPESTATUS[1]:-$?}"
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" "$timeout" "$max_bytes" <<'PY'
import sys, time, urllib.error, urllib.request

url, timeout, max_bytes = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
total = 0
start = time.perf_counter()
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        while total < max_bytes:
            chunk = r.read(min(65536, max_bytes - total))
            if not chunk:
                break
            total += len(chunk)
except urllib.error.HTTPError as e:
    try:
        total = max(1, len(e.read(4096)))
    except Exception:
        total = 1
except Exception:
    pass
elapsed = time.perf_counter() - start
if elapsed > 0 and total > 0:
    print(f"{total / 1024 / elapsed:.1f}")
else:
    sys.exit(1)
PY
    return $?
  fi

  return 1
}

normalize_source_profile() {
  case "${DOCKER_SOURCE_PROFILE:-auto}" in
    native|origin|official)
      printf '%s' "native"
      ;;
    mirror|cn|accelerated)
      printf '%s' "mirror"
      ;;
    auto|"")
      printf '%s' "auto"
      ;;
    *)
      echo "警告：未知 DOCKER_SOURCE_PROFILE=${DOCKER_SOURCE_PROFILE:-}，回退到 auto" >&2
      printf '%s' "auto"
      ;;
  esac
}

get_default_candidates() {
  case "$1" in
    APT)
      cat <<'EOF2'
official|http://deb.debian.org|http://deb.debian.org/debian/dists/bookworm/main/binary-amd64/Packages.gz
tsinghua|https://mirrors.tuna.tsinghua.edu.cn|https://mirrors.tuna.tsinghua.edu.cn/debian/dists/bookworm/main/binary-amd64/Packages.gz
ustc|https://mirrors.ustc.edu.cn|https://mirrors.ustc.edu.cn/debian/dists/bookworm/main/binary-amd64/Packages.gz
aliyun|https://mirrors.aliyun.com|https://mirrors.aliyun.com/debian/dists/bookworm/main/binary-amd64/Packages.gz
tencent|https://mirrors.cloud.tencent.com|https://mirrors.cloud.tencent.com/debian/dists/bookworm/main/binary-amd64/Packages.gz
huaweicloud|https://mirrors.huaweicloud.com|https://mirrors.huaweicloud.com/debian/dists/bookworm/main/binary-amd64/Packages.gz
bfsu|https://mirrors.bfsu.edu.cn|https://mirrors.bfsu.edu.cn/debian/dists/bookworm/main/binary-amd64/Packages.gz
sjtug|https://mirror.sjtu.edu.cn|https://mirror.sjtu.edu.cn/debian/dists/bookworm/main/binary-amd64/Packages.gz
EOF2
      ;;
    PyPI)
      cat <<'EOF2'
official|https://pypi.org/simple|https://pypi.org/simple/pip/
tsinghua|https://pypi.tuna.tsinghua.edu.cn/simple|https://pypi.tuna.tsinghua.edu.cn/simple/pip/
ustc|https://mirrors.ustc.edu.cn/pypi/simple|https://mirrors.ustc.edu.cn/pypi/simple/pip/
aliyun|https://mirrors.aliyun.com/pypi/simple|https://mirrors.aliyun.com/pypi/simple/pip/
tencent|https://mirrors.cloud.tencent.com/pypi/simple|https://mirrors.cloud.tencent.com/pypi/simple/pip/
huaweicloud|https://mirrors.huaweicloud.com/repository/pypi/simple|https://mirrors.huaweicloud.com/repository/pypi/simple/pip/
bfsu|https://mirrors.bfsu.edu.cn/pypi/web/simple|https://mirrors.bfsu.edu.cn/pypi/web/simple/pip/
sjtug|https://mirror.sjtu.edu.cn/pypi/web/simple|https://mirror.sjtu.edu.cn/pypi/web/simple/pip/
EOF2
      ;;
    npm)
      cat <<'EOF2'
official|https://registry.npmjs.org|https://registry.npmjs.org/npm
npmmirror|https://registry.npmmirror.com|https://registry.npmmirror.com/npm
tencent|https://mirrors.cloud.tencent.com/npm|https://mirrors.cloud.tencent.com/npm/npm
huaweicloud|https://mirrors.huaweicloud.com/repository/npm|https://mirrors.huaweicloud.com/repository/npm/npm
sjtug|https://mirror.sjtu.edu.cn/npm-registry|https://mirror.sjtu.edu.cn/npm-registry/npm
EOF2
      ;;
    HuggingFace)
      cat <<'EOF2'
official|https://huggingface.co|https://huggingface.co/api/models/Qdrant/bm25
hf-mirror|https://hf-mirror.com|https://hf-mirror.com/api/models/Qdrant/bm25
EOF2
      ;;
    Playwright)
      cat <<'EOF2'
official|https://playwright.azureedge.net|https://playwright.azureedge.net/builds/
npmmirror|https://registry.npmmirror.com/-/binary/playwright|https://registry.npmmirror.com/-/binary/playwright/builds/
EOF2
      ;;
    *)
      return 1
      ;;
  esac
}

get_extra_candidates() {
  local env_name="$1"
  local raw="${!env_name:-}"

  if [ -z "$raw" ]; then
    return 0
  fi

  printf '%s' "$raw" | tr ';' '\n' | sed '/^[[:space:]]*$/d'
}

select_source_from_candidates() {
  local label="$1"
  local extra_env_name="$2"
  local profile="$3"
  local candidates=""
  local candidate_name=""
  local candidate_value=""
  local candidate_probe=""
  local official_value=""

  candidates="$({ get_default_candidates "$label"; get_extra_candidates "$extra_env_name"; } | sed '/^[[:space:]]*$/d')"

  # native 模式直接使用官方源
  while IFS='|' read -r candidate_name candidate_value candidate_probe; do
    if [ "$candidate_name" = "official" ]; then
      official_value="$candidate_value"
      if [ "$profile" = "native" ]; then
        echo "$label: 直接使用官方源 => $official_value" >&2
        printf '%s' "$official_value"
        return 0
      fi
      break
    fi
  done <<< "$candidates"

  # 并行带宽测速（下载最多 5MB 实际数据）
  local tmpdir=""
  tmpdir=$(mktemp -d)
  local pids=()
  local max_parallel=5
  local running=0

  echo "$label: 并行带宽测速..." >&2

  while IFS='|' read -r candidate_name candidate_value candidate_probe; do
    [ -n "$candidate_name" ] || continue
    [ -n "$candidate_value" ] || continue
    [ -n "$candidate_probe" ] || continue

    if [ "$profile" = "mirror" ] && [ "$candidate_name" = "official" ]; then
      continue
    fi

    (
      local speed=""
      speed=$(probe_url_speed "$candidate_probe" 12 5242880 2>/dev/null) || true
      if [ -n "$speed" ]; then
        echo "$candidate_name|$candidate_value|$speed" > "$tmpdir/$candidate_name"
        local display=""
        display=$(format_speed "$speed")
        echo "$label/$candidate_name: $display => $candidate_value" >&2
      else
        echo "$label/$candidate_name: 探测失败" >&2
      fi
    ) &
    pids+=($!)
    running=$((running + 1))
    if [ "$running" -ge "$max_parallel" ]; then
      wait -n 2>/dev/null || true
      running=$((running - 1))
    fi
  done <<< "$candidates"

  wait "${pids[@]}" 2>/dev/null || true

  # 按速度排序选最快
  local results=""
  local f=""
  for f in "$tmpdir"/*; do
    [ -f "$f" ] || continue
    results+="$(cat "$f")"$'\n'
  done
  rm -rf "$tmpdir"

  if [ -n "$results" ]; then
    local best_line=""
    best_line=$(printf '%s' "$results" | sort -t '|' -k 3,3rn | head -n 1)
    local best_name="" best_value="" best_speed=""
    IFS='|' read -r best_name best_value best_speed <<< "$best_line"
    local display=""
    display=$(format_speed "$best_speed")
    echo "$label: 选择 $best_name ($display) => $best_value" >&2
    printf '%s' "$best_value"
    return 0
  fi

  if [ -n "$official_value" ]; then
    echo "$label: 候选源测速失败，回退官方源 => $official_value" >&2
    printf '%s' "$official_value"
    return 0
  fi

  echo "$label: 未找到可用候选源" >&2
  return 1
}

build_source_fallbacks() {
  local label="$1"
  local extra_env_name="$2"
  local profile="$3"
  local primary_value="$4"
  local candidates=""
  local candidate_name=""
  local candidate_value=""
  local candidate_probe=""
  local fallbacks=""

  if [ "$profile" = "native" ]; then
    return 0
  fi

  candidates="$({ get_default_candidates "$label"; get_extra_candidates "$extra_env_name"; } | sed '/^[[:space:]]*$/d')"

  while IFS='|' read -r candidate_name candidate_value candidate_probe; do
    [ -n "$candidate_name" ] || continue
    [ -n "$candidate_value" ] || continue

    if [ "$profile" = "mirror" ] && [ "$candidate_name" = "official" ]; then
      continue
    fi

    if [ "$candidate_value" = "$primary_value" ]; then
      continue
    fi

    case " $fallbacks " in
      *" $candidate_value "*)
        continue
        ;;
    esac

    if [ -n "$fallbacks" ]; then
      fallbacks="$fallbacks $candidate_value"
    else
      fallbacks="$candidate_value"
    fi
  done <<< "$candidates"

  printf '%s' "$fallbacks"
}

configure_download_sources() {
  local profile=""
  profile=$(normalize_source_profile)
  echo "下载源策略: $profile"

  if [ -z "${DOCKER_APT_BASE_URL:-}" ]; then
    export DOCKER_APT_BASE_URL
    DOCKER_APT_BASE_URL=$(select_source_from_candidates "APT" "DOCKER_APT_CANDIDATES_EXTRA" "$profile")
  else
    echo "APT: 使用手动配置 $DOCKER_APT_BASE_URL"
  fi

  if [ -z "${DOCKER_PIP_INDEX_URL:-}" ]; then
    export DOCKER_PIP_INDEX_URL
    DOCKER_PIP_INDEX_URL=$(select_source_from_candidates "PyPI" "DOCKER_PIP_CANDIDATES_EXTRA" "$profile")
  else
    echo "PyPI: 使用手动配置 $DOCKER_PIP_INDEX_URL"
  fi

  if [ -z "${DOCKER_PIP_INDEX_FALLBACKS:-}" ]; then
    export DOCKER_PIP_INDEX_FALLBACKS
    DOCKER_PIP_INDEX_FALLBACKS=$(build_source_fallbacks "PyPI" "DOCKER_PIP_CANDIDATES_EXTRA" "$profile" "$DOCKER_PIP_INDEX_URL")
  else
    echo "PyPI fallback: 使用手动配置 $DOCKER_PIP_INDEX_FALLBACKS"
  fi

  if [ -z "${DOCKER_NPM_REGISTRY:-}" ]; then
    export DOCKER_NPM_REGISTRY
    DOCKER_NPM_REGISTRY=$(select_source_from_candidates "npm" "DOCKER_NPM_CANDIDATES_EXTRA" "$profile")
  else
    echo "npm: 使用手动配置 $DOCKER_NPM_REGISTRY"
  fi

  if [ -z "${DOCKER_HF_ENDPOINT:-}" ]; then
    export DOCKER_HF_ENDPOINT
    DOCKER_HF_ENDPOINT=$(select_source_from_candidates "HuggingFace" "DOCKER_HF_CANDIDATES_EXTRA" "$profile")
  else
    echo "HuggingFace: 使用手动配置 $DOCKER_HF_ENDPOINT"
  fi

  if [ -z "${DOCKER_PLAYWRIGHT_DOWNLOAD_HOST:-}" ]; then
    export DOCKER_PLAYWRIGHT_DOWNLOAD_HOST
    DOCKER_PLAYWRIGHT_DOWNLOAD_HOST=$(select_source_from_candidates "Playwright" "DOCKER_PLAYWRIGHT_CANDIDATES_EXTRA" "$profile")
  else
    echo "Playwright: 使用手动配置 $DOCKER_PLAYWRIGHT_DOWNLOAD_HOST"
  fi

  echo "已选择下载源："
  echo "- APT: $DOCKER_APT_BASE_URL"
  echo "- PyPI: $DOCKER_PIP_INDEX_URL"
  if [ -n "${DOCKER_PIP_INDEX_FALLBACKS:-}" ]; then
    echo "- PyPI fallback: $DOCKER_PIP_INDEX_FALLBACKS"
  fi
  echo "- npm: $DOCKER_NPM_REGISTRY"
  echo "- HuggingFace: $DOCKER_HF_ENDPOINT"
  echo "- Playwright: $DOCKER_PLAYWRIGHT_DOWNLOAD_HOST"
}

normalize_image_ref() {
  local image="$1"
  local registry=""
  local remainder=""
  local repo=""
  local tag=""
  local first_segment=""

  first_segment=${image%%/*}

  if [ "$first_segment" != "$image" ] && { [[ "$first_segment" == *.* ]] || [[ "$first_segment" == *:* ]] || [ "$first_segment" = "localhost" ]; }; then
    registry="$first_segment"
    remainder=${image#*/}
  else
    registry="docker.io"
    remainder="$image"
  fi

  if [[ "$remainder" == *:* ]]; then
    repo=${remainder%:*}
    tag=${remainder##*:}
  else
    repo="$remainder"
    tag="latest"
  fi

  if [ "$registry" = "docker.io" ] && [[ "$repo" != */* ]]; then
    repo="library/$repo"
  fi

  printf '%s/%s:%s' "$registry" "$repo" "$tag"
}

get_remote_registry_candidates() {
  case "$1" in
    dockerhub)
      cat <<'EOF2'
official|official|https://registry-1.docker.io/v2/
panel|dockerhub_host:docker.1panel.live|https://docker.1panel.live/v2/
one_ms|dockerhub_host:docker.1ms.run|https://docker.1ms.run/v2/
xuanyuan|dockerhub_host:docker.xuanyuan.me|https://docker.xuanyuan.me/v2/
daocloud|dockerhub_host:docker.m.daocloud.io|https://docker.m.daocloud.io/v2/
rat|dockerhub_host:hub.rat.dev|https://hub.rat.dev/v2/
atomhub|dockerhub_host:atomhub.openatom.cn|https://atomhub.openatom.cn/v2/
timeweb|dockerhub_host:dockerhub.timeweb.cloud|https://dockerhub.timeweb.cloud/v2/
anyhub|dockerhub_host:docker.anyhub.us.kg|https://docker.anyhub.us.kg/v2/
uuuadc|dockerhub_host:hub.uuuadc.top|https://hub.uuuadc.top/v2/
ckyl|dockerhub_host:docker.ckyl.me|https://docker.ckyl.me/v2/
rainbond|dockerhub_host:docker.rainbond.cc|https://docker.rainbond.cc/v2/
hpcloud|dockerhub_host:docker.hpcloud.cloud|https://docker.hpcloud.cloud/v2/
dockerproxy|dockerhub_host:dockerproxy.cn|https://dockerproxy.cn/v2/
panel_proxy|dockerhub_host:docker.1panelproxy.com|https://docker.1panelproxy.com/v2/
kejilion|dockerhub_host:docker.kejilion.pro|https://docker.kejilion.pro/v2/
kubesre|dockerhub_host:dhub.kubesre.xyz|https://dhub.kubesre.xyz/v2/
nastool|dockerhub_host:docker.nastool.de|https://docker.nastool.de/v2/
noohub|dockerhub_host:noohub.ru|https://noohub.ru/v2/
huecker|dockerhub_host:huecker.io|https://huecker.io/v2/
EOF2
      ;;
    ghcr)
      cat <<'EOF2'
official|official|https://ghcr.io/v2/
one_ms|ghcr_host:ghcr.1ms.run|https://ghcr.1ms.run/v2/
nju|ghcr_host:ghcr.nju.edu.cn|https://ghcr.nju.edu.cn/v2/
daocloud|ghcr_host:ghcr.m.daocloud.io|https://ghcr.m.daocloud.io/v2/
lank8s|ghcr_host:ghcr.lank8s.cn|https://ghcr.lank8s.cn/v2/
dockerproxy|ghcr_host:ghcr.dockerproxy.cn|https://ghcr.dockerproxy.cn/v2/
EOF2
      ;;
    mcr)
      cat <<'EOF2'
official|official|https://mcr.microsoft.com/v2/
azure_cn|mcr_host:mcr.azure.cn|https://mcr.azure.cn/v2/
daocloud|mcr_host:mcr.m.daocloud.io|https://mcr.m.daocloud.io/v2/
one_ms|mcr_host:mcr.1ms.run|https://mcr.1ms.run/v2/
dockerproxy|mcr_host:mcr.dockerproxy.cn|https://mcr.dockerproxy.cn/v2/
EOF2
      ;;
    *)
      return 1
      ;;
  esac
}

get_remote_registry_validation_images() {
  case "$1" in
    dockerhub)
      cat <<'EOF2'
postgres:16-alpine
redis:7-alpine
qdrant/qdrant:latest
EOF2
      ;;
    ghcr)
      cat <<'EOF2'
ghcr.io/mgdaaslab/wharttest-backend:latest
ghcr.io/mgdaaslab/wharttest-frontend:latest
ghcr.io/mgdaaslab/wharttest-mcp:latest
EOF2
      ;;
    mcr)
      cat <<'EOF2'
mcr.microsoft.com/playwright/mcp
EOF2
      ;;
    *)
      return 1
      ;;
  esac
}

probe_remote_image_manifest() {
  local image="$1"
  local candidate_kind="$2"
  local timeout="${3:-5}"
  local selected_image=""
  local normalized=""
  local registry=""
  local registry_host=""
  local remainder=""
  local repo=""
  local tag=""
  local url=""
  local accept_header="application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"

  selected_image=$(rewrite_remote_image "$image" "$candidate_kind")
  normalized=$(normalize_image_ref "$selected_image")
  registry=${normalized%%/*}
  remainder=${normalized#*/}
  repo=${remainder%:*}
  tag=${remainder##*:}

  case "$registry" in
    docker.io)
      registry_host="registry-1.docker.io"
      ;;
    *)
      registry_host="$registry"
      ;;
  esac

  url="https://$registry_host/v2/$repo/manifests/$tag"

  if command -v curl >/dev/null 2>&1; then
    local result=""
    local http_code=""
    local time_total=""
    local auth_header=""
    local realm=""
    local service=""
    local scope=""
    local token_response=""
    local token=""
    local -a token_cmd=()

    result=$(curl -I -sS -D - -o /dev/null \
      -w '\nCURL_HTTP_CODE=%{http_code}\nCURL_TIME_TOTAL=%{time_total}\n' \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      -H "Accept: $accept_header" \
      "$url" 2>/dev/null || true)
    http_code=$(printf '%s\n' "$result" | sed -n 's/^CURL_HTTP_CODE=//p' | tail -n 1)
    time_total=$(printf '%s\n' "$result" | sed -n 's/^CURL_TIME_TOTAL=//p' | tail -n 1)

    case "$http_code" in
      200|204|301|302|307|308)
        printf '%s' "$time_total"
        return 0
        ;;
    esac

    if [ "$http_code" != "401" ]; then
      return 1
    fi

    auth_header=$(printf '%s\n' "$result" | tr -d '\r' | awk 'BEGIN { IGNORECASE = 1 } /^www-authenticate:/ { sub(/^[^:]*:[[:space:]]*/, ""); value = $0 } END { print value }')
    realm=$(printf '%s' "$auth_header" | sed -n 's/.*realm="\([^"]*\)".*/\1/p')
    service=$(printf '%s' "$auth_header" | sed -n 's/.*service="\([^"]*\)".*/\1/p')
    scope=$(printf '%s' "$auth_header" | sed -n 's/.*scope="\([^"]*\)".*/\1/p')

    if [ -z "$realm" ]; then
      return 1
    fi

    token_cmd=(curl -sS --get --connect-timeout "$timeout" --max-time "$timeout")
    if [ -n "$service" ]; then
      token_cmd+=(--data-urlencode "service=$service")
    fi
    if [ -n "$scope" ]; then
      token_cmd+=(--data-urlencode "scope=$scope")
    fi
    token_response=$("${token_cmd[@]}" "$realm" 2>/dev/null || true)
    token=$(printf '%s' "$token_response" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    if [ -z "$token" ]; then
      token=$(printf '%s' "$token_response" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    fi

    if [ -z "$token" ]; then
      return 1
    fi

    result=$(curl -I -sS -o /dev/null -w '%{http_code} %{time_total}' \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      -H "Accept: $accept_header" \
      -H "Authorization: Bearer $token" \
      "$url" 2>/dev/null || true)
    http_code=${result%% *}
    time_total=${result#* }

    case "$http_code" in
      200|204|301|302|307|308)
        printf '%s' "$time_total"
        return 0
        ;;
      *)
        return 1
        ;;
    esac
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" "$timeout" <<'PY'
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

url = sys.argv[1]
timeout = float(sys.argv[2])
accept = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
success_codes = {200, 204, 301, 302, 307, 308}


def request_once(extra_headers=None):
    headers = {"Accept": accept}
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, headers=headers, method="HEAD")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read(0)
            return response.getcode(), response.headers, time.perf_counter() - start
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, time.perf_counter() - start


status, headers, elapsed = request_once()
if status in success_codes:
    print(f"{elapsed:.6f}")
    sys.exit(0)

if status != 401:
    sys.exit(1)

auth_header = headers.get("WWW-Authenticate", "")
if not auth_header.lower().startswith("bearer "):
    sys.exit(1)

attrs = dict(re.findall(r'(\w+)="([^"]+)"', auth_header))
realm = attrs.pop("realm", "")
if not realm:
    sys.exit(1)

token_url = realm
if attrs:
    token_url = f"{realm}?{urllib.parse.urlencode(attrs)}"

token_request = urllib.request.Request(token_url, headers={"Accept": "application/json"})
try:
    with urllib.request.urlopen(token_request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
except Exception:
    sys.exit(1)

token = payload.get("token") or payload.get("access_token")
if not token:
    sys.exit(1)

status, headers, elapsed2 = request_once({"Authorization": f"Bearer {token}"})
if status in success_codes:
    print(f"{elapsed + elapsed2:.6f}")
    sys.exit(0)

sys.exit(1)
PY
    return $?
  fi

  return 1
}

remote_candidate_supports_images() {
  local registry_group="$1"
  local candidate_kind="$2"
  local image=""

  while IFS= read -r image; do
    [ -n "$image" ] || continue
    if ! probe_remote_image_manifest "$image" "$candidate_kind" 5 >/dev/null; then
      return 1
    fi
  done <<< "$(get_remote_registry_validation_images "$registry_group")"

  return 0
}

probe_candidate_worker() {
  local registry_group="$1"
  local candidate_name="$2"
  local candidate_kind="$3"
  local result_file="$4"
  local validation_image="$5"
  local raw_result=""
  local speed_kbps=""
  local speed_type=""

  raw_result=$(measure_registry_speed "$validation_image" "$candidate_kind" 10 2097152 2>/dev/null) || true

  if [ -n "$raw_result" ]; then
    speed_kbps=${raw_result%%|*}
    speed_type=${raw_result##*|}
    local display_speed=""
    display_speed=$(format_speed "$speed_kbps")
    local type_label=""
    if [ "$speed_type" = "blob" ]; then
      type_label="blob 测速"
    else
      type_label="manifest 测速"
    fi
    echo "$candidate_name|$candidate_kind|$speed_kbps" > "$result_file"
    echo "remote/$registry_group/$candidate_name: $display_speed ($type_label)" >&2
  else
    echo "remote/$registry_group/$candidate_name: 探测失败" >&2
  fi
}

measure_registry_speed() {
  local image="$1"
  local candidate_kind="$2"
  local timeout="${3:-8}"
  local max_bytes="${4:-524288}"
  local selected_image=""
  local normalized="" registry="" remainder="" repo="" tag="" registry_host=""

  selected_image=$(rewrite_remote_image "$image" "$candidate_kind")
  normalized=$(normalize_image_ref "$selected_image")
  registry=${normalized%%/*}
  remainder=${normalized#*/}
  repo=${remainder%:*}
  tag=${remainder##*:}

  case "$registry" in
    docker.io) registry_host="registry-1.docker.io" ;;
    *)         registry_host="$registry" ;;
  esac

  local accept_header="application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json"
  local base_url="https://$registry_host/v2/$repo"
  local manifest_url="$base_url/manifests/$tag"

  if command -v curl >/dev/null 2>&1; then
    local result="" http_code="" auth_header="" realm="" service="" scope=""
    local token_response="" token="" speed_download=""
    local -a token_cmd=()

    result=$(curl -sS -D - -o /dev/null \
      -w '\nCURL_HTTP_CODE=%{http_code}\nCURL_SPEED=%{speed_download}\n' \
      --connect-timeout "$timeout" \
      --max-time "$timeout" \
      -H "Accept: $accept_header" \
      "$manifest_url" 2>/dev/null || true)
    http_code=$(printf '%s\n' "$result" | sed -n 's/^CURL_HTTP_CODE=//p' | tail -n 1)

    if [ "$http_code" = "401" ]; then
      auth_header=$(printf '%s\n' "$result" | tr -d '\r' | awk 'BEGIN { IGNORECASE = 1 } /^www-authenticate:/ { sub(/^[^:]*:[[:space:]]*/, ""); value = $0 } END { print value }')
      realm=$(printf '%s' "$auth_header" | sed -n 's/.*realm="\([^"]*\)".*/\1/p')
      service=$(printf '%s' "$auth_header" | sed -n 's/.*service="\([^"]*\)".*/\1/p')
      scope=$(printf '%s' "$auth_header" | sed -n 's/.*scope="\([^"]*\)".*/\1/p')

      if [ -n "$realm" ]; then
        token_cmd=(curl -sS --get --connect-timeout "$timeout" --max-time "$timeout")
        [ -n "$service" ] && token_cmd+=(--data-urlencode "service=$service")
        [ -n "$scope" ] && token_cmd+=(--data-urlencode "scope=$scope")
        token_response=$("${token_cmd[@]}" "$realm" 2>/dev/null || true)
        token=$(printf '%s' "$token_response" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        [ -z "$token" ] && token=$(printf '%s' "$token_response" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
      fi

      if [ -n "$token" ]; then
        result=$(curl -sS -o /dev/null \
          -w '%{http_code} %{speed_download}' \
          --connect-timeout "$timeout" \
          --max-time "$timeout" \
          -r "0-$((max_bytes - 1))" \
          -H "Accept: $accept_header" \
          -H "Authorization: Bearer $token" \
          "$manifest_url" 2>/dev/null || true)
        http_code=${result%% *}
        speed_download=${result#* }
      fi
    else
      speed_download=$(printf '%s\n' "$result" | sed -n 's/^CURL_SPEED=//p' | tail -n 1)
    fi

    case "$http_code" in
      200|301|302)
        if [ -n "$speed_download" ]; then
          local speed_kbps=""
          speed_kbps=$(awk -v s="$speed_download" 'BEGIN { if (s > 0) printf "%.1f", s / 1024; else exit 1 }') || return 1
          printf '%s|manifest' "$speed_kbps"
          return 0
        fi
        ;;
    esac
    return 1
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$registry_host" "$repo" "$tag" "$timeout" "$max_bytes" <<'PYEOF'
import json, re, sys, time, urllib.error, urllib.parse, urllib.request


class StripAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """跨域重定向时自动剥离 Authorization 头，避免与 CDN 预签名 URL 冲突"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            orig_host = urllib.parse.urlparse(req.full_url).netloc
            new_host = urllib.parse.urlparse(newurl).netloc
            if orig_host != new_host:
                new_req.remove_header("Authorization")
        return new_req


opener = urllib.request.build_opener(StripAuthRedirectHandler)

registry_host = sys.argv[1]
repo = sys.argv[2]
tag = sys.argv[3]
timeout = float(sys.argv[4])
max_bytes = int(sys.argv[5])

accept = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
])


def get_token(headers):
    auth = headers.get("WWW-Authenticate", "")
    if not auth.lower().startswith("bearer "):
        return None
    attrs = dict(re.findall(r'(\w+)="([^"]+)"', auth))
    realm = attrs.pop("realm", "")
    if not realm:
        return None
    token_url = f"{realm}?{urllib.parse.urlencode(attrs)}" if attrs else realm
    with opener.open(token_url, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return data.get("token") or data.get("access_token")


def fetch(url, headers, read_body=False):
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read() if read_body else b""
            return r.getcode(), r.headers, body
    except urllib.error.HTTPError as e:
        return e.code, e.headers, b""


# 计时从第一个实际请求开始
overall_start = time.perf_counter()
total_bytes = 0

token = None
base = f"https://{registry_host}/v2/{repo}"
manifest_url = f"{base}/manifests/{tag}"

code, headers, body = fetch(manifest_url, {"Accept": accept}, read_body=True)
if code == 401:
    token = get_token(headers)
    if not token:
        sys.exit(1)
    code, headers, body = fetch(
        manifest_url,
        {"Accept": accept, "Authorization": f"Bearer {token}"},
        read_body=True,
    )
if code not in (200, 301, 302):
    sys.exit(1)

total_bytes += len(body)
manifest = json.loads(body) if body else {}

# 解析 manifest 获取 blob
layers = manifest.get("layers", [])
if not layers:
    ms = manifest.get("manifests", [])
    if ms:
        digest = ms[0].get("digest", "")
        if digest:
            sub_url = f"{base}/manifests/{digest}"
            h = {"Accept": accept}
            if token:
                h["Authorization"] = f"Bearer {token}"
            _, _, sub_body = fetch(sub_url, h, read_body=True)
            if sub_body:
                total_bytes += len(sub_body)
                layers = json.loads(sub_body).get("layers", [])

if not layers:
    config = manifest.get("config", {})
    if config.get("digest"):
        layers = [config]

# 尝试下载 blob 层进行带宽测速（仅计时数据传输阶段，排除 auth/manifest 开销）
blob_ok = False
blob_speed = 0.0
if layers:
    # 优先选 >= 1MB 的层，更能反映真实带宽
    large = [l for l in layers if l.get("size", 0) >= 1048576]
    if large:
        target = min(large, key=lambda l: l.get("size", float("inf")))
    else:
        target = max(layers, key=lambda l: l.get("size", 0))
    digest = target.get("digest", "")
    if digest:
        blob_url = f"{base}/blobs/{digest}"
        h = {}
        if token:
            h["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(blob_url, headers=h)
        try:
            blob_bytes = 0
            blob_start = time.perf_counter()
            with opener.open(req, timeout=timeout) as r:
                while blob_bytes < max_bytes:
                    chunk = r.read(min(65536, max_bytes - blob_bytes))
                    if not chunk:
                        break
                    blob_bytes += len(chunk)
            blob_elapsed = time.perf_counter() - blob_start
            if blob_elapsed > 0 and blob_bytes > 0:
                blob_speed = (blob_bytes / 1024) / blob_elapsed
                blob_ok = True
        except Exception:
            pass

if blob_ok:
    print(f"{blob_speed:.1f}|blob")
else:
    elapsed = time.perf_counter() - overall_start
    if elapsed <= 0 or total_bytes == 0:
        sys.exit(1)
    speed_kbps = (total_bytes / 1024) / elapsed
    print(f"{speed_kbps:.1f}|manifest")
PYEOF
    return $?
  fi

  return 1
}

select_remote_candidate() {
  local registry_group="$1"
  local profile="$2"
  local candidates=""
  local candidate_name=""
  local candidate_kind=""
  local candidate_probe=""
  local best_name=""
  local best_kind=""
  local best_time=""
  local official_kind="official"
  local ranked_candidates=""

  candidates=$(get_remote_registry_candidates "$registry_group")

  # native 模式直接使用官方
  if [ "$profile" = "native" ]; then
    while IFS='|' read -r candidate_name candidate_kind candidate_probe; do
      if [ "$candidate_name" = "official" ]; then
        echo "remote/$registry_group: 直接使用官方仓库" >&2
        printf '%s' "$candidate_kind"
        return 0
      fi
    done <<< "$candidates"
  fi

  # 获取第一个校验镜像用于真实 manifest 下载测速
  local first_validation_image=""
  first_validation_image=$(get_remote_registry_validation_images "$registry_group" | head -n 1)

  # 并行探测候选源（限制并发数避免资源竞争）
  local tmpdir=""
  tmpdir=$(mktemp -d)
  local pids=()
  local max_parallel=5
  local running=0

  echo "remote/$registry_group: 并行探测 $(echo "$candidates" | grep -c '|') 个候选源..." >&2

  while IFS='|' read -r candidate_name candidate_kind candidate_probe; do
    [ -n "$candidate_name" ] || continue

    if [ "$profile" = "mirror" ] && [ "$candidate_name" = "official" ]; then
      continue
    fi

    probe_candidate_worker "$registry_group" "$candidate_name" "$candidate_kind" \
      "$tmpdir/$candidate_name" "$first_validation_image" &
    pids+=($!)
    running=$((running + 1))
    if [ "$running" -ge "$max_parallel" ]; then
      wait -n 2>/dev/null || true
      running=$((running - 1))
    fi
  done <<< "$candidates"

  # 等待所有并行探测完成
  wait "${pids[@]}" 2>/dev/null || true

  # 收集结果
  local f=""
  for f in "$tmpdir"/*; do
    [ -f "$f" ] || continue
    ranked_candidates+="$(cat "$f")"$'\n'
  done
  rm -rf "$tmpdir"

  local sorted_ranked=""
  if [ -n "$ranked_candidates" ]; then
    sorted_ranked=$(printf '%s' "$ranked_candidates" | sort -t '|' -k 3,3rn)

    # 存储排序后的候选列表到文件（跨子 shell 共享）
    if [ -n "$_RANKED_DIR" ]; then
      printf '%s' "$sorted_ranked" > "$_RANKED_DIR/$registry_group"
    fi

    # 测速阶段已验证 manifest 可下载，直接选最快的
    IFS='|' read -r best_name best_kind best_time <<< "$(head -n 1 <<< "$sorted_ranked")"
  fi

  if [ -n "$best_kind" ]; then
    local display_speed=""
    display_speed=$(format_speed "$best_time")
    echo "remote/$registry_group: 选择 $best_name ($display_speed)" >&2
    printf '%s' "$best_kind"
    return 0
  fi

  echo "remote/$registry_group: 候选仓库不可用，回退官方仓库" >&2
  printf '%s' "$official_kind"
}

get_ranked_candidates_for_group() {
  local group="$1"
  if [ -n "$_RANKED_DIR" ] && [ -f "$_RANKED_DIR/$group" ]; then
    cat "$_RANKED_DIR/$group"
  fi
}

registry_group_for_image() {
  local image="$1"
  local normalized
  normalized=$(normalize_image_ref "$image")
  local registry="${normalized%%/*}"
  case "$registry" in
    docker.io)          echo "dockerhub" ;;
    ghcr.io)            echo "ghcr" ;;
    mcr.microsoft.com)  echo "mcr" ;;
    *)                  echo "" ;;
  esac
}

pull_image_with_fallback() {
  local env_name="$1"
  local default_image="$2"
  local registry_group="$3"
  local current_image="${!env_name}"
  local ranked
  ranked=$(get_ranked_candidates_for_group "$registry_group")

  echo "拉取镜像: $current_image ..."
  if docker pull "$current_image" 2>&1; then
    echo "✔ $env_name 拉取成功"
    return 0
  fi

  echo "⚠ $env_name 拉取失败（$current_image），尝试备选镜像源..."

  local candidate_name candidate_kind candidate_time fallback_image
  if [ -n "$ranked" ]; then
    while IFS='|' read -r candidate_name candidate_kind candidate_time; do
      [ -n "$candidate_name" ] || continue
      fallback_image=$(rewrite_remote_image "$default_image" "$candidate_kind")
      [ "$fallback_image" != "$current_image" ] || continue

      echo "  尝试备选: $fallback_image ..."
      if docker pull "$fallback_image" 2>&1; then
        printf -v "$env_name" '%s' "$fallback_image"
        export "$env_name"
        echo "✔ $env_name 使用备选源拉取成功: $fallback_image"
        return 0
      fi
      echo "  ⚠ 备选 $fallback_image 拉取失败"
    done <<< "$ranked"
  fi

  # 最后尝试官方源
  if [ "$default_image" != "$current_image" ]; then
    echo "  尝试官方源: $default_image ..."
    if docker pull "$default_image" 2>&1; then
      printf -v "$env_name" '%s' "$default_image"
      export "$env_name"
      echo "✔ $env_name 使用官方源拉取成功: $default_image"
      return 0
    fi
  fi

  echo "✘ $env_name 所有镜像源均拉取失败" >&2
  return 1
}

rewrite_remote_image() {
  local image="$1"
  local candidate_kind="$2"
  local normalized=""
  local host=""

  case "$candidate_kind" in
    official)
      printf '%s' "$image"
      return 0
      ;;
    *)
      normalized=$(normalize_image_ref "$image")
      ;;
  esac

  case "$candidate_kind" in
    dockerhub_host:*)
      host=${candidate_kind#dockerhub_host:}
      printf '%s' "$host/${normalized#docker.io/}"
      ;;
    ghcr_host:*)
      host=${candidate_kind#ghcr_host:}
      printf '%s' "$host/${normalized#ghcr.io/}"
      ;;
    mcr_host:*)
      host=${candidate_kind#mcr_host:}
      printf '%s' "$host/${normalized#mcr.microsoft.com/}"
      ;;
    *)
      printf '%s' "$image"
      ;;
  esac
}

apply_remote_image_override() {
  local env_name="$1"
  local default_image="$2"
  local candidate_kind="$3"
  local selected_image=""

  if [ -n "${!env_name:-}" ]; then
    echo "$env_name: 使用手动配置 ${!env_name}"
    return 0
  fi

  selected_image=$(rewrite_remote_image "$default_image" "$candidate_kind")
  printf -v "$env_name" '%s' "$selected_image"
  export "$env_name"
  echo "$env_name: $selected_image"
}

configure_remote_image_sources() {
  local profile=""
  local dockerhub_candidate=""
  local ghcr_candidate=""
  local mcr_candidate=""

  profile=$(normalize_source_profile)
  echo "远程镜像策略: $profile"

  # 创建临时目录存储排名数据（跨子 shell 共享）
  _RANKED_DIR=$(mktemp -d)
  export _RANKED_DIR

  dockerhub_candidate=$(select_remote_candidate dockerhub "$profile")
  ghcr_candidate=$(select_remote_candidate ghcr "$profile")
  mcr_candidate=$(select_remote_candidate mcr "$profile")

  apply_remote_image_override DOCKER_BACKEND_IMAGE "ghcr.io/mgdaaslab/wharttest-backend:latest" "$ghcr_candidate"
  apply_remote_image_override DOCKER_FRONTEND_IMAGE "ghcr.io/mgdaaslab/wharttest-frontend:latest" "$ghcr_candidate"
  apply_remote_image_override DOCKER_MCP_IMAGE "ghcr.io/mgdaaslab/wharttest-mcp:latest" "$ghcr_candidate"

  apply_remote_image_override DOCKER_POSTGRES_IMAGE "postgres:16-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_REDIS_IMAGE "redis:7-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_QDRANT_IMAGE "qdrant/qdrant:latest" "$dockerhub_candidate"

  apply_remote_image_override DOCKER_PLAYWRIGHT_MCP_IMAGE "mcr.microsoft.com/playwright/mcp" "$mcr_candidate"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "错误：未找到 docker 命令。请先安装 Docker Desktop 或 Docker Engine。" >&2
    exit 2
  fi

  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  else
    COMPOSE_CMD=(docker-compose)
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "错误：无法连接到 Docker daemon。请确认 Docker Desktop / daemon 已启动；若使用 WSL，请确认该发行版已启用集成。" >&2
    echo "你也可以在远程 Docker 引擎可用时设置 DOCKER_HOST。" >&2
    exit 3
  fi
}

run_remote_mode() {
  local up_args=(-d --remove-orphans)

  configure_remote_image_sources

  if [ "${DOCKER_REMOTE_PULL:-1}" = "1" ]; then
    echo "开始逐个拉取远程预构建镜像（支持自动回退备选源）..."
    local pull_failed=0

    pull_image_with_fallback DOCKER_BACKEND_IMAGE "ghcr.io/mgdaaslab/wharttest-backend:latest" ghcr || pull_failed=1
    pull_image_with_fallback DOCKER_FRONTEND_IMAGE "ghcr.io/mgdaaslab/wharttest-frontend:latest" ghcr || pull_failed=1
    pull_image_with_fallback DOCKER_MCP_IMAGE "ghcr.io/mgdaaslab/wharttest-mcp:latest" ghcr || pull_failed=1
    pull_image_with_fallback DOCKER_POSTGRES_IMAGE "postgres:16-alpine" dockerhub || pull_failed=1
    pull_image_with_fallback DOCKER_REDIS_IMAGE "redis:7-alpine" dockerhub || pull_failed=1
    pull_image_with_fallback DOCKER_QDRANT_IMAGE "qdrant/qdrant:latest" dockerhub || pull_failed=1
    pull_image_with_fallback DOCKER_PLAYWRIGHT_MCP_IMAGE "mcr.microsoft.com/playwright/mcp" mcr || pull_failed=1

    if [ "$pull_failed" -eq 1 ]; then
      echo "错误：部分镜像拉取失败，请检查网络连接或手动指定镜像源" >&2
      exit 1
    fi
    echo "所有镜像拉取完成。"
  else
    echo "已跳过远程镜像拉取（DOCKER_REMOTE_PULL=0）"
  fi

  # 清理排名临时目录
  if [ -n "${_RANKED_DIR:-}" ] && [ -d "$_RANKED_DIR" ]; then
    rm -rf "$_RANKED_DIR"
  fi

  if [ "${DOCKER_FORCE_RECREATE:-1}" = "1" ]; then
    up_args+=(--force-recreate)
  fi

  echo "启动容器（远程镜像模式）..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up "${up_args[@]}"
}

configure_local_base_images() {
  local profile=""
  profile=$(normalize_source_profile)

  if [ "$profile" = "native" ]; then
    echo "基础镜像: 使用官方源（native 模式）"
    return 0
  fi

  echo "基础镜像加速: 探测最快 DockerHub / MCR 镜像源..."

  _RANKED_DIR=$(mktemp -d)
  export _RANKED_DIR

  local dockerhub_candidate=""
  local mcr_candidate=""
  dockerhub_candidate=$(select_remote_candidate dockerhub "$profile")
  mcr_candidate=$(select_remote_candidate mcr "$profile")

  # 构建参数中的基础镜像
  apply_remote_image_override DOCKER_PYTHON_BASE_IMAGE "python:3.11-slim" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_NODE_BASE_IMAGE "node:20-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_NODE_22_BASE_IMAGE "node:22-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_NGINX_BASE_IMAGE "nginx:alpine" "$dockerhub_candidate"

  # 直接拉取的服务镜像
  apply_remote_image_override DOCKER_POSTGRES_IMAGE "postgres:16-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_REDIS_IMAGE "redis:7-alpine" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_QDRANT_IMAGE "qdrant/qdrant:latest" "$dockerhub_candidate"
  apply_remote_image_override DOCKER_PLAYWRIGHT_MCP_IMAGE "mcr.microsoft.com/playwright/mcp" "$mcr_candidate"

  echo "已选择基础镜像源："
  echo "- Python: ${DOCKER_PYTHON_BASE_IMAGE:-python:3.11-slim}"
  echo "- Node: ${DOCKER_NODE_BASE_IMAGE:-node:20-alpine}"
  echo "- Node 22: ${DOCKER_NODE_22_BASE_IMAGE:-node:22-alpine}"
  echo "- Nginx: ${DOCKER_NGINX_BASE_IMAGE:-nginx:alpine}"
  echo "- PostgreSQL: ${DOCKER_POSTGRES_IMAGE:-postgres:16-alpine}"
  echo "- Redis: ${DOCKER_REDIS_IMAGE:-redis:7-alpine}"
  echo "- Qdrant: ${DOCKER_QDRANT_IMAGE:-qdrant/qdrant:latest}"
  echo "- Playwright MCP: ${DOCKER_PLAYWRIGHT_MCP_IMAGE:-mcr.microsoft.com/playwright/mcp}"

  if [ -n "${_RANKED_DIR:-}" ] && [ -d "$_RANKED_DIR" ]; then
    rm -rf "$_RANKED_DIR"
  fi
}

run_local_mode() {
  local build_args=()
  local up_args=(-d --remove-orphans)

  # 启用 BuildKit：并行层构建 + 更智能的缓存
  export DOCKER_BUILDKIT=1
  export COMPOSE_DOCKER_CLI_BUILD=1

  configure_download_sources
  configure_local_base_images

  if [ "${DOCKER_BUILD_NO_CACHE:-0}" = "1" ]; then
    build_args+=(--no-cache)
    echo "开始构建镜像（禁用缓存）..."
  else
    echo "开始构建镜像（启用缓存）..."
  fi

  if [ "${DOCKER_BUILD_PULL:-0}" = "1" ]; then
    build_args+=(--pull)
  fi

  if [ "${DOCKER_FORCE_RECREATE:-1}" = "1" ]; then
    up_args+=(--force-recreate)
  fi

  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" build "${build_args[@]}"

  echo "启动容器（本地构建模式）..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up "${up_args[@]}"
}

collect_status_and_logs() {
  echo "收集主要服务状态与日志..."
  local services=(backend redis postgres qdrant mcp frontend playwright-mcp)

  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps

  for svc in "${services[@]}"; do
    echo "--- 日志: $svc（最近 200 行）---"
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" logs --tail 200 "$svc" | tee "$LOG_DIR/$svc.log" || true
  done

  echo "日志已保存到 $LOG_DIR/*.log"
  echo "如果服务启动失败，请先查看日志，并检查端口占用与宿主机挂载文件是否可用。"
}

print_summary() {
  cat <<'EOF2'
说明:
- 运行脚本后可选择两种模式：`remote` 远程拉预构建镜像，`local` 本地构建镜像。
- `remote` 模式会按仓库类型自动测速：Docker Hub 在官方 / `docker.1panel.live` / `docker.1ms.run` / `docker.xuanyuan.me` / `docker.m.daocloud.io` 之间择优，GHCR 在官方 / `ghcr.1ms.run` / `ghcr.nju.edu.cn` / `ghcr.m.daocloud.io` 之间择优，MCR 在官方 / `mcr.azure.cn` / `mcr.m.daocloud.io` 之间择优。
- `local` 模式会自动探测下载源和基础镜像加速；下载源内置候选已扩展为官方源 + 清华 / 中科大 / 阿里云 / 腾讯云 / 华为云 / 北外 / 交大 / `npmmirror` / `hf-mirror` 等；基础镜像（Python / Node / Nginx / PostgreSQL / Redis / Qdrant / Playwright MCP）会自动选最快的 DockerHub / MCR 镜像源加速拉取。
- `DOCKER_SOURCE_PROFILE` 支持 `auto|native|mirror`；`auto` 会在全部候选里测速选最快，`mirror` 只在镜像源里选最快。
- `DOCKER_BUILD_NO_CACHE=1` 只对 `local` 模式生效；`DOCKER_REMOTE_PULL=0` 可跳过 `remote` 模式下的 `pull`。
EOF2
}

main() {
  load_env_file
  resolve_mode_and_compose "$@"
  require_docker

  case "$DEPLOY_MODE" in
    remote)
      run_remote_mode
      ;;
    local)
      run_local_mode
      ;;
  esac

  collect_status_and_logs
  print_summary
}

main "$@"

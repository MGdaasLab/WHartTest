#!/usr/bin/env bash
set -euo pipefail

# 统一 Docker 启动脚本。
# 用法：
#   ./run_compose.sh                 # 使用本地源码构建镜像
#   ./run_compose.sh local          # 使用本地源码构建镜像
#   ./run_compose.sh local docker-compose.local.yml

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="$SCRIPT_DIR"

cd "$REPO_ROOT"

LOG_DIR="data/docker-logs"
ENV_FILE=${DOCKER_ENV_FILE:-.env}
DEPLOY_MODE=""
RUN_ACTION=""
COMPOSE_FILE=""
COMPOSE_CMD=()
_RANKED_DIR=""
ENSURE_DB=0
PREPARE_DB_BEFORE_UP=0
POSTGRES_CONTAINER_NAME=${POSTGRES_CONTAINER_NAME:-wharttest-postgres}
mkdir -p "$LOG_DIR"

usage() {
  cat <<'USAGE'
用法:
  ./run_compose.sh [local] [up|db-check|db-upgrade|db-init] [compose-file] [--ensure-db]

模式:
  local    本地源码构建镜像（默认 compose: docker-compose.local.yml）

动作（通过参数或 DOCKER_RUN_ACTION 指定；未指定时默认 up）:
  up           正常启动服务
  db-check     检测数据库连通性与目标数据库是否存在
  db-upgrade   检测并执行 Django migrations 升级数据库结构
  db-init      检测/创建数据库 + migrations + 初始化数据（管理员、技能、默认提示词）

选项:
  --ensure-db  当目标 PostgreSQL 数据库不存在时，自动创建后再升级

环境变量:
  DOCKER_DEPLOY_MODE=local
  DOCKER_RUN_ACTION=up|db-check|db-upgrade|db-init
  DOCKER_ENSURE_DB=0|1
  DOCKER_PREPARE_DB_BEFORE_UP=0|1
  DOCKER_SOURCE_PROFILE=auto|native|mirror
  DOCKER_BUILD_NO_CACHE=1   # local 模式下不使用缓存，适用于版本升级
  DOCKER_BUILD_PULL=1
  DOCKER_LOCAL_PULL_RUNTIME=0|1
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

# 生成随机密钥：优先 openssl，退化为 od（POSIX），最后用 python3
random_secret() {
  local bytes="$1"

  if [ -z "$bytes" ]; then
    bytes=32
  fi

  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
    return 0
  fi

  if command -v od >/dev/null 2>&1; then
    od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_hex($bytes))"
    return 0
  fi

  echo "错误：缺少 openssl / od / python3，无法生成随机密钥" >&2
  return 1
}

# 读取 .env 中某个键当前生效的值（忽略注释行与行尾 CR）
env_file_value() {
  local name="$1"

  [ -f "$ENV_FILE" ] || return 0

  # 未配置该键时 grep 返回 1，这里必须容忍，否则 set -e + pipefail 会中止脚本
  tr -d "\r" < "$ENV_FILE" \
    | grep -E "^[[:space:]]*$name=" \
    | tail -n 1 \
    | cut -d= -f2- \
    | sed -E 's/^"(.*)"$/\1/' \
    || true
}

# 写入/替换 .env 中某个键，注释掉的示例行会被替换为生效行
env_file_set() {
  local name="$1"
  local value="$2"
  local tmp_file=""

  [ -f "$ENV_FILE" ] || return 1

  tmp_file=$(mktemp "$ENV_FILE.XXXXXX") || return 1
  tr -d "\r" < "$ENV_FILE" | sed -E "s|^[[:space:]]*#?[[:space:]]*$name=.*|$name=$value|" > "$tmp_file"
  grep -qE "^[[:space:]]*$name=" "$tmp_file" || printf "%s=%s\n" "$name" "$value" >> "$tmp_file"
  # 用 cat 覆盖而不是 mv，保留 .env 原有权限与属主
  cat "$tmp_file" > "$ENV_FILE"
  rm -f "$tmp_file"
}

# 确保 .env 中某个密钥非空：缺失则生成并回写，同时导出给 compose 使用
ensure_env_secret() {
  local name="$1"
  local bytes="${2:-32}"
  local prefix="${3:-}"
  local current=""
  local generated=""

  if [ -z "$bytes" ]; then
    bytes=32
  fi

  current=$(env_file_value "$name")
  if [ -n "$current" ]; then
    export "$name=$current"
    return 0
  fi

  generated="$prefix$(random_secret "$bytes")" || return 1
  env_file_set "$name" "$generated"
  export "$name=$generated"
  echo "已自动生成 $name 并写入 $ENV_FILE（无需手工配置）"
}

# 同步 WS 认证密钥到本机执行器配置（config.toml / config.example.toml）。
# 只改 [server] ws_token 一行，其余内容原样保留；文件不存在时从 example 复制生成。
sync_actuator_ws_token() {
  local token_value="$1"
  local actuator_dir="$SCRIPT_DIR/WHartTest_Actuator"
  local example_path="$actuator_dir/config.example.toml"
  local config_path="$actuator_dir/config.toml"

  # 首次部署：config.toml 尚未生成（用户还没跑过 main.py），
  # 先从 example 复制一份，保证用户之后首次启动即带密钥。
  if [ ! -f "$config_path" ] && [ -f "$example_path" ]; then
    cp "$example_path" "$config_path"
    echo "已从 config.example.toml 生成 $config_path"
  fi

  local target
  for target in "$config_path" "$example_path"; do
    [ -f "$target" ] || continue
    if grep -qE '^[[:space:]]*ws_token[[:space:]]*=' "$target"; then
      # 已有 ws_token 行：值一致则跳过，不一致则覆盖为新密钥
      local current
      current=$(grep -E '^[[:space:]]*ws_token[[:space:]]*=' "$target" | tail -n 1 | sed -E 's/^[^=]*=[[:space:]]*"([^"]*)".*/\1/')
      if [ "$current" = "$token_value" ]; then
        continue
      fi
      sed -i -E "s|^[[:space:]]*ws_token[[:space:]]*=.*|ws_token = \"$token_value\"|" "$target"
      echo "已更新 $target 中的 ws_token（与本机后端密钥保持一致）"
    else
      # 无 ws_token 行：追加到 [server] 段末尾（第一个 [ 区块结束前）
      if grep -qE '^[[:space:]]*\[server\]' "$target"; then
        awk -v tok="ws_token = \"$token_value\"" '
          BEGIN{done=0} /^\[server\]/{insrv=1}
          insrv && /^[[:space:]]*\[/ && !/^\[server\]/ && !done {print tok; done=1}
          {print}
          END{if(!done) print tok}
        ' "$target" > "$target.tmp" && mv "$target.tmp" "$target"
        echo "已在 $target 的 [server] 段写入 ws_token"
      fi
    fi
  done
}

# 首次运行引导：补齐 .env 与密钥，使“复制 .env.example 后直接执行”即可使用
bootstrap_env_secrets() {
  local secret_key=""
  local generated_secret=""

  if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f .env.example ]; then
      echo "错误：未找到 $ENV_FILE，且没有 .env.example 可作为模板" >&2
      return 1
    fi
    cp .env.example "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    echo "未检测到 $ENV_FILE，已从 .env.example 创建"
    # 新建的 .env 需要立即生效，否则后续步骤读不到示例里的其它配置
    set -a
    # shellcheck disable=SC1090
    source <(sed 's/\r$//' "$ENV_FILE")
    set +a
  fi

  # backend 与 skill-runner 两侧共用同一个值：启动前生成即可，无需启动后再重启
  ensure_env_secret SKILL_RUNNER_TOKEN 32
  ensure_env_secret DJANGO_ADMIN_PASSWORD 24
  ensure_env_secret WHARTTEST_API_KEY 24 "whart-"
  # UI 自动化 WS 认证：执行器连接共享密钥，与执行器侧 WHARTTEST_ACTUATOR_WS_TOKEN
  # 同值（下方统一注入），无需手工配置
  ensure_env_secret UI_WS_ACTUATOR_TOKEN 32

  # 执行器通过独立变量注入，未配置时复用同一把平台 Key（必须与数据库中的记录一致）
  local actuator_key=""
  actuator_key=$(env_file_value WHARTTEST_ACTUATOR_API_KEY)
  if [ -z "$actuator_key" ]; then
    actuator_key="$WHARTTEST_API_KEY"
    env_file_set WHARTTEST_ACTUATOR_API_KEY "$actuator_key"
  fi
  export WHARTTEST_ACTUATOR_API_KEY="$actuator_key"

  # 执行器 WS 认证 token：与后端 UI_WS_ACTUATOR_TOKEN 同值（兼容模式留空也可运行）
  local ws_token=""
  ws_token=$(env_file_value WHARTTEST_ACTUATOR_WS_TOKEN)
  if [ -z "$ws_token" ]; then
    ws_token="$UI_WS_ACTUATOR_TOKEN"
    env_file_set WHARTTEST_ACTUATOR_WS_TOKEN "$ws_token"
  fi
  export WHARTTEST_ACTUATOR_WS_TOKEN="$ws_token"

  # 本地执行器配置同步：把 WS 认证密钥写进 WHartTest_Actuator/config.toml
  # 的 [server] ws_token（不存在则从 config.example.toml 生成后再写），
  # 使本机手动运行的执行器（python main.py）与容器后端密钥一致，升级后
  # 无需手工配置。config.example.toml 同步写入：保证"先跑执行器、后跑
  # 本脚本"时由 example 生成的 config.toml 也带上密钥。
  sync_actuator_ws_token "$ws_token"

  # 示例中的占位密钥：未替换时自动生成，避免以公开占位值上线
  secret_key=$(env_file_value DJANGO_SECRET_KEY)
  if [ -z "$secret_key" ] || [ "$secret_key" = "your-secret-key-here-change-in-production" ]; then
    generated_secret=$(random_secret 32) || return 1
    env_file_set DJANGO_SECRET_KEY "$generated_secret"
    export DJANGO_SECRET_KEY="$generated_secret"
    echo "已自动生成 DJANGO_SECRET_KEY 并写入 $ENV_FILE"
  fi

  # skill-runner 以非 root 运行：数据目录需由当前用户预先创建，否则容器内无法写产物
  mkdir -p data/media/skill_runtime data/playwright-screenshots 2>/dev/null || true
  if [ -d data/media/skill_runtime ] && [ ! -w data/media/skill_runtime ]; then
    echo "警告：data/media/skill_runtime 当前用户不可写，skill-runner 写产物会失败。" >&2
    echo "      可执行: sudo chown -R $(id -u):$(id -g) data/media/skill_runtime" >&2
  fi

  # 默认以当前宿主用户身份运行 runner，避免 uid 1000 与宿主用户不一致导致写权限失败
  if [ -z "${SKILL_RUNNER_UID:-}" ] && command -v id >/dev/null 2>&1; then
    export SKILL_RUNNER_UID
    SKILL_RUNNER_UID=$(id -u)
  fi
  if [ -z "${SKILL_RUNNER_GID:-}" ] && command -v id >/dev/null 2>&1; then
    export SKILL_RUNNER_GID
    SKILL_RUNNER_GID=$(id -g)
  fi
}

prompt_local_build_mode() {
  local choice=""

  if [ "$DEPLOY_MODE" != "local" ]; then
    return 0
  fi

  if [ -n "${DOCKER_BUILD_NO_CACHE+x}" ]; then
    if [ "${DOCKER_BUILD_NO_CACHE:-0}" = "1" ]; then
      echo "本地构建方式: 从 0 构建 / 不使用缓存（由 DOCKER_BUILD_NO_CACHE=1 指定）"
    else
      echo "本地构建方式: 使用缓存构建（由 DOCKER_BUILD_NO_CACHE=${DOCKER_BUILD_NO_CACHE:-0} 指定）"
    fi
    return 0
  fi

  echo "请选择本地构建方式："
  echo "  1) 使用缓存构建（默认，速度更快）"
  echo "  2) 从 0 构建 / 不使用缓存（适用于版本升级）"
  echo "  3) 先检测/修复数据库，再使用缓存构建并启动服务"
  echo "  4) 仅迁移数据库并初始化数据（不构建/不启动服务）"

  while true; do
    read -r -p "请输入 1、2、3 或 4（默认 1）: " choice
    choice=${choice:-1}

    case "$choice" in
      1|cache)
        DOCKER_BUILD_NO_CACHE=0
        export DOCKER_BUILD_NO_CACHE
        echo "构建策略: 使用缓存构建"
        return 0
        ;;
      2|no-cache|rebuild|clean)
        DOCKER_BUILD_NO_CACHE=1
        export DOCKER_BUILD_NO_CACHE

        if [ -z "${DOCKER_BUILD_PULL+x}" ]; then
          DOCKER_BUILD_PULL=1
          export DOCKER_BUILD_PULL
        fi

        echo "构建策略: 从 0 构建 / 不使用缓存"
        echo "说明: 已自动启用 DOCKER_BUILD_PULL=${DOCKER_BUILD_PULL:-1}，用于拉取最新基础镜像。"
        return 0
        ;;
      3|db|db-upgrade|prepare-db|ensure-db)
        DOCKER_BUILD_NO_CACHE=0
        DOCKER_PREPARE_DB_BEFORE_UP=1
        PREPARE_DB_BEFORE_UP=1
        ENSURE_DB=1
        export DOCKER_BUILD_NO_CACHE DOCKER_PREPARE_DB_BEFORE_UP
        echo "构建策略: 先检测/修复数据库，再使用缓存构建"
        echo "说明: 若 PostgreSQL 数据库不存在会自动创建；随后会执行 Django migrations 修正表结构。"
        return 0
        ;;
      4|init|migrate|db-init)
        RUN_ACTION="db-init"
        ENSURE_DB=1
        echo "执行模式: 仅迁移数据库并初始化数据"
        echo "说明: 若数据库不存在会自动创建；执行 migrations 后运行初始化脚本。"
        return 0
        ;;
      *)
        echo "输入无效，请输入 1、2、3 或 4。"
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
      up|db-check|db-upgrade|db-init)
        RUN_ACTION="$1"
        ;;
      --ensure-db)
        ENSURE_DB=1
        ;;
      remote)
        echo "错误：remote 模式已移除，请使用 local（默认）。" >&2
        exit 1
        ;;
      init-models|init|models)
        echo "错误：模型初始化模式已移除，请使用 local（默认）。" >&2
        exit 1
        ;;
      local)
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

  if [ -z "$RUN_ACTION" ] && [ -n "${DOCKER_RUN_ACTION:-}" ]; then
    RUN_ACTION="$DOCKER_RUN_ACTION"
  fi

  if [ "$ENSURE_DB" -eq 0 ] && [ "${DOCKER_ENSURE_DB:-0}" = "1" ]; then
    ENSURE_DB=1
  fi

  if [ "${DOCKER_PREPARE_DB_BEFORE_UP:-0}" = "1" ]; then
    PREPARE_DB_BEFORE_UP=1
    ENSURE_DB=1
  fi

  if [ -z "$DEPLOY_MODE" ] && [ -n "${DOCKER_DEPLOY_MODE:-}" ]; then
    DEPLOY_MODE="$DOCKER_DEPLOY_MODE"
  fi

  if [ -z "$DEPLOY_MODE" ]; then
    DEPLOY_MODE="local"
  fi

  case "$DEPLOY_MODE" in
    local)
      COMPOSE_FILE=${COMPOSE_FILE:-${DOCKER_LOCAL_COMPOSE_FILE:-docker-compose.local.yml}}
      ;;
    init|models|init-models)
      echo "错误：DOCKER_DEPLOY_MODE=$DEPLOY_MODE 已不再支持，请改用 local。" >&2
      exit 1
      ;;
    remote)
      echo "错误：DOCKER_DEPLOY_MODE=remote 已不再支持，请改用 local。" >&2
      exit 1
      ;;
    *)
      echo "错误：DOCKER_DEPLOY_MODE 仅支持 local，当前值为 '$DEPLOY_MODE'" >&2
      exit 1
      ;;
  esac

  if [ ! -f "$COMPOSE_FILE" ]; then
    echo "错误：compose 文件不存在: $COMPOSE_FILE" >&2
    exit 1
  fi

  if [ -z "$RUN_ACTION" ]; then
    RUN_ACTION="up"
  fi

  case "$RUN_ACTION" in
    up|db-check|db-upgrade|db-init)
      ;;
    *)
      echo "错误：DOCKER_RUN_ACTION 仅支持 up、db-check、db-upgrade、db-init，当前值为 '$RUN_ACTION'" >&2
      exit 1
      ;;
  esac

  if [ "$DEPLOY_MODE" = "local" ] && [ "$RUN_ACTION" != "db-check" ] && [ -t 0 ] && [ -t 1 ]; then
    prompt_local_build_mode
  fi

  echo "部署模式: $DEPLOY_MODE"
  echo "使用的 compose 文件: $COMPOSE_FILE"
  echo "执行动作: $RUN_ACTION"
  if [ "$PREPARE_DB_BEFORE_UP" -eq 1 ]; then
    echo "启动前数据库预检: 启用"
  fi
}

normalize_branch_data_variant() {
  case "$1" in
    ce|pe|dev|auto)
      printf '%s' "$1"
      ;;
    *)
      printf '%s' ""
      ;;
  esac
}

get_current_branch_name() {
  git rev-parse --abbrev-ref HEAD 2>/dev/null || true
}

get_branch_data_variant() {
  local branch_name="${1:-}"

  if [[ "$branch_name" == *-ce ]]; then
    printf '%s' "ce"
    return 0
  fi

  if [[ "$branch_name" == *-pe ]]; then
    printf '%s' "pe"
    return 0
  fi

  printf '%s' "dev"
}

build_postgres_db_name() {
  local variant="$1"
  if [ "$variant" = "dev" ]; then
    printf '%s' "wharttest_dev"
  else
    printf 'wharttest_%s' "$variant"
  fi
}

is_default_postgres_db_name() {
  case "$1" in
    ""|wharttest|wharttest_dev|wharttest_ce|wharttest_pe)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_default_sqlite_path() {
  case "$1" in
    ""|/app/data/db.sqlite3|db.sqlite3)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_default_checkpoint_sqlite_path() {
  case "$1" in
    ""|/app/data/chat_history.sqlite|chat_history.sqlite)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

configure_branch_data_variant() {
  if [ "$DEPLOY_MODE" != "local" ]; then
    return 0
  fi

  if [ "${WHARTTEST_AUTO_BRANCH_DATA:-1}" != "1" ]; then
    echo "本地开发数据自动切换已禁用（WHARTTEST_AUTO_BRANCH_DATA=${WHARTTEST_AUTO_BRANCH_DATA:-0}）"
    return 0
  fi

  local branch_name=""
  local variant=""
  local explicit_variant=""
  local sqlite_path=""
  local checkpoint_path=""

  branch_name=$(get_current_branch_name)
  explicit_variant=$(normalize_branch_data_variant "${POSTGRES_DB_VARIANT:-}")
  if [ -n "$explicit_variant" ] && [ "$explicit_variant" != "auto" ]; then
    variant="$explicit_variant"
  else
    variant=$(get_branch_data_variant "$branch_name")
  fi

  export POSTGRES_DB_VARIANT="$variant"

  if is_default_postgres_db_name "${POSTGRES_DB:-}"; then
    export POSTGRES_DB
    POSTGRES_DB=$(build_postgres_db_name "$variant")
  fi

  if is_default_sqlite_path "${DATABASE_PATH:-}"; then
    export DATABASE_PATH
    if [ "$variant" = "dev" ]; then
      DATABASE_PATH="/app/data/db.sqlite3"
    else
      DATABASE_PATH="/app/data/db_${variant}.sqlite3"
    fi
  fi

  if is_default_checkpoint_sqlite_path "${LANGGRAPH_CHECKPOINT_SQLITE_PATH:-}"; then
    export LANGGRAPH_CHECKPOINT_SQLITE_PATH
    if [ "$variant" = "dev" ]; then
      LANGGRAPH_CHECKPOINT_SQLITE_PATH="/app/data/chat_history.sqlite"
    else
      LANGGRAPH_CHECKPOINT_SQLITE_PATH="/app/data/chat_history_${variant}.sqlite"
    fi
  fi

  echo "本地开发数据变体: $variant"
  if [ -n "$branch_name" ]; then
    echo "当前 Git 分支: $branch_name"
  fi
  echo "- POSTGRES_DB: ${POSTGRES_DB:-}"
  echo "- DATABASE_PATH: ${DATABASE_PATH:-}"
  echo "- LANGGRAPH_CHECKPOINT_SQLITE_PATH: ${LANGGRAPH_CHECKPOINT_SQLITE_PATH:-}"
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

cleanup_ranked_dir() {
  if [ -n "${_RANKED_DIR:-}" ] && [ -d "$_RANKED_DIR" ]; then
    rm -rf "$_RANKED_DIR"
  fi
  _RANKED_DIR=""
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

validate_compose_file() {
  local output=""
  local line_no=""
  local start=1
  local end=1

  if output=$("${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" config 2>&1 >/dev/null); then
    return 0
  fi

  echo "错误：compose 文件校验失败: $COMPOSE_FILE" >&2
  echo "$output" >&2

  if [[ "$output" =~ yaml:\ line\ ([0-9]+): ]]; then
    line_no="${BASH_REMATCH[1]}"
    start=$(( line_no > 3 ? line_no - 3 : 1 ))
    end=$(( line_no + 3 ))
    echo "以下是出错行附近内容（第 ${line_no} 行）：" >&2
    nl -ba "$COMPOSE_FILE" | sed -n "${start},${end}p" >&2 || true
  fi

  echo "脚本已停止。由于开头启用了 set -euo pipefail，compose 校验或构建命令一旦返回非 0，脚本会立即退出。" >&2
  exit 1
}

compose_has_service() {
  local service_name="$1"
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -Fxq "$service_name"
}

resolve_target_postgres_db() {
  local explicit_variant=""
  local explicit_db=""
  local branch_name=""
  local variant=""

  explicit_variant=$(normalize_branch_data_variant "${POSTGRES_DB_VARIANT:-}")
  if [ -n "$explicit_variant" ]; then
    if [ "$explicit_variant" = "auto" ]; then
      branch_name=$(get_current_branch_name)
      variant=$(get_branch_data_variant "$branch_name")
    else
      variant="$explicit_variant"
    fi
    build_postgres_db_name "$variant"
    return 0
  fi

  explicit_db=${POSTGRES_DB:-}
  if [ -n "$explicit_db" ]; then
    printf '%s' "$explicit_db"
    return 0
  fi

  branch_name=$(get_current_branch_name)
  variant=$(get_branch_data_variant "$branch_name")
  build_postgres_db_name "$variant"
}

quote_sql_literal() {
  local value="${1//\'/\'\'}"
  printf "'%s'" "$value"
}

quote_sql_identifier() {
  local value="${1//\"/\"\"}"
  printf '"%s"' "$value"
}

wait_for_service_ready() {
  local service="$1"
  local timeout="${2:-120}"
  local interval=2
  local elapsed=0
  local container_id=""
  local status=""

  while [ "$elapsed" -lt "$timeout" ]; do
    container_id=$("${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null || true)

    if [ -n "$container_id" ]; then
      status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
      case "$status" in
        healthy|running)
          echo "服务 $service 已就绪（$status）"
          return 0
          ;;
        exited|dead)
          echo "错误：服务 $service 启动失败（$status）" >&2
          return 1
          ;;
      esac
    fi

    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  echo "错误：等待服务 $service 就绪超时（${timeout}s）" >&2
  return 1
}

wait_for_container_ready() {
  local container_name="$1"
  local timeout="${2:-120}"
  local interval=2
  local elapsed=0
  local status=""

  while [ "$elapsed" -lt "$timeout" ]; do
    status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_name" 2>/dev/null || true)

    case "$status" in
      healthy|running)
        echo "容器 $container_name 已就绪（$status）"
        return 0
        ;;
      exited|dead)
        echo "错误：容器 $container_name 状态异常（$status）" >&2
        return 1
        ;;
    esac

    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  echo "错误：等待容器 $container_name 就绪超时（${timeout}s）" >&2
  return 1
}

postgres_container_exists() {
  docker inspect "$POSTGRES_CONTAINER_NAME" >/dev/null 2>&1
}

ensure_postgres_service() {
  if ! compose_has_service postgres; then
    echo "错误：当前 compose 文件未启用 postgres 服务，无法执行 PostgreSQL 相关操作。" >&2
    return 1
  fi

  if postgres_container_exists; then
    echo "检测到已存在 PostgreSQL 容器: $POSTGRES_CONTAINER_NAME，直接复用。"
    wait_for_container_ready "$POSTGRES_CONTAINER_NAME" "${DOCKER_POSTGRES_READY_TIMEOUT:-120}"
    return 0
  fi

  echo "启动 PostgreSQL 服务..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up -d postgres
  wait_for_container_ready "$POSTGRES_CONTAINER_NAME" "${DOCKER_POSTGRES_READY_TIMEOUT:-120}"
}

run_postgres_psql() {
  docker exec -i "$POSTGRES_CONTAINER_NAME" \
    psql --username "${POSTGRES_USER:-postgres}" --dbname postgres "$@"
}

postgres_database_exists() {
  local db_name="$1"
  local quoted_db=""
  local result=""

  quoted_db=$(quote_sql_literal "$db_name")
  result=$(run_postgres_psql \
    -tAc "SELECT 1 FROM pg_database WHERE datname = ${quoted_db}" 2>/dev/null | tr -d '[:space:]' || true)

  [ "$result" = "1" ]
}

create_postgres_database() {
  local db_name="$1"
  local quoted_db=""

  quoted_db=$(quote_sql_identifier "$db_name")
  echo "创建 PostgreSQL 数据库: $db_name"
  run_postgres_psql -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE ${quoted_db};"
}

confirm_create_database() {
  local db_name="$1"
  local answer=""

  if [ "$ENSURE_DB" -eq 1 ]; then
    return 0
  fi

  if [ -t 0 ] && [ -t 1 ]; then
    read -r -p "数据库 '$db_name' 不存在，是否立即创建？[y/N]: " answer
    case "$answer" in
      y|Y|yes|YES)
        return 0
        ;;
    esac
  fi

  return 1
}

prepare_backend_for_db_action() {
  local build_args=()
  local backend_image=""

  # 检查 backend 镜像是否已存在，已存在则跳过测速和构建
  backend_image=$("${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" config --images 2>/dev/null | grep -i backend | head -n 1 || true)
  if [ -n "$backend_image" ] && docker image inspect "$backend_image" >/dev/null 2>&1; then
    echo "backend 镜像已存在（$backend_image），跳过构建。"
    return 0
  fi

  export DOCKER_BUILDKIT=1
  export COMPOSE_DOCKER_CLI_BUILD=1

  configure_download_sources
  configure_local_base_images

  if [ "${DOCKER_BUILD_NO_CACHE:-0}" = "1" ]; then
    build_args+=(--no-cache)
  fi

  if [ "${DOCKER_BUILD_PULL:-0}" = "1" ]; then
    build_args+=(--pull)
  fi

  echo "构建 backend 镜像（数据库维护模式）..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" build "${build_args[@]}" backend

  cleanup_ranked_dir
}

run_backend_python() {
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" run --rm --no-deps --entrypoint python backend "$@"
}

run_db_check() {
  local database_type="${DATABASE_TYPE:-postgres}"
  local target_db=""

  echo "开始检测数据库状态..."
  echo "数据库类型: $database_type"

  if [ "$database_type" = "postgres" ]; then
    target_db=$(resolve_target_postgres_db)

    echo "目标 PostgreSQL 数据库: $target_db"
    echo "连接地址: ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}"

    ensure_postgres_service

    if postgres_database_exists "$target_db"; then
      echo "✔ 数据库存在：$target_db"
      echo "提示：如需升级数据库结构，可执行: ./run_compose.sh db-upgrade"
      return 0
    fi

    echo "✘ 数据库不存在：$target_db" >&2
    echo "提示：可使用 --ensure-db 让 db-upgrade 在升级前自动创建该数据库。" >&2
    return 1
  fi

  echo "SQLite 模式无需预检查远程数据库，迁移时会直接使用当前 DATABASE_PATH。"
}

run_db_upgrade() {
  local database_type="${DATABASE_TYPE:-postgres}"
  local target_db=""

  echo "开始执行数据库结构升级..."
  echo "数据库类型: $database_type"

  if [ "$database_type" = "postgres" ]; then
    target_db=$(resolve_target_postgres_db)

    echo "目标 PostgreSQL 数据库: $target_db"
    echo "连接地址: ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}"

    ensure_postgres_service

    if ! postgres_database_exists "$target_db"; then
      echo "目标数据库不存在：$target_db"
      if confirm_create_database "$target_db"; then
        create_postgres_database "$target_db"
      else
        echo "已取消自动创建数据库。你也可以重试并附加 --ensure-db。" >&2
        return 1
      fi
    else
      echo "✔ 数据库存在：$target_db"
    fi
  fi

  prepare_backend_for_db_action

  echo "执行 Django migrations..."
  run_backend_python manage.py migrate --noinput
  echo "✔ 数据库结构升级完成。"
}

run_db_prepare_before_up() {
  local database_type="${DATABASE_TYPE:-postgres}"
  local target_db=""

  echo "步骤 1/3：检测数据库..."
  echo "数据库类型: $database_type"

  if [ "$database_type" = "postgres" ]; then
    target_db=$(resolve_target_postgres_db)

    echo "目标 PostgreSQL 数据库: $target_db"
    echo "连接地址: ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}"

    ensure_postgres_service

    if postgres_database_exists "$target_db"; then
      echo "✔ 数据库存在：$target_db"
    else
      echo "✘ 数据库不存在：$target_db"
      echo "步骤 2/3：自动创建数据库..."
      create_postgres_database "$target_db"
      echo "✔ 数据库已创建：$target_db"
    fi
  else
    echo "SQLite 模式无需创建数据库文件，迁移时会直接使用当前 DATABASE_PATH。"
  fi

  echo "步骤 3/3：检测并迁移表结构..."
  prepare_backend_for_db_action
  run_backend_python manage.py migrate --noinput
  echo "✔ 数据库检测/创建/迁移完成。"
}

run_db_init() {
  local database_type="${DATABASE_TYPE:-postgres}"
  local target_db=""

  echo "=== 数据库初始化（检测/创建/迁移/初始数据） ==="
  echo "数据库类型: $database_type"

  if [ "$database_type" = "postgres" ]; then
    target_db=$(resolve_target_postgres_db)

    echo "目标 PostgreSQL 数据库: $target_db"
    echo "连接地址: ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}"

    ensure_postgres_service

    if postgres_database_exists "$target_db"; then
      echo "✔ 数据库已存在：$target_db"
    else
      echo "数据库不存在：$target_db，自动创建..."
      create_postgres_database "$target_db"
      echo "✔ 数据库已创建：$target_db"
    fi
  else
    echo "SQLite 模式无需创建数据库文件，迁移时会直接使用当前 DATABASE_PATH。"
  fi

  prepare_backend_for_db_action

  echo "执行 Django migrations..."
  run_backend_python manage.py migrate --noinput
  echo "✔ 数据库迁移完成。"

  echo "执行初始化脚本..."
  run_backend_python manage.py init_admin
  run_backend_python manage.py init_skills
  run_backend_python manage.py init_default_prompts
  echo "✔ 初始化数据写入完成。"

  echo "=== 数据库初始化全部完成 ==="
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

}

pull_local_runtime_images() {
  local pull_failed=0

  echo "开始预拉取运行时镜像（本地构建模式）..."

  if compose_has_service postgres; then
    pull_image_with_fallback DOCKER_POSTGRES_IMAGE "postgres:16-alpine" dockerhub || pull_failed=1
  fi

  if compose_has_service redis; then
    pull_image_with_fallback DOCKER_REDIS_IMAGE "redis:7-alpine" dockerhub || pull_failed=1
  fi

  if compose_has_service qdrant; then
    pull_image_with_fallback DOCKER_QDRANT_IMAGE "qdrant/qdrant:latest" dockerhub || pull_failed=1
  fi

  if compose_has_service playwright-mcp; then
    pull_image_with_fallback DOCKER_PLAYWRIGHT_MCP_IMAGE "mcr.microsoft.com/playwright/mcp" mcr || pull_failed=1
  fi

  if [ "$pull_failed" -eq 1 ]; then
    echo "错误：部分运行时镜像拉取失败，请检查网络连接或手动指定镜像源" >&2
    return 1
  fi

  echo "运行时镜像拉取完成。"
}

run_local_mode() {
  local build_args=()
  local up_args=(-d --remove-orphans)

  # 启用 BuildKit：并行层构建 + 更智能的缓存
  export DOCKER_BUILDKIT=1
  export COMPOSE_DOCKER_CLI_BUILD=1

  validate_compose_file

  if [ "$PREPARE_DB_BEFORE_UP" -eq 1 ]; then
    echo "启动前先检测数据库，必要时创建并执行表结构迁移..."
    run_db_prepare_before_up
    echo "数据库准备完成，继续构建并启动服务..."
  else
    configure_download_sources
    configure_local_base_images
  fi

  if [ "${DOCKER_LOCAL_PULL_RUNTIME:-1}" = "1" ]; then
    pull_local_runtime_images
  else
    echo "已跳过运行时镜像预拉取（DOCKER_LOCAL_PULL_RUNTIME=0）"
  fi

  if [ "${DOCKER_BUILD_NO_CACHE:-0}" = "1" ]; then
    build_args+=(--no-cache)
    if [ "${DOCKER_BUILD_PULL:-0}" = "1" ]; then
      echo "开始构建镜像（从 0 构建，不使用缓存，并拉取最新基础镜像）..."
    else
      echo "开始构建镜像（从 0 构建，不使用缓存）..."
    fi
  else
    echo "开始构建镜像（启用缓存）..."
  fi

  if [ "${DOCKER_BUILD_PULL:-0}" = "1" ]; then
    build_args+=(--pull)
  fi

  if [ "${DOCKER_FORCE_RECREATE:-1}" = "1" ]; then
    up_args+=(--force-recreate)
  fi

  echo "构建业务服务镜像..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" build "${build_args[@]}"

  echo "启动容器（本地构建模式）..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up "${up_args[@]}"

  cleanup_ranked_dir
}

collect_status_and_logs() {
  echo "收集主要服务状态..."
  local services=(backend redis postgres qdrant mcp frontend playwright-mcp xinference)

  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps

  for svc in "${services[@]}"; do
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" logs --tail 200 "$svc" > "$LOG_DIR/$svc.log" 2>&1 || true
  done

  echo "日志已保存到 $LOG_DIR/*.log"
  echo "如果服务启动失败，请查看日志文件，并检查端口占用与宿主机挂载文件是否可用。"
}

print_summary() {
  cat <<'EOF2'
部署完成！访问 http://localhost:8913 体验 WhartTest,默认管理员账号 admin，密码 admin123456
数据库维护命令：./run_compose.sh [local] [db-check|db-upgrade] [compose-file] [--ensure-db]
EOF2
}

main() {
  load_env_file
  resolve_mode_and_compose "$@"
  configure_branch_data_variant
  require_docker

  if [ "$RUN_ACTION" = "db-check" ] || [ "$RUN_ACTION" = "db-upgrade" ] || [ "$RUN_ACTION" = "db-init" ]; then
    validate_compose_file
  fi

  if [ "$RUN_ACTION" = "db-check" ]; then
    run_db_check
    return 0
  fi

  if [ "$RUN_ACTION" = "db-upgrade" ]; then
    run_db_upgrade
    return 0
  fi

  if [ "$RUN_ACTION" = "db-init" ]; then
    run_db_init
    return 0
  fi

  case "$DEPLOY_MODE" in
    local)
      run_local_mode
      ;;
  esac

  collect_status_and_logs
  print_summary
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '%s\n' "[xinference-qwen3vl] $*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "missing required command: $1"
    exit 1
  fi
}

XINFERENCE_CONTAINER_NAME="${XINFERENCE_CONTAINER_NAME:-wharttest-xinference}"
XINFERENCE_IMAGE="${XINFERENCE_IMAGE:-xprobe/xinference:latest-cpu}"
XINFERENCE_HOST_PORT="${XINFERENCE_HOST_PORT:-8917}"
XINFERENCE_DATA_VOLUME="${XINFERENCE_DATA_VOLUME:-xinference-data}"
XINFERENCE_CACHE_VOLUME="${XINFERENCE_CACHE_VOLUME:-xinference-cache}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
XINFERENCE_DOCKER_NETWORK="${XINFERENCE_DOCKER_NETWORK:-}"

XINFERENCE_MODEL_UID="${XINFERENCE_MODEL_UID:-qwen3-vl-emb-2b}"
XINFERENCE_MODEL_NAME="${XINFERENCE_MODEL_NAME:-Qwen3-VL-Embedding-2B}"

XINFERENCE_RERANK_ENABLED="${XINFERENCE_RERANK_ENABLED:-1}"
XINFERENCE_RERANK_MODEL_UID="${XINFERENCE_RERANK_MODEL_UID:-Qwen3-VL-Reranker-2B}"
XINFERENCE_RERANK_MODEL_NAME="${XINFERENCE_RERANK_MODEL_NAME:-Qwen3-VL-Reranker-2B}"

XINFERENCE_CREATE_CONTAINER="${XINFERENCE_CREATE_CONTAINER:-1}"
XINFERENCE_ENTRYPOINT_SCRIPT="${XINFERENCE_ENTRYPOINT_SCRIPT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/xinference-entrypoint-qwen3-vl-embedding-2b.sh}"
XINFERENCE_USE_ENTRYPOINT="${XINFERENCE_USE_ENTRYPOINT:-1}"

container_uses_entrypoint_script() {
  local entrypoint cmd
  entrypoint="$(docker inspect -f '{{.Config.Entrypoint}}' "$XINFERENCE_CONTAINER_NAME" 2>/dev/null || true)"
  cmd="$(docker inspect -f '{{.Config.Cmd}}' "$XINFERENCE_CONTAINER_NAME" 2>/dev/null || true)"
  [[ "${entrypoint} ${cmd}" == *"xinference-entrypoint.sh"* ]]
}

container_exists() {
  docker inspect "$XINFERENCE_CONTAINER_NAME" >/dev/null 2>&1
}

container_running() {
  local running
  running="$(docker inspect -f '{{.State.Running}}' "$XINFERENCE_CONTAINER_NAME" 2>/dev/null || true)"
  [[ "$running" == "true" ]]
}

maybe_connect_network() {
  local network="$XINFERENCE_DOCKER_NETWORK"
  if [[ -z "$network" ]] && docker inspect wharttest-backend >/dev/null 2>&1; then
    network="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' wharttest-backend 2>/dev/null | head -n 1 || true)"
  fi

  if [[ -z "$network" ]]; then
    return 0
  fi

  log "connecting container to docker network: $network"
  docker network connect "$network" "$XINFERENCE_CONTAINER_NAME" >/dev/null 2>&1 || true
}

ensure_container() {
  if container_exists; then
    if ! container_running; then
      log "starting existing container: $XINFERENCE_CONTAINER_NAME"
      docker start "$XINFERENCE_CONTAINER_NAME" >/dev/null
    fi
    maybe_connect_network
    return 0
  fi

  if [[ "$XINFERENCE_CREATE_CONTAINER" != "1" ]]; then
    log "container not found: $XINFERENCE_CONTAINER_NAME (set XINFERENCE_CREATE_CONTAINER=1 to auto-create)"
    exit 1
  fi

  log "creating container: $XINFERENCE_CONTAINER_NAME"
  if [[ "$XINFERENCE_USE_ENTRYPOINT" == "1" ]] && [[ -f "$XINFERENCE_ENTRYPOINT_SCRIPT" ]]; then
    docker run -d \
      --name "$XINFERENCE_CONTAINER_NAME" \
      --restart unless-stopped \
      -p "0.0.0.0:${XINFERENCE_HOST_PORT}:9997" \
      -v "${XINFERENCE_DATA_VOLUME}:/root/.xinference" \
      -v "${XINFERENCE_CACHE_VOLUME}:/root/.cache/huggingface" \
      -v "${XINFERENCE_ENTRYPOINT_SCRIPT}:/usr/local/bin/xinference-entrypoint.sh:ro" \
      -e "HF_ENDPOINT=${HF_ENDPOINT}" \
      -e "XINFERENCE_MODEL_UID=${XINFERENCE_MODEL_UID}" \
      -e "XINFERENCE_MODEL_NAME=${XINFERENCE_MODEL_NAME}" \
      -e "XINFERENCE_RERANK_ENABLED=${XINFERENCE_RERANK_ENABLED}" \
      -e "XINFERENCE_RERANK_MODEL_UID=${XINFERENCE_RERANK_MODEL_UID}" \
      -e "XINFERENCE_RERANK_MODEL_NAME=${XINFERENCE_RERANK_MODEL_NAME}" \
      --entrypoint bash \
      "$XINFERENCE_IMAGE" \
      /usr/local/bin/xinference-entrypoint.sh >/dev/null
  else
    log "entrypoint script not found (or disabled), falling back to plain xinference-local (container restarts won't auto-load the model)"
    docker run -d \
      --name "$XINFERENCE_CONTAINER_NAME" \
      --restart unless-stopped \
      -p "0.0.0.0:${XINFERENCE_HOST_PORT}:9997" \
      -v "${XINFERENCE_DATA_VOLUME}:/root/.xinference" \
      -v "${XINFERENCE_CACHE_VOLUME}:/root/.cache/huggingface" \
      -e "HF_ENDPOINT=${HF_ENDPOINT}" \
      "$XINFERENCE_IMAGE" \
      xinference-local -H 0.0.0.0 >/dev/null
  fi

  maybe_connect_network
}

wait_xinference_ready() {
  local attempts="${1:-120}"
  log "waiting for xinference API to be ready (attempts=${attempts})"
  for _ in $(seq 1 "$attempts"); do
    if docker exec -i "$XINFERENCE_CONTAINER_NAME" python - <<'PY' >/dev/null 2>&1; then
import urllib.request
urllib.request.urlopen("http://127.0.0.1:9997/status", timeout=2).read()
PY
      return 0
    fi
    sleep 1
  done
  log "xinference API not ready; recent logs:"
  docker logs --tail 80 "$XINFERENCE_CONTAINER_NAME" >&2 || true
  exit 1
}

rerank_enabled() {
  local v="${XINFERENCE_RERANK_ENABLED:-1}"
  v="${v,,}"
  [[ "$v" != "0" && "$v" != "false" && "$v" != "no" && -n "$v" ]]
}

wait_model_uid_ready() {
  local model_uid="$1"
  local attempts="${2:-1800}" # seconds
  log "waiting for model to be READY: ${model_uid} (timeout=${attempts}s)"
  for i in $(seq 1 "$attempts"); do
    if docker exec -i \
      -e "WHARTTEST_MODEL_UID=${model_uid}" \
      "$XINFERENCE_CONTAINER_NAME" \
      python - <<'PY' >/dev/null 2>&1; then
import json
import os
import urllib.request

uid = os.environ["WHARTTEST_MODEL_UID"]
data = json.loads(urllib.request.urlopen("http://127.0.0.1:9997/v1/models/instances", timeout=2).read())
inst = next((x for x in data if x.get("model_uid") == uid), None)
if inst and inst.get("status") == "READY":
    raise SystemExit(0)
raise SystemExit(1)
PY
      return 0
    fi
    sleep 1
    if (( i % 30 == 0 )); then
      log "still waiting for model... (${i}/${attempts})"
    fi
  done
  log "model not ready after ${attempts}s; recent logs:"
  docker logs --tail 120 "$XINFERENCE_CONTAINER_NAME" >&2 || true
  exit 1
}

smoke_test_embeddings() {
  log "smoke testing embeddings API (text + image) (${XINFERENCE_MODEL_UID})"
  docker exec -i \
    -e "XINFERENCE_MODEL_UID=${XINFERENCE_MODEL_UID}" \
    "$XINFERENCE_CONTAINER_NAME" \
    python - <<'PY'
import json
import os
import urllib.request

MODEL_UID = os.environ["XINFERENCE_MODEL_UID"]
BASE = "http://127.0.0.1:9997"

def request(method: str, path: str, body=None, timeout=30):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def post_json(path: str, body):
    return json.loads(request("POST", path, body, timeout=300))

emb = post_json("/v1/embeddings", {"model": MODEL_UID, "input": "ping"})
print("TEXT_EMBEDDING_OK", len(emb["data"][0]["embedding"]))

from PIL import Image

image_path = "/tmp/wharttest-qwen3vl-smoke.png"
Image.new("RGB", (32, 32), (255, 0, 0)).save(image_path)
emb_img = post_json(
    "/v1/embeddings",
    {"model": MODEL_UID, "input": [{"image": image_path, "text": "a red square"}]},
)
print("IMAGE_EMBEDDING_OK", len(emb_img["data"][0]["embedding"]))
PY
}

smoke_test_reranker() {
  if ! rerank_enabled; then
    return 0
  fi
  log "smoke testing rerank API (${XINFERENCE_RERANK_MODEL_UID})"
  docker exec -i \
    -e "XINFERENCE_RERANK_MODEL_UID=${XINFERENCE_RERANK_MODEL_UID}" \
    "$XINFERENCE_CONTAINER_NAME" \
    python - <<'PY'
import json
import os
import urllib.request

MODEL_UID = os.environ["XINFERENCE_RERANK_MODEL_UID"]
BASE = "http://127.0.0.1:9997"

def request(method: str, path: str, body=None, timeout=30):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def post_json(path: str, body):
    return json.loads(request("POST", path, body, timeout=300))

resp = post_json(
    "/v1/rerank",
    {
        "model": MODEL_UID,
        "query": "what is xinference",
        "documents": ["xinference is a model serving framework", "postgres is a database"],
        "top_n": 2,
    },
)
results = resp.get("results") or []
print("RERANK_OK", len(results))
PY
}

patch_qwen3vl_loader() {
  log "patching xinference dynamic loader for Qwen3-VL (idempotent)"
  docker exec -i "$XINFERENCE_CONTAINER_NAME" python - <<'PY'
import pathlib
import re
import sys

import xinference.model.embedding.sentence_transformers.core as st_core

path = pathlib.Path(st_core.__file__)
text = path.read_text(encoding="utf-8").splitlines()

already = any("sys.modules[spec.name]" in line for line in text)
if already:
    print("ALREADY")
    raise SystemExit(0)

# Ensure `import sys` exists (needed for sys.modules injection).
has_import_sys = any(re.match(r"^\s*import\s+sys\s*$", line) for line in text)
if not has_import_sys:
    inserted = False
    for i, line in enumerate(text):
        if re.match(r"^\s*import\s+os\s*$", line):
            text.insert(i + 1, "import sys")
            inserted = True
            break
    if not inserted:
        # Best-effort fallback: insert after first import line.
        for i, line in enumerate(text):
            if re.match(r"^\s*import\s+", line):
                text.insert(i + 1, "import sys")
                inserted = True
                break
    if not inserted:
        print(f"ERROR: cannot find insertion point for 'import sys' in {path}", file=sys.stderr)
        raise SystemExit(2)

# Insert `sys.modules[spec.name] = module` before `exec_module`.
patched = False
for i, line in enumerate(text):
    if "module = importlib.util.module_from_spec(spec)" in line:
        indent = re.match(r"^(\s*)", line).group(1)
        for j in range(i + 1, min(i + 8, len(text))):
            if "spec.loader.exec_module(module)" in text[j]:
                text.insert(j, f"{indent}sys.modules[spec.name] = module")
                patched = True
                break
        if patched:
            break

if not patched:
    print(f"ERROR: cannot find exec_module block to patch in {path}", file=sys.stderr)
    raise SystemExit(3)

path.write_text("\n".join(text) + "\n", encoding="utf-8")
print("PATCHED")
PY
}

restart_container_if_patched() {
  local patch_state
  patch_state="$(patch_qwen3vl_loader | tail -n 1)"
  if [[ "$patch_state" == "PATCHED" ]]; then
    log "restart container to apply patch"
    docker restart "$XINFERENCE_CONTAINER_NAME" >/dev/null
    wait_xinference_ready 180
  else
    log "patch already present; no restart needed"
  fi
}

launch_models() {
  log "launching models: ${XINFERENCE_MODEL_UID} (${XINFERENCE_MODEL_NAME}) + ${XINFERENCE_RERANK_MODEL_UID} (${XINFERENCE_RERANK_MODEL_NAME})"
  docker exec -i \
    -e "XINFERENCE_MODEL_UID=${XINFERENCE_MODEL_UID}" \
    -e "XINFERENCE_MODEL_NAME=${XINFERENCE_MODEL_NAME}" \
    -e "XINFERENCE_RERANK_ENABLED=${XINFERENCE_RERANK_ENABLED}" \
    -e "XINFERENCE_RERANK_MODEL_UID=${XINFERENCE_RERANK_MODEL_UID}" \
    -e "XINFERENCE_RERANK_MODEL_NAME=${XINFERENCE_RERANK_MODEL_NAME}" \
    "$XINFERENCE_CONTAINER_NAME" \
    python - <<'PY'
import json
import time
import urllib.request
import urllib.error
import sys
import os

BASE = "http://127.0.0.1:9997"
EMB_UID = os.environ["XINFERENCE_MODEL_UID"]
EMB_NAME = os.environ["XINFERENCE_MODEL_NAME"]

RERANK_ENABLED = os.environ.get("XINFERENCE_RERANK_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
RERANK_UID = os.environ.get("XINFERENCE_RERANK_MODEL_UID", "Qwen3-VL-Reranker-2B")
RERANK_NAME = os.environ.get("XINFERENCE_RERANK_MODEL_NAME", "Qwen3-VL-Reranker-2B")

def request(method: str, path: str, body=None, timeout=30):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def get_json(path: str):
    return json.loads(request("GET", path, None, timeout=30))

def post_json(path: str, body):
    return json.loads(request("POST", path, body, timeout=300))

def ensure_model_ready(uid: str, body: dict):
    models = get_json("/v1/models").get("data", [])
    if any(m.get("id") == uid for m in models):
        print("ALREADY_READY_OR_RUNNING", uid)
    else:
        post_json("/v1/models?wait_ready=false", body)
        print("LAUNCHED", uid)

    deadline = time.time() + 1800  # 30 min
    last_status = None
    while time.time() < deadline:
        instances = get_json("/v1/models/instances")
        inst = next((x for x in instances if x.get("model_uid") == uid), None)
        if not inst:
            time.sleep(2)
            continue
        status = inst.get("status")
        if status != last_status:
            print("STATUS", uid, status)
            last_status = status
        if status == "READY":
            return
        if status == "ERROR":
            replica = (inst.get("replica_statuses") or [{}])[0]
            err = replica.get("error_message") or "unknown error"
            print(err, file=sys.stderr)
            raise SystemExit(1)
        time.sleep(5)
    print(f"ERROR: timed out waiting for READY ({uid})", file=sys.stderr)
    raise SystemExit(1)

ensure_model_ready(
    EMB_UID,
    {
        "model_uid": EMB_UID,
        "model_name": EMB_NAME,
        "model_type": "embedding",
        "model_format": "pytorch",
        "quantization": "none",
        "model_engine": "sentence_transformers",
    },
)

# Smoke test: text embedding
emb = post_json("/v1/embeddings", {"model": EMB_UID, "input": "ping"})
dim = len(emb["data"][0]["embedding"])
print("EMBEDDING_OK", dim)

# Smoke test: image embedding
try:
    from PIL import Image

    image_path = "/tmp/wharttest-qwen3vl-smoke.png"
    Image.new("RGB", (32, 32), (255, 0, 0)).save(image_path)
    emb_img = post_json(
        "/v1/embeddings",
        {"model": EMB_UID, "input": [{"image": image_path, "text": "a red square"}]},
    )
    dim_img = len(emb_img["data"][0]["embedding"])
    print("IMAGE_EMBEDDING_OK", dim_img)
except Exception as e:
    print(f"IMAGE_EMBEDDING_FAILED: {e}", file=sys.stderr)
    raise

if RERANK_ENABLED:
    rerank_body = {"model_uid": RERANK_UID, "model_name": RERANK_NAME, "model_type": "rerank"}
    if (RERANK_NAME or "").lower() == "qwen3-vl-reranker-2b" or (RERANK_UID or "").lower() == "qwen3-vl-reranker-2b":
        rerank_body.update(
            {
                "enable_virtual_env": True,
                "virtual_env_packages": [
                    "transformers>=5.1.0",
                    "qwen-vl-utils>=0.0.14",
                ],
            }
        )
    ensure_model_ready(RERANK_UID, rerank_body)
    rerank = post_json(
        "/v1/rerank",
        {
            "model": RERANK_UID,
            "query": "what is xinference",
            "documents": ["xinference is a model serving framework", "postgres is a database"],
            "top_n": 2,
        },
    )
    results = rerank.get("results") or []
    if not results:
        print("RERANK_EMPTY_RESULTS", file=sys.stderr)
        raise SystemExit(1)
    print("RERANK_OK", len(results))
PY
}

print_result() {
  local port_mapping
  port_mapping="$(docker port "$XINFERENCE_CONTAINER_NAME" 9997/tcp 2>/dev/null | head -n 1 || true)"
  if [[ -n "$port_mapping" ]]; then
    local host_port="${port_mapping##*:}"
    if rerank_enabled; then
      log "ready: http://localhost:${host_port}/v1/embeddings (model=${XINFERENCE_MODEL_UID}) + /v1/rerank (model=${XINFERENCE_RERANK_MODEL_UID})"
    else
      log "ready: http://localhost:${host_port}/v1/embeddings (model=${XINFERENCE_MODEL_UID})"
    fi
  else
    log "ready (model=${XINFERENCE_MODEL_UID}); container port 9997 is not published to host"
  fi
}

main() {
  require_cmd docker

  ensure_container
  wait_xinference_ready 180
  if container_uses_entrypoint_script; then
    log "container is using wharttest entrypoint; entrypoint will handle patch + model load"
    wait_model_uid_ready "${XINFERENCE_MODEL_UID}" 1800
    smoke_test_embeddings
    if rerank_enabled; then
      wait_model_uid_ready "${XINFERENCE_RERANK_MODEL_UID}" 1800
      smoke_test_reranker
    fi
  else
    restart_container_if_patched
    launch_models
  fi
  print_result
}

main "$@"

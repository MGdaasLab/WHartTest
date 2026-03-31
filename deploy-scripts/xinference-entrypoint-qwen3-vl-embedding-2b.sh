#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '%s\n' "[xinference-entrypoint] $*" >&2
}

XINFERENCE_HOST="${XINFERENCE_HOST:-0.0.0.0}"
XINFERENCE_PORT="${XINFERENCE_PORT:-9997}"
XINFERENCE_BASE_URL="${XINFERENCE_BASE_URL:-http://127.0.0.1:${XINFERENCE_PORT}}"

XINFERENCE_MODEL_UID="${XINFERENCE_MODEL_UID:-qwen3-vl-emb-2b}"
XINFERENCE_MODEL_NAME="${XINFERENCE_MODEL_NAME:-Qwen3-VL-Embedding-2B}"

XINFERENCE_RERANK_ENABLED="${XINFERENCE_RERANK_ENABLED:-1}"
XINFERENCE_RERANK_MODEL_UID="${XINFERENCE_RERANK_MODEL_UID:-Qwen3-VL-Reranker-2B}"
XINFERENCE_RERANK_MODEL_NAME="${XINFERENCE_RERANK_MODEL_NAME:-Qwen3-VL-Reranker-2B}"

patch_qwen3vl_loader() {
  python - <<'PY'
import pathlib
import re
import sys

import xinference.model.embedding.sentence_transformers.core as st_core

path = pathlib.Path(st_core.__file__)
text = path.read_text(encoding="utf-8").splitlines()

already = any("sys.modules[spec.name] = module" in line for line in text)
if already:
    print("PATCH_ALREADY_PRESENT")
    raise SystemExit(0)

# Ensure `import sys` exists.
has_import_sys = any(re.match(r"^\s*import\s+sys\s*$", line) for line in text)
if not has_import_sys:
    inserted = False
    for i, line in enumerate(text):
        if re.match(r"^\s*import\s+os\s*$", line):
            text.insert(i + 1, "import sys")
            inserted = True
            break
    if not inserted:
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

wait_xinference_ready() {
  local attempts="${1:-180}"
  for i in $(seq 1 "$attempts"); do
    if python - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("${XINFERENCE_BASE_URL}/status", timeout=2).read()
PY
    then
      return 0
    fi
    sleep 1
    if (( i % 30 == 0 )); then
      log "waiting for xinference API... (${i}/${attempts})"
    fi
  done
  log "xinference API not ready after ${attempts}s"
  return 1
}

rerank_enabled() {
  local v="${XINFERENCE_RERANK_ENABLED:-1}"
  v="${v,,}"
  [[ "$v" != "0" && "$v" != "false" && "$v" != "no" && -n "$v" ]]
}

launch_models() {
  python - <<'PY'
import json
import os
import time
import urllib.request
import sys

BASE_URL = os.environ.get("XINFERENCE_BASE_URL", "http://127.0.0.1:9997")
EMB_MODEL_UID = os.environ.get("XINFERENCE_MODEL_UID", "qwen3-vl-emb-2b")
EMB_MODEL_NAME = os.environ.get("XINFERENCE_MODEL_NAME", "Qwen3-VL-Embedding-2B")

RERANK_ENABLED = os.environ.get("XINFERENCE_RERANK_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
RERANK_MODEL_UID = os.environ.get("XINFERENCE_RERANK_MODEL_UID", "Qwen3-VL-Reranker-2B")
RERANK_MODEL_NAME = os.environ.get("XINFERENCE_RERANK_MODEL_NAME", "Qwen3-VL-Reranker-2B")

def request(method: str, path: str, body=None, timeout=30):
    url = BASE_URL + path
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

def ensure_model_ready(model_uid: str, create_body: dict):
    models = get_json("/v1/models").get("data", [])
    if any(m.get("id") == model_uid for m in models):
        print("MODEL_ALREADY_RUNNING", model_uid)
    else:
        post_json("/v1/models?wait_ready=false", create_body)
        print("MODEL_LAUNCHED", model_uid)

    deadline = time.time() + 1800  # 30 min
    while time.time() < deadline:
        instances = get_json("/v1/models/instances")
        inst = next((x for x in instances if x.get("model_uid") == model_uid), None)
        if not inst:
            time.sleep(2)
            continue
        status = inst.get("status")
        if status == "READY":
            return
        if status == "ERROR":
            replica = (inst.get("replica_statuses") or [{}])[0]
            err = replica.get("error_message") or "unknown error"
            print(err, file=sys.stderr)
            raise SystemExit(1)
        time.sleep(5)
    print(f"ERROR: timed out waiting for READY ({model_uid})", file=sys.stderr)
    raise SystemExit(1)

ensure_model_ready(
    EMB_MODEL_UID,
    {
        "model_uid": EMB_MODEL_UID,
        "model_name": EMB_MODEL_NAME,
        "model_type": "embedding",
        "model_format": "pytorch",
        "quantization": "none",
        "model_engine": "sentence_transformers",
    },
)

# Smoke tests
emb = post_json("/v1/embeddings", {"model": EMB_MODEL_UID, "input": "ping"})
dim = len(emb["data"][0]["embedding"])
print("TEXT_EMBEDDING_OK", dim)

from PIL import Image

image_path = "/tmp/wharttest-qwen3vl-smoke.png"
Image.new("RGB", (32, 32), (255, 0, 0)).save(image_path)
emb_img = post_json(
    "/v1/embeddings",
    {"model": EMB_MODEL_UID, "input": [{"image": image_path, "text": "a red square"}]},
)
dim_img = len(emb_img["data"][0]["embedding"])
print("IMAGE_EMBEDDING_OK", dim_img)

if RERANK_ENABLED:
    rerank_body = {
        "model_uid": RERANK_MODEL_UID,
        "model_name": RERANK_MODEL_NAME,
        "model_type": "rerank",
    }
    # Qwen3-VL-Reranker requires a newer `transformers` that includes
    # `Qwen3VLForConditionalGeneration`.
    if (RERANK_MODEL_NAME or "").lower() == "qwen3-vl-reranker-2b" or (RERANK_MODEL_UID or "").lower() == "qwen3-vl-reranker-2b":
        rerank_body.update(
            {
                "enable_virtual_env": True,
                "virtual_env_packages": [
                    "transformers>=5.1.0",
                    "qwen-vl-utils>=0.0.14",
                ],
            }
        )
    ensure_model_ready(RERANK_MODEL_UID, rerank_body)

    rerank = post_json(
        "/v1/rerank",
        {
            "model": RERANK_MODEL_UID,
            "query": "what is xinference",
            "documents": ["xinference is a model serving framework", "postgres is a database"],
            "top_n": 2,
        },
    )
    results = rerank.get("results") or []
    if not results:
        print("ERROR: rerank returned empty results", file=sys.stderr)
        raise SystemExit(1)
    print("RERANK_OK", len(results))
PY
}

main() {
  log "starting xinference-local (${XINFERENCE_HOST}:${XINFERENCE_PORT})"

  export XINFERENCE_BASE_URL
  export XINFERENCE_MODEL_UID
  export XINFERENCE_MODEL_NAME
  export XINFERENCE_RERANK_ENABLED
  export XINFERENCE_RERANK_MODEL_UID
  export XINFERENCE_RERANK_MODEL_NAME

  # Patch before starting the server to avoid Qwen3-VL dynamic import crash.
  local patch_state
  patch_state="$(patch_qwen3vl_loader | tail -n 1 || true)"
  log "patch state: ${patch_state:-unknown}"

  xinference-local -H "${XINFERENCE_HOST}" -p "${XINFERENCE_PORT}" &
  local xinference_pid=$!

  trap 'log "stopping xinference-local"; kill "${xinference_pid}" 2>/dev/null || true; wait "${xinference_pid}" 2>/dev/null || true' INT TERM

  wait_xinference_ready 180
  if rerank_enabled; then
    log "xinference API ready; launching models: ${XINFERENCE_MODEL_UID} + ${XINFERENCE_RERANK_MODEL_UID}"
  else
    log "xinference API ready; launching model: ${XINFERENCE_MODEL_UID} (rerank disabled)"
  fi
  launch_models
  if rerank_enabled; then
    log "models READY: ${XINFERENCE_MODEL_UID} (${XINFERENCE_MODEL_NAME}) + ${XINFERENCE_RERANK_MODEL_UID} (${XINFERENCE_RERANK_MODEL_NAME})"
  else
    log "model READY: ${XINFERENCE_MODEL_UID} (${XINFERENCE_MODEL_NAME})"
  fi

  wait "${xinference_pid}"
}

main "$@"

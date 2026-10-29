#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.demo"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
FRONTEND_LOG="$RUNTIME_DIR/frontend.log"
NEO4J_LOG="$RUNTIME_DIR/neo4j.log"
BACKEND_PID=""
FRONTEND_PID=""
NEO4J_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$NEO4J_PID" ]]; then
    kill "$NEO4J_PID" 2>/dev/null || true
    wait "$NEO4J_PID" 2>/dev/null || true
  fi
  if [[ $status -ne 0 ]]; then
    echo
    echo "演示启动失败。后端日志: $BACKEND_LOG"
    echo "前端日志: $FRONTEND_LOG"
    echo "Neo4j 日志: $NEO4J_LOG"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1" >&2
    exit 1
  fi
}

wait_for_url() {
  local url=$1
  local label=$2
  local attempts=${3:-90}
  local index
  for ((index = 1; index <= attempts; index++)); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "$label 未在 ${attempts} 秒内就绪: $url" >&2
  return 1
}

require_command curl
require_command node
require_command npm

DOCKER_CMD=(docker)
DOCKER_AVAILABLE="false"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER_AVAILABLE="true"
elif [[ "${ONTOFORGE_DOCKER_USE_SUDO:-false}" == "true" ]]; then
  require_command sudo
  DOCKER_CMD=(sudo docker)
  if "${DOCKER_CMD[@]}" info >/dev/null 2>&1; then
    DOCKER_AVAILABLE="true"
  fi
fi

PORTABLE_RUNTIME_ROOT="${ONTOFORGE_PORTABLE_RUNTIME_ROOT:-$HOME/.local/ontoforge-runtime}"
PORTABLE_JAVA_HOME="$PORTABLE_RUNTIME_ROOT/jre"
PORTABLE_NEO4J_ARCHIVE="$PORTABLE_RUNTIME_ROOT/neo4j.tar.gz"
PORTABLE_NEO4J_HOME="$RUNTIME_DIR/neo4j-runtime"
PORTABLE_AVAILABLE="false"
if [[ -x "$PORTABLE_JAVA_HOME/bin/java" && -r "$PORTABLE_NEO4J_ARCHIVE" ]]; then
  PORTABLE_AVAILABLE="true"
fi

if [[ "$DOCKER_AVAILABLE" != "true" && "$PORTABLE_AVAILABLE" != "true" ]]; then
  echo "Docker daemon 不可访问，且未找到便携 Neo4j 运行时。" >&2
  echo "期望路径: $PORTABLE_NEO4J_ARCHIVE 和 $PORTABLE_JAVA_HOME/bin/java" >&2
  exit 1
fi

PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "缺少后端虚拟环境。请先按 LOCAL_SETUP.md 安装 backend/.venv。" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "缺少前端依赖。请先在 frontend 目录运行 npm install。" >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"

# The automated demo uses isolated ports, user data and Neo4j volumes. Loading
# mock data therefore never clears the developer's normal OntoForge database.
export ONTOFORGE_VOLUME_PREFIX="ontoforge_demo"
export NEO4J_HTTP_PORT="${ONTOFORGE_DEMO_NEO4J_HTTP_PORT:-17474}"
export NEO4J_BOLT_PORT="${ONTOFORGE_DEMO_NEO4J_BOLT_PORT:-17687}"
export NEO4J_URI="bolt://127.0.0.1:${NEO4J_BOLT_PORT}"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="${ONTOFORGE_DEMO_NEO4J_PASSWORD:-demo-password}"
export ONTOFORGE_USER_STORE="$RUNTIME_DIR/users.json"
export ONTOFORGE_SEED_DEMO_USER="true"
export ONTOFORGE_DEMO_PASSWORD="${ONTOFORGE_DEMO_PASSWORD:-demo1234}"

BACKEND_PORT="${ONTOFORGE_DEMO_BACKEND_PORT:-18765}"
FRONTEND_PORT="${ONTOFORGE_DEMO_FRONTEND_PORT:-15173}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
export VITE_ONTOFORGE_BACKEND_URL="$BACKEND_URL"

echo "[1/5] 启动隔离的 Neo4j 演示数据库..."
if [[ "$DOCKER_AVAILABLE" == "true" && "${ONTOFORGE_DOCKER_USE_SUDO:-false}" == "true" ]]; then
  sudo env \
    ONTOFORGE_VOLUME_PREFIX="$ONTOFORGE_VOLUME_PREFIX" \
    NEO4J_HTTP_PORT="$NEO4J_HTTP_PORT" \
    NEO4J_BOLT_PORT="$NEO4J_BOLT_PORT" \
    NEO4J_PASSWORD="$NEO4J_PASSWORD" \
    docker compose -p ontoforge-demo -f "$ROOT_DIR/compose.yaml" up -d neo4j
elif [[ "$DOCKER_AVAILABLE" == "true" ]]; then
  docker compose -p ontoforge-demo -f "$ROOT_DIR/compose.yaml" up -d neo4j
else
  echo "Docker 不可访问，使用便携 Neo4j: $PORTABLE_NEO4J_ARCHIVE"
  if [[ ! -x "$PORTABLE_NEO4J_HOME/bin/neo4j" ]]; then
    mkdir -p "$PORTABLE_NEO4J_HOME"
    tar -xzf "$PORTABLE_NEO4J_ARCHIVE" --strip-components=1 -C "$PORTABLE_NEO4J_HOME"
  fi

  export JAVA_HOME="$PORTABLE_JAVA_HOME"
  export NEO4J_HOME="$PORTABLE_NEO4J_HOME"
  PORTABLE_CONFIG="$PORTABLE_NEO4J_HOME/conf/neo4j.conf"
  if ! grep -q 'OntoForge portable demo settings' "$PORTABLE_CONFIG"; then
    {
      echo
      echo '# OntoForge portable demo settings'
      echo 'server.default_listen_address=127.0.0.1'
      echo "server.bolt.listen_address=127.0.0.1:${NEO4J_BOLT_PORT}"
      echo "server.http.listen_address=127.0.0.1:${NEO4J_HTTP_PORT}"
      echo 'server.memory.heap.initial_size=256m'
      echo 'server.memory.heap.max_size=512m'
      echo 'server.memory.pagecache.size=256m'
      echo 'server.jvm.additional=-Dio.netty.transport.noNative=true'
    } >>"$PORTABLE_CONFIG"
  fi

  if [[ ! -f "$PORTABLE_NEO4J_HOME/data/dbms/auth.ini" ]]; then
    "$PORTABLE_NEO4J_HOME/bin/neo4j-admin" dbms set-initial-password "$NEO4J_PASSWORD"
  fi
  "$PORTABLE_NEO4J_HOME/bin/neo4j" console >"$NEO4J_LOG" 2>&1 &
  NEO4J_PID=$!
fi

echo "[2/5] 等待数据库并准备演示账号..."
for ((attempt = 1; attempt <= 90; attempt++)); do
  if "$PYTHON_BIN" -c \
    'from neo4j import GraphDatabase; import os; d=GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])); d.verify_connectivity(); d.close()' \
    >/dev/null 2>&1; then
    break
  fi
  if [[ $attempt -eq 90 ]]; then
    echo "Neo4j 未在 90 秒内就绪。" >&2
    exit 1
  fi
  sleep 1
done

(
  cd "$ROOT_DIR"
  "$PYTHON_BIN" -c 'from backend.services.auth_service import ensure_demo_user; ensure_demo_user()'
  "$PYTHON_BIN" -m backend.scripts.load_mock_data
)

echo "[3/5] 启动后端..."
(
  cd "$ROOT_DIR"
  exec "$PYTHON_BIN" -m uvicorn backend.server.app:app --host 127.0.0.1 --port "$BACKEND_PORT"
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
wait_for_url "$BACKEND_URL/health" "后端"

echo "[4/5] 启动前端..."
(
  cd "$ROOT_DIR/frontend"
  exec npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
wait_for_url "$FRONTEND_URL" "前端"

echo "[5/5] 打开浏览器并自动演示..."
DEMO_ARGS=(
  "--url=$FRONTEND_URL"
  "--username=demo"
  "--password=$ONTOFORGE_DEMO_PASSWORD"
  "--slow=${ONTOFORGE_DEMO_STEP_DELAY_MS:-1800}"
  "--hold=${ONTOFORGE_DEMO_FINAL_HOLD_MS:-5000}"
)
if [[ "${ONTOFORGE_DEMO_HEADLESS:-false}" == "true" ]]; then
  DEMO_ARGS+=("--headless")
fi

node "$ROOT_DIR/frontend/scripts/ui_demo.mjs" "${DEMO_ARGS[@]}"
if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
  echo "演示完成。Neo4j 演示容器保留运行，应用进程将自动关闭。"
else
  echo "演示完成。便携 Neo4j 和应用进程将自动关闭。"
fi

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
TEST_DB_STARTED="false"
TEST_NEO4J_HTTP_PORT="${ONTOFORGE_TEST_NEO4J_HTTP_PORT:-27474}"
TEST_NEO4J_BOLT_PORT="${ONTOFORGE_TEST_NEO4J_BOLT_PORT:-27687}"
TEST_NEO4J_PASSWORD="${ONTOFORGE_TEST_NEO4J_PASSWORD:-test-password}"

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ "$TEST_DB_STARTED" == "true" ]]; then
    sudo env \
      ONTOFORGE_VOLUME_PREFIX=ontoforge_test \
      NEO4J_HTTP_PORT="$TEST_NEO4J_HTTP_PORT" \
      NEO4J_BOLT_PORT="$TEST_NEO4J_BOLT_PORT" \
      NEO4J_PASSWORD="$TEST_NEO4J_PASSWORD" \
      docker compose -p ontoforge-test -f "$ROOT_DIR/compose.yaml" stop neo4j \
      >/dev/null 2>&1 || true
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

require_command docker
require_command node
require_command npm

DOCKER_CMD=(docker)
if [[ "${ONTOFORGE_DOCKER_USE_SUDO:-false}" == "true" ]]; then
  require_command sudo
  DOCKER_CMD=(sudo docker)
fi

if ! "${DOCKER_CMD[@]}" info >/dev/null 2>&1; then
  echo "Docker daemon 未运行，无法执行 Neo4j 集成测试和 UI 端到端演示。" >&2
  echo "若只是权限不足，请先运行 sudo -v，再使用 ONTOFORGE_DOCKER_USE_SUDO=true。" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "缺少 backend/.venv，请先按 LOCAL_SETUP.md 安装后端依赖。" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "缺少 frontend/node_modules，请先在 frontend 目录运行 npm install。" >&2
  exit 1
fi

if [[ "${ONTOFORGE_DOCKER_USE_SUDO:-false}" == "true" ]]; then
  echo "[0/4] 以 sudo 启动隔离的 Neo4j 集成测试数据库..."
  sudo env \
    ONTOFORGE_VOLUME_PREFIX=ontoforge_test \
    NEO4J_HTTP_PORT="$TEST_NEO4J_HTTP_PORT" \
    NEO4J_BOLT_PORT="$TEST_NEO4J_BOLT_PORT" \
    NEO4J_PASSWORD="$TEST_NEO4J_PASSWORD" \
    docker compose -p ontoforge-test -f "$ROOT_DIR/compose.yaml" up -d neo4j
  TEST_DB_STARTED="true"

  for ((attempt = 1; attempt <= 90; attempt++)); do
    if NEO4J_URI="bolt://127.0.0.1:${TEST_NEO4J_BOLT_PORT}" \
      NEO4J_USER=neo4j \
      NEO4J_PASSWORD="$TEST_NEO4J_PASSWORD" \
      "$PYTHON_BIN" -c \
      'from neo4j import GraphDatabase; import os; d=GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])); d.verify_connectivity(); d.close()' \
      >/dev/null 2>&1; then
      break
    fi
    if [[ $attempt -eq 90 ]]; then
      echo "Neo4j 集成测试数据库未在 90 秒内就绪。" >&2
      exit 1
    fi
    sleep 1
  done
fi

echo "[1/4] 后端单元、协议和强制 Neo4j 集成测试（含覆盖率）..."
(
  cd "$ROOT_DIR"
  if [[ "${ONTOFORGE_DOCKER_USE_SUDO:-false}" == "true" ]]; then
    ONTOFORGE_TEST_NEO4J_URI="bolt://127.0.0.1:${TEST_NEO4J_BOLT_PORT}" \
      NEO4J_USER=neo4j \
      NEO4J_PASSWORD="$TEST_NEO4J_PASSWORD" \
      ONTOFORGE_REQUIRE_INTEGRATION=true \
      "$PYTHON_BIN" -m pytest backend/tests
  else
    ONTOFORGE_REQUIRE_INTEGRATION=true "$PYTHON_BIN" -m pytest backend/tests
  fi
)

echo "[2/4] 前端 TypeScript 类型检查..."
(
  cd "$ROOT_DIR/frontend"
  npm run type-check
)

echo "[3/4] 前端 ESLint 和生产构建..."
(
  cd "$ROOT_DIR/frontend"
  npm run lint
  npm run build
)

echo "[4/4] 隔离数据库上的 Playwright UI 端到端演示..."
ONTOFORGE_DEMO_HEADLESS=true \
  ONTOFORGE_DOCKER_USE_SUDO="${ONTOFORGE_DOCKER_USE_SUDO:-false}" \
  "$ROOT_DIR/scripts/run_ui_demo.sh"

echo
echo "完整测试通过。UI 截图位于: $ROOT_DIR/frontend/demo-screenshots"
echo "演示日志位于: $ROOT_DIR/.demo"

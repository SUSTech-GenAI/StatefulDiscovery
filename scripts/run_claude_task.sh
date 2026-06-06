#!/usr/bin/env bash
set -euo pipefail

# Run the Claude Code discovery agent in a Docker container.
#
# Usage:
#   ./scripts/run_claude_task.sh <data_path> [output_path] [--dashboard <port>]
#
# Examples:
#   ./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration
#   ./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration discovery_output/discoverybench/nls_incarceration
#   ./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration --dashboard 8050

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-stateful-discovery-claude}"
LOG_ROOT="${DISCOVERY_LOG_ROOT:-${PROJECT_ROOT}/discovery_log}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

usage() {
    echo "Usage: $0 <data_path> [output_path] [--dashboard <port>]" >&2
}

status() {
    printf "\n[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

DATA_PATH=""
OUTPUT_PATH=""
DASHBOARD_PORT=""

while [ $# -gt 0 ]; do
    case "$1" in
        --dashboard)
            shift
            if [ $# -eq 0 ]; then
                echo "Error: --dashboard requires a port" >&2
                usage
                exit 1
            fi
            DASHBOARD_PORT="$1"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Error: unknown option: $1" >&2
            usage
            exit 1
            ;;
        *)
            if [ -z "$DATA_PATH" ]; then
                DATA_PATH="$1"
            elif [ -z "$OUTPUT_PATH" ]; then
                OUTPUT_PATH="$1"
            else
                echo "Error: too many positional arguments" >&2
                usage
                exit 1
            fi
            ;;
    esac
    shift
done

if [ -z "$DATA_PATH" ]; then
    usage
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found. Install Python 3 and ensure it is on PATH." >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker not found. Install and start Docker Desktop (macOS/Windows) or Docker Engine (Linux)." >&2
    exit 1
fi

DATA_PATH="$(cd "$(dirname "$DATA_PATH")" && pwd)/$(basename "$DATA_PATH")"

if [ ! -f "${DATA_PATH}/task_packet.json" ]; then
    echo "Error: ${DATA_PATH}/task_packet.json not found" >&2
    exit 1
fi

TASK_NAME="$(basename "${DATA_PATH}")"
BENCHMARK_NAME="$(basename "$(dirname "${DATA_PATH}")")"

if [ -z "$OUTPUT_PATH" ]; then
    OUTPUT_PATH="${PROJECT_ROOT}/discovery_output/${BENCHMARK_NAME}/${TASK_NAME}"
else
    OUTPUT_PATH="$(mkdir -p "$(dirname "$OUTPUT_PATH")" && cd "$(dirname "$OUTPUT_PATH")" && pwd)/$(basename "$OUTPUT_PATH")"
fi

LOG_ROOT="$(mkdir -p "$LOG_ROOT" && cd "$LOG_ROOT" && pwd)"
LOG_OUTPUT_PATH="${LOG_ROOT}/${BENCHMARK_NAME}/${TASK_NAME}"

CONFIG_ENV="${PROJECT_ROOT}/config.env"
if [ ! -f "$CONFIG_ENV" ]; then
    echo "Error: config.env not found. Copy config.env.example to config.env and fill it in." >&2
    exit 1
fi

set -a
# shellcheck source=/dev/null
source "$CONFIG_ENV"
set +a

for var in ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL; do
    if [ -z "${!var:-}" ]; then
        echo "Error: ${var} is empty in config.env" >&2
        exit 1
    fi
done

copy_task_files() {
    local src="$1" dest="$2"
    local rel_path src_file dest_file
    cp "${src}/task_packet.json" "$dest/"

    while IFS= read -r rel_path; do
        src_file="${src}/${rel_path}"
        dest_file="${dest}/${rel_path}"
        if [ ! -f "$src_file" ]; then
            echo "Error: dataset file listed in task_packet.json not found: ${src_file}" >&2
            exit 1
        fi
        mkdir -p "$(dirname "$dest_file")"
        cp -L "$src_file" "$dest_file"
    done < <(
        python3 - "$src/task_packet.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    packet = json.load(f)

for path in packet.get("dataset_paths", []):
    print(path)
PY
    )
}

RUN_DIR="${OUTPUT_PATH}/run_${TIMESTAMP}"
LOG_DIR="${LOG_OUTPUT_PATH}/run_${TIMESTAMP}"
status "Preparing run directory and copying task data..."
mkdir -p "$RUN_DIR" "$LOG_DIR"
copy_task_files "$DATA_PATH" "$RUN_DIR"
status "Task data prepared."

echo "=========================================="
echo "Discovery Agent Run (Claude Code)"
echo "=========================================="
echo "Data:   ${DATA_PATH}"
echo "Model:  ${ANTHROPIC_MODEL}"
echo "Output: ${RUN_DIR}"
echo "Log:    ${LOG_DIR}"
echo "Image:  ${IMAGE_NAME}"
echo "=========================================="

status "Building Docker image ${IMAGE_NAME}. Cached layers will be reused when available."
docker build --progress plain -t "${IMAGE_NAME}" \
    -f "${PROJECT_ROOT}/dockerfiles/Dockerfile.claude" \
    --network host \
    --build-arg HOST_UID="$(id -u)" \
    --build-arg http_proxy="${http_proxy:-${HTTP_PROXY:-}}" \
    --build-arg https_proxy="${https_proxy:-${HTTPS_PROXY:-}}" \
    "${PROJECT_ROOT}"
status "Docker image is ready."

DASHBOARD_PID=""
HEARTBEAT_PID=""
CONTAINER_NAME=""
cleanup() {
    if [ -n "$HEARTBEAT_PID" ]; then
        kill "$HEARTBEAT_PID" 2>/dev/null || true
    fi
    if [ -n "$DASHBOARD_PID" ]; then
        kill "$DASHBOARD_PID" 2>/dev/null || true
    fi
    if [ -n "$CONTAINER_NAME" ]; then
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [ -n "$DASHBOARD_PORT" ]; then
    if command -v lsof >/dev/null 2>&1; then
        kill $(lsof -ti:"$DASHBOARD_PORT") 2>/dev/null || true
    fi
    python3 "${PROJECT_ROOT}/dashboard/server.py" "$RUN_DIR" --port "$DASHBOARD_PORT" &
    DASHBOARD_PID=$!
    status "Dashboard started: http://localhost:${DASHBOARD_PORT}"
fi

CONTAINER_NAME="sd-$(basename "${OUTPUT_PATH}")-$$"
STREAM_FILE="${LOG_DIR}/stream.jsonl"
PROMPT="Read /workspace/run/task_packet.json and follow CLAUDE.md instructions to perform scientific discovery. Write all outputs to /workspace/run/"

status "Starting discovery agent in container ${CONTAINER_NAME}."
echo "Stream log: ${STREAM_FILE}"
echo "Follow log: tail -f ${STREAM_FILE}"
echo "The agent may run for a long time; a heartbeat will be printed every 60 seconds."

(
    while sleep 60; do
        stream_size="$(du -h "$STREAM_FILE" 2>/dev/null | cut -f1)"
        printf "\n[%s] Discovery agent is still running (stream log: %s).\n" \
            "$(date '+%Y-%m-%d %H:%M:%S')" "${stream_size:-0B}"
    done
) &
HEARTBEAT_PID=$!

if docker run --rm \
    --name "${CONTAINER_NAME}" \
    --network host \
    -v "${RUN_DIR}:/workspace/run" \
    -v "${LOG_DIR}:/workspace/log" \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
    -e ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL}" \
    -e ANTHROPIC_MODEL="${ANTHROPIC_MODEL}" \
    -e CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-}" \
    -e HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}" -e HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}" \
    -e http_proxy="${http_proxy:-${HTTP_PROXY:-}}" -e https_proxy="${https_proxy:-${HTTPS_PROXY:-}}" \
    "${IMAGE_NAME}" \
    claude --dangerously-skip-permissions --output-format stream-json --verbose \
        -p "$PROMPT" \
    > "${STREAM_FILE}" 2>&1; then
    status "Discovery agent exited successfully. Updating latest links..."
else
    exit_code=$?
    kill "$HEARTBEAT_PID" 2>/dev/null || true
    HEARTBEAT_PID=""
    status "Discovery agent failed with exit code ${exit_code}. Inspect ${STREAM_FILE}"
    exit "$exit_code"
fi

kill "$HEARTBEAT_PID" 2>/dev/null || true
HEARTBEAT_PID=""

ln -sfn "$(basename "$RUN_DIR")" "${OUTPUT_PATH}/latest"
ln -sfn "$(basename "$LOG_DIR")" "${LOG_OUTPUT_PATH}/latest"

echo ""
echo "=========================================="
echo "Done! Results in: ${RUN_DIR}"
echo "Stream log in: ${STREAM_FILE}"
echo "=========================================="

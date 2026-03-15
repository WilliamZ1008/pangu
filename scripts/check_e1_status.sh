#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/opt/pangu/pangu"
LATEST_LINK="${PROJECT_ROOT}/runtime/logs/e1_latest"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-ascend-pangu}"

if [ ! -e "${LATEST_LINK}" ]; then
    echo "No detached E1 run found."
    exit 1
fi

RUN_DIR="$(readlink -f "${LATEST_LINK}")"
RUN_NAME="$(basename "${RUN_DIR}")"

echo "Run directory: ${RUN_DIR}"
echo "Run name: ${RUN_NAME}"
echo

for label in service_1b service_7b e1; do
    pid_file="${RUN_DIR}/${label}.pid"
    if [ ! -f "${pid_file}" ]; then
        echo "${label}: pid file missing"
        continue
    fi

    pid="$(cat "${pid_file}")"
    if docker exec "${CONTAINER_NAME}" bash -lc "kill -0 ${pid}" >/dev/null 2>&1; then
        echo "${label}: RUNNING (pid ${pid})"
    else
        echo "${label}: STOPPED (pid ${pid})"
    fi
done

echo
for endpoint in "1B=http://127.0.0.1:1040/v1/models" "7B=http://127.0.0.1:8000/v1/models"; do
    name="${endpoint%%=*}"
    url="${endpoint#*=}"
    if docker exec "${CONTAINER_NAME}" bash -lc "curl -fsS -m 5 '${url}'" >/dev/null 2>&1; then
        echo "${name} endpoint: READY"
    else
        echo "${name} endpoint: NOT READY"
    fi
done

echo
echo "Completed summary files:"
ls -1 "${PROJECT_ROOT}/outputs/summaries/"*"${RUN_NAME}"*.json 2>/dev/null || echo "(none yet)"

echo
echo "Aggregate calibration summary:"
if [ -f "${PROJECT_ROOT}/outputs/summaries/${RUN_NAME}.json" ]; then
    echo "${PROJECT_ROOT}/outputs/summaries/${RUN_NAME}.json"
else
    echo "(not built yet)"
fi

echo
echo "Recent calibration log:"
tail -n 40 "${RUN_DIR}/e1.log" 2>/dev/null || echo "(no log output yet)"

#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/opt/pangu/pangu"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-ascend-pangu}"
RUN_PATH="${1:-${PROJECT_ROOT}/runtime/logs/paper_latest}"

if [ -L "${RUN_PATH}" ]; then
    RUN_DIR="$(readlink -f "${RUN_PATH}")"
else
    RUN_DIR="${RUN_PATH}"
fi

RUN_NAME="$(basename "${RUN_DIR}")"
STATUS_DIR="${RUN_DIR}/status"
PIPELINE_LOG="${RUN_DIR}/paper_pipeline.log"
PIPELINE_PID_FILE="${RUN_DIR}/paper_pipeline.pid"

echo "Run name: ${RUN_NAME}"
echo "Run directory: ${RUN_DIR}"

if [ -f "${STATUS_DIR}/pipeline_state.txt" ]; then
    echo "Pipeline state: $(cat "${STATUS_DIR}/pipeline_state.txt")"
fi

if [ -f "${STATUS_DIR}/current_stage.txt" ]; then
    echo "Current stage: $(cat "${STATUS_DIR}/current_stage.txt")"
fi

if [ -f "${PIPELINE_PID_FILE}" ]; then
    PIPELINE_PID="$(cat "${PIPELINE_PID_FILE}")"
    if docker exec "${CONTAINER_NAME}" bash -lc "kill -0 ${PIPELINE_PID}" >/dev/null 2>&1; then
        echo "Pipeline process: running (pid ${PIPELINE_PID})"
    else
        echo "Pipeline process: not running (pid ${PIPELINE_PID})"
    fi
fi

echo "Completed stages:"
if compgen -G "${STATUS_DIR}/*.done" >/dev/null; then
    for path in $(printf '%s\n' "${STATUS_DIR}"/*.done | sort); do
        basename "${path}" .done
    done
else
    echo "none"
fi

echo "Artifact counts:"
echo "predictions: $(find "${PROJECT_ROOT}/outputs/predictions" -maxdepth 1 -name "*__${RUN_NAME}__*.jsonl" | wc -l)"
echo "traces: $(find "${PROJECT_ROOT}/outputs/traces" -maxdepth 1 -name "*__${RUN_NAME}__*.jsonl" | wc -l)"
echo "summaries: $(find "${PROJECT_ROOT}/outputs/summaries" -maxdepth 1 -name "*__${RUN_NAME}__*.json" | wc -l)"
echo "results: $(find "${PROJECT_ROOT}/outputs/results" -maxdepth 1 -name "*${RUN_NAME}*" | wc -l)"

echo "Recent pipeline log:"
if [ -f "${PIPELINE_LOG}" ]; then
    tail -n 40 "${PIPELINE_LOG}"
else
    echo "missing ${PIPELINE_LOG}"
fi

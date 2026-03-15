#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/opt/pangu/pangu"
LOG_ROOT="${PROJECT_ROOT}/runtime/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_NAME="${RUN_NAME:-paper_detached_${TIMESTAMP}}"
RUN_DIR="${LOG_ROOT}/${RUN_NAME}"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-ascend-pangu}"
MAX_WORKERS="${MAX_WORKERS:-4}"
E1_SUMMARY="${E1_SUMMARY:-${PROJECT_ROOT}/outputs/summaries/e1_detached_20260315_103207.json}"
TEST_SAMPLE_FRACTION="${TEST_SAMPLE_FRACTION:-1.0}"
ABLATION_SAMPLE_FRACTION="${ABLATION_SAMPLE_FRACTION:-1.0}"
ENABLE_RULE_V2="${ENABLE_RULE_V2:-1}"

mkdir -p "${RUN_DIR}"
ln -sfn "${RUN_DIR}" "${LOG_ROOT}/paper_latest"

PIPELINE_LOG="${RUN_DIR}/paper_pipeline.log"
PIPELINE_PID_FILE="${RUN_DIR}/paper_pipeline.pid"
ONE_B_LOG="${RUN_DIR}/service_1b.log"
SEVEN_B_LOG="${RUN_DIR}/service_7b.log"
ONE_B_STATUS_FILE="${RUN_DIR}/service_1b.status"
SEVEN_B_STATUS_FILE="${RUN_DIR}/service_7b.status"

start_container_job() {
    local command="$1"
    docker exec "${CONTAINER_NAME}" bash -lc "${command}"
}

wait_for_endpoint() {
    local url="$1"
    local name="$2"
    local max_attempts="${3:-180}"
    local attempt=1

    while [ "${attempt}" -le "${max_attempts}" ]; do
        if docker exec "${CONTAINER_NAME}" bash -lc "curl -fsS -m 5 '${url}'" >/dev/null 2>&1; then
            echo "${name} is ready at ${url}"
            return 0
        fi
        sleep 5
        attempt=$((attempt + 1))
    done

    echo "Timed out waiting for ${name} at ${url}" >&2
    return 1
}

ensure_service() {
    local url="$1"
    local name="$2"
    local start_command="$3"
    local log_file="$4"
    local status_file="$5"

    if docker exec "${CONTAINER_NAME}" bash -lc "curl -fsS -m 5 '${url}'" >/dev/null 2>&1; then
        echo "reused_existing_endpoint" > "${status_file}"
        echo "${name} already healthy at ${url}"
        return 0
    fi

    start_container_job "cd ${PROJECT_ROOT} && nohup bash ${start_command} >'${log_file}' 2>&1 &"
    wait_for_endpoint "${url}" "${name}"
    echo "started_by_detached_runner" > "${status_file}"
}

ensure_service "http://127.0.0.1:1040/v1/models" "1B service" "scripts/run_service_1b.sh" "${ONE_B_LOG}" "${ONE_B_STATUS_FILE}"
ensure_service "http://127.0.0.1:8000/v1/models" "7B service" "scripts/run_service_7b.sh" "${SEVEN_B_LOG}" "${SEVEN_B_STATUS_FILE}"

start_container_job \
    "cd ${PROJECT_ROOT} && nohup env RUN_DIR='${RUN_DIR}' OUTPUT_TAG='${RUN_NAME}' MAX_WORKERS='${MAX_WORKERS}' E1_SUMMARY='${E1_SUMMARY}' TEST_SAMPLE_FRACTION='${TEST_SAMPLE_FRACTION}' ABLATION_SAMPLE_FRACTION='${ABLATION_SAMPLE_FRACTION}' ENABLE_RULE_V2='${ENABLE_RULE_V2}' bash scripts/run_paper_pipeline.sh >'${PIPELINE_LOG}' 2>&1 & echo \$! >'${PIPELINE_PID_FILE}'"

cat > "${RUN_DIR}/README.txt" <<EOF
Run name: ${RUN_NAME}
Run directory: ${RUN_DIR}
Container: ${CONTAINER_NAME}
Pipeline log: ${PIPELINE_LOG}
Pipeline pid file: ${PIPELINE_PID_FILE}
1B service status: ${ONE_B_STATUS_FILE}
7B service status: ${SEVEN_B_STATUS_FILE}
Output tag: ${RUN_NAME}
Test sample fraction: ${TEST_SAMPLE_FRACTION}
Ablation sample fraction: ${ABLATION_SAMPLE_FRACTION}
Include rule_v2: ${ENABLE_RULE_V2}

Reconnect command:
bash /opt/pangu/pangu/scripts/check_paper_status.sh
EOF

echo "Run name: ${RUN_NAME}"
echo "Run directory: ${RUN_DIR}"
echo "Pipeline pid: $(cat "${PIPELINE_PID_FILE}")"

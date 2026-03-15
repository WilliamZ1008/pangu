#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/opt/pangu/pangu"
LOG_ROOT="${PROJECT_ROOT}/runtime/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_NAME="${RUN_NAME:-e1_detached_${TIMESTAMP}}"
MAX_WORKERS="${MAX_WORKERS:-4}"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-ascend-pangu}"
RUN_DIR="${LOG_ROOT}/${RUN_NAME}"

mkdir -p "${RUN_DIR}"
ln -sfn "${RUN_DIR}" "${LOG_ROOT}/e1_latest"

ONE_B_LOG="${RUN_DIR}/service_1b.log"
SEVEN_B_LOG="${RUN_DIR}/service_7b.log"
E1_LOG="${RUN_DIR}/e1.log"
ONE_B_PID_FILE="${RUN_DIR}/service_1b.pid"
SEVEN_B_PID_FILE="${RUN_DIR}/service_7b.pid"
E1_PID_FILE="${RUN_DIR}/e1.pid"

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

start_container_job \
    "cd ${PROJECT_ROOT} && nohup bash scripts/run_service_1b.sh >'${ONE_B_LOG}' 2>&1 & echo \$! >'${ONE_B_PID_FILE}'"
start_container_job \
    "cd ${PROJECT_ROOT} && nohup bash scripts/run_service_7b.sh >'${SEVEN_B_LOG}' 2>&1 & echo \$! >'${SEVEN_B_PID_FILE}'"

wait_for_endpoint "http://127.0.0.1:1040/v1/models" "1B service"
wait_for_endpoint "http://127.0.0.1:8000/v1/models" "7B service"

start_container_job \
    "cd ${PROJECT_ROOT} && nohup env MAX_WORKERS=${MAX_WORKERS} bash scripts/run_calibration.sh --output-tag ${RUN_NAME} >'${E1_LOG}' 2>&1 & echo \$! >'${E1_PID_FILE}'"

cat > "${RUN_DIR}/README.txt" <<EOF
Run name: ${RUN_NAME}
Run directory: ${RUN_DIR}
1B log: ${ONE_B_LOG}
7B log: ${SEVEN_B_LOG}
E1 log: ${E1_LOG}
1B pid file: ${ONE_B_PID_FILE}
7B pid file: ${SEVEN_B_PID_FILE}
E1 pid file: ${E1_PID_FILE}
Output tag: ${RUN_NAME}

Reconnect command:
bash /opt/pangu/pangu/scripts/check_e1_status.sh
EOF

echo "Run name: ${RUN_NAME}"
echo "Run directory: ${RUN_DIR}"
echo "1B pid: $(cat "${ONE_B_PID_FILE}")"
echo "7B pid: $(cat "${SEVEN_B_PID_FILE}")"
echo "E1 pid: $(cat "${E1_PID_FILE}")"

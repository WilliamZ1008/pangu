#!/bin/bash
set -euo pipefail

# Default to 4 cards so this can run concurrently with the 1B service.
export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3}"
export VLLM_USE_V1="${VLLM_USE_V1:-1}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
LOCAL_CKPT_DIR="${LOCAL_CKPT_DIR:-/opt/pangu/openPangu-Embedded-7B-V1.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-pangu_embedded_7b}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-4}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-2048}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"

DEVICE_COUNT=$(awk -F',' '{print NF}' <<<"${ASCEND_RT_VISIBLE_DEVICES}")
if [[ "${DEVICE_COUNT}" -ne "${TENSOR_PARALLEL_SIZE}" ]]; then
    echo "Error: device count (${DEVICE_COUNT}) must equal TENSOR_PARALLEL_SIZE (${TENSOR_PARALLEL_SIZE})." >&2
    echo "ASCEND_RT_VISIBLE_DEVICES=${ASCEND_RT_VISIBLE_DEVICES}" >&2
    exit 1
fi

vllm serve "${LOCAL_CKPT_DIR}" \
    --served-model-name "${SERVED_MODEL_NAME}" \
    --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
    --trust-remote-code \
    --host "${HOST}" \
    --port "${PORT}" \
    --max-num-seqs "${MAX_NUM_SEQS}" \
    --max-model-len "${MAX_MODEL_LEN}" \
    --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS}" \
    --tokenizer-mode slow \
    --dtype bfloat16 \
    --distributed-executor-backend mp \
    --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
    --no-enable-prefix-caching \
    --no-enable-chunked-prefill

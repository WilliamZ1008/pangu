#!/bin/bash
set -euo pipefail

export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-0}"
export VLLM_USE_V1="${VLLM_USE_V1:-1}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-1040}"
LOCAL_CKPT_DIR="${LOCAL_CKPT_DIR:-/opt/pangu/openPangu-Embedded-1B-V1.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-pangu_embedded_1b}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"

vllm serve "${LOCAL_CKPT_DIR}" \
    --served-model-name "${SERVED_MODEL_NAME}" \
    --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
    --trust-remote-code \
    --host "${HOST}" \
    --port "${PORT}" \
    --max-num-seqs 16 \
    --max-model-len 16384 \
    --max-num-batched-tokens 2048 \
    --tokenizer-mode slow \
    --dtype bfloat16 \
    --distributed-executor-backend mp \
    --gpu-memory-utilization 0.90 \
    --no-enable-prefix-caching \
    --no-enable-chunked-prefill

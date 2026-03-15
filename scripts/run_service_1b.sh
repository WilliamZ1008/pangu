#!/bin/bash
set -euo pipefail

# Default to device 7 so it can co-exist with the 7B default shard set.
export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-7}"
export VLLM_USE_V1="${VLLM_USE_V1:-1}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-1040}"
LOCAL_CKPT_DIR="${LOCAL_CKPT_DIR:-/opt/pangu/openPangu-Embedded-1B-V1.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-pangu_embedded_1b}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-2048}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

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

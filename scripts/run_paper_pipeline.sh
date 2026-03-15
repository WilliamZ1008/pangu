#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/opt/pangu/pangu"
OUTPUT_TAG="${OUTPUT_TAG:-paper_detached_$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="${RUN_DIR:-${PROJECT_ROOT}/runtime/logs/${OUTPUT_TAG}}"
MAX_WORKERS="${MAX_WORKERS:-4}"
E1_SUMMARY="${E1_SUMMARY:-${PROJECT_ROOT}/outputs/summaries/e1_detached_20260315_103207.json}"
TEST_SAMPLE_FRACTION="${TEST_SAMPLE_FRACTION:-1.0}"
ABLATION_SAMPLE_FRACTION="${ABLATION_SAMPLE_FRACTION:-1.0}"
ENABLE_RULE_V2="${ENABLE_RULE_V2:-1}"
STATUS_DIR="${RUN_DIR}/status"
MANIFEST_DIR="${RUN_DIR}/manifests"

mkdir -p "${RUN_DIR}" "${STATUS_DIR}" "${MANIFEST_DIR}"
cd "${PROJECT_ROOT}"

shopt -s nullglob

log() {
    echo "[$(date --iso-8601=seconds)] $*"
}

set_stage() {
    local stage="$1"
    echo "${stage}" > "${STATUS_DIR}/current_stage.txt"
    date --iso-8601=seconds > "${STATUS_DIR}/${stage}.started"
}

complete_stage() {
    local stage="$1"
    date --iso-8601=seconds > "${STATUS_DIR}/${stage}.done"
}

latest_matching() {
    local pattern="$1"
    local matches=( ${pattern} )
    if [ "${#matches[@]}" -eq 0 ]; then
        return 1
    fi
    printf '%s\n' "${matches[@]}" | sort | tail -n 1
}

run_stage() {
    local stage="$1"
    shift
    set_stage "${stage}"
    log "Starting ${stage}: $*"
    "$@" > "${MANIFEST_DIR}/${stage}.json"
    complete_stage "${stage}"
    log "Completed ${stage}"
}

fail() {
    local message="$1"
    echo "failed" > "${STATUS_DIR}/pipeline_state.txt"
    log "${message}"
    exit 1
}

trap 'fail "Pipeline failed near line ${LINENO}."' ERR

echo "running" > "${STATUS_DIR}/pipeline_state.txt"

TEST_ARGS=()
ABLATION_ARGS=()
if [ "${TEST_SAMPLE_FRACTION}" != "1.0" ]; then
    TEST_ARGS+=(--sample-fraction "${TEST_SAMPLE_FRACTION}")
fi
if [ "${ABLATION_SAMPLE_FRACTION}" != "1.0" ]; then
    ABLATION_ARGS+=(--sample-fraction "${ABLATION_SAMPLE_FRACTION}")
fi

run_stage "E0_verify" test -f "${PROJECT_ROOT}/outputs/results/e0_shared8_count_report.json"
run_stage "E0_verify_split" test -f "${PROJECT_ROOT}/outputs/results/e0_shared8_split_report.json"
run_stage "E0_verify_manual" test -f "${PROJECT_ROOT}/outputs/results/e0_manual_audit.md"

run_stage \
    "E1_threshold_freeze" \
    python scripts/write_threshold_freeze_report.py \
    --e1-summary "${E1_SUMMARY}" \
    --decision freeze \
    --output-json "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__threshold_freeze.json" \
    --output-md "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__threshold_freeze.md"

run_stage "E2_cascade_final_zh_test" python main_parallel.py --system cascade_final --lang zh --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E2_7b_only_zh_test" python main_parallel.py --system 7b_only --lang zh --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E2_1b_only_zh_test" python main_parallel.py --system 1b_only --lang zh --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"

run_stage "E3_cascade_final_en_test" python main_parallel.py --system cascade_final --lang en --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E3_7b_only_en_test" python main_parallel.py --system 7b_only --lang en --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E3_1b_only_en_test" python main_parallel.py --system 1b_only --lang en --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"

run_stage "E4_cascade_final_zh_ablation" python main_parallel.py --system cascade_final --lang zh --split ablation "${ABLATION_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E4_cascade_no_calibrator_zh_ablation" python main_parallel.py --system cascade_no_calibrator --lang zh --split ablation "${ABLATION_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E4_cascade_no_specialist_prompt_zh_ablation" python main_parallel.py --system cascade_no_specialist_prompt --lang zh --split ablation "${ABLATION_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
run_stage "E4_cascade_no_draft_conditioning_zh_ablation" python main_parallel.py --system cascade_no_draft_conditioning --lang zh --split ablation "${ABLATION_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"

if [ "${ENABLE_RULE_V2}" = "1" ]; then
    run_stage "E2_rule_v2_zh_test" python main_parallel.py --system rule_v2 --lang zh --split test "${TEST_ARGS[@]}" --max-workers "${MAX_WORKERS}" --output-tag "${OUTPUT_TAG}"
fi

CASCADE_ZH_PRED="$(latest_matching "${PROJECT_ROOT}/outputs/predictions/cascade_final__zh__test__${OUTPUT_TAG}__*.jsonl")"
CASCADE_ZH_TRACE="$(latest_matching "${PROJECT_ROOT}/outputs/traces/cascade_final__zh__test__${OUTPUT_TAG}__*.jsonl")"
CASCADE_ZH_SUMMARY="$(latest_matching "${PROJECT_ROOT}/outputs/summaries/cascade_final__zh__test__${OUTPUT_TAG}__*.json")"

run_stage \
    "E5_routing_analysis" \
    python scripts/build_routing_analysis.py \
    --predictions "${CASCADE_ZH_PRED}" \
    --traces "${CASCADE_ZH_TRACE}" \
    --summary "${CASCADE_ZH_SUMMARY}" \
    --output-json "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__cascade_final__zh__test__routing_analysis.json" \
    --output-md "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__cascade_final__zh__test__routing_analysis.md"

run_stage \
    "E6_case_study_pack" \
    python scripts/build_case_study_pack.py \
    --predictions "${CASCADE_ZH_PRED}" \
    --traces "${CASCADE_ZH_TRACE}" \
    --output-json "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__cascade_final__zh__test__case_study_pack.json" \
    --output-md "${PROJECT_ROOT}/outputs/results/${OUTPUT_TAG}__cascade_final__zh__test__case_study_pack.md" \
    --extra-audit-count 50

echo "complete" > "${STATUS_DIR}/pipeline_state.txt"
date --iso-8601=seconds > "${STATUS_DIR}/completed_at.txt"
log "Pipeline finished successfully."

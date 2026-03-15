#!/bin/bash
set -euo pipefail

cd /opt/pangu/pangu
MAX_WORKERS="${MAX_WORKERS:-4}"
OUTPUT_TAG=""

args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[$i]}" in
        --output-tag)
            if [ $((i + 1)) -lt ${#args[@]} ]; then
                OUTPUT_TAG="${args[$((i + 1))]}"
            fi
            ;;
        --output-tag=*)
            OUTPUT_TAG="${args[$i]#--output-tag=}"
            ;;
    esac
done

python main_parallel.py --system 1b_only --lang zh --split dev --max-workers "${MAX_WORKERS}" "$@"
python main_parallel.py --system 7b_only --lang zh --split dev --max-workers "${MAX_WORKERS}" "$@"
python main_parallel.py --system cascade_final --lang zh --split dev --max-workers "${MAX_WORKERS}" "$@"
python main_parallel.py --system 1b_only --lang en --split dev --max-workers "${MAX_WORKERS}" "$@"
python main_parallel.py --system 7b_only --lang en --split dev --max-workers "${MAX_WORKERS}" "$@"
python main_parallel.py --system cascade_final --lang en --split dev --max-workers "${MAX_WORKERS}" "$@"

if [ -n "${OUTPUT_TAG}" ]; then
    python scripts/build_calibration_summary.py --run-tag "${OUTPUT_TAG}"
fi

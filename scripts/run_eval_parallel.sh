#!/bin/bash
set -euo pipefail

cd /opt/pangu/pangu
if [ "$#" -eq 0 ]; then
    python main_parallel.py --system cascade_final --lang zh --split test --max-workers 4
else
    python main_parallel.py "$@"
fi

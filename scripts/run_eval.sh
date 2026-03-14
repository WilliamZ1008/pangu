#!/bin/bash
set -euo pipefail

cd /opt/pangu/pangu
if [ "$#" -eq 0 ]; then
    python main.py --system cascade_final --lang zh --split test
else
    python main.py "$@"
fi

#!/bin/bash
set -euo pipefail

cd /opt/pangu/pangu

python main.py --system 1b_only --lang zh --split dev "$@"
python main.py --system 7b_only --lang zh --split dev "$@"
python main.py --system cascade_final --lang zh --split dev "$@"
python main.py --system 1b_only --lang en --split dev "$@"
python main.py --system 7b_only --lang en --split dev "$@"
python main.py --system cascade_final --lang en --split dev "$@"

#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-}:src"
python -m compileall -q src
pytest -q
if [[ "${RUN_LIVE_TESTS:-0}" == "1" ]]; then
  pytest -m live -o addopts='' -q -vv
fi

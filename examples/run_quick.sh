#!/usr/bin/env sh
set -eu

python -m cubesec_sim init-config simulation.json
python -m cubesec_sim run \
  --config simulation.json \
  --profile quick \
  --output artifacts/quick \
  --save-iq none


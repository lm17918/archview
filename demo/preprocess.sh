#!/usr/bin/env bash
# Pre-generate augmented data, then hand off to the training launcher.
set -e

python dataset.py --config config.yaml
bash run.sh

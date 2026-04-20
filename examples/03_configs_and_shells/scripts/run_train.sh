#!/usr/bin/env bash
# Launches training with the yaml config.

set -e

python train.py
bash scripts/evaluate.sh

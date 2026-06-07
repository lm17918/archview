#!/usr/bin/env bash
# Launch training with the default config.
set -e

python main.py train config.yaml
python main.py eval config.yaml

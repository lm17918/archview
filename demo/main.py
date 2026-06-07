"""Entry point: load config, then train or evaluate."""

import sys

from evaluate import evaluate
from helpers import load_config, save_config_snapshot
from train import train


def run():
    cfg = load_config("config.yaml")
    save_config_snapshot(cfg)
    mode = sys.argv[1] if len(sys.argv) > 1 else "train"
    if mode == "train":
        best = train(cfg)
        print(f"best train acc: {best:.3f}")
    else:
        acc = evaluate(cfg)
        print(f"eval acc: {acc:.3f}")


if __name__ == "__main__":
    run()

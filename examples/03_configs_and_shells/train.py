"""Entry point: loads a YAML config and class mapping JSON."""
import json
from pathlib import Path


def load_config():
    # references configs/train.yaml
    return Path("configs/train.yaml").read_text()


def load_classes():
    # references configs/classes.json
    with open("configs/classes.json") as f:
        return json.load(f)


if __name__ == "__main__":
    print(load_config())
    print(load_classes())

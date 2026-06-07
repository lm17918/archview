"""Grab-bag of helpers: config, device, logging, transforms, metrics, checkpoints."""

import json
import logging
import os

import torch
import yaml
from torchvision import transforms


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def save_config_snapshot(cfg, path="config.json"):
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def get_device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    return logging.getLogger("trainer")


def build_transforms(train=True):
    ops = [transforms.Resize((32, 32)), transforms.ToTensor()]
    if train:
        ops.insert(0, transforms.RandomHorizontalFlip())
    return transforms.Compose(ops)


def accuracy(output, target):
    pred = output.argmax(dim=1)
    return (pred == target).float().mean().item()


class AverageMeter:
    def __init__(self):
        self.sum = 0.0
        self.count = 0

    def update(self, value, n=1):
        self.sum += value * n
        self.count += n

    @property
    def avg(self):
        return self.sum / max(self.count, 1)


def save_checkpoint(model, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(model.state_dict(), path)


def load_checkpoint(model, path):
    model.load_state_dict(torch.load(path))
    return model

"""Evaluation entry."""

import torch

from dataset import make_loader
from helpers import AverageMeter, get_device, load_checkpoint
from metrics import confusion_counts, top_k_accuracy
from model import build_model


def evaluate(cfg):
    device = get_device()
    model = build_model()
    model = load_checkpoint(model, cfg["checkpoint"])
    model.eval()
    loader = make_loader(train=False, batch_size=cfg["batch_size"])
    acc_meter = AverageMeter()
    with torch.no_grad():
        for images, labels in loader:
            out = model(images.to(device))
            acc_meter.update(top_k_accuracy(out, labels), images.size(0))
    return acc_meter.avg

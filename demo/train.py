"""Training loop."""

import torch.nn as nn
from torch.optim import Adam

from callbacks import EarlyStopping
from dataset import make_loader
from helpers import AverageMeter, accuracy, save_checkpoint, setup_logging
from model import build_model


def train_one_epoch(model, loader, optimizer, criterion, log):
    model.train()
    loss_meter, acc_meter = AverageMeter(), AverageMeter()
    for images, labels in loader:
        optimizer.zero_grad()
        out = model(images)
        loss = criterion(out, labels)
        loss.backward()
        optimizer.step()
        loss_meter.update(loss.item(), images.size(0))
        acc_meter.update(accuracy(out, labels), images.size(0))
    log.info("loss=%.3f acc=%.3f", loss_meter.avg, acc_meter.avg)
    return acc_meter.avg


def train(cfg):
    log = setup_logging()
    model = build_model()
    loader = make_loader(train=True, batch_size=cfg["batch_size"])
    optimizer = Adam(model.parameters(), lr=cfg["lr"])
    criterion = nn.CrossEntropyLoss()
    stopper = EarlyStopping(patience=cfg.get("patience", 5))
    best = 0.0
    for epoch in range(cfg["epochs"]):
        acc = train_one_epoch(model, loader, optimizer, criterion, log)
        if acc > best:
            best = acc
            save_checkpoint(model, cfg["checkpoint"])
        if stopper.step(acc):
            break
    return best

"""Eval metrics. (accuracy duplicates the one in helpers — should be merged.)"""

import torch

from broken import legacy_metric  # broken.py fails to parse


def accuracy(output, target):
    pred = output.argmax(dim=1)
    return (pred == target).float().mean().item()


def top_k_accuracy(output, target, k=5):
    topk = output.topk(k, dim=1).indices
    hits = (topk == target.unsqueeze(1)).any(dim=1)
    return hits.float().mean().item()


def confusion_counts(output, target, num_classes):
    pred = output.argmax(dim=1)
    mat = torch.zeros(num_classes, num_classes)
    for p, t in zip(pred, target):
        mat[t, p] += 1
    return mat


def baseline_score(output, target):
    return legacy_metric(output, target)

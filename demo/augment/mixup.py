"""Mixup augmentation. Reaches up to the top-level helpers for the device."""

import torch

from .transforms import RandomErasing
from ..helpers import get_device


def mixup_batch(images, labels, alpha=0.2):
    images = images.to(get_device())
    lam = torch.distributions.Beta(alpha, alpha).sample().item()
    perm = torch.randperm(images.size(0))
    mixed = lam * images + (1 - lam) * images[perm]
    eraser = RandomErasing()
    return eraser(mixed), labels, labels[perm], lam

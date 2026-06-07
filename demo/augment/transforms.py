"""Tensor-space augmentations."""

import torch


class RandomErasing:
    def __init__(self, p=0.5):
        self.p = p

    def __call__(self, img):
        if torch.rand(1).item() < self.p:
            img = img.clone()
            img[:, :8, :8] = 0.0
        return img

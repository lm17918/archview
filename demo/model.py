"""Backbone + classifier head. (Imports dataset for NUM_CLASSES — circular.)"""

import torch
import torch.nn as nn

from dataset import NUM_CLASSES
from helpers import get_device


def preprocess_for_model(img):
    return (img - 0.5) / 0.5


class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )

    def forward(self, x):
        return self.net(x).flatten(1)


class Classifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = Backbone()
        self.head = nn.Linear(32, NUM_CLASSES)

    def forward(self, x):
        return self.head(self.backbone(x))


def build_model():
    return Classifier().to(get_device())

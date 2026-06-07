"""CIFAR dataset wrapper. (Imports model for a preprocessing helper — tangled.)"""

import torch
from torch.utils.data import Dataset
from torchvision.datasets import CIFAR10

from augment import RandomErasing  # resolved through the package re-export
from helpers import build_transforms, load_config
from model import preprocess_for_model

NUM_CLASSES = 10


class ImageDataset(Dataset):
    def __init__(self, train=True):
        cfg = load_config()
        self.tf = build_transforms(train=train)
        self.erase = RandomErasing() if train else None
        self.base = CIFAR10(cfg["data_root"], train=train, download=True)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        img, label = self.base[idx]
        img = self.tf(img)
        img = preprocess_for_model(img)
        if self.erase is not None:
            img = self.erase(img)
        return img, label


def make_loader(train=True, batch_size=64):
    ds = ImageDataset(train=train)
    return torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=train)

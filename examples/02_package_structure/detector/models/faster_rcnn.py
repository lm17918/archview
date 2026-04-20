"""Faster R-CNN implementation stub."""
from detector.models.backbone import ResNet50


class FasterRCNN:
    def __init__(self, num_classes: int):
        self.backbone = ResNet50()
        self.num_classes = num_classes

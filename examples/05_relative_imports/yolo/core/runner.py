"""Uses a sibling module and a cross-package module via relative imports."""
from . import nms
from ..heads.detect_head import DetectHead


def detect(path: str):
    head = DetectHead()
    raw = head.forward(path)
    return nms.suppress(raw)

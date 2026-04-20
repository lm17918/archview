"""Orchestrates detector + postprocessing."""
from detector import Detector
from utils import draw_boxes


def run(image_path: str):
    det = Detector()
    boxes = det.predict(image_path)
    draw_boxes(image_path, boxes)

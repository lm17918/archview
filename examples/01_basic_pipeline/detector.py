"""Detector wrapper around the model."""
from model import load_model


class Detector:
    def __init__(self):
        self.model = load_model()

    def predict(self, path: str):
        return self.model.forward(path)

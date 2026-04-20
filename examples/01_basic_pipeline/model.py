"""Leaf: fake model with forward pass."""


class Model:
    def forward(self, path: str):
        return [(10, 20, 100, 200, "cat")]


def load_model():
    return Model()

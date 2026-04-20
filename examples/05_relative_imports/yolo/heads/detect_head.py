"""Detection head."""


class DetectHead:
    def forward(self, path: str):
        return [(0, 0, 1, 1, 0.9)]

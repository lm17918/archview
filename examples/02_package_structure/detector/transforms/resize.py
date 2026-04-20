"""Image resize transform."""


class Resize:
    def __init__(self, size: int):
        self.size = size

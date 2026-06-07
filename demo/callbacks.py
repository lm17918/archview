"""Training callbacks. (Pulls registry, which pulls train back -> 3-way cycle.)"""

from registry import get_callback


class EarlyStopping:
    def __init__(self, patience=5):
        self.patience = patience
        self.best = 0.0
        self.bad_epochs = 0

    def step(self, metric):
        if metric > self.best:
            self.best = metric
            self.bad_epochs = 0
        else:
            self.bad_epochs += 1
        return self.bad_epochs >= self.patience


def build_callback(name):
    return get_callback(name)()

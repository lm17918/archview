"""Name -> callback registry. (Imports train_one_epoch, closing the cycle.)"""

from train import train_one_epoch

CALLBACKS = {}


def register(name):
    def deco(cls):
        CALLBACKS[name] = cls
        return cls

    return deco


def get_callback(name):
    return CALLBACKS[name]


def run_single_epoch(model, loader, opt, criterion, log):
    return train_one_epoch(model, loader, opt, criterion, log)

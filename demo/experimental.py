"""Experimental tricks. (Several imports point at things that don't exist.)"""

import torch

from helpers import GLOBAL_SEED, get_device  # GLOBAL_SEED is not defined in helpers
from quantization import quantize_model  # quantization.py does not exist
from augment import CutMix  # augment never exports CutMix


def setup(model):
    torch.manual_seed(GLOBAL_SEED)
    model = quantize_model(model.to(get_device()))
    return CutMix(model)

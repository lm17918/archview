"""Half-finished refactor, left broken. (Syntax error on purpose.)"""

import torch


def legacy_metric(output, target)  # missing colon -> SyntaxError
    return (output.argmax(1) == target).float().mean()

"""Old training script kept "just in case". Nobody imports it anymore."""

import torch


def old_loop(model, data, epochs=10):
    opt = torch.optim.SGD(model.parameters(), lr=0.01)
    for _ in range(epochs):
        for x, y in data:
            opt.zero_grad()
            loss = ((model(x) - y) ** 2).mean()
            loss.backward()
            opt.step()
    return model

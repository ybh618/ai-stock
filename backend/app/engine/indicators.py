from __future__ import annotations


def moving_average(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    result: list[float] = []
    running_sum = 0.0
    for index, value in enumerate(values):
        running_sum += value
        if index >= period:
            running_sum -= values[index - period]
        denom = min(index + 1, period)
        result.append(running_sum / denom)
    return result


def rsi(values: list[float], period: int = 14) -> list[float]:
    if len(values) < 2:
        return [50.0 for _ in values]
    gains = [0.0]
    losses = [0.0]
    for idx in range(1, len(values)):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gains = moving_average(gains, period)
    avg_losses = moving_average(losses, period)
    output: list[float] = []
    for gain, loss in zip(avg_gains, avg_losses, strict=False):
        if loss == 0:
            output.append(100.0 if gain > 0 else 50.0)
            continue
        rs = gain / loss
        output.append(100.0 - (100.0 / (1 + rs)))
    return output

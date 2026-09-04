from __future__ import annotations

import random


def paired_bootstrap_accuracy_difference(gold: list[str], baseline: list[str], active: list[str], samples: int = 5000, seed: int = 20260903) -> dict:
    if not (len(gold) == len(baseline) == len(active)):
        raise ValueError("paired inputs must have equal length")
    n = len(gold)
    if n == 0:
        return {"difference": 0.0, "ci95": [0.0, 0.0], "samples": 0}
    observed = sum(a == g for a, g in zip(active, gold, strict=True)) / n - sum(b == g for b, g in zip(baseline, gold, strict=True)) / n
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        indices = [rng.randrange(n) for _ in range(n)]
        a = sum(active[i] == gold[i] for i in indices) / n
        b = sum(baseline[i] == gold[i] for i in indices) / n
        draws.append(a - b)
    draws.sort()
    return {"difference": observed, "ci95": [draws[int(.025 * samples)], draws[min(samples - 1, int(.975 * samples))]], "samples": samples}


def mcnemar_exact(gold: list[str], left: list[str], right: list[str]) -> dict:
    left_only = sum(l == g and r != g for g, l, r in zip(gold, left, right, strict=True))
    right_only = sum(l != g and r == g for g, l, r in zip(gold, left, right, strict=True))
    discordant = left_only + right_only
    if discordant == 0:
        p = 1.0
    else:
        k = min(left_only, right_only)
        p = min(1.0, 2 * sum(math_comb(discordant, i) for i in range(k + 1)) / (2 ** discordant))
    return {"left_only": left_only, "right_only": right_only, "discordant": discordant, "exact_p_two_sided": p, "low_power_warning": discordant < 10}


def math_comb(n: int, k: int) -> int:
    import math
    return math.comb(n, k)


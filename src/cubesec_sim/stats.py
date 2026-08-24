"""Dependency-light statistics with explicit paired denominators."""

from __future__ import annotations

import math

import numpy as np


def wilson(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid binomial counts")
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    lower = 0.0 if successes == 0 else max(0.0, center - half)
    upper = 1.0 if successes == total else min(1.0, center + half)
    return lower, upper


def mcnemar_exact(
    baseline: list[bool], candidate: list[bool]
) -> dict[str, float | int]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired non-empty outcomes required")
    b = sum(x and not y for x, y in zip(baseline, candidate))
    c = sum(y and not x for x, y in zip(baseline, candidate))
    n = b + c
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n
        p_value = min(1.0, 2 * tail)
    return {
        "baseline_only": b,
        "candidate_only": c,
        "discordant": n,
        "p_exact": p_value,
    }


def paired_bootstrap_difference(
    baseline: list[float], candidate: list[float], *, seed: int, draws: int = 5000
) -> dict[str, float]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired non-empty values required")
    differences = np.asarray(candidate, dtype=float) - np.asarray(baseline, dtype=float)
    rng = np.random.Generator(np.random.PCG64(seed))
    means = differences[
        rng.integers(0, len(differences), size=(draws, len(differences)))
    ].mean(axis=1)
    return {
        "mean_difference": float(differences.mean()),
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
        "draws": float(draws),
    }

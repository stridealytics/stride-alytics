"""Correlation between a candidate trade and the open book (docs: BR-013).

Pure functions on daily return series. A candidate that moves almost in lock-step with something
already held adds the same risk twice, so the gate blocks it above a threshold.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import sqrt

MIN_OVERLAP = 20  # fewer shared daily returns than this and a correlation means nothing


def pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Correlation of the most recent shared returns, or None if there is too little to judge.

    The series are aligned on their latest ends; a flat series has no correlation (None).
    """
    n = min(len(a), len(b))
    if n < MIN_OVERLAP:
        return None
    x, y = list(a[-n:]), list(b[-n:])
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((v - mx) ** 2 for v in x)
    syy = sum((v - my) ** 2 for v in y)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((u - mx) * (v - my) for u, v in zip(x, y))
    return round(max(-1.0, min(1.0, sxy / sqrt(sxx * syy))), 3)


def correlations_with_held(
    candidate: str,
    returns: Mapping[str, Sequence[float] | None],
    held: Sequence[str],
) -> dict[str, float | None]:
    """Correlation of ``candidate`` with each distinct held symbol (None = could not be computed).

    The candidate's own symbol is skipped: adding to a position is not a diversification question.
    """
    mine = returns.get(candidate)
    out: dict[str, float | None] = {}
    for symbol in sorted({h for h in held if h != candidate}):
        theirs = returns.get(symbol)
        out[symbol] = None if mine is None or theirs is None else pearson(mine, theirs)
    return out

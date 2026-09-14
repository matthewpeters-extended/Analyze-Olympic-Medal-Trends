"""Locate structural breaks in a short, evenly ordered series.

Why this exists: it is easy to look at a concentration chart, see the Cold War, and
declare a break there. This module makes the claim falsifiable. It searches every
possible split point rather than the ones the analyst already believes in, and it
accepts a break only when a penalty term says the fit improved enough to be worth
the extra parameter.

Method
------
Binary segmentation on a piecewise constant mean model. At each round every legal
split of every current segment is scored by the total within segment sum of squares,
the best one is taken, and it is kept only if it lowers a Bayesian information
criterion for a Gaussian model with unknown common variance:

    bic(k) = n * log(sse_k / n) + 2 * k * log(n)

The search stops at the first round where the criterion does not improve. Segments
are never allowed shorter than `min_size`, so a single wild Games cannot become its
own regime on the strength of one point.

Scaling matters here. Run this on an interpretable, roughly linear quantity such as
the effective number of competitors, not on a bounded index such as a Herfindahl
score, whose extreme early values dominate a squared error criterion and push every
break into the first decade.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Segment:
    start: int
    stop: int
    mean: float
    n: int


def _sse(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(((values - values.mean()) ** 2).sum())


def _total_sse(values: np.ndarray, segments: list[tuple[int, int]]) -> float:
    return sum(_sse(values[a:b]) for a, b in segments)


def find_breaks(
    values: np.ndarray,
    min_size: int = 3,
    max_breaks: int = 6,
) -> tuple[list[int], list[Segment]]:
    """Return the break indices and the resulting segments.

    A break index is the position of the first observation of the new segment.
    """
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 2 * min_size:
        return [], [Segment(0, n, float(values.mean()), n)]

    segments: list[tuple[int, int]] = [(0, n)]
    breaks: list[int] = []
    current_sse = _sse(values)

    for _ in range(max_breaks):
        best: tuple[float, list[tuple[int, int]], int] | None = None
        for index, (start, stop) in enumerate(segments):
            for split in range(start + min_size, stop - min_size + 1):
                candidate = segments[:index] + [(start, split), (split, stop)] + segments[index + 1:]
                score = _total_sse(values, candidate)
                if best is None or score < best[0]:
                    best = (score, candidate, split)
        if best is None:
            break

        score, candidate, split = best
        if score <= 0:
            break
        before = n * np.log(current_sse / n) + 2 * len(breaks) * np.log(n)
        after = n * np.log(score / n) + 2 * (len(breaks) + 1) * np.log(n)
        if after >= before:
            break

        segments, current_sse = candidate, score
        breaks.append(split)
        breaks.sort()

    segments.sort()
    described = [
        Segment(start, stop, float(values[start:stop].mean()), stop - start)
        for start, stop in segments
    ]
    return breaks, described

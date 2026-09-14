"""Bounded, deterministic width allocation, independent of slide rendering.

Auto sizing uses sampled height profiles, not a global constraint solver. The
score prioritizes overall height, then total content height. A feasible balanced
allocation provides a baseline so the heuristic cannot do worse on that score.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .diagnostics import Diagnostic, LayoutError
from .model import ColumnWidth


@dataclass(frozen=True)
class WidthRequirement:
    minimum: float
    preferred: float
    maximum: float | None = None


@dataclass(frozen=True)
class WidthProfile:
    minimum: float
    preferred: float
    heights: Callable[[float], tuple[float, ...]]


def constrain(
    profiles: Sequence[WidthProfile], bounds: Sequence[ColumnWidth], path: str
) -> tuple[WidthRequirement, ...]:
    requirements = []
    for index, profile in enumerate(profiles):
        bound = bounds[index] if bounds else ColumnWidth()
        minimum = max(profile.minimum, bound.minimum, 1e-6)
        maximum = bound.maximum
        if maximum is not None and minimum > maximum + 1e-6:
            raise LayoutError(
                Diagnostic(
                    f"{path}/column/{index}",
                    "width",
                    minimum,
                    maximum,
                    "The maximum is below the content minimum (including padding and unbreakable text). "
                    "Increase maximum or add an explicit text break.",
                    "width_constraints",
                )
            )
        preferred = max(minimum, profile.preferred)
        if maximum is not None:
            preferred = min(preferred, maximum)
        requirements.append(WidthRequirement(minimum, preferred, maximum))
    return tuple(requirements)


def _distribute(widths: list[float], caps: Sequence[float], budget: float) -> list[float]:
    """Distribute spare width equally, redistributing shares from capped columns."""
    result = list(widths)
    while budget > 1e-7:
        active = [i for i, (value, cap) in enumerate(zip(result, caps)) if cap - value > 1e-7]
        if not active:
            break
        share = budget / len(active)
        used = 0.0
        for index in active:
            addition = min(share, caps[index] - result[index])
            result[index] += addition
            used += addition
        budget -= used
    return result


def _balanced(width: float, minima: Sequence[float], maxima: Sequence[float]) -> list[float]:
    """Closest equal-width allocation subject to hard lower and upper bounds."""
    low, high = 0.0, width
    for _ in range(50):
        level = (low + high) / 2
        total = sum(max(lo, min(hi, level)) for lo, hi in zip(minima, maxima))
        if total <= width:
            low = level
        else:
            high = level
    result = [max(lo, min(hi, low)) for lo, hi in zip(minima, maxima)]
    return _distribute(result, maxima, max(0, width - sum(result)))


def allocate_auto(
    width: float,
    profiles: Sequence[WidthProfile],
    bounds: Sequence[ColumnWidth],
    path: str,
    *,
    table: bool = False,
) -> tuple[tuple[float, ...], tuple[WidthRequirement, ...]]:
    requirements = constrain(profiles, bounds, path)
    if not profiles:
        return (), requirements
    minima = [r.minimum for r in requirements]
    if sum(minima) > width + 1e-6:
        raise LayoutError(
            Diagnostic(
                f"{path}/columns",
                "width",
                sum(minima),
                max(0, width),
                "Combined column minima exceed the available width. Reduce minimum bounds or padding, "
                "add breaks to long identifiers, or increase the available width.",
                "width_constraints",
            )
        )
    maxima = [r.maximum if r.maximum is not None else width for r in requirements]
    # Never spend more than all caps allow. Remaining space stays outside the columns.
    target = min(width, sum(maxima))
    preferred = [
        min(r.preferred, cap, target - sum(minima) + lo)
        for r, cap, lo in zip(requirements, maxima, minima)
    ]
    cache: dict[tuple[int, float], tuple[float, ...]] = {}

    def heights(index: int, value: float) -> tuple[float, ...]:
        key = (index, value)
        if key not in cache:
            cache[key] = profiles[index].heights(value)
        return cache[key]

    def score(values: Sequence[float]) -> tuple[float, float]:
        columns = [heights(i, value) for i, value in enumerate(values)]
        primary = (
            sum(max(row) for row in zip(*columns))
            if table
            else max((sum(column) for column in columns), default=0)
        )
        return primary, sum(sum(column) for column in columns)

    # 32 intervals per column, plus endpoints. Sampling bounds the cost even for
    # long prose; stable column order breaks ties. Final rows are measured again.
    samples = [
        [lo + (hi - lo) * step / 32 for step in range(1, 33)] for lo, hi in zip(minima, preferred)
    ]
    current = list(minima)
    budget = max(0, target - sum(current))
    while budget > 1e-7:
        before = score(current)
        best = None
        for index, candidates in enumerate(samples):
            for candidate in candidates:
                cost = candidate - current[index]
                if cost <= 1e-7 or cost > budget + 1e-7:
                    continue
                trial = list(current)
                trial[index] = candidate
                after = score(trial)
                gain = (before[0] - after[0], before[1] - after[1])
                if gain <= (0, 0):
                    continue
                rank = (gain[0] / cost, gain[1] / cost, -cost, -index)
                if best is None or rank > best[0]:
                    best = (rank, index, candidate, cost)
        if best is None:
            break
        _, index, candidate, cost = best
        current[index] = candidate
        budget = max(0, budget - cost)
    current = _distribute(current, preferred, max(0, target - sum(current)))
    current = _distribute(current, maxima, max(0, target - sum(current)))
    balanced = _balanced(target, minima, maxima)
    # Keep auto sizing deterministic and never worse than feasible equal widths.
    winner = min((current, balanced), key=score)
    assert all(math.isfinite(value) for value in winner)
    return tuple(winner), requirements

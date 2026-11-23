"""Rule thresholds a user can change in Settings (docs: FR-830).

The defaults are the documented values. A user stores only the values they changed; anything
missing falls back to its default. Every value has bounds, and an unknown key or an
out-of-range value is rejected. Changing a safety rule to a *looser* value is allowed within the
bounds but reported back as a warning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class Thresholds:
    # Do-Not-Trade gate
    spread_max_pct: float = 10.0  # BR-017: widest bid/ask spread allowed (% of mid)
    open_interest_min: float = 500  # BR-018
    market_cap_min: float = 2_000_000_000  # BR-019
    earnings_window_days: float = 14  # BR-020: block entries this close to earnings
    correlation_max: float = 0.85  # BR-013: block entries this correlated with an open position
    allow_band_d: float = 0  # BR-024: 1 lets band D (speculative) trades through; band E never
    # Portfolio limits
    max_capital_at_risk_pct: float = 50.0  # BR-081 (blocks new entries)
    max_sector_risk_pct: float = 25.0  # BR-080 (reported)
    max_net_delta_pct: float = 100.0  # BR-080 (reported)
    # Exit alerts
    dte_watch: float = 7  # BR-050: days to expiry that start a Watch
    dte_warning: float = 3  # BR-050: days to expiry that raise a Warning
    delta_assignment: float = (
        0.70  # BR-052: |delta| of a short option counted as an assignment alarm
    )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


DEFAULTS = Thresholds()

# (minimum, maximum) accepted for each value.
BOUNDS: dict[str, tuple[float, float]] = {
    "spread_max_pct": (1, 25),
    "open_interest_min": (0, 5000),
    "market_cap_min": (0, 50_000_000_000),
    "earnings_window_days": (0, 60),
    "correlation_max": (0.5, 0.99),
    "allow_band_d": (0, 1),
    "max_capital_at_risk_pct": (5, 100),
    "max_sector_risk_pct": (5, 100),
    "max_net_delta_pct": (10, 300),
    "dte_watch": (1, 45),
    "dte_warning": (0, 30),
    "delta_assignment": (0.3, 0.95),
}

# For these, a larger value is looser (allows more), so going above the default is a loosening;
# for the others a smaller value is looser.
_LOOSER_WHEN_HIGHER = {
    "spread_max_pct",
    "max_capital_at_risk_pct",
    "max_sector_risk_pct",
    "max_net_delta_pct",
    "delta_assignment",
    "correlation_max",
    "allow_band_d",
}
_LOOSER_WHEN_LOWER = {"open_interest_min", "market_cap_min", "earnings_window_days"}
# dte_watch / dte_warning are alert timings, not safety rules, so they never warn.

_NAMES = {f.name for f in fields(Thresholds)}


def validate(overrides: dict[str, Any]) -> dict[str, float]:
    """Return the cleaned overrides, or raise ValueError describing the first problem."""
    clean: dict[str, float] = {}
    for key, value in overrides.items():
        if key not in _NAMES:
            raise ValueError(f"unknown threshold: {key}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        low, high = BOUNDS[key]
        if not low <= value <= high:
            raise ValueError(f"{key} must be between {low:g} and {high:g}")
        clean[key] = float(value)
    merged = resolve(clean)
    if merged.dte_warning >= merged.dte_watch:
        raise ValueError("dte_warning must be smaller than dte_watch")
    return clean


def resolve(overrides: dict[str, Any] | None) -> Thresholds:
    """Defaults with the user's valid overrides applied; unknown or invalid entries are ignored."""
    values = DEFAULTS.to_dict()
    for key, value in (overrides or {}).items():
        if key in values and isinstance(value, (int, float)) and not isinstance(value, bool):
            low, high = BOUNDS[key]
            if low <= value <= high:
                values[key] = float(value)
    return Thresholds(**values)


def loosened(overrides: dict[str, Any]) -> list[str]:
    """Names of safety thresholds set looser than their default (for a warning in the UI)."""
    out = []
    for key, value in overrides.items():
        default = getattr(DEFAULTS, key, None)
        if default is None:
            continue
        if (key in _LOOSER_WHEN_HIGHER and value > default) or (
            key in _LOOSER_WHEN_LOWER and value < default
        ):
            out.append(key)
    return sorted(out)

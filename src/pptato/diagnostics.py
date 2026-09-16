"""Shared fit diagnostics for measurement and allocation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    path: str
    axis: str
    required: float
    available: float
    suggestion: str
    code: str = "overflow"
    severity: str = "error"


class LayoutWarning(UserWarning):
    """A rendered layout crosses an explicitly allowed readability threshold."""


class LayoutError(ValueError):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        super().__init__(
            f"{diagnostic.path}: {diagnostic.axis} overflow; "
            f"requires {diagnostic.required:.2f} pt, available {diagnostic.available:.2f} pt. "
            f"{diagnostic.suggestion}"
        )

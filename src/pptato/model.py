"""Public content objects. Lengths are points (72 points = one inch)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence


def positive(value: float, name: str, *, zero: bool = False) -> None:
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")


def color(value: str) -> None:
    if len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("color must be a six-digit RGB hex string")


@dataclass(frozen=True)
class FontFamily:
    """Matching installed typeface and font files used for measurement."""

    name: str
    regular: Path
    bold: Path

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Font family name must not be empty")
        for key in ("regular", "bold"):
            path = Path(getattr(self, key)).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Missing {key} font file: {path}")
            object.__setattr__(self, key, path)

    @classmethod
    def system(cls) -> FontFamily:
        """Choose a known pair; never silently measure with a substitute face."""
        candidates = [
            ("Arial", "/System/Library/Fonts/Supplemental", "Arial.ttf", "Arial Bold.ttf"),
            ("Arial", "C:/Windows/Fonts", "arial.ttf", "arialbd.ttf"),
            (
                "Liberation Sans",
                "/usr/share/fonts/truetype/liberation2",
                "LiberationSans-Regular.ttf",
                "LiberationSans-Bold.ttf",
            ),
            (
                "DejaVu Sans",
                "/usr/share/fonts/truetype/dejavu",
                "DejaVuSans.ttf",
                "DejaVuSans-Bold.ttf",
            ),
        ]
        for name, root, regular, bold in candidates:
            if (Path(root) / regular).is_file() and (Path(root) / bold).is_file():
                return cls(name, Path(root) / regular, Path(root) / bold)
        raise ValueError("No supported system font found. Supply Theme(font=FontFamily(...)).")


@dataclass(frozen=True)
class TextStyle:
    size: float = 18
    bold: bool = False
    color: str = "263445"
    line_height: float = 1.25
    paragraph_gap: float = 6

    def __post_init__(self) -> None:
        positive(self.size, "font size")
        positive(self.line_height, "line height")
        positive(self.paragraph_gap, "paragraph gap", zero=True)
        color(self.color)


@dataclass(frozen=True)
class Theme:
    font: FontFamily = field(default_factory=FontFamily.system)
    margin: float = 36
    gap: float = 16
    title_gap: float = 24
    footer_gap: float = 18
    cell_padding: float = 7
    table_header_fill: str = "DFEBEE"
    table_fill: str = "FFFFFF"
    table_alternate_fill: str = "F3F6F8"
    body: TextStyle = field(default_factory=TextStyle)
    title: TextStyle = field(default_factory=lambda: TextStyle(30, True, "143E4B"))
    heading: TextStyle = field(default_factory=lambda: TextStyle(20, True, "143E4B"))
    note: TextStyle = field(default_factory=lambda: TextStyle(10, False, "566575", 1.25, 4))
    table: TextStyle = field(default_factory=lambda: TextStyle(15, paragraph_gap=0))

    def __post_init__(self) -> None:
        for key in ("margin", "gap", "title_gap", "footer_gap", "cell_padding"):
            positive(getattr(self, key), key, zero=True)
        for key in ("table_header_fill", "table_fill", "table_alternate_fill"):
            color(getattr(self, key))


@dataclass(frozen=True)
class Text:
    text: str
    style: TextStyle | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("Text content must be a string")


@dataclass(frozen=True)
class Heading(Text):
    pass


@dataclass(frozen=True)
class Footnote(Text):
    """An unnumbered slide note. Inline reference numbering is deferred."""


@dataclass(frozen=True)
class Bullets:
    items: Sequence[str]
    style: TextStyle | None = None

    def __post_init__(self) -> None:
        if isinstance(self.items, str) or any(not isinstance(item, str) for item in self.items):
            raise TypeError("Bullets requires a sequence of strings")
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True)
class Stack:
    children: Sequence[Block]
    gap: float | None = None
    padding: float = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        if self.gap is not None:
            positive(self.gap, "gap", zero=True)
        positive(self.padding, "padding", zero=True)


@dataclass(frozen=True)
class ColumnWidth:
    """Hard bounds in points for one automatically sized column, including padding."""

    minimum: float = 0
    maximum: float | None = None

    def __post_init__(self) -> None:
        positive(self.minimum, "minimum column width", zero=True)
        if self.maximum is not None:
            positive(self.maximum, "maximum column width")
            if self.maximum < self.minimum:
                raise ValueError("maximum column width must be at least minimum")


def _column_bounds(bounds, widths, count: int) -> tuple[ColumnWidth, ...]:
    if bounds is None or len(bounds) == 0:
        return ()
    if widths != "auto":
        raise ValueError("Column bounds require widths='auto'")
    result = tuple(bounds)
    if len(result) != count or any(not isinstance(bound, ColumnWidth) for bound in result):
        raise ValueError("Provide one ColumnWidth bound for each column")
    return result


@dataclass(frozen=True)
class Row(Stack):
    widths: Sequence[float] | Literal["equal", "auto"] = "equal"
    align: Literal["start", "center", "end"] = "start"
    bounds: Sequence[ColumnWidth] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if isinstance(self.widths, str):
            if self.widths not in ("equal", "auto"):
                raise ValueError("widths supports 'equal', 'auto', or positive relative weights")
        else:
            object.__setattr__(self, "widths", tuple(self.widths))
            if len(self.widths) != len(self.children):
                raise ValueError("Provide one width weight for each child")
            for value in self.widths:
                positive(value, "width weight")
        if self.align not in ("start", "center", "end"):
            raise ValueError("align must be start, center, or end")
        object.__setattr__(
            self, "bounds", _column_bounds(self.bounds, self.widths, len(self.children))
        )


class Columns(Row):
    """A row of equal, weighted, or content-aware columns."""


@dataclass(frozen=True)
class TextFit:
    """Opt-in table text fitting, with an allowed warning band (all sizes in points)."""

    preferred: float = 15
    normal_min: float = 12
    absolute_min: float = 10

    def __post_init__(self) -> None:
        for name in ("preferred", "normal_min", "absolute_min"):
            positive(getattr(self, name), name)
        if not self.absolute_min <= self.normal_min <= self.preferred:
            raise ValueError("TextFit requires absolute_min <= normal_min <= preferred")

    def candidates(self) -> tuple[float, ...]:
        """Descending quarter-point steps, including both exact threshold boundaries."""
        steps = math.floor((self.preferred - self.absolute_min) / 0.25)
        values = {self.preferred - index * 0.25 for index in range(steps + 1)}
        values.update((self.normal_min, self.absolute_min))
        return tuple(sorted(values, reverse=True))


@dataclass(frozen=True)
class Table:
    headers: Sequence[str]
    rows: Sequence[Sequence[str]]
    widths: Sequence[float] | Literal["equal", "auto"] = "equal"
    style: TextStyle | None = None
    bounds: Sequence[ColumnWidth] | None = None
    overflow: Literal["error", "shrink", "continue"] = "error"
    fit: TextFit | None = None

    def __post_init__(self) -> None:
        if self.overflow not in ("error", "shrink", "continue"):
            raise ValueError("Table overflow must be 'error', 'shrink', or 'continue'")
        if self.overflow == "shrink" and not isinstance(self.fit, TextFit):
            raise ValueError("overflow='shrink' requires an explicit TextFit policy")
        if self.overflow != "shrink" and self.fit is not None:
            raise ValueError("TextFit is only valid with overflow='shrink'")
        object.__setattr__(self, "headers", tuple(str(v) for v in self.headers))
        object.__setattr__(self, "rows", tuple(tuple(str(v) for v in row) for row in self.rows))
        if not self.headers:
            raise ValueError("Tables require at least one column")
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Every table row must match the header column count")
        if isinstance(self.widths, str):
            if self.widths not in ("equal", "auto"):
                raise ValueError("Table widths supports 'equal', 'auto', or relative weights")
        else:
            object.__setattr__(self, "widths", tuple(self.widths))
            if len(self.widths) != len(self.headers):
                raise ValueError("Provide one width weight per table column")
            for value in self.widths:
                positive(value, "table width weight")
        object.__setattr__(
            self, "bounds", _column_bounds(self.bounds, self.widths, len(self.headers))
        )


@dataclass(frozen=True)
class Image:
    path: Path
    height: float = 180

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        positive(self.height, "image height")


@dataclass(frozen=True)
class Spacer:
    height: float

    def __post_init__(self) -> None:
        positive(self.height, "spacer height", zero=True)


Block = Text | Bullets | Stack | Table | Image | Spacer


@dataclass(frozen=True)
class Slide:
    title: str
    body: Block
    notes: tuple[Footnote, ...] = ()


class Deck:
    def __init__(self, *, theme: Theme | None = None, size: tuple[float, float] = (960, 540)):
        self.theme = theme if theme is not None else Theme()
        positive(size[0], "slide width")
        positive(size[1], "slide height")
        self.size = tuple(size)
        self.slides: list[Slide] = []

    def add_slide(self, *, title: str, body: Block, notes: Sequence[Footnote] = ()) -> Slide:
        if any(not isinstance(note, Footnote) for note in notes):
            raise TypeError("notes must contain Footnote objects")
        slide = Slide(title, body, tuple(notes))
        self.slides.append(slide)
        return slide

    def layout(self):
        from .layout import layout_deck

        return layout_deck(self)

    def save(self, path: str | Path) -> None:
        self.layout().save(path)

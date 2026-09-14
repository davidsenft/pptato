"""Deterministic, width-dependent text measurement using explicit font files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from PIL import ImageFont

from .model import FontFamily, TextStyle


class TextTooWide(ValueError):
    def __init__(self, word: str, required: float):
        self.word = word
        self.required = required


@dataclass(frozen=True)
class Paragraph:
    lines: tuple[str, ...]
    bullet: bool = False


@dataclass(frozen=True)
class MeasuredText:
    paragraphs: tuple[Paragraph, ...]
    height: float
    line_height: float
    indent: float


class TextMeasurer:
    """Greedy word wrapping. Complex shaping and hyphenation are not yet supported."""

    SCALE = 4
    SAFETY = 2.0  # Reserved at the right and bottom of each text area, in points.

    def __init__(self, family: FontFamily):
        self.family = family
        self._fonts: dict[tuple[float, bool], ImageFont.FreeTypeFont] = {}

    def fingerprint(self) -> dict[str, str]:
        import PIL
        from PIL import features

        return {
            "family": self.family.name,
            "regular_sha256": sha256(self.family.regular.read_bytes()).hexdigest(),
            "bold_sha256": sha256(self.family.bold.read_bytes()).hexdigest(),
            "pillow": PIL.__version__,
            "freetype": features.version_module("freetype2"),
            "algorithm": "pptato-greedy-v1",
        }

    def font(self, style: TextStyle) -> ImageFont.FreeTypeFont:
        key = (style.size, style.bold)
        if key not in self._fonts:
            path = self.family.bold if style.bold else self.family.regular
            self._fonts[key] = ImageFont.truetype(
                str(path),
                max(1, round(style.size * self.SCALE)),
                layout_engine=ImageFont.Layout.BASIC,
            )
        return self._fonts[key]

    def measure(
        self, texts: tuple[str, ...], width: float, style: TextStyle, *, bullets: bool = False
    ) -> MeasuredText:
        font = self.font(style)
        indent = style.size if bullets else 0.0
        usable = width - indent - self.SAFETY
        ascent, descent = font.getmetrics()
        line_height = max(style.size * style.line_height, (ascent + descent) / self.SCALE)
        paragraphs = []
        for text in texts:
            lines: list[str] = []
            for hard_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                words = re.findall(r"\S+", hard_line)
                current = ""
                for word in words:
                    word_width = font.getlength(word) / self.SCALE
                    if word_width > usable:
                        raise TextTooWide(word, word_width + indent + self.SAFETY)
                    candidate = f"{current} {word}" if current else word
                    if current and font.getlength(candidate) / self.SCALE > usable:
                        lines.append(current)
                        current = word
                    else:
                        current = candidate
                lines.append(current)
            paragraphs.append(Paragraph(tuple(lines), bullets))
        height = (
            sum(len(p.lines) for p in paragraphs) * line_height
            + max(0, len(paragraphs) - 1) * style.paragraph_gap
            + (self.SAFETY if paragraphs else 0)
        )
        return MeasuredText(tuple(paragraphs), height, line_height, indent)

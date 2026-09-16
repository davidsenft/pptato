"""Declarative slide composition with explicit layout results."""

from .diagnostics import LayoutWarning
from .layout import Box, Continuation, Diagnostic, Layout, LayoutError, Node, TableFit
from .model import (
    Bullets,
    Columns,
    ColumnWidth,
    Deck,
    FontFamily,
    Footnote,
    Heading,
    Image,
    Row,
    Spacer,
    Stack,
    Table,
    Text,
    TextFit,
    TextStyle,
    Theme,
)

__all__ = [
    "Box",
    "Bullets",
    "Columns",
    "ColumnWidth",
    "Continuation",
    "Deck",
    "Diagnostic",
    "FontFamily",
    "Footnote",
    "Heading",
    "Image",
    "Layout",
    "LayoutError",
    "LayoutWarning",
    "Node",
    "Row",
    "Spacer",
    "Stack",
    "Table",
    "TableFit",
    "Text",
    "TextStyle",
    "TextFit",
    "Theme",
]

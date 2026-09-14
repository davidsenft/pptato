"""Resolve content into geometry without importing any PowerPoint code."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage

from .diagnostics import Diagnostic, LayoutError
from .measure import MeasuredText, TextMeasurer, TextTooWide
from .model import (
    Block,
    Bullets,
    Deck,
    Footnote,
    Heading,
    Image,
    Row,
    Spacer,
    Stack,
    Table,
    Text,
    TextStyle,
    Theme,
)
from .sizing import WidthProfile, WidthRequirement, allocate_auto, constrain


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class Node:
    kind: str
    path: str
    box: Box
    children: tuple[Node, ...] = ()
    text: MeasuredText | None = None
    style: TextStyle | None = None
    column_widths: tuple[float, ...] = ()
    row_heights: tuple[float, ...] = ()
    image_data: bytes | None = None
    padding: float = 0
    fill: str | None = None
    column_requirements: tuple[WidthRequirement, ...] = ()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Layout:
    size: tuple[float, float]
    font_name: str
    font_fingerprint: tuple[tuple[str, str], ...]
    slides: tuple[Node, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict:
        """JSON-safe snapshot. Image bytes are represented by their SHA-256."""

        def encode(value):
            if isinstance(value, bytes):
                return {"sha256": sha256(value).hexdigest()}
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [encode(item) for item in value]
            return value

        return encode(asdict(self))

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    def save(self, path: str | Path) -> None:
        from .renderers.pptx import save

        save(self, path)


def _fit(required: float, available: float, path: str, axis: str) -> None:
    if required > available + 1e-6:
        suggestion = (
            "Increase the width, shorten unbreakable text, or choose a smaller text style."
            if axis == "width"
            else "Reduce content or spacing, use a smaller text style, or move content to another slide."
        )
        raise LayoutError(Diagnostic(path, axis, required, max(0, available), suggestion))


def allocate_widths(width: float, count: int, weights, gap: float, path: str) -> tuple[float, ...]:
    if count == 0:
        return ()
    available = width - gap * (count - 1)
    if available <= 0:
        raise LayoutError(
            Diagnostic(
                path,
                "width",
                gap * (count - 1) + 1,
                max(0, width),
                "Reduce gaps or use fewer columns.",
            )
        )
    ratios = (1.0,) * count if isinstance(weights, str) else weights
    # Normalize before summing to avoid overflow for large finite weights.
    normalized = tuple(value / max(ratios) for value in ratios)
    total = sum(normalized)
    widths = tuple(available * value / total for value in normalized[:-1])
    return (*widths, available - sum(widths))


def _move(node: Node, dx: float, dy: float) -> Node:
    return replace(
        node,
        box=replace(node.box, x=node.box.x + dx, y=node.box.y + dy),
        children=tuple(_move(child, dx, dy) for child in node.children),
    )


class Engine:
    def __init__(self, theme: Theme):
        self.theme = theme
        self.measurer = TextMeasurer(theme.font)
        self._intrinsics: dict[Block, tuple[float, float]] = {}

    def text_style(self, block: Text | Bullets) -> TextStyle:
        default = (
            self.theme.heading
            if isinstance(block, Heading)
            else self.theme.note
            if isinstance(block, Footnote)
            else self.theme.body
        )
        return block.style or default

    def table_profiles(self, block: Table) -> tuple[WidthProfile, ...]:
        style = block.style or self.theme.table
        padding = self.theme.cell_padding
        styles = (replace(style, bold=True),) + (style,) * len(block.rows)
        profiles = []
        for values in zip(block.headers, *block.rows):
            sizes = [
                self.measurer.intrinsic((value,), cell_style)
                for value, cell_style in zip(values, styles)
            ]

            def heights(width, values=values):
                return tuple(
                    self.measurer.measure((value,), width - 2 * padding, cell_style).height
                    + 2 * padding
                    for value, cell_style in zip(values, styles)
                )

            profiles.append(
                WidthProfile(
                    max(size[0] for size in sizes) + 2 * padding,
                    max(size[1] for size in sizes) + 2 * padding,
                    heights,
                )
            )
        return tuple(profiles)

    def profile(self, block: Block, path: str) -> WidthProfile:
        minimum, preferred = self.intrinsic(block, path)
        return WidthProfile(
            minimum,
            preferred,
            lambda width: (self.resolve(block, 0, 0, width, float("inf"), path).box.height,),
        )

    def intrinsic(self, block: Block, path: str) -> tuple[float, float]:
        """Width requirements of a subtree, respecting nested allocation modes."""
        if block in self._intrinsics:
            return self._intrinsics[block]
        if isinstance(block, (Text, Bullets)):
            texts = tuple(block.items) if isinstance(block, Bullets) else (block.text,)
            result = self.measurer.intrinsic(
                texts, self.text_style(block), bullets=isinstance(block, Bullets)
            )
        elif isinstance(block, (Row, Table)):
            profiles = (
                self.table_profiles(block)
                if isinstance(block, Table)
                else tuple(
                    self.profile(child, f"{path}/{index}")
                    for index, child in enumerate(block.children)
                )
            )
            extra = (
                0
                if isinstance(block, Table)
                else 2 * block.padding
                + max(0, len(profiles) - 1) * (self.theme.gap if block.gap is None else block.gap)
            )
            if not profiles:
                result = (extra, extra)
            elif block.widths == "auto":
                requirements = constrain(profiles, block.bounds, path)
                result = (
                    sum(r.minimum for r in requirements) + extra,
                    sum(r.preferred for r in requirements) + extra,
                )
            else:
                ratios = (1,) * len(profiles) if block.widths == "equal" else block.widths
                scaled = [value / max(ratios) for value in ratios]
                shares = [value / sum(scaled) for value in scaled]
                if any(share == 0 for share in shares):
                    raise LayoutError(
                        Diagnostic(
                            path,
                            "width",
                            1,
                            0,
                            "Width weights differ too greatly to allocate finite space.",
                        )
                    )
                result = (
                    max(p.minimum / share for p, share in zip(profiles, shares)) + extra,
                    max(p.preferred / share for p, share in zip(profiles, shares)) + extra,
                )
        elif isinstance(block, Stack):
            sizes = [
                self.intrinsic(child, f"{path}/{index}")
                for index, child in enumerate(block.children)
            ]
            result = (
                max((size[0] for size in sizes), default=0) + 2 * block.padding,
                max((size[1] for size in sizes), default=0) + 2 * block.padding,
            )
        elif isinstance(block, Image):
            from PIL import ImageOps

            with PILImage.open(block.path) as image:
                oriented = ImageOps.exif_transpose(image)
                result = (0, block.height * oriented.width / oriented.height)
        elif isinstance(block, Spacer):
            result = (0, 0)
        else:
            raise TypeError(f"{path}: unsupported block {type(block).__name__}")
        self._intrinsics[block] = result
        return result

    def text(
        self,
        texts: tuple[str, ...],
        width: float,
        style: TextStyle,
        path: str,
        *,
        bullets: bool = False,
    ) -> MeasuredText:
        try:
            return self.measurer.measure(texts, width, style, bullets=bullets)
        except TextTooWide as exc:
            raise LayoutError(
                Diagnostic(
                    path,
                    "width",
                    exc.required,
                    max(0, width),
                    f"Unbreakable text {exc.word[:40]!r} is too wide. Increase width or add a break.",
                )
            ) from exc

    def resolve(
        self, block: Block, x: float, y: float, width: float, available: float, path: str
    ) -> Node:
        _fit(0, width, path, "width")
        _fit(0, available, path, "height")
        if isinstance(block, (Text, Bullets)):
            style = self.text_style(block)
            texts = tuple(block.items) if isinstance(block, Bullets) else (block.text,)
            measured = self.text(texts, width, style, path, bullets=isinstance(block, Bullets))
            node = Node("text", path, Box(x, y, width, measured.height), text=measured, style=style)
        elif isinstance(block, Stack):
            gap = self.theme.gap if block.gap is None else block.gap
            padding = block.padding
            _fit(2 * padding, width, path, "width")
            _fit(2 * padding, available, path, "height")
            inner = width - 2 * padding
            children: list[Node] = []
            requirements = ()
            widths = ()
            if isinstance(block, Row):
                if block.widths == "auto":
                    widths, requirements = allocate_auto(
                        inner - max(0, len(block.children) - 1) * gap,
                        tuple(
                            self.profile(child, f"{path}/{index}")
                            for index, child in enumerate(block.children)
                        ),
                        block.bounds,
                        path,
                    )
                else:
                    widths = allocate_widths(inner, len(block.children), block.widths, gap, path)
                current_x = x + padding
                for index, (child, child_width) in enumerate(zip(block.children, widths)):
                    children.append(
                        self.resolve(
                            child,
                            current_x,
                            y + padding,
                            child_width,
                            available - 2 * padding,
                            f"{path}/{index}",
                        )
                    )
                    current_x += child_width + gap
                content_h = max((child.box.height for child in children), default=0)
                factor = {"start": 0, "center": 0.5, "end": 1}[block.align]
                children = [
                    _move(child, 0, factor * (content_h - child.box.height)) for child in children
                ]
                height = content_h + 2 * padding
            else:
                current_y = y + padding
                for index, child in enumerate(block.children):
                    if index:
                        current_y += gap
                    _fit(current_y - y + padding, available, path, "height")
                    resolved = self.resolve(
                        child,
                        x + padding,
                        current_y,
                        inner,
                        y + available - padding - current_y,
                        f"{path}/{index}",
                    )
                    children.append(resolved)
                    current_y = resolved.box.bottom
                height = current_y - y + padding
            node = Node(
                "row" if isinstance(block, Row) else "stack",
                path,
                Box(x, y, width, height),
                tuple(children),
                column_widths=widths,
                column_requirements=requirements,
            )
        elif isinstance(block, Table):
            requirements = ()
            if block.widths == "auto":
                widths, requirements = allocate_auto(
                    width, self.table_profiles(block), block.bounds, path, table=True
                )
            else:
                widths = allocate_widths(width, len(block.headers), block.widths, 0, path)
            style = block.style or self.theme.table
            padding = self.theme.cell_padding
            for column_index, cell_width in enumerate(widths):
                _fit(2 * padding, cell_width, f"{path}/column/{column_index}/padding", "width")
            children = []
            row_heights: list[float] = []
            current_y = y
            for row_index, row in enumerate((block.headers, *block.rows)):
                row_style = replace(style, bold=True) if row_index == 0 else style
                texts = [
                    self.text(
                        (value,),
                        cell_width - 2 * padding,
                        row_style,
                        f"{path}/row/{row_index}/cell/{col_index}",
                    )
                    for col_index, (value, cell_width) in enumerate(zip(row, widths))
                ]
                row_height = max(text.height for text in texts) + 2 * padding
                _fit(current_y - y + row_height, available, f"{path}/row/{row_index}", "height")
                current_x = x
                for col_index, (text, cell_width) in enumerate(zip(texts, widths)):
                    children.append(
                        Node(
                            "cell",
                            f"{path}/row/{row_index}/cell/{col_index}",
                            Box(current_x, current_y, cell_width, row_height),
                            text=text,
                            style=row_style,
                            padding=padding,
                            fill=(
                                self.theme.table_header_fill
                                if row_index == 0
                                else self.theme.table_alternate_fill
                                if row_index % 2 == 0
                                else self.theme.table_fill
                            ),
                        )
                    )
                    current_x += cell_width
                row_heights.append(row_height)
                current_y += row_height
            node = Node(
                "table",
                path,
                Box(x, y, sum(widths), current_y - y),
                tuple(children),
                column_widths=widths,
                row_heights=tuple(row_heights),
                column_requirements=requirements,
            )
        elif isinstance(block, Image):
            data = block.path.read_bytes()
            with PILImage.open(BytesIO(data)) as image:
                pixel_w, pixel_h = image.size
                # Normalize orientation and format; pixels stay an individual image asset.
                from PIL import ImageOps

                image = ImageOps.exif_transpose(image)
                pixel_w, pixel_h = image.size
                buffer = BytesIO()
                image.convert("RGBA").save(buffer, format="PNG")
                data = buffer.getvalue()
            scale = min(width / pixel_w, block.height / pixel_h)
            picture_w, picture_h = pixel_w * scale, pixel_h * scale
            picture = Node(
                "picture",
                f"{path}/picture",
                Box(
                    x + (width - picture_w) / 2,
                    y + (block.height - picture_h) / 2,
                    picture_w,
                    picture_h,
                ),
                image_data=data,
            )
            node = Node("image", path, Box(x, y, width, block.height), (picture,))
        elif isinstance(block, Spacer):
            node = Node("spacer", path, Box(x, y, width, block.height))
        else:
            raise TypeError(f"{path}: unsupported block {type(block).__name__}")
        _fit(node.box.height, available, path, "height")
        return node


def layout_deck(deck: Deck) -> Layout:
    theme = deck.theme
    engine = Engine(theme)
    width, height = deck.size
    margin = theme.margin
    _fit(margin * 2, width, "deck/margins", "width")
    _fit(margin * 2, height, "deck/margins", "height")
    body_width = width - 2 * margin
    inner_height = height - 2 * margin
    slides = []
    for index, slide in enumerate(deck.slides):
        path = f"slide/{index + 1}"
        title = (
            engine.resolve(
                Text(slide.title, theme.title),
                margin,
                margin,
                body_width,
                inner_height,
                f"{path}/title",
            )
            if slide.title
            else None
        )
        footer = (
            engine.resolve(
                Stack(slide.notes, gap=theme.note.paragraph_gap),
                margin,
                0,
                body_width,
                inner_height,
                f"{path}/notes",
            )
            if slide.notes
            else None
        )
        body_top = title.box.bottom + theme.title_gap if title else margin
        body_bottom = height - margin
        if footer:
            footer = _move(footer, 0, height - margin - footer.box.height)
            body_bottom = footer.box.y - theme.footer_gap
        reserved = (body_top - margin) + (height - margin - body_bottom)
        _fit(reserved, inner_height, f"{path}/reserved-regions", "height")
        body = engine.resolve(
            slide.body, margin, body_top, body_width, body_bottom - body_top, f"{path}/body"
        )
        # The body region records available space; its child records occupied space.
        region = Node(
            "body",
            f"{path}/body-region",
            Box(margin, body_top, body_width, body_bottom - body_top),
            (body,),
        )
        children = tuple(node for node in (title, region, footer) if node is not None)
        slides.append(Node("slide", path, Box(0, 0, width, height), children))
    return Layout(
        deck.size, theme.font.name, tuple(engine.measurer.fingerprint().items()), tuple(slides)
    )

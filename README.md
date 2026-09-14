# pptato

Declarative Python layout for native, editable PowerPoint presentations.

Describe the content and its arrangement. pptato computes column widths, text
heights, table rows, spacing, and space for notes before writing a `.pptx`.

This is an early prototype. Overflow raises a `LayoutError`; the library never
silently drops content or shrinks fonts.

## Development setup

Requires Python 3.10 or later.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python examples/demo.py
```

The example creates `outputs/demo.pptx` and an inspectable
`outputs/demo.layout.json`. The fifth slide uses the included synthetic chart
image; pass `--image path/to/chart.png` to substitute your own. All example content
is synthetic. `examples/make_chart.py` regenerates the chart with matplotlib
(an optional tool, not a pptato dependency).

## Example

```python
from pptato import Bullets, Columns, Deck, Footnote, Heading, Stack, Table

deck = Deck()
deck.add_slide(
    title="Quarterly performance",
    body=Columns([
        Stack([
            Heading("What changed"),
            Bullets(["Revenue increased", "Costs remained stable"]),
        ]),
        Table(
            headers=["Metric", "Actual", "Plan"],
            rows=[["Revenue", "125", "120"], ["Margin", "24%", "23%"]],
            widths=[2, 1, 1],
        ),
    ]),
    notes=[Footnote("Source: illustrative data.")],
)

layout = deck.layout()
layout.write_json("quarterly.layout.json")
layout.save("quarterly.pptx")
# Or: deck.save("quarterly.pptx")
```

All dimensions are **points** (72 = one inch). The default slide is 960 × 540
points. Use `Theme` for margins, gaps, typography, and cell padding. `Columns`
accepts `widths="equal"` or relative weights such as `[1, 2, 1]`. `Stack` supports
`gap` and `padding`; `Row` also supports `align="start"`, `"center"`, or `"end"`.
`Text`, `Heading`, `Bullets`, `Footnote`, and `Table` accept an optional `TextStyle`.

## Fonts and fit

The default resolves a known installed font family and its matching regular/bold
files, or raises an error. For reproducibility, supply fonts explicitly:

```python
from pptato import Deck, FontFamily, Theme

theme = Theme(font=FontFamily(
    name="Your Font Family",
    regular="/path/to/Regular.ttf",
    bold="/path/to/Bold.ttf",
))
deck = Deck(theme=theme)
```

Use the actual installed family name. Fonts are not embedded into the deck.
Text measurement currently targets simple Latin text, uses explicit line breaks,
and includes a small safety allowance. Review generated slides in your target
office application. Editing text in PowerPoint preserves editability but does
not rerun layout; regenerate the deck to reflow it.

Inspect fit errors programmatically through `error.diagnostic`, including
`path`, `axis`, `required`, `available`, and `suggestion` (dimensions in points).
Geometry is deterministic with the same font files and measurement runtime.
Rendered appearance can vary across office applications.

See [the design note](docs/design.md) for architecture and limitations. Automatic
width optimization, rich text, pagination, native charts, and opt-in shrinking
are planned follow-on work.

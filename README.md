# pptato

Declarative Python layout for native, editable PowerPoint presentations.

Describe the content and its arrangement. pptato computes column widths, text
heights, table rows, spacing, and space for notes before writing a `.pptx`.

This is an early prototype. Overflow raises a `LayoutError` by default. Tables
can explicitly opt into bounded text shrinking or continuation onto more slides.
The library never silently drops content or enables either remedy.

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
accepts `widths="equal"`, `widths="auto"`, or relative weights such as `[1, 2, 1]`. `Stack` supports
`gap` and `padding`; `Row` also supports `align="start"`, `"center"`, or `"end"`.
`Text`, `Heading`, `Bullets`, `Footnote`, and `Table` accept an optional `TextStyle`.

## Automatic widths

Use `widths="auto"` on `Table`, `Columns`, or `Row`. Optional `ColumnWidth`
bounds specify hard minimum/maximum widths in points, including cell or child
padding. Omit `bounds` for content-driven sizing without explicit limits.

```python
from pptato import ColumnWidth, Table

table = Table(
    headers=["Description", "Count", "Rate"],
    rows=[
        ["Accounts that renewed after a temporary pause in service", "128", "24%"],
        ["New accounts that completed onboarding", "46", "18%"],
    ],
    widths="auto",
    bounds=[
        ColumnWidth(minimum=240),
        ColumnWidth(maximum=110),
        ColumnWidth(maximum=110),
    ],
)
```

The same API works on `Columns([table, commentary], widths="auto", bounds=[...])`.
Each bound applies to one column. Bounds require auto mode; equal and weighted
modes retain their existing behavior.

Automatic sizing measures bold headers and body text, protects unbreakable
words, then tests where additional width reduces content height. It chooses a
result no taller than a feasible balanced allocation under the same bounds.
Tables remeasure every row at the selected widths. This is a deterministic
heuristic, not an exhaustive search for the optimal layout.

If all maxima together are narrower than the available space, the table stays
at that narrower width, aligned left. A row retains its outer region and leaves
the spare space after its children. Maximum bounds are never exceeded to fill
space. Images can scale down in auto columns; use an explicit minimum when
image readability requires a particular width.

Conflicting bounds or combined content minima raise `LayoutError` with
`diagnostic.code == "width_constraints"` and a column path. A height overflow
means the chosen allocation cannot fit; another explicit allocation may still
work. Font sizes, content, and column count never change implicitly.

Run `python examples/auto_widths.py` for six demanding examples, including an
equal/auto comparison, nested tables beside commentary, capped widths, and long
notes. It writes `outputs/auto-widths.pptx` and a JSON snapshot and prints two
expected constraint failures. Resolved nodes expose `column_widths` and
`column_requirements` (effective minimum, preferred, and maximum widths).

## Explicit table overflow policies

`Table(..., overflow="error")` is the default: fitting neither adds slides nor
changes font size. Two opt-in alternatives are available.

```python
from pptato import Table, TextFit

table = Table(
    headers=["Batch", "Files"],
    rows=[["North", "24"], ["South", "17"]],
    widths="auto",
    overflow="shrink",
    fit=TextFit(preferred=15, normal_min=12, absolute_min=10),
)
```

`shrink` tests sizes from the preferred size down to the absolute minimum,
remeasuring columns and rows at each candidate. It selects the largest fitting
candidate in quarter-point steps, also testing the exact normal/absolute minima.
The explicit `preferred` size overrides the table's style/theme font size; other
styling and padding remain unchanged. Header boldness is preserved.

| Selected size in this example | Result |
| --- | --- |
| 12–15 pt | Render normally |
| 10–below 12 pt | Render, emit `LayoutWarning`, and record a readability diagnostic |
| No candidate fits at or above 10 pt | Raise `LayoutError` with code `text_fit_limit` |

Set `absolute_min=normal_min` to prohibit the warning range. The resolved table's
`table_fit` records preferred/selected sizes, thresholds, and status even when
no warning is needed. `layout.diagnostics` stores warning details and is included
in the JSON snapshot. Warnings emit during layout, not when saving an already
resolved result. Shrink never falls back to continuation.

For continuation, use `Table(..., overflow="continue")` as the slide's **entire
body**. The engine splits between complete rows, repeats headers and all slide
notes, and appends “(continued)” to subsequent titles. It measures widths once
using the whole table and preserves them across pages. Font sizes do not change.
The source `Deck` stays unchanged. Inspect `layout.slides` for the resulting
slide count and each slide/table's `continuation` metadata for source slide,
part count, and original data row range.

Nested continuation is currently rejected explicitly. Shrink can be used in
nested layouts; a table in a stack reserves following siblings' natural heights
before fitting. Several independently shrinking siblings are not a joint layout
optimization. A row too tall to fit with its header on a fresh continuation
slide raises `continuation_row_too_tall`. No rows or cells are split or omitted.

Run `python examples/table_overflow.py` for normal/warning fits, continuation,
and deliberate failures. See [the overflow design](docs/table-overflow.md) for
details and limitations. Ordered combinations of remedies are deferred.

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

See [the design note](docs/design.md) and [automatic sizing](docs/automatic-widths.md)
for architecture and limitations. Rich text, nested continuation, native charts,
and ordered overflow fallback policies are planned follow-on work.

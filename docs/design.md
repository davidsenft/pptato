# Initial design

pptato is a Python layout library for native, editable PowerPoint. Callers own
content and structure. The library owns geometry, spacing, measurement, and fit
diagnostics. The initial backend is python-pptx.

## Boundaries

- `model.py`: content, containers, theme, and the author-facing deck API.
- `measure.py`: font metrics and width-dependent text wrapping.
- `layout.py`: allocation, reserved slide regions, immutable resolved nodes,
  diagnostics, and JSON inspection.
- `renderers/pptx.py`: native text, bullets, tables, and individual images.

The model and engine do not import python-pptx. A resolved layout contains all
geometry, chosen line breaks, final text styles, table row heights, and image
bytes needed for rendering. The renderer must not make new fitting decisions.

## Terms and units

All geometry uses points: 72 points = 1 inch. The default canvas is 960 × 540
points (16:9). `Box` uses absolute slide coordinates. PowerPoint EMU conversion
happens at the renderer boundary.

`Stack` lays children out vertically at their measured heights. `Row` allocates
horizontal space; `Columns` is its presentation-oriented spelling. Children
receive equal widths or positive relative weights. Row alignment supports start,
center, and end against the tallest child. Containers have explicit padding and
gaps; there is no margin collapsing. Empty containers contribute only padding.

Text, headings, bullets, and tables take their natural measured heights. Images
reserve a specified height and contain the source image without cropping or
distortion. Remaining vertical space stays empty. No content is stretched or
shrunk implicitly.

## Resolution

1. Resolve theme and explicit font files.
2. Measure title and notes at the slide's inner width.
3. Anchor notes above the bottom margin and reserve their height plus a gap.
4. Allocate body columns, accounting for gaps and padding.
5. Measure each child at its allocated width. Stack measured heights vertically.
6. Reject any overflow with the content path and required/available dimensions.
7. Return an inspectable immutable layout, then render it separately.

Tables allocate column widths before measuring cells, including header boldness
and padding. Each row uses the maximum cell height. Both the native table and
the layout snapshot use those exact row heights.

Footnote objects are initially ordered, unnumbered slide notes. They reserve
space centrally. Inline markers, deduplication, table-local notes, and references
across continuation slides need a later semantic model.

## Measurement contract

The first measurer uses Pillow/FreeType with explicit regular and bold font
files. It measures at four pixels per point with BASIC layout, uses greedy word
wrapping, preserves explicit newline breaks (including blank lines), and
normalizes horizontal whitespace. It reserves two points at the right and
bottom of each text area. Bullet indents reduce available text width.

The renderer emits those breaks as soft breaks inside native paragraphs,
disables wrapping/autofit, and sets explicit font and line spacing. Text remains
editable. Manual edits in PowerPoint do not run pptato's layout engine; regenerate
from Python to reflow.

Geometry is deterministic given content, theme, size, font bytes, and measurement
runtime. Snapshots record font SHA-256 values, Pillow version, and algorithm ID.
The initial default chooses an installed known family and matching regular/bold
files; cross-machine reproducibility requires supplying the same files. Fonts
are not embedded. Identical geometry does not promise byte-identical ZIP output
or pixel-identical rendering in every office application.

This approximation must be checked against rendered examples. Font substitution,
complex scripts, bidirectional shaping, and unusual glyph fallback can change
appearance. The current measurer targets simple Latin text; it does not claim
general international typography support. Unbreakable words raise width errors.

## Initial scope and follow-on work

The first slice includes text, headings, simple bullets, nested stacks/rows,
weighted columns, notes, basic native tables, individual images, resolved boxes,
and strict overflow errors. Custom text styles allow deliberate font changes.

Next: automatic table/column widths with explicit bounds; bounded opt-in shrink;
table continuation with repeated headers and note scope; rich text; shared
caption/baseline alignment; and native charts. Keep these out of the initial
allocator until examples establish their contracts. In particular, do not
silently choose a new column count or omit content to make a slide fit.

A general constraint solver, full CSS emulation, template import, slide-type
catalog, Markdown input, AI integration, and UI are deferred.

## Validation

Tests cover allocation, width-dependent wrapping, footer/title reflow, nesting,
containment, deterministic snapshots, invalid constraints, and precise overflow
paths. PPTX tests reopen files to verify native tables, native bullets, preserved
text, and agreement with resolved geometry. Synthetic examples span prose,
tables, and images without depending on private source material.

Visual inspection is an integration check, separate from geometry assertions.
An office renderer may differ from the estimator even when all boxes fit.

# Automatic widths

`Table`, `Columns`, and `Row` accept `widths="auto"`. Their optional `bounds`
sequence contains one `ColumnWidth(minimum=0, maximum=None)` per column. Lengths
are points, including cell/container padding. Equal and weighted allocations
remain unchanged and reject nonempty bounds rather than silently ignoring them.

## Requirements

Text's intrinsic minimum is its longest unbreakable word, with the same safety
allowance and bullet indentation used by the renderer's measurement pass. Its
preferred width is its longest normalized hard line. Explicit newlines remain
breaks. Each table column takes the largest minimum and preferred widths across
its cells, including bold headers and padding.

For nested content, stacks take the widest child requirement; automatic rows
sum child requirements plus gaps and padding. Equal and weighted rows derive
the total width needed to satisfy every child's proportional share. Tables
participate as ordinary children of outer rows. Images have a preferred width
derived from their reserved height and aspect ratio, and can scale down; callers
can impose minimum widths for readability.

Explicit minima raise content minima. Explicit maxima cap preferences. A maximum
below the effective minimum raises a `width_constraints` diagnostic at that
column. If combined minima exceed the available width after gutters and padding,
allocation fails at the parent's `/columns` path. These checks precede rendering.

## Allocation heuristic

1. Start at the effective minima.
2. Sample 32 intervals between each minimum and its useful preferred width,
   limited by the total available budget and explicit maximum.
3. Measure a height profile at candidate widths. For a table, each profile holds
   a height for every row's cell; for a slide column it holds the whole subtree's
   height. Cache measurements within the allocation.
4. Repeatedly choose the candidate offering the largest overall height reduction
   per additional point of width. Overall height is the sum of row maxima for a
   table, or the tallest child for a row. Break ties by total content height
   reduction, then smaller width cost, then earlier column order. Evaluating
   candidates beyond the next sample crosses plateaus in line wrapping.
5. Distribute remaining space equally toward preferences, then toward maxima,
   redistributing shares whenever a column reaches its cap.
6. Compare with an equalized allocation constrained by the same minima/maxima.
   Keep the result with the lower overall height, then lower total content
   height. Retain the content-driven result on a complete tie.
7. Resolve all content at the final widths and run ordinary overflow checks.

The result is deterministic for the same inputs and fonts. The balanced fallback
ensures the chosen result does not score worse than a feasible equal-width
allocation under the same bounds. It does not guarantee a globally minimal
height. Changes in available width can select different sampled candidates.
For difficult layouts, callers can supply deliberate relative widths instead.
An ordinary height error describes the chosen layout, not a proof that every
possible allocation would fail. Automatic width sizing alone does not shrink
text, remove rows, alter the number of columns, or paginate. Explicit
[overflow policies](table-overflow.md) can opt into shrinking or continuation.

If total maxima leave unused width, tables occupy only the sum of their final
columns, aligned to the left of their allotted region. Rows retain their outer
box and leave the unused width after the last child. This honors hard maximum
constraints without treating whitespace as an error.

## Inspection and testing

Resolved row/table nodes include `column_widths` and `column_requirements` with
effective minimum, preferred, and maximum widths. These appear in JSON snapshots
alongside final row heights, boxes, and line breaks. Renderers consume resolved
geometry and do not run the allocator.

`examples/auto_widths.py` provides six synthetic slides. In the local Arial
reference run, the four-row description table falls from 305 pt tall with equal
widths to 173.75 pt with automatic widths, preserving every row and font size.
This is an example measurement, not a cross-platform golden value.

Tests cover prose beside numbers, identifiers, bold header metrics, explicit
breaks, bounds and combined-minimum failures, unused width, footer fit, nested
equal/weighted/auto containers, deterministic snapshots, and native PPTX column
width/row-height agreement. Synthetic profile tests exercise shared row
bottlenecks and budget/cap invariants without PowerPoint or fonts.

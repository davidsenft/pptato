# Explicit table overflow

The default `overflow="error"` preserves the authored font size and number of
slides. Remedies require an explicit choice on each table. No policy removes
content or silently falls back to another remedy.

## Bounded shrink

`overflow="shrink"` requires an explicit `TextFit(preferred, normal_min,
absolute_min)`. All three values must be finite, positive, and ordered:
`absolute_min <= normal_min <= preferred`. The preferred size is the requested
starting font size, overriding `Table.style.size` or the theme's table size.
Other style properties, padding, and constraints remain in force.

Candidate sizes descend from preferred in 0.25 pt steps. Both exact thresholds
are also candidates, including when they are off the quarter-point grid. The
engine tries candidates in descending order and takes the first that fits both
width and height. This selects the largest **tested** size, not the continuous
mathematical optimum. An exhaustive descending scan avoids assuming that the
automatic-width heuristic is monotonic in font size.

Each candidate runs the entire table allocation and text measurement process.
It recomputes auto column widths, wrapping, and row heights. The implementation
uses the existing native header boldness and body styling at the selected size.
Independent header/body sizes and rich text are not yet supported; when added,
they will require proportional scaling and separate readability floors.

At or above `normal_min`, rendering proceeds without a warning. Below it but
at or above `absolute_min`, rendering proceeds and records a `readability_warning`
diagnostic with severity `warning`. `LayoutWarning` also emits via Python's
warnings module so callers using only `deck.save()` see the compromise. Only
final successful layouts emit warnings, never speculative font candidates or
layouts that subsequently fail on another slide. Applications can inspect
`layout.diagnostics` or use standard Python warning filters.

Every successfully fitted table has `TableFit` metadata, including a table that
fits at preferred size. If no candidate fits, the last constraint failure is
retained with code `text_fit_limit`, the failed dimensions, and a suggestion to
increase space or explicitly choose another policy. The engine never renders
below the floor and never automatically creates a continuation slide.

Nested shrinking uses the table's allocated width and height. In a vertical
stack, following siblings reserve their natural heights before a directly
contained shrinking table is fitted. In automatic columns, intrinsic minima
reflect the permitted font floor; candidate profiles and final resolution still
select the largest allowed fitting font. Multiple shrinking siblings and deeply
nested container budgets are not globally optimized.

## Continuation

`overflow="continue"` currently requires a Table as the entire slide body.
Rejecting nested continuation is deliberate: duplicating commentary, dropping
sibling content, or deciding which headings belong to later pages needs a
separate contract. Users can put a continuing table on a dedicated slide today.

The engine measures the entire table once at its original font size, preserving
auto column widths, cell line breaks, and row striping across all fragments.
It fills each slide with the repeated header and as many whole data rows as fit.
It reserves title and notes before allocating rows. Subsequent titles append
`(continued)`; they are measured separately because they can wrap differently.
All slide notes repeat on each page. A blank source title becomes `Continued`
on later pages. Table-local or row-specific note scope is deferred.

A row that cannot fit with the repeated header on a fresh slide raises
`continuation_row_too_tall`. A header or title that cannot fit produces a normal
fit error. Horizontal overflow remains an error. Continuation neither shrinks
text nor splits the contents of a row. Header-only tables produce one page;
exact-fit tables do not create an empty trailing page.

Pagination expands only the resolved layout, leaving the authored `Deck` and
its tables unchanged. Output paths follow physical slide numbers. Each fragment
and its slide carry `Continuation` metadata: one-based original `source_slide`,
one-based `part`, total `parts`, and zero-based, end-exclusive data row bounds
`row_start`/`row_end`. Cell paths retain the original table row indices (header
row 0), so diagnostics and snapshots can trace data back to the source.

## Validation and future policies

Tests cover both threshold boundaries, off-grid sizes, largest-candidate
selection, width overflow, auto column remeasurement, nested fitting, warning
visibility, failed-layout behavior, preserved source data, page order, repeated
headers/notes, stable widths, row striping, and native PPTX sizes/content.

Ordered policies such as “shrink in the normal range, then continue” are deferred.
They must explicitly specify whether the warning band is used before pagination.
Combining `fit` with `overflow="continue"` is rejected rather than guessing.

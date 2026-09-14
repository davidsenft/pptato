import json
import os
import subprocess
import sys
from dataclasses import replace

import pytest

from pptato import (
    Bullets,
    Columns,
    Deck,
    Footnote,
    Heading,
    Image,
    LayoutError,
    Row,
    Spacer,
    Stack,
    Table,
    Text,
    TextStyle,
    Theme,
)


@pytest.fixture
def theme():
    return Theme()


def make_layout(theme, body=None, notes=(), title="Quarterly performance"):
    deck = Deck(theme=theme)
    deck.add_slide(
        title=title, body=body if body is not None else Text("A short result."), notes=notes
    )
    return deck.layout()


def find(layout, path):
    return next(n for n in layout.slides[0].walk() if n.path == path)


def test_notes_reserve_space_and_remain_at_bottom(theme):
    plain = make_layout(theme)
    short = make_layout(theme, notes=[Footnote("Source: example data.")])
    long = make_layout(theme, notes=[Footnote("Detailed methodological note. " * 35)])
    heights = [find(layout, "slide/1/body-region").box.height for layout in (plain, short, long)]
    assert heights[0] > heights[1] > heights[2]
    for layout in (short, long):
        footer = find(layout, "slide/1/notes").box
        assert footer.bottom == pytest.approx(540 - theme.margin)
        assert find(layout, "slide/1/body-region").box.bottom + theme.footer_gap == pytest.approx(
            footer.y
        )


@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_columns_fill_available_width(theme, count):
    layout = make_layout(theme, Columns([Text("Hello")] * count))
    body = find(layout, "slide/1/body")
    assert sum(n.box.width for n in body.children) + theme.gap * (count - 1) == pytest.approx(
        body.box.width
    )
    assert body.children[-1].box.right == pytest.approx(body.box.right)
    assert len({round(n.box.width, 6) for n in body.children}) == 1


def test_weights_and_narrower_columns_remeasure_text(theme):
    text = Text("A longer explanation needs more lines when its column becomes narrower. " * 3)
    layout = make_layout(theme, Columns([text, text], widths=[1, 2]))
    left, right = find(layout, "slide/1/body").children
    assert right.box.width == pytest.approx(2 * left.box.width)
    assert left.box.height > right.box.height


def test_longer_title_pushes_body_down(theme):
    short = make_layout(theme)
    long = make_layout(
        theme, title="Quarterly performance and an extended explanation of operating results " * 2
    )
    assert find(long, "slide/1/body-region").box.y > find(short, "slide/1/body-region").box.y


def test_margins_recompute_width_and_position(theme):
    small = make_layout(theme)
    large = make_layout(replace(theme, margin=60))
    a, b = (find(layout, "slide/1/body-region").box for layout in (small, large))
    assert b.x - a.x == 24
    assert a.width - b.width == 48


def test_stack_padding_gaps_and_row_alignment(theme):
    layout = make_layout(
        theme,
        Stack(
            [Row([Spacer(20), Spacer(60)], align="end", padding=5), Text("Next section")],
            padding=10,
            gap=7,
        ),
    )
    stack = find(layout, "slide/1/body")
    row, text = stack.children
    assert row.box.x == stack.box.x + 10
    assert row.children[0].box.bottom == row.children[1].box.bottom
    assert text.box.y == row.box.bottom + 7
    assert stack.box.bottom == text.box.bottom + 10


def test_table_rows_measure_wrapped_cells(theme):
    layout = make_layout(
        theme,
        Table(
            ["Item", "Comment"],
            [["One", "Short"], ["Two", "Longer comment that wraps across several lines. " * 8]],
            widths=[1, 3],
        ),
    )
    table = find(layout, "slide/1/body")
    assert table.row_heights[2] > table.row_heights[1]
    assert table.box.height == pytest.approx(sum(table.row_heights))
    assert len(table.children) == 6


def test_all_boxes_contained_and_siblings_do_not_overlap(theme):
    layout = make_layout(
        theme,
        Columns(
            [
                Stack([Heading("Context"), Bullets(["First observation", "Second observation"])]),
                Table(["Metric", "Value"], [["Volume", "42"], ["Rate", "17%"]]),
            ]
        ),
        notes=[Footnote("Synthetic data.")],
    )
    for parent in layout.slides[0].walk():
        for child in parent.children:
            assert child.box.x >= parent.box.x - 1e-6
            assert child.box.y >= parent.box.y - 1e-6
            assert child.box.right <= parent.box.right + 1e-6
            assert child.box.bottom <= parent.box.bottom + 1e-6
        for a, b in zip(parent.children, parent.children[1:]):
            assert a.box.right <= b.box.x + 1e-6 or a.box.bottom <= b.box.y + 1e-6


def test_overflow_reports_exact_content_path(theme):
    with pytest.raises(LayoutError) as error:
        make_layout(
            theme,
            Columns([Text("Fits"), Stack([Heading("Details"), Text("More content. " * 500)])]),
        )
    diagnostic = error.value.diagnostic
    assert diagnostic.path == "slide/1/body/1/1"
    assert diagnostic.axis == "height"
    assert diagnostic.required > diagnostic.available


def test_table_overflow_reports_row(theme):
    with pytest.raises(LayoutError, match="body/row/"):
        make_layout(theme, Table(["Name"], [[f"Row {i}"] for i in range(100)]))


def test_notes_can_make_previously_valid_body_fail(theme):
    body = Spacer(350)
    make_layout(theme, body)
    with pytest.raises(LayoutError):
        make_layout(theme, body, notes=[Footnote("A longer note. " * 100)])


def test_unbreakable_word_errors_without_clipping(theme):
    with pytest.raises(LayoutError) as error:
        make_layout(theme, Columns([Text("W" * 100), Text("Fits")]))
    assert error.value.diagnostic.axis == "width"
    assert "Unbreakable" in str(error.value)


def test_line_breaks_and_bullet_paragraphs_survive_measurement(theme):
    layout = make_layout(theme, Bullets(["First line\n\nThird line", "Next item"]))
    measured = find(layout, "slide/1/body").text
    assert measured.paragraphs[0].lines == ("First line", "", "Third line")
    assert len(measured.paragraphs) == 2
    assert all(p.bullet for p in measured.paragraphs)


def test_empty_containers_have_no_spurious_gaps(theme):
    for body in (Stack([]), Row([]), Bullets([])):
        assert find(make_layout(theme, body), "slide/1/body").box.height == 0


def test_repeated_layout_is_identical_and_serializable(theme, tmp_path):
    deck = Deck(theme=theme)
    deck.add_slide(title="Repeatable", body=Bullets(["One", "Two"]))
    first, second = deck.layout(), deck.layout()
    assert first == second
    path = tmp_path / "layout.json"
    first.write_json(path)
    assert json.loads(path.read_text()) == first.to_dict()
    assert len(dict(first.font_fingerprint)["regular_sha256"]) == 64


def test_image_preserves_aspect_and_snapshots_bytes(theme, tmp_path):
    from PIL import Image as PILImage

    path = tmp_path / "image.png"
    PILImage.new("RGB", (400, 100)).save(path)
    layout = make_layout(theme, Image(path, height=160))
    image = find(layout, "slide/1/body/picture")
    assert image.box.width / image.box.height == pytest.approx(4)
    path.unlink()
    layout.save(tmp_path / "saved.pptx")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Columns([Text("x")], widths=[0]),
        lambda: Columns([Text("x")], widths=[1, 2]),
        lambda: Columns([], widths="unsupported"),
        lambda: Stack([], gap=-1),
        lambda: Spacer(float("nan")),
        lambda: Table(["A", "B"], [["One"]]),
        lambda: TextStyle(size=0),
    ],
)
def test_invalid_constraints_fail_at_construction(factory):
    with pytest.raises(ValueError):
        factory()


def test_geometry_import_does_not_import_powerpoint():
    result = subprocess.run(
        [sys.executable, "-c", "import pptato; import sys; assert 'pptx' not in sys.modules"],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_excessive_gap_reports_positive_shortage(theme):
    with pytest.raises(LayoutError) as error:
        make_layout(theme, Stack([Text("One"), Text("Two")], gap=1000))
    assert error.value.diagnostic.required > error.value.diagnostic.available
    assert error.value.diagnostic.available > 0


def test_excessive_table_padding_reports_width_failure(theme):
    with pytest.raises(LayoutError, match="padding"):
        make_layout(replace(theme, cell_padding=500), Table(["A"], [[""]]))


def test_reserved_regions_cannot_consume_entire_slide(theme):
    with pytest.raises(LayoutError, match="reserved-regions"):
        make_layout(replace(theme, footer_gap=500), notes=[Footnote("Source")])


def test_extreme_finite_weights_do_not_overflow_arithmetic(theme):
    layout = make_layout(theme, Columns([Text("A"), Text("B")], widths=[1e308, 1e308]))
    a, b = find(layout, "slide/1/body").children
    assert a.box.width == b.box.width

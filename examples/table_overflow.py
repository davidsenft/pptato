"""Explicit table overflow policies: python examples/table_overflow.py."""

from dataclasses import replace
from pathlib import Path

from pptato import Deck, Footnote, LayoutError, Table, TextFit


def inventory(count: int) -> Table:
    return Table(
        ["Batch", "Description", "Files"],
        [
            [f"B-{index + 1:03}", "Regional source review", str(12 + index)]
            for index in range(count)
        ],
        widths="auto",
    )


def build_examples() -> Deck:
    deck = Deck()
    policy = TextFit(preferred=15, normal_min=12, absolute_min=10)
    deck.add_slide(
        title="Inventory: normal text range",
        body=replace(inventory(11), overflow="shrink", fit=policy),
        notes=[Footnote("Synthetic inventory. Text fitting is explicitly enabled.")],
    )
    deck.add_slide(
        title="Inventory: permitted warning range",
        body=replace(inventory(12), overflow="shrink", fit=policy),
        notes=[
            Footnote(
                "Synthetic inventory. The layout reports a readability warning for the selected size."
            )
        ],
    )
    deck.add_slide(
        title="Regional inventory",
        body=replace(inventory(24), overflow="continue"),
        notes=[Footnote("Synthetic inventory. Source notes repeat on every continuation slide.")],
    )
    return deck


def main() -> None:
    out = Path("outputs/table-overflow.pptx")
    out.parent.mkdir(exist_ok=True)
    layout = build_examples().layout()
    layout.save(out)
    layout.write_json(out.with_suffix(".layout.json"))
    for slide in layout.slides:
        for node in slide.walk():
            if node.table_fit:
                print(f"{node.path}: {node.table_fit}")
        if slide.continuation:
            print(f"{slide.path}: {slide.continuation}")
    for name, table in (
        ("strict default", inventory(24)),
        ("absolute minimum", replace(inventory(24), overflow="shrink", fit=TextFit())),
    ):
        deck = Deck()
        deck.add_slide(title="Expected failure", body=table)
        try:
            deck.layout()
        except LayoutError as error:
            print(f"Expected {name} diagnostic: {error}")
        else:
            raise AssertionError(f"Expected {name} to fail")
    print(f"Wrote {len(layout.slides)} slides to {out}")


if __name__ == "__main__":
    main()

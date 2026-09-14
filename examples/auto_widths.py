"""Demanding, synthetic width-allocation examples and expected failures.

Run: python examples/auto_widths.py
"""

from dataclasses import replace
from pathlib import Path

from pptato import (
    Bullets,
    Columns,
    ColumnWidth,
    Deck,
    Footnote,
    Heading,
    LayoutError,
    Stack,
    Table,
    Text,
    Theme,
)


def description_table() -> Table:
    return Table(
        ["Description", "Count", "Rate"],
        [
            [
                "Accounts that renewed after a temporary pause in service during the previous quarter.",
                "128",
                "24%",
            ],
            [
                "New accounts that completed onboarding and submitted their first monthly report.",
                "46",
                "18%",
            ],
            [
                "Existing accounts that expanded their subscription to include an additional region.",
                "73",
                "31%",
            ],
            [
                "Accounts awaiting a source-data correction before their next report can be issued.",
                "12",
                "9%",
            ],
        ],
    )


def build_examples() -> Deck:
    deck = Deck(theme=Theme())
    table = description_table()
    deck.add_slide(
        title="Account activity: equal widths",
        body=table,
        notes=[
            Footnote("Synthetic data. The next slide uses the same content with automatic widths.")
        ],
    )
    deck.add_slide(
        title="Account activity: automatic widths",
        body=replace(table, widths="auto"),
        notes=[Footnote("Synthetic data. All rows and font sizes match the preceding slide.")],
    )
    deck.add_slide(
        title="Processing status",
        body=Columns(
            [
                Table(
                    ["Identifier", "Status", "Count"],
                    [
                        ["NORTH-2026-000184", "Reviewed", "32"],
                        ["SOUTH-2026-000297", "Pending", "17"],
                        ["WEST-2026-000046", "Reviewed", "28"],
                    ],
                    widths="auto",
                ),
                Stack(
                    [
                        Heading("Review notes"),
                        Bullets(
                            [
                                "The southern region is waiting for the source owner to confirm a correction.",
                                "The remaining batches have completed their initial review.",
                            ]
                        ),
                    ]
                ),
            ],
            widths="auto",
            bounds=[ColumnWidth(minimum=330, maximum=560), ColumnWidth(minimum=240)],
        ),
        notes=[Footnote("Synthetic batches. Identifiers remain unbroken and editable.")],
    )
    deck.add_slide(
        title="Reporting coverage",
        body=Stack(
            [
                Table(
                    ["Region", "Files", "Checks"],
                    [
                        ["North", "24", "48"],
                        ["South", "17", "34"],
                        ["West", "31", "62"],
                    ],
                    widths="auto",
                    bounds=[
                        ColumnWidth(maximum=220),
                        ColumnWidth(maximum=110),
                        ColumnWidth(maximum=110),
                    ],
                ),
                Text(
                    "Each column has a maximum width. The table uses only the space those bounds allow."
                ),
            ]
        ),
        notes=[
            Footnote("Synthetic inventory. No columns stretch beyond their configured maximum.")
        ],
    )
    deck.add_slide(
        title="Measurement summary",
        body=Table(
            ["Observation window", "Adjusted observations", "Residual dispersion"],
            [
                ["Q1", "124", "0.18"],
                ["Q2", "138", "0.21"],
                ["Q3", "147", "0.16"],
            ],
            widths="auto",
        ),
        notes=[
            Footnote(
                "Synthetic measurements. Header text participates in sizing using its bold font."
            )
        ],
    )
    deck.add_slide(
        title="Account activity with methodological notes",
        body=replace(table, widths="auto"),
        notes=[
            Footnote(
                "Synthetic data. Counts represent fictional accounts and rates use unrelated illustrative denominators."
            ),
            Footnote(
                "Renewals include accounts that temporarily paused service. New accounts must complete onboarding before they enter the count. Regional expansions refer to changes in subscription coverage and can overlap with other categories."
            ),
            Footnote(
                "Pending corrections remain in the source inventory until a reviewer approves the update. The four categories are not mutually exclusive and should not be added together."
            ),
        ],
    )
    return deck


def main() -> None:
    output = Path("outputs/auto-widths.pptx")
    output.parent.mkdir(exist_ok=True)
    layout = build_examples().layout()
    layout.save(output)
    layout.write_json(output.with_suffix(".layout.json"))
    for slide in layout.slides:
        for node in slide.walk():
            if node.kind == "table":
                print(
                    f"{node.path}: widths={[round(w, 1) for w in node.column_widths]}, height={node.box.height:.1f} pt"
                )
    failures = [
        Table(
            ["Identifier", "Count"],
            [["UNBREAKABLE-IDENTIFIER-000142", "4"]],
            widths="auto",
            bounds=[ColumnWidth(maximum=80), ColumnWidth()],
        ),
        replace(
            description_table(),
            widths="auto",
            bounds=[ColumnWidth(minimum=700), ColumnWidth(minimum=150), ColumnWidth(minimum=150)],
        ),
    ]
    for table in failures:
        deck = Deck()
        deck.add_slide(title="Expected width failure", body=table)
        try:
            deck.layout()
        except LayoutError as error:
            print(f"Expected diagnostic: {error}")
        else:
            raise AssertionError("The deliberately impossible constraints unexpectedly fit")
    print(f"Wrote {len(layout.slides)} slides to {output}")


if __name__ == "__main__":
    main()

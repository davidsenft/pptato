"""Build synthetic examples: python examples/demo.py [--image chart.png]."""

from __future__ import annotations

import argparse
from pathlib import Path

from pptato import (
    Bullets,
    Columns,
    Deck,
    Footnote,
    Heading,
    Image,
    LayoutError,
    Stack,
    Table,
    Text,
    Theme,
)


def build_demo(image: Path | None = None) -> Deck:
    deck = Deck(theme=Theme())
    body = Columns(
        [
            Stack(
                [
                    Heading("Operating context"),
                    Bullets(
                        [
                            "Recurring contracts account for most of the quarter's revenue.",
                            "Support staffing remained stable as customer activity increased.",
                        ]
                    ),
                ]
            ),
            Stack(
                [
                    Heading("Quarterly results"),
                    Table(
                        headers=["Metric", "Actual", "Plan"],
                        rows=[
                            ["Revenue", "125", "120"],
                            ["Gross margin", "24%", "23%"],
                            ["New accounts", "48", "45"],
                        ],
                        widths=[2, 1, 1],
                    ),
                ]
            ),
        ],
        widths=[1, 1.15],
    )
    deck.add_slide(
        title="Quarterly performance",
        body=body,
        notes=[Footnote("Illustrative data. Revenue uses an arbitrary index.")],
    )
    deck.add_slide(
        title="Quarterly performance with additional notes",
        body=body,
        notes=[
            Footnote("Illustrative data. Revenue uses an arbitrary index."),
            Footnote(
                "Method: recurring contracts include renewals and committed subscriptions. "
                "New accounts include customers with an initial contract signed during the quarter. "
                "These synthetic figures demonstrate layout behavior and describe no actual business."
            ),
        ],
    )
    deck.add_slide(
        title="Research workstreams",
        body=Columns(
            [
                Stack(
                    [
                        Heading("Data collection"),
                        Text(
                            "The research team is checking source coverage "
                            "before it compares results across regions."
                        ),
                        Bullets(["Review source definitions", "Identify missing periods"]),
                    ]
                ),
                Stack(
                    [
                        Heading("Analysis"),
                        Text(
                            "The first comparison separates changes in volume "
                            "from changes in the population covered."
                        ),
                        Bullets(["Compare matched samples", "Review unusual observations"]),
                    ]
                ),
                Stack(
                    [
                        Heading("Publication"),
                        Text("The report will explain the assumptions alongside the results."),
                        Bullets(["Draft methods note", "Review figures with authors"]),
                    ]
                ),
            ]
        ),
        notes=[Footnote("Fictional research plan for demonstration.")],
    )
    deck.add_slide(
        title="Program status",
        body=Stack(
            [
                Table(
                    ["Workstream", "Status", "Next step"],
                    [
                        [
                            "Source inventory",
                            "Complete",
                            "Confirm ownership of the remaining historical files.",
                        ],
                        [
                            "Definition review",
                            "In progress",
                            "Resolve differences in how regional teams classify returning customers, including accounts that paused activity before renewing.",
                        ],
                        [
                            "Pilot report",
                            "Planned",
                            "Assemble a draft after the definition review closes.",
                        ],
                    ],
                    widths=[1.2, 1, 3],
                ),
                Text("The definition review determines when the pilot can begin."),
            ]
        ),
        notes=[Footnote("Fictional program status. Table row heights respond to wrapped text.")],
    )
    if image:
        deck.add_slide(
            title="Volume trend",
            body=Columns(
                [
                    Image(image, height=280),
                    Stack(
                        [
                            Heading("Observations"),
                            Bullets(
                                [
                                    "The example series increases across the four periods.",
                                    "The chart keeps its proportions within the allocated column.",
                                ]
                            ),
                        ]
                    ),
                ],
                widths=[1.5, 1],
            ),
            notes=[Footnote("Synthetic series for demonstration.")],
        )
    return deck


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", type=Path, default=Path(__file__).parent / "assets" / "volume.png"
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/demo.pptx"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    layout = build_demo(args.image).layout()
    layout.save(args.output)
    layout.write_json(args.output.with_suffix(".layout.json"))
    print(f"Wrote {len(layout.slides)} slides to {args.output}")
    impossible = Deck()
    impossible.add_slide(title="Overflow example", body=Bullets(["Too much content. " * 300]))
    try:
        impossible.layout()
    except LayoutError as error:
        print(f"Expected diagnostic: {error}")


if __name__ == "__main__":
    main()

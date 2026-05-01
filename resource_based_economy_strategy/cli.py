from __future__ import annotations

import argparse
import json

from resource_based_economy_strategy.scenarios import create_empty_map_settlement


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the resource-only economy simulation prototype."
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--people", type=int, default=6)
    parser.add_argument("--latitude", type=float, default=45.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settlement = create_empty_map_settlement(
        people=args.people,
        latitude=args.latitude,
        initial_resources={
            "food": args.people * 15.0,
            "water": args.people * 24.0,
            "wood": 30.0,
            "stone": 20.0,
        },
    )
    report = settlement.fast_forward(args.days)
    print(
        json.dumps(
            {
                "day": settlement.day,
                "people": settlement.people,
                "inventory": settlement.inventory,
                "average_needs_satisfied_ratio": (
                    report.average_needs_satisfied_ratio
                ),
                "unlocked_technologies": sorted(
                    settlement.unlocked_technologies
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

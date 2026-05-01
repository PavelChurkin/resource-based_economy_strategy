import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from resource_based_economy_strategy.scenarios import (
        create_empty_map_settlement,
    )

    settlement = create_empty_map_settlement(
        people=8,
        initial_resources={
            "food": 160,
            "water": 220,
            "wood": 40,
            "stone": 20,
        },
        latitude=50,
    )

    for _ in range(14):
        report = settlement.tick()
        print(
            f"day={report.day} people={report.population} "
            f"needs={report.needs_satisfied_ratio:.2f} "
            f"food={settlement.inventory.get('food', 0):.1f} "
            f"water={settlement.inventory.get('water', 0):.1f}"
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import TextIO

from resource_based_economy_strategy.scenarios import create_empty_map_settlement
from resource_based_economy_strategy.simulation import DayReport, Settlement


RESOURCE_NAMES = {
    "electricity": "электричество",
    "food": "еда",
    "grain": "зерно",
    "heat": "тепло",
    "herbs": "травы",
    "housing": "жильё",
    "iron_ore": "железная руда",
    "medicine": "лекарства",
    "plank": "доски",
    "roundwood": "кругляк",
    "sawdust": "опилки",
    "stone": "камень",
    "water": "вода",
    "wood": "древесина",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Запустить прототип ресурсной экономической стратегии."
    )
    parser.add_argument("--days", type=int, default=30, help="сколько дней сыграть")
    parser.add_argument("--people", type=int, default=6, help="начальное население")
    parser.add_argument("--latitude", type=float, default=45.0, help="широта старта")
    parser.add_argument("--seed", type=int, default=None, help="зерно генерации мира")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="пройти все дни без ожидания ввода",
    )
    return parser


def build_starting_settlement(
    people: int,
    latitude: float,
    seed: int | None,
) -> Settlement:
    return create_empty_map_settlement(
        people=people,
        latitude=latitude,
        seed=seed,
        initial_resources={
            "food": people * 15.0,
            "water": people * 24.0,
            "wood": 30.0,
            "stone": 20.0,
        },
    )


def run_managed_simulation(
    settlement: Settlement,
    *,
    days: int,
    auto: bool = False,
    input_func: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> str:
    if days < 0:
        raise ValueError("Количество дней не может быть отрицательным")
    if output is None:
        import sys

        output = sys.stdout

    reason = "Заданное количество дней завершено."
    print("Ресурсная стратегия 0.01", file=output)
    print(
        "Цель: сохранить жизнь поселения без денег, только через ресурсы.",
        file=output,
    )
    print('Введите "0", чтобы завершить игру досрочно.', file=output)
    print(_format_inventory(settlement.inventory), file=output)

    for _ in range(days):
        if settlement.people <= 0:
            reason = "Игра окончена: все жители погибли."
            break
        if not auto:
            command = input_func("Enter — следующий день, 0 — выход: ").strip()
            if command == "0":
                reason = 'Игра завершена пользователем командой "0".'
                break
        report = settlement.tick()
        print(_format_day_report(report, settlement), file=output)
        if settlement.people <= 0:
            reason = "Игра окончена: все жители погибли."
            break

    print(reason, file=output)
    print(_format_inventory(settlement.inventory), file=output)
    return reason


def _format_day_report(report: DayReport, settlement: Settlement) -> str:
    needs_percent = report.needs_satisfied_ratio * 100
    parts = [
        f"День {report.day}",
        f"жители: {report.population}",
        f"потребности: {needs_percent:.0f}%",
    ]
    if report.deaths:
        parts.append(f"смерти: {report.deaths}")
    if report.births:
        parts.append(f"рождения: {report.births}")
    if report.missing_needs:
        parts.append(f"не хватает: {_format_resources(report.missing_needs)}")
    if report.unlocked_technologies:
        parts.append(f"открыты технологии: {', '.join(report.unlocked_technologies)}")
    parts.append(
        f"еда: {settlement.inventory.get('food', 0.0):.1f}, "
        f"вода: {settlement.inventory.get('water', 0.0):.1f}"
    )
    return " | ".join(parts)


def _format_inventory(inventory: dict[str, float]) -> str:
    return f"Склад: {_format_resources(inventory)}"


def _format_resources(resources: dict[str, float]) -> str:
    if not resources:
        return "пусто"
    return ", ".join(
        f"{RESOURCE_NAMES.get(resource, resource)} {amount:.1f}"
        for resource, amount in sorted(resources.items())
    )


def main() -> None:
    args = build_parser().parse_args()
    settlement = build_starting_settlement(
        people=args.people,
        latitude=args.latitude,
        seed=args.seed,
    )
    run_managed_simulation(settlement, days=args.days, auto=args.auto)


if __name__ == "__main__":
    main()

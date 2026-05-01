import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from game1.tech_tree import (
    Condition,
    TechTree,
    Technology,
    load_tech_tree,
    parse_tech_tree,
)


SAMPLE_PAYLOAD = {
    "технологии": [
        {
            "название": "Колесо",
            "описание": "Базовая технология транспорта.",
            "условия": [],
        },
        {
            "название": "Двигатель внутреннего сгорания",
            "описание": "ДВС.",
            "условия": ["Бензин", "Колесо"],
        },
        {
            "название": "Автомобиль",
            "описание": "Транспорт.",
            "условия": [
                "Двигатель внутреннего сгорания",
                "Бензин",
                "Листовой корпус",
            ],
        },
        {
            "название": "Абразив",
            "описание": "",
            "условия": [["Карбид кремния"], ["Алмаз"]],
        },
    ]
}


class TechTreeTests(unittest.TestCase):
    def test_parse_flat_and_nested_conditions(self) -> None:
        tree = parse_tech_tree(SAMPLE_PAYLOAD)
        self.assertEqual(len(tree), 4)
        car = tree["Автомобиль"]
        self.assertEqual(len(car.conditions), 1)
        self.assertEqual(
            car.conditions[0].requires_all,
            (
                "Двигатель внутреннего сгорания",
                "Бензин",
                "Листовой корпус",
            ),
        )
        abrasive = tree["Абразив"]
        self.assertEqual(len(abrasive.conditions), 2)
        self.assertEqual(abrasive.conditions[0].requires_all, ("Карбид кремния",))
        self.assertEqual(abrasive.conditions[1].requires_all, ("Алмаз",))

    def test_root_technologies_have_no_conditions(self) -> None:
        tree = parse_tech_tree(SAMPLE_PAYLOAD)
        roots = tree.roots()
        self.assertEqual([t.name for t in roots], ["Колесо"])

    def test_or_of_and_conditions(self) -> None:
        tree = parse_tech_tree(SAMPLE_PAYLOAD)
        self.assertTrue(tree.is_unlocked("Абразив", {"Карбид кремния"}))
        self.assertTrue(tree.is_unlocked("Абразив", {"Алмаз"}))
        self.assertFalse(tree.is_unlocked("Абразив", set()))

    def test_newly_unlockable(self) -> None:
        tree = parse_tech_tree(SAMPLE_PAYLOAD)
        unlocked = {"Колесо", "Бензин"}
        candidates = tree.newly_unlockable(unlocked)
        self.assertIn("Двигатель внутреннего сгорания", candidates)
        self.assertNotIn("Колесо", candidates)
        self.assertNotIn("Автомобиль", candidates)

    def test_unknown_dependencies_lists_missing_nodes(self) -> None:
        tree = parse_tech_tree(SAMPLE_PAYLOAD)
        missing = tree.unknown_dependencies()
        self.assertIn("Бензин", missing)
        self.assertIn("Листовой корпус", missing)
        self.assertNotIn("Колесо", missing)

    def test_load_tech_tree_from_disk(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "techno.json"
            path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")
            tree = load_tech_tree(path)
            self.assertIsInstance(tree, TechTree)
            self.assertEqual(len(tree), 4)

    def test_invalid_payload_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_tech_tree({})
        with self.assertRaises(ValueError):
            parse_tech_tree({"технологии": "not a list"})
        with self.assertRaises(ValueError):
            parse_tech_tree({"технологии": [{"название": ""}]})

    def test_technology_unlock_with_no_conditions(self) -> None:
        tech = Technology(name="Root", description="", conditions=())
        self.assertTrue(tech.is_unlocked(set()))

    def test_condition_satisfied_by(self) -> None:
        cond = Condition(requires_all=("a", "b"))
        self.assertTrue(cond.satisfied_by({"a", "b", "c"}))
        self.assertFalse(cond.satisfied_by({"a"}))


if __name__ == "__main__":
    unittest.main()

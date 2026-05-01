"""Tech tree loader compatible with the external ``techno2.json`` schema.

The schema in
https://github.com/PavelChurkin/tech_tree0.4/blob/main/techno2.json
uses Russian field names::

    {
      "технологии": [
        {
          "название": "<name>",
          "описание": "<description>",
          "условия": [...]   // list of strings or list-of-lists
        }
      ]
    }

``условия`` (conditions) can be either a flat list of names — interpreted as
AND — or a list of lists, interpreted as OR-of-AND. The loader normalises
both forms into ``Condition`` objects so the simulation can ask
``tech_tree.is_unlocked("Автомобиль", unlocked={"Двигатель внутреннего сгорания", ...})``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping
import json


@dataclass(frozen=True)
class Condition:
    """A conjunction of required technology names."""

    requires_all: tuple[str, ...]

    def satisfied_by(self, unlocked: Iterable[str]) -> bool:
        unlocked_set = set(unlocked)
        return all(name in unlocked_set for name in self.requires_all)


@dataclass(frozen=True)
class Technology:
    """A single technology node.

    ``conditions`` is a disjunction of ``Condition`` objects: the technology
    is unlocked if ANY of its conditions is fully satisfied.
    """

    name: str
    description: str
    conditions: tuple[Condition, ...]

    def is_unlocked(self, unlocked: Iterable[str]) -> bool:
        if not self.conditions:
            return True  # root technologies have no prerequisites
        return any(condition.satisfied_by(unlocked) for condition in self.conditions)


@dataclass
class TechTree:
    """Collection of technologies indexed by name."""

    technologies: dict[str, Technology] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.technologies)

    def __contains__(self, name: str) -> bool:
        return name in self.technologies

    def __getitem__(self, name: str) -> Technology:
        return self.technologies[name]

    def names(self) -> list[str]:
        return list(self.technologies.keys())

    def roots(self) -> list[Technology]:
        return [tech for tech in self.technologies.values() if not tech.conditions]

    def is_unlocked(self, name: str, unlocked: Iterable[str]) -> bool:
        if name not in self.technologies:
            raise KeyError(f"unknown technology {name!r}")
        return self.technologies[name].is_unlocked(unlocked)

    def newly_unlockable(self, unlocked: Iterable[str]) -> list[str]:
        unlocked_set = set(unlocked)
        result: list[str] = []
        for name, tech in self.technologies.items():
            if name in unlocked_set:
                continue
            if tech.is_unlocked(unlocked_set):
                result.append(name)
        return result

    def unknown_dependencies(self) -> set[str]:
        """Return condition names that do not match any technology in the tree.

        ``techno2.json`` may reference names that are themselves not yet
        defined as nodes (basic raw materials, for example). Surfacing these
        helps the simulation seed an initial inventory.
        """

        known = set(self.technologies.keys())
        missing: set[str] = set()
        for tech in self.technologies.values():
            for condition in tech.conditions:
                for name in condition.requires_all:
                    if name not in known:
                        missing.add(name)
        return missing


def _normalise_conditions(raw: object) -> tuple[Condition, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"условия must be a list, got {type(raw).__name__}")
    if not raw:
        return ()

    # Detect OR-of-AND form: list of lists.
    if all(isinstance(item, list) for item in raw):
        return tuple(
            Condition(requires_all=tuple(str(name) for name in group))
            for group in raw
            if group
        )

    # Otherwise it's a flat AND list.
    if all(isinstance(item, str) for item in raw):
        return (Condition(requires_all=tuple(raw)),)

    raise ValueError(
        "условия must be a flat list of strings or a list of lists of strings"
    )


def parse_tech_tree(payload: Mapping[str, object]) -> TechTree:
    """Parse a dictionary already loaded from ``techno2.json``."""

    raw_list = payload.get("технологии")
    if raw_list is None:
        raise ValueError("payload missing 'технологии' field")
    if not isinstance(raw_list, list):
        raise ValueError("'технологии' must be a list")

    tree = TechTree()
    for entry in raw_list:
        if not isinstance(entry, dict):
            raise ValueError("each technology entry must be an object")
        name = entry.get("название")
        if not isinstance(name, str) or not name:
            raise ValueError("each technology entry needs a non-empty 'название'")
        description = entry.get("описание", "") or ""
        if not isinstance(description, str):
            raise ValueError("'описание' must be a string when provided")
        conditions = _normalise_conditions(entry.get("условия"))
        tree.technologies[name] = Technology(
            name=name,
            description=description,
            conditions=conditions,
        )
    return tree


def load_tech_tree(path: str | Path) -> TechTree:
    """Load and parse a ``techno2.json`` style file from disk."""

    text = Path(path).read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("tech tree file must contain a JSON object at the top level")
    return parse_tech_tree(payload)

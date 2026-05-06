"""Export a static WebGL viewer for the spherical point cloud (issue #11).

Run with::

    python examples/run_webgl_planet_viewer.py
    python examples/run_webgl_planet_viewer.py --counts 4000,40000,400000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_counts(value: str) -> tuple[int, ...]:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("at least one count is required")
    counts: list[int] = []
    for part in parts:
        try:
            number = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"count must be an integer, got {part!r}"
            ) from exc
        if number < 1:
            raise argparse.ArgumentTypeError("each count must be positive")
        counts.append(number)
    return tuple(sorted(set(counts)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a static WebGL2 viewer that renders the planet as a "
            "spherical point cloud with multi-LOD switching."
        ),
    )
    parser.add_argument(
        "--counts",
        type=_parse_counts,
        default=(2_000, 20_000, 200_000),
        help=(
            "comma-separated point counts per LOD, lowest first. "
            "Defaults to 2000,20000,200000."
        ),
    )
    parser.add_argument(
        "--target-logical-count",
        type=int,
        default=10_000_000,
        help=(
            "logical (server-side) point count the LOD ladder represents. "
            "Defaults to 10 million."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/webgl_planet_viewer.html"),
        help="HTML output path",
    )
    return parser


def main() -> None:
    from game1.webgl_planet_viewer import write_webgl_viewer_html

    args = build_parser().parse_args()
    output_path = write_webgl_viewer_html(
        args.output,
        counts=args.counts,
        target_logical_count=args.target_logical_count,
    )
    print(output_path)


if __name__ == "__main__":
    main()

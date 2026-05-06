"""Export a static interactive viewer for the ISEA3H hex sphere.

Run with::

    python examples/run_hex_sphere_viewer.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_resolutions(value: str) -> tuple[int, ...]:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("at least one resolution is required")
    resolutions: list[int] = []
    for part in parts:
        try:
            number = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"resolution must be an integer, got {part!r}"
            ) from exc
        if number < 0 or number % 2:
            raise argparse.ArgumentTypeError(
                "render resolutions must be non-negative even integers"
            )
        resolutions.append(number)
    return tuple(sorted(set(resolutions)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a static ISEA3H hex-sphere viewer with LOD layers."
    )
    parser.add_argument(
        "--resolutions",
        type=_parse_resolutions,
        default=(2, 4, 6),
        help=(
            "comma separated even ISEA3H render resolutions, lowest first. "
            "Defaults to 2,4,6 which yields 92 / 812 / 7292 cells per LOD."
        ),
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=None,
        help=(
            "deprecated: render a single resolution instead of the LOD ladder. "
            "When provided it overrides --resolutions."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/hex_sphere_viewer.html"),
        help="HTML output path",
    )
    return parser


def main() -> None:
    from game1.hex_sphere_viewer import write_lod_viewer_html

    args = build_parser().parse_args()
    resolutions = (
        (args.resolution,) if args.resolution is not None else args.resolutions
    )
    output_path = write_lod_viewer_html(
        args.output,
        grid_resolutions=resolutions,
    )
    print(output_path)


if __name__ == "__main__":
    main()

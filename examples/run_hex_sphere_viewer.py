"""Export a static interactive viewer for the ISEA3H hex sphere.

Run with::

    python examples/run_hex_sphere_viewer.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a static ISEA3H hex-sphere viewer."
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=4,
        help="even ISEA3H render resolution; 4 renders 812 cells",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/hex_sphere_viewer.html"),
        help="HTML output path",
    )
    return parser


def main() -> None:
    from game1.hex_sphere import build_hex_sphere_mesh
    from game1.hex_sphere_viewer import write_viewer_html

    args = build_parser().parse_args()
    mesh = build_hex_sphere_mesh(grid_resolution=args.resolution)
    output_path = write_viewer_html(args.output, mesh)
    print(output_path)


if __name__ == "__main__":
    main()

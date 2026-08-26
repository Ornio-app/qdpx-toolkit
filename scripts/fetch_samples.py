#!/usr/bin/env python3
"""Fetch real-world REFI-QDA (.qdpx) sample files on demand.

This script is deliberately a placeholder. As of writing, neither
qdasoftware.org nor the two obvious open-source REFI-QDA implementations
(QualCoder, https://github.com/ccbogel/QualCoder; OpenQDA refi-tools,
https://github.com/openqda/refi-tools) ship a sample .qdpx or .qde file
with a licence clear enough to vendor into this repository's test suite --
see the top-level project report / commit message for exactly what was
checked and when. `tests/fixtures/hand_authored/` is a small, hand-built
substitute used by the unit test suite instead.

Rather than silently having no path to real samples at all, this script
gives contributors one place to register a downloadable URL once a
suitable sample is found (a vendor's own published example, a
CC0/permissively-licensed research dataset, etc.), and a consistent
target directory (gitignored) to fetch it into.

Usage:

    python scripts/fetch_samples.py                 # fetch everything registered below
    python scripts/fetch_samples.py --list           # show what would be fetched
    python scripts/fetch_samples.py --dest DIR        # fetch into a custom directory

Add entries to SAMPLES below as they are found. Each entry MUST record
the source URL and the licence you verified it under -- do not add a URL
without checking the licence first; that is the whole reason this is a
script and not just a README link.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DEST = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / ".downloaded"


@dataclass(frozen=True)
class Sample:
    filename: str
    url: str
    license: str
    note: str = ""


# No sample is registered yet -- see the module docstring. Add entries
# like the (illustrative, non-functional) example below once a real one
# with a clear licence is found:
#
# Sample(
#     filename="example_study.qdpx",
#     url="https://example.org/downloads/example_study.qdpx",
#     license="CC0-1.0",
#     note="Public example project published by <source>.",
# ),
SAMPLES: tuple[Sample, ...] = ()


def fetch(sample: Sample, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / sample.filename
    print(f"Fetching {sample.filename} ({sample.license}) from {sample.url} ...")
    urllib.request.urlretrieve(sample.url, dest_path)
    print(f"  -> {dest_path}")
    return dest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"directory to download into (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--list", action="store_true", help="list registered samples without downloading"
    )
    args = parser.parse_args(argv)

    if not SAMPLES:
        print(
            "No samples are registered in scripts/fetch_samples.py yet. "
            "See its module docstring for why, and how to add one once a "
            "suitably-licensed real .qdpx is found.",
            file=sys.stderr,
        )
        return 1

    if args.list:
        for sample in SAMPLES:
            print(f"{sample.filename}  [{sample.license}]  {sample.url}")
        return 0

    for sample in SAMPLES:
        fetch(sample, args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

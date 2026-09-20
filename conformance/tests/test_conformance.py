"""Conformance test suite driver. See ../README.md for the methodology.

Auto-discovers whatever `.qdpx` fixtures exist under
`conformance/fixtures/{seed,nvivo,atlasti,maxqda}/` and:

* skips cleanly, with a reason naming the missing directory, when a
  category has no fixtures yet (so this suite is green today and does not
  need editing once real exports land -- it just starts doing something);
* parses every fixture found, which is itself a conformance finding if a
  vendor export doesn't parse;
* when both the canonical seed and a vendor export exist, structurally
  diffs them (see conformance/diffing.py) and writes a Markdown report to
  conformance/reports/, per SPEC.md §1.2 step 6 ("not just pass/fail, but
  exactly what is lost and where").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conformance.diffing import diff_projects
from refi_qda.parser import parse_qdpx

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = CONFORMANCE_DIR / "fixtures"
REPORTS_DIR = CONFORMANCE_DIR / "reports"

SEED_DIR = FIXTURES_DIR / "seed"
TOOL_DIRS = {
    "nvivo": FIXTURES_DIR / "nvivo",
    "atlasti": FIXTURES_DIR / "atlasti",
    "maxqda": FIXTURES_DIR / "maxqda",
}


def _discover(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.qdpx") if p.is_file())


def _params(directory: Path, label: str) -> list[object]:
    """Build parametrize params, or a single skipped placeholder if none found."""
    found = _discover(directory)
    if not found:
        relative = directory.relative_to(CONFORMANCE_DIR.parent)
        return [
            pytest.param(
                None,
                id=f"{label}-no-fixtures",
                marks=pytest.mark.skip(
                    reason=f"No fixtures in {relative}/ yet -- see {relative}/README.md."
                ),
            )
        ]
    return [pytest.param(p, id=p.name) for p in found]


# --------------------------------------------------------------------------
# Seed: parses on its own, no baseline to diff against.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _params(SEED_DIR, "seed"))
def test_seed_project_parses(qdpx_path: Path | None) -> None:
    assert qdpx_path is not None  # only reached when a real fixture exists
    project = parse_qdpx(qdpx_path)
    assert project.sources or project.codebook, (
        "Seed project parsed but has no sources and no codebook -- "
        "that's not a representative seed project per SPEC.md §1.2 step 1."
    )


# --------------------------------------------------------------------------
# Per-tool exports: parse, and diff against the seed when both exist.
# --------------------------------------------------------------------------


def _make_tool_test(tool: str, directory: Path):  # type: ignore[no-untyped-def]
    @pytest.mark.parametrize("qdpx_path", _params(directory, tool))
    def _test(qdpx_path: Path | None) -> None:
        assert qdpx_path is not None  # only reached when a real fixture exists
        exported_project = parse_qdpx(qdpx_path)

        seed_candidates = _discover(SEED_DIR)
        if not seed_candidates:
            pytest.skip(
                f"{qdpx_path.name} parsed successfully, but no seed project is present "
                "in conformance/fixtures/seed/ to diff it against."
            )

        seed_project = parse_qdpx(seed_candidates[0])
        report = diff_projects(seed_project, exported_project)

        REPORTS_DIR.mkdir(exist_ok=True)
        report_path = REPORTS_DIR / f"{tool}__{qdpx_path.stem}__vs__seed.md"
        report_path.write_text(report.render())

        # This suite documents divergence; it does not gate on it. A vendor
        # export that parses but diverges from the seed is exactly the
        # finding this project exists to publish (see README.md "Why this
        # exists"), not a bug in this test suite.
        if not report.is_lossless:
            print(f"\n{report.render()}\n(full report written to {report_path})")

    _test.__name__ = f"test_{tool}_export_vs_seed"
    return _test


for _tool, _directory in TOOL_DIRS.items():
    globals()[f"test_{_tool}_export_vs_seed"] = _make_tool_test(_tool, _directory)
del _tool, _directory

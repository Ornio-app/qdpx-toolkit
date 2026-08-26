"""Shared pytest fixtures for refi_qda's test suite.

The primary fixture, ``sample_qdpx_path``, zips a small, hand-authored but
structurally rich REFI-QDA project (committed under
``tests/fixtures/hand_authored/``) into a real ``.qdpx`` file at test time.
No real vendor-exported ``.qdpx`` sample was available with a licence
clear enough to vendor (see the top-level README/report); this fixture
exists so the parser/container test suite is real and non-trivial rather
than a smoke test against synthetic in-memory XML.

The fixture covers: a three-level code hierarchy (folder > code > child
code), two deliberately overlapping text selections, all five source
types, a PDF selection with an inline text representation, an audio
transcript with sync points, mixed-type case variables (integer +
boolean), sets, links, notes, graphs, and both ``relative://`` and
``absolute://`` external source references.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "hand_authored"
SAMPLE_QDE_PATH = FIXTURES_DIR / "project.qde"
SAMPLE_SOURCES_DIR = FIXTURES_DIR / "sources"


@pytest.fixture
def sample_qdpx_path(tmp_path: Path) -> Path:
    """Path to a freshly zipped copy of the hand-authored sample project."""
    dest = tmp_path / "sample_study.qdpx"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(SAMPLE_QDE_PATH, "project.qde")
        for source_file in sorted(SAMPLE_SOURCES_DIR.iterdir()):
            zf.write(source_file, f"sources/{source_file.name}")
    return dest


@pytest.fixture
def sample_qde_bytes() -> bytes:
    """Raw bytes of the hand-authored sample project's ``project.qde``."""
    return SAMPLE_QDE_PATH.read_bytes()


@pytest.fixture
def nested_sources_qdpx_path(tmp_path: Path) -> Path:
    """A ``.qdpx`` whose ``sources/`` folder is not flat (violates REFI-QDA 8.1)."""
    dest = tmp_path / "nested_sources.qdpx"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(SAMPLE_QDE_PATH, "project.qde")
        zf.writestr("sources/subfolder/nested.txt", "this should not be allowed")
    return dest


@pytest.fixture
def missing_qde_qdpx_path(tmp_path: Path) -> Path:
    """A ``.qdpx``-shaped ZIP with no ``project.qde`` at all."""
    dest = tmp_path / "missing_qde.qdpx"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", "oops, no project.qde in here")
    return dest

"""Pins the ATLAS.ti 26 findings documented in ``../fixtures/atlasti/README.md``.

This module exists so that two things cannot happen quietly:

1. **The container-filename defect cannot be "fixed" without a decision.**
   ATLAS.ti 26 names the XML inside a ``.qdpx`` after the *project* rather
   than ``project.qde``, which REFI-QDA v1.5 p.21 and §8.1 require. That
   stops :func:`refi_qda.parser.parse_qdpx` from opening a real ATLAS.ti
   export at all. :func:`test_public_api_cannot_open_atlasti_export` is
   marked ``xfail(strict=True)``, so relaxing the container check turns
   this test into an ``XPASS`` *failure* rather than a silent green tick.
   That is deliberate: see "Open design question" in the fixtures README.
   There are at least four reasonable ways to resolve it and this suite
   should not pick one by accident.

2. **The findings cannot regress silently.** The remaining tests are
   characterisation tests -- they assert what ATLAS.ti *actually* does
   today (memos flattened to ``<Description>``, GUIDs reassigned on every
   export, a zero-length selection), not what it ought to do. If a later
   ATLAS.ti build changes any of this, these fail and the README needs
   updating. A failure here is a finding, not necessarily a bug.

Nothing in this module tests the three risk areas named in SPEC.md §1.3
(overlapping selections, nested codes, character offsets). Neither fixture
exercises them -- see the fixtures README's "Known gaps" section.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from refi_qda.container import QDE_FILENAME
from refi_qda.exceptions import ContainerError
from refi_qda.model import VideoSelection, VideoSource
from refi_qda.parser import parse_qde, parse_qdpx

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "atlasti"

BASELINE = FIXTURES_DIR / "atlasti_26_handbuilt_01_baseline.qdpx"
CODES_MEMOS = FIXTURES_DIR / "atlasti_26_handbuilt_02_codes_memos.qdpx"

#: The name REFI-QDA requires, and the name ATLAS.ti 26 actually writes.
EXPECTED_QDE_NAME = QDE_FILENAME
ACTUAL_QDE_NAME = "Trial.qde"

_ALL_FIXTURES = [BASELINE, CODES_MEMOS]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _ALL_FIXTURES),
    reason=(
        "ATLAS.ti fixtures are missing from conformance/fixtures/atlasti/ -- "
        "see that directory's README.md."
    ),
)


def _read_qde_bypassing_container(qdpx_path: Path) -> bytes:
    """Read the one ``*.qde`` member directly, ignoring what it is named.

    Deliberately does *not* go through :class:`refi_qda.container.QdpxContainer`:
    the whole point of these fixtures is that the container layer rejects
    them, and we still need to get at the payload to show the payload is
    fine.
    """
    with zipfile.ZipFile(qdpx_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".qde")]
        assert len(members) == 1, f"{qdpx_path.name} should hold exactly one .qde, got {members}"
        return archive.read(members[0])


# --------------------------------------------------------------------------
# 1. The defect itself.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
@pytest.mark.xfail(
    strict=True,
    raises=ContainerError,
    reason=(
        "ATLAS.ti 26 names the archive's XML after the project (e.g. 'Trial.qde'), "
        "not 'project.qde' as REFI-QDA v1.5 p.21/§8.1 require, so parse_qdpx cannot "
        "open a real ATLAS.ti export. strict=True is intentional: if you relax the "
        "container check this test XPASSes and the suite FAILS, because whether to "
        "accept any single *.qde is an open design question, not a settled bug. "
        "Read 'Open design question' in conformance/fixtures/atlasti/README.md first."
    ),
)
def test_public_api_cannot_open_atlasti_export(qdpx_path: Path) -> None:
    parse_qdpx(qdpx_path)


def test_inner_qde_is_named_after_the_project_not_the_archive() -> None:
    """The workaround of guessing the name from the archive is not available.

    ``atlasti_26_handbuilt_02_codes_memos.qdpx`` was exported from ATLAS.ti
    to a file the user named ``Project.qdpx`` and *still* contains
    ``Trial.qde`` -- the inner name tracks the ATLAS.ti project name, which
    a reader has no way to know in advance.
    """
    for qdpx_path in _ALL_FIXTURES:
        with zipfile.ZipFile(qdpx_path) as archive:
            assert archive.namelist() == [ACTUAL_QDE_NAME], (
                f"{qdpx_path.name} no longer contains exactly [{ACTUAL_QDE_NAME!r}] -- "
                "if ATLAS.ti changed its naming, update the fixtures README."
            )
            assert EXPECTED_QDE_NAME not in archive.namelist()


# --------------------------------------------------------------------------
# 2. The payload is fine. Only the container check fails.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_payload_parses_once_the_container_check_is_bypassed(qdpx_path: Path) -> None:
    """Establishes that the filename is the *only* thing wrong with these files."""
    project = parse_qde(_read_qde_bypassing_container(qdpx_path))
    assert project.name == "Trial"
    assert project.origin is not None and project.origin.startswith("ATLAS.ti 26.1.2")
    assert len(project.sources) == 1
    assert isinstance(project.sources[0], VideoSource)


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_payload_is_schema_valid(qdpx_path: Path) -> None:
    """Both exports validate against the REFI-QDA Project v1.0 XSD.

    Skipped when no schema is configured: the XSD is not vendored in this
    repository (see ``schema/README.md``), so CI without one still runs
    everything else in this module.
    """
    pytest.importorskip("lxml")
    from refi_qda.validator import validate

    configured = os.environ.get("REFI_QDA_SCHEMA_PATH")
    schema_path = Path(configured) if configured else Path("schema/refi-qda-project-1.0.xsd")
    if not schema_path.is_file():
        pytest.skip(
            f"No REFI-QDA XSD at {schema_path} -- run scripts/fetch_schema.py or set "
            "REFI_QDA_SCHEMA_PATH. See schema/README.md."
        )

    validate(_read_qde_bypassing_container(qdpx_path), schema_path=schema_path)


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_read_write_read_is_lossless(qdpx_path: Path) -> None:
    """Round-trip fidelity, per SPEC.md §1.2 step 4."""
    from refi_qda.writer import to_qde

    original = parse_qde(_read_qde_bypassing_container(qdpx_path))
    assert parse_qde(to_qde(original)) == original


# --------------------------------------------------------------------------
# 3. Characterisation of what ATLAS.ti 26 actually exports.
# --------------------------------------------------------------------------


def _codes_memos_project():  # type: ignore[no-untyped-def]
    return parse_qde(_read_qde_bypassing_container(CODES_MEMOS))


def test_memos_are_flattened_to_description_losing_author_and_date() -> None:
    """SPEC.md §1.3's memo risk area, as it actually manifests.

    REFI-QDA models a memo as a ``<Note>`` of type ``TextSourceType``
    (spec §3.9, "A note is a text source") referenced via ``<NoteRef>``,
    carrying a GUID, an author and timestamps. ATLAS.ti exports quotation
    comments as bare ``<Description>`` strings instead, so the memo stops
    being an addressable object: who wrote it and when are unrecoverable.
    """
    project = _codes_memos_project()
    source = project.sources[0]

    described = [s for s in source.selections if s.description]
    assert len(described) == 3, "expected 3 quotation comments in fixture 02"

    # The comments exist as text...
    assert {s.description for s in described} == {
        "Hello Trying this out",
        "Afdadfa Asdasd Yes Hi Claude",
        "Hello Yes Assay Asda Asd Eww",
    }

    # ...but not as notes, and nothing references a note anywhere.
    assert project.notes == [], "ATLAS.ti 26 emits no <Notes> for quotation comments"
    assert project.note_refs == []
    assert source.note_refs == []
    assert all(s.note_refs == [] for s in source.selections)


def test_guids_are_reassigned_on_every_export() -> None:
    """Two exports of one project share no source identity.

    Both fixtures are the same ATLAS.ti project (identical project
    ``creationDateTime`` and user GUIDs) holding the same video (identical
    ``name``, and byte-identical media files on the machine that produced
    them). Nothing that should be stable, is -- which is why
    ``conformance/diffing.py`` matches on names and coordinates, not GUIDs.
    """
    first = parse_qde(_read_qde_bypassing_container(BASELINE))
    second = _codes_memos_project()

    # Same project, same video.
    assert first.creation_datetime == second.creation_datetime
    assert [u.guid for u in first.users] == [u.guid for u in second.users]
    assert first.sources[0].name == second.sources[0].name == "Christos vagias-2.MP4"

    # Different identity for both the source and its media file.
    assert first.sources[0].guid != second.sources[0].guid
    assert first.sources[0].path != second.sources[0].path


def test_multi_coding_one_selection_carries_several_codes() -> None:
    """Two codes on one selection. Not the same as overlapping selections."""
    project = _codes_memos_project()
    by_guid = {c.guid: c.name for code in project.codebook for c in code.iter_all()}
    assert sorted(by_guid.values()) == ["hello", "test"]

    multi = {
        s.name: sorted(by_guid[c.code_ref] for c in s.codings)
        for s in project.sources[0].selections
        if len(s.codings) > 1
    }
    assert multi == {"2s": ["hello", "test"], "15s": ["hello", "test"]}


def test_zero_length_selection_survives_parsing() -> None:
    """A 0 ms selection: schema-legal, and the shape that breaks naive importers."""
    project = _codes_memos_project()
    degenerate = [
        s
        for s in project.sources[0].selections
        if isinstance(s, VideoSelection) and s.begin == s.end
    ]
    assert len(degenerate) == 1
    assert degenerate[0].begin == 21477
    assert degenerate[0].description == "Hello Trying this out"


def test_original_media_location_is_unrecoverable() -> None:
    """``currentPath`` is omitted, so the source's real path is lost.

    REFI-QDA §8.3 reserves ``currentPath`` for "the original path and
    filename of the source". ATLAS.ti omits it and GUID-renames the media,
    so the only trace of the original file is the human-readable ``name``
    -- which disagrees with the referenced extension (``.MP4`` vs ``.mov``).
    """
    for qdpx_path in _ALL_FIXTURES:
        source = parse_qde(_read_qde_bypassing_container(qdpx_path)).sources[0]
        assert source.current_path is None
        assert source.path is not None and source.path.startswith("relative:///")
        assert source.name is not None and source.name.endswith(".MP4")
        assert source.path.endswith(".mov")

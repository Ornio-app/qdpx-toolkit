"""Pins the ATLAS.ti 26 findings documented in ``../fixtures/atlasti/README.md``.

**Container filename: resolved, option 3 (accept-and-warn).** ATLAS.ti 26
names the XML inside a ``.qdpx`` after the *project* rather than
``project.qde``, which REFI-QDA v1.5 p.21 and section 8.1 require. This
reader now accepts any single root-level ``.qde`` and emits a
:class:`refi_qda.exceptions.ContainerNamingWarning` naming the deviation,
rather than refusing real data or normalising it in silence.

These tests guard that decision from regressing in *either* direction:

* back to refusing -- :func:`test_atlasti_export_now_opens` fails if the
  fixtures stop opening;
* forward into silent acceptance -- the same test uses ``pytest.warns``
  and matches the warning's *content*, so deleting the warning fails the
  suite just as loudly as deleting the support would;
* into over-warning -- :func:`test_conformant_archive_emits_no_warning`
  fails if a correctly named ``project.qde`` starts warning too.

What was deliberately *not* relaxed is "exactly one project file":
:func:`test_no_qde_still_raises` and :func:`test_multiple_qde_still_raises`
pin that zero or several ``.qde`` files remain a hard ``ContainerError``.

The remaining tests are characterisation tests -- they assert what
ATLAS.ti *actually* does today (memos flattened to ``<Description>``,
GUIDs reassigned on every export, a zero-length selection), not what it
ought to do. If a later ATLAS.ti build changes any of this, these fail and
the README needs updating. A failure here is a finding, not necessarily a
bug.

Nothing in this module tests the three risk areas named in SPEC.md §1.3
(overlapping selections, nested codes, character offsets). Neither fixture
exercises them -- see the fixtures README's "Known gaps" section.
"""

from __future__ import annotations

import os
import warnings
import zipfile
from pathlib import Path

import pytest

from refi_qda.container import QDE_FILENAME, QdpxContainer
from refi_qda.exceptions import ContainerError, ContainerNamingWarning
from refi_qda.model import VideoSelection, VideoSource
from refi_qda.parser import parse_qde, parse_qdpx
from refi_qda.writer import to_qde, write_qdpx

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "atlasti"

BASELINE = FIXTURES_DIR / "atlasti_26_handbuilt_01_baseline.qdpx"
CODES_MEMOS = FIXTURES_DIR / "atlasti_26_handbuilt_02_codes_memos.qdpx"

#: What ATLAS.ti 26 actually names the file, in both fixtures.
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

    Used by the payload-level characterisation tests below, which are about
    what ATLAS.ti put *in* the XML and have nothing to say about the
    container. Going direct keeps them independent of container behaviour
    and free of the naming warning.
    """
    with zipfile.ZipFile(qdpx_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".qde")]
        assert len(members) == 1, f"{qdpx_path.name} should hold exactly one .qde, got {members}"
        return archive.read(members[0])


def _qdpx_containing(tmp_path: Path, name: str, *members: str) -> Path:
    """Build a throwaway ``.qdpx`` holding exactly the named members."""
    dest = tmp_path / name
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for member in members:
            zf.writestr(member, "<Project/>")
    return dest


# --------------------------------------------------------------------------
# 1. The resolved behaviour: accept, but say so.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_atlasti_export_now_opens_and_warns(qdpx_path: Path) -> None:
    """Both fixtures open, and the deviation is reported rather than swallowed.

    ``pytest.warns`` fails the test if *no* warning is emitted, so this is
    also the regression guard against someone quietly dropping the warning
    and leaving silent acceptance behind.
    """
    with pytest.warns(ContainerNamingWarning) as recorded:
        project = parse_qdpx(qdpx_path)

    # It actually parsed.
    assert project.name == "Trial"
    assert len(project.sources) == 1

    # And the warning says something useful: which file, and why it matters.
    assert len(recorded) == 1, "the naming deviation should be reported exactly once"
    message = str(recorded[0].message)
    assert ACTUAL_QDE_NAME in message, "the warning must name the file it actually found"
    assert QDE_FILENAME in message, "the warning must name what the spec expected"
    assert "8.1" in message, "the warning must cite the clause being deviated from"


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_container_reports_which_qde_it_used(qdpx_path: Path) -> None:
    """The deviation is inspectable, not only announced."""
    with pytest.warns(ContainerNamingWarning), QdpxContainer.open(qdpx_path) as container:
        assert container.qde_filename == ACTUAL_QDE_NAME
        assert container.read_qde().startswith(b"<?xml")


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_warning_is_emitted_once_per_archive_not_once_per_read(qdpx_path: Path) -> None:
    """Resolution happens at open time, so repeated reads stay quiet."""
    with pytest.warns(ContainerNamingWarning) as recorded, QdpxContainer.open(qdpx_path) as c:
        c.read_qde()
        c.read_qde()
        c.read_qde()
    assert len(recorded) == 1


def test_conformant_archive_emits_no_warning(tmp_path: Path) -> None:
    """Guards the opposite regression: don't warn about correct files."""
    conformant = _qdpx_containing(tmp_path, "conformant.qdpx", QDE_FILENAME)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ContainerNamingWarning)
        with QdpxContainer.open(conformant) as container:
            assert container.qde_filename == QDE_FILENAME


def test_warning_can_be_escalated_to_an_error(tmp_path: Path) -> None:
    """A conformance-checking caller can still demand strictness.

    This is the reason the deviation is a ``warnings`` warning rather than
    a log line: the caller, not this library, decides how strict to be.
    """
    deviant = _qdpx_containing(tmp_path, "deviant.qdpx", "Trial.qde")
    with warnings.catch_warnings():
        warnings.simplefilter("error", ContainerNamingWarning)
        with pytest.raises(ContainerNamingWarning):
            QdpxContainer.open(deviant)


# --------------------------------------------------------------------------
# 2. What was NOT relaxed: exactly one project file.
# --------------------------------------------------------------------------


def test_no_qde_still_raises(tmp_path: Path) -> None:
    archive = _qdpx_containing(tmp_path, "empty.qdpx", "readme.txt")
    with pytest.raises(ContainerError, match=r"no '\.qde' file at its root"):
        QdpxContainer.open(archive)


def test_multiple_qde_still_raises(tmp_path: Path) -> None:
    archive = _qdpx_containing(tmp_path, "ambiguous.qdpx", "Trial.qde", "Other.qde")
    with pytest.raises(ContainerError, match="no unambiguous project file"):
        QdpxContainer.open(archive)


def test_multiple_qde_raises_even_when_one_is_conformant(tmp_path: Path) -> None:
    """Don't silently prefer ``project.qde`` -- two project files is still ambiguous."""
    archive = _qdpx_containing(tmp_path, "both.qdpx", QDE_FILENAME, "Trial.qde")
    with pytest.raises(ContainerError, match="no unambiguous project file"):
        QdpxContainer.open(archive)


def test_qde_in_a_subfolder_does_not_count(tmp_path: Path) -> None:
    """Only root-level members are candidates, per section 8.1."""
    archive = _qdpx_containing(tmp_path, "nested.qdpx", "nested/Trial.qde")
    with pytest.raises(ContainerError, match=r"no '\.qde' file at its root"):
        QdpxContainer.open(archive)


# --------------------------------------------------------------------------
# 3. The repair path: read non-conformant, write conformant.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_reading_then_writing_repairs_the_filename(qdpx_path: Path, tmp_path: Path) -> None:
    """The most useful consequence of accept-and-warn: this toolkit fixes the defect.

    Read a non-conformant ATLAS.ti export, write it back out, and the
    result is a spec-correct ``project.qde`` that opens without any
    warning -- with the project data unchanged.
    """
    with pytest.warns(ContainerNamingWarning):
        original = parse_qdpx(qdpx_path)

    repaired = tmp_path / "repaired.qdpx"
    write_qdpx(original, repaired)

    # The archive is now conformant...
    with zipfile.ZipFile(repaired) as archive:
        assert archive.namelist() == [QDE_FILENAME]

    # ...it opens silently...
    with warnings.catch_warnings():
        warnings.simplefilter("error", ContainerNamingWarning)
        reparsed = parse_qdpx(repaired)

    # ...and nothing was lost on the way through.
    assert reparsed == original


# --------------------------------------------------------------------------
# 4. The payload was always fine. Only the container name was wrong.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("qdpx_path", _ALL_FIXTURES, ids=lambda p: p.name)
def test_payload_parses(qdpx_path: Path) -> None:
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
    original = parse_qde(_read_qde_bypassing_container(qdpx_path))
    assert parse_qde(to_qde(original)) == original


def test_inner_qde_is_named_after_the_project_not_the_archive() -> None:
    """Why the name could not simply be guessed instead of relaxed.

    ``atlasti_26_handbuilt_02_codes_memos.qdpx`` was exported from ATLAS.ti
    to a file the user named ``Project.qdpx`` and *still* contains
    ``Trial.qde`` -- the inner name tracks the ATLAS.ti project name, which
    a reader has no way to know in advance. Deriving the expected filename
    from the archive filename was never an option.
    """
    for qdpx_path in _ALL_FIXTURES:
        with zipfile.ZipFile(qdpx_path) as archive:
            assert archive.namelist() == [ACTUAL_QDE_NAME], (
                f"{qdpx_path.name} no longer contains exactly [{ACTUAL_QDE_NAME!r}] -- "
                "if ATLAS.ti changed its naming, update the fixtures README."
            )


# --------------------------------------------------------------------------
# 5. Characterisation of what ATLAS.ti 26 actually exports.
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

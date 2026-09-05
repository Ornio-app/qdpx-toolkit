"""Tests for refi_qda.writer -- the reader's exact serialisation inverse.

The property that matters most here is round-tripping: for every construct
the hand-authored fixture exercises (a three-level code hierarchy,
deliberately overlapping text selections, all five source types, a PDF
selection's inline text representation, an audio transcript with sync
points, mixed-type case variables, sets, links, notes, graphs, and both
``relative://`` and ``absolute://`` external source references),
``parse_qdpx(write_qdpx(p))`` must reproduce ``p`` exactly -- see
tests/roundtrip_diff.py for how a divergence is reported.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from refi_qda.container import QdpxContainer
from refi_qda.exceptions import ExternalSourceError
from refi_qda.model import (
    Case,
    Code,
    Project,
    TextSource,
    Variable,
    VariableType,
    VariableValue,
)
from refi_qda.parser import parse_qde, parse_qdpx
from refi_qda.writer import to_qde, write_qdpx
from roundtrip_diff import first_divergence

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "hand_authored"
SOURCES_DIR = FIXTURES_DIR / "sources"

#: The three source GUIDs the hand-authored fixture bundles internally --
#: see tests/fixtures/hand_authored/project.qde's plainTextPath/path
#: attributes, all of which already use the internal:// scheme.
INTERNAL_SOURCE_FILES = {
    "40000000-0000-0000-0000-000000000001": SOURCES_DIR
    / "11111111-1111-1111-1111-111111111111.txt",
    "40000000-0000-0000-0000-000000000002": SOURCES_DIR
    / "22222222-2222-2222-2222-222222222222.jpg",
    "40000000-0000-0000-0000-000000000003": SOURCES_DIR
    / "33333333-3333-3333-3333-333333333333.pdf",
}


class TestFixtureRoundTrip:
    def test_hand_authored_fixture_survives_write_then_reparse(
        self, sample_qdpx_path: Path, tmp_path: Path
    ) -> None:
        original = parse_qdpx(sample_qdpx_path)

        out_path = tmp_path / "roundtrip.qdpx"
        write_qdpx(original, out_path, source_files=INTERNAL_SOURCE_FILES)
        reparsed = parse_qdpx(out_path)

        diff = first_divergence(original, reparsed)
        assert diff is None, diff
        assert original == reparsed

    def test_write_qdpx_bundles_exactly_the_given_internal_sources(
        self, sample_qdpx_path: Path, tmp_path: Path
    ) -> None:
        project = parse_qdpx(sample_qdpx_path)
        out_path = tmp_path / "roundtrip.qdpx"
        write_qdpx(project, out_path, source_files=INTERNAL_SOURCE_FILES)

        with QdpxContainer.open(out_path) as container:
            assert sorted(container.list_internal_sources()) == sorted(
                p.name for p in INTERNAL_SOURCE_FILES.values()
            )
            assert container.read_qde() == to_qde(project)

    def test_external_sources_are_left_as_external_references(
        self, sample_qdpx_path: Path, tmp_path: Path
    ) -> None:
        # AudioSource/VideoSource in the fixture are relative:// / absolute://
        # and deliberately not passed via source_files.
        project = parse_qdpx(sample_qdpx_path)
        out_path = tmp_path / "roundtrip.qdpx"
        write_qdpx(project, out_path, source_files=INTERNAL_SOURCE_FILES)
        reparsed = parse_qdpx(out_path)

        audio = reparsed.find_source("40000000-0000-0000-0000-000000000004")
        video = reparsed.find_source("40000000-0000-0000-0000-000000000005")
        assert audio is not None and audio.path == "relative:///Audio/interview.m4a"
        assert (
            video is not None and video.path == "absolute:///Users/example/ExternalMedia/clip.mp4"
        )


class TestWriteQdpxErrors:
    def test_unknown_guid_in_source_files_raises(self, tmp_path: Path) -> None:
        project = Project(name="Empty")
        with pytest.raises(ExternalSourceError, match="not a top-level source"):
            write_qdpx(
                project, tmp_path / "out.qdpx", source_files={"nonexistent-guid": Path("x.txt")}
            )

    def test_external_scheme_source_in_source_files_raises(self, tmp_path: Path) -> None:
        source = TextSource(guid="src-1", plain_text_path="relative:///docs/a.txt")
        project = Project(name="P", sources=[source])
        with pytest.raises(ExternalSourceError, match="not internal://"):
            write_qdpx(project, tmp_path / "out.qdpx", source_files={"src-1": Path("a.txt")})

    def test_source_with_no_path_in_source_files_raises(self, tmp_path: Path) -> None:
        source = TextSource(guid="src-1", plain_text_content="inline text, no path")
        project = Project(name="P", sources=[source])
        with pytest.raises(ExternalSourceError, match="no path"):
            write_qdpx(project, tmp_path / "out.qdpx", source_files={"src-1": Path("a.txt")})


class TestToQdeInMemoryRoundTrips:
    """Constructs match parse_qde(to_qde(p)) == p without touching the ZIP layer."""

    def test_minimal_project(self) -> None:
        project = Project(name="Bare minimum")
        assert parse_qde(to_qde(project)) == project

    def test_non_ascii_content_survives(self) -> None:
        # The library's first real consumer's data is Greek.
        project = Project(
            name="Ελληνική μελέτη",
            description="Περιγραφή με ελληνικούς χαρακτήρες.",
            sources=[
                TextSource(
                    guid="11111111-1111-1111-1111-111111111111",
                    name="Συνέντευξη 1.txt",
                    plain_text_content="Η υγεία και η διατροφή είναι συνδεδεμένες.",  # noqa: RUF001
                )
            ],
        )
        reparsed = parse_qde(to_qde(project))
        diff = first_divergence(project, reparsed)
        assert diff is None, diff

    def test_decimal_date_and_datetime_variable_values(self) -> None:
        project = Project(
            name="P",
            variables=[
                Variable(guid="v1", name="Score", type_of_variable=VariableType.FLOAT),
                Variable(guid="v2", name="Enrolled", type_of_variable=VariableType.DATE),
                Variable(guid="v3", name="LastSeen", type_of_variable=VariableType.DATE_TIME),
            ],
            cases=[
                Case(
                    guid="c1",
                    name="Case 1",
                    variable_values=[
                        VariableValue(variable_ref="v1", value=Decimal("3.140")),
                        VariableValue(variable_ref="v2", value=datetime(2024, 5, 1).date()),
                        VariableValue(variable_ref="v3", value=datetime(2024, 5, 1, 9, 30, 0)),
                    ],
                )
            ],
        )
        reparsed = parse_qde(to_qde(project))
        diff = first_divergence(project, reparsed)
        assert diff is None, diff

    def test_unset_variable_value_round_trips_as_none(self) -> None:
        project = Project(
            name="P",
            variables=[Variable(guid="v1", name="Notes", type_of_variable=VariableType.TEXT)],
            cases=[Case(guid="c1", variable_values=[VariableValue(variable_ref="v1", value=None)])],
        )
        reparsed = parse_qde(to_qde(project))
        assert reparsed.cases[0].variable_values[0].value is None

    def test_empty_codebook_sources_etc_are_omitted_not_written_empty(self) -> None:
        project = Project(name="P")
        xml = to_qde(project)
        assert b"<CodeBook" not in xml
        assert b"<Sources" not in xml
        assert b"<Users" not in xml
        reparsed = parse_qde(xml)
        assert reparsed == project

    def test_three_level_code_hierarchy_round_trips(self) -> None:
        grandchild = Code(guid="c3", name="Diet", is_codable=True, color="#dc0000")
        child = Code(guid="c2", name="Health", is_codable=True, children=[grandchild])
        folder = Code(guid="c1", name="Topics", is_codable=False, children=[child])
        project = Project(name="P", codebook=[folder])
        reparsed = parse_qde(to_qde(project))
        diff = first_divergence(project, reparsed)
        assert diff is None, diff

    def test_to_qde_returns_bytes(self) -> None:
        assert isinstance(to_qde(Project(name="P")), bytes)

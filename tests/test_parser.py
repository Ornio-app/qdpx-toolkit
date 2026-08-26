"""Tests for refi_qda.parser against the hand-authored sample project.

These exercise every part of the object model the sample fixture touches:
a three-level code hierarchy, deliberately overlapping text selections,
all five source types (including a PDF selection's inline text
representation and an audio transcript with sync points), mixed-type case
variables, sets, links, notes, and graphs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from refi_qda.exceptions import ParseError, UnsupportedFeatureError
from refi_qda.model import (
    AudioSource,
    LinkDirection,
    PDFSource,
    PictureSource,
    Shape,
    TextSource,
    VideoSource,
)
from refi_qda.parser import normalize_guid, parse_qde, parse_qdpx


def test_normalize_guid_strips_braces_and_lowercases() -> None:
    assert normalize_guid("{ABCD1234-0000-0000-0000-000000000000}") == (
        "abcd1234-0000-0000-0000-000000000000"
    )
    assert normalize_guid("abcd1234-0000-0000-0000-000000000000") == (
        "abcd1234-0000-0000-0000-000000000000"
    )


class TestProjectAttributes:
    def test_top_level_attributes(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert project.name == "Sample Study"
        assert project.origin == "refi_qda test fixture"
        assert project.base_path == "/Users/example/ExternalMedia"
        assert project.creation_datetime == datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert project.note_refs == ["a0000000-0000-0000-0000-000000000001"]

    def test_users(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.users) == 1
        assert project.users[0].name == "Researcher A"


class TestCodebook:
    def test_three_level_hierarchy(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.codebook) == 1
        topics = project.codebook[0]
        assert topics.name == "Topics"
        assert topics.is_codable is False
        assert {c.name for c in topics.children} == {"Health", "Wellbeing"}

        health = next(c for c in topics.children if c.name == "Health")
        assert health.is_codable is True
        assert health.color == "#33cc33"
        assert [c.name for c in health.children] == ["Diet"]

    def test_iter_codes_flattens_all_four(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        names = {code.name for code in project.iter_codes()}
        assert names == {"Topics", "Health", "Diet", "Wellbeing"}


class TestOverlappingSelections:
    def test_text_source_has_two_overlapping_selections(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        text_source = project.find_source("40000000-0000-0000-0000-000000000001")
        assert isinstance(text_source, TextSource)
        assert len(text_source.selections) == 2

        first, second = text_source.selections
        assert (first.start_position, first.end_position) == (0, 15)
        assert (second.start_position, second.end_position) == (9, 23)
        # They genuinely overlap on codepoints 9-15.
        assert second.start_position < first.end_position

        assert first.codings[0].code_ref == "20000000-0000-0000-0000-000000000002"  # Health
        assert second.codings[0].code_ref == "20000000-0000-0000-0000-000000000003"  # Diet


class TestSourceTypes:
    def test_picture_source_and_selection(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        picture = project.find_source("40000000-0000-0000-0000-000000000002")
        assert isinstance(picture, PictureSource)
        assert len(picture.selections) == 1
        selection = picture.selections[0]
        assert (selection.first_x, selection.first_y) == (10, 20)
        assert (selection.second_x, selection.second_y) == (100, 200)

    def test_pdf_source_with_inline_representation(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        pdf = project.find_source("40000000-0000-0000-0000-000000000003")
        assert isinstance(pdf, PDFSource)
        assert pdf.representation is not None
        assert (
            pdf.representation.plain_text_content
            == "Notes about diet and health from the document."
        )

        assert len(pdf.selections) == 1
        selection = pdf.selections[0]
        assert selection.page == 0
        assert (selection.first_x, selection.first_y, selection.second_x, selection.second_y) == (
            18,
            45,
            577,
            234,
        )
        assert selection.representation is not None
        assert selection.representation.plain_text_content == "diet and health"

    def test_audio_source_transcript_and_sync_points(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        audio = project.find_source("40000000-0000-0000-0000-000000000004")
        assert isinstance(audio, AudioSource)
        assert audio.path == "relative:///Audio/interview.m4a"

        assert len(audio.transcripts) == 1
        transcript = audio.transcripts[0]
        assert [sp.time_stamp for sp in transcript.sync_points] == [0, 5000]
        assert len(transcript.selections) == 1
        assert transcript.selections[0].from_sync_point == "90000000-0000-0000-0000-000000000001"
        assert transcript.selections[0].to_sync_point == "90000000-0000-0000-0000-000000000002"

        assert len(audio.selections) == 1
        assert (audio.selections[0].begin, audio.selections[0].end) == (1000, 5000)

    def test_video_source_selection(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        video = project.find_source("40000000-0000-0000-0000-000000000005")
        assert isinstance(video, VideoSource)
        assert video.path == "absolute:///Users/example/ExternalMedia/clip.mp4"
        assert (video.selections[0].begin, video.selections[0].end) == (2000, 8000)


class TestCasesVariablesSetsLinksNotesGraphs:
    def test_case_has_mixed_type_variable_values(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        case = project.find_case("d0000000-0000-0000-0000-000000000001")
        assert case is not None
        assert case.name == "Participant 1"

        values = {v.variable_ref: v.value for v in case.variable_values}
        assert values["30000000-0000-0000-0000-000000000001"] == 34
        assert isinstance(values["30000000-0000-0000-0000-000000000001"], int)
        assert values["30000000-0000-0000-0000-000000000002"] is True

        assert case.code_refs == ["20000000-0000-0000-0000-000000000002"]
        assert case.source_refs == ["40000000-0000-0000-0000-000000000001"]
        assert case.selection_refs == ["50000000-0000-0000-0000-000000000001"]

    def test_notes_are_text_source_shaped(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.notes) == 1
        memo = project.notes[0]
        assert memo.name == "Research memo"
        assert memo.plain_text_content == "Remember to follow up on diet-related comments."

    def test_links(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.links) == 1
        link = project.links[0]
        assert link.direction is LinkDirection.ONE_WAY
        assert link.origin_guid == "a0000000-0000-0000-0000-000000000001"
        assert link.target_guid == "50000000-0000-0000-0000-000000000001"

    def test_sets(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.sets) == 1
        diet_set = project.find_set("c0000000-0000-0000-0000-000000000001")
        assert diet_set is not None
        assert diet_set.member_codes == ["20000000-0000-0000-0000-000000000003"]
        assert diet_set.member_sources == ["40000000-0000-0000-0000-000000000001"]

    def test_graphs(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        assert len(project.graphs) == 1
        graph = project.graphs[0]
        assert len(graph.vertices) == 2
        assert len(graph.edges) == 1
        oval_vertex = next(v for v in graph.vertices if v.shape is Shape.OVAL)
        assert oval_vertex.represented_guid == "20000000-0000-0000-0000-000000000002"
        edge = graph.edges[0]
        assert edge.direction is LinkDirection.ASSOCIATIVE
        assert edge.source_vertex == oval_vertex.guid


class TestParseQdpx:
    def test_parse_qdpx_end_to_end(self, sample_qdpx_path: Path) -> None:
        project = parse_qdpx(sample_qdpx_path)
        assert project.name == "Sample Study"
        assert len(project.sources) == 5


class TestErrorHandling:
    def test_malformed_xml_raises_parse_error(self) -> None:
        with pytest.raises(ParseError, match="well-formed"):
            parse_qde(b"<Project><Unclosed>")

    def test_wrong_root_namespace_raises_parse_error(self) -> None:
        xml = b'<Project xmlns="urn:something:else:1.0" name="X"/>'
        with pytest.raises(ParseError, match="Unsupported root element"):
            parse_qde(xml)

    def test_codebook_root_raises_unsupported_feature_error(self) -> None:
        xml = b'<CodeBook xmlns="urn:QDA-XML:codebook:1.0"></CodeBook>'
        with pytest.raises(UnsupportedFeatureError, match="qdc"):
            parse_qde(xml)
        # UnsupportedFeatureError is also a NotImplementedError, by design.
        with pytest.raises(NotImplementedError):
            parse_qde(xml)

    def test_unknown_source_element_raises_unsupported_feature_error(self) -> None:
        xml = b"""<?xml version="1.0"?>
        <Project xmlns="urn:QDA-XML:project:1.0" name="X">
          <Sources>
            <SpreadsheetSource guid="11111111-1111-1111-1111-111111111111" name="budget.xlsx"/>
          </Sources>
        </Project>"""
        with pytest.raises(UnsupportedFeatureError, match="SpreadsheetSource"):
            parse_qde(xml)

    def test_missing_required_attribute_raises_parse_error(self) -> None:
        # <Code> without the required isCodable attribute.
        xml = b"""<?xml version="1.0"?>
        <Project xmlns="urn:QDA-XML:project:1.0" name="X">
          <CodeBook>
            <Codes>
              <Code guid="11111111-1111-1111-1111-111111111111" name="Broken"/>
            </Codes>
          </CodeBook>
        </Project>"""
        with pytest.raises(ParseError, match="isCodable"):
            parse_qde(xml)


def test_float_variable_value_parses_as_decimal() -> None:
    xml = b"""<?xml version="1.0"?>
    <Project xmlns="urn:QDA-XML:project:1.0" name="X">
      <Cases>
        <Case guid="11111111-1111-1111-1111-111111111111">
          <VariableValue>
            <VariableRef targetGUID="22222222-2222-2222-2222-222222222222"/>
            <FloatValue>3.5</FloatValue>
          </VariableValue>
        </Case>
      </Cases>
    </Project>"""
    project = parse_qde(xml)
    value = project.cases[0].variable_values[0].value
    assert value == Decimal("3.5")

"""Tests for refi_qda.container: the .qdpx ZIP layer.

Uses the hand-authored sample .qdpx fixture (see conftest.py) plus two
deliberately-broken fixtures to exercise the "surface, don't fail
silently" error paths REFI-QDA section 8.1 and this project's design
call for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from refi_qda.container import (
    ExternalSourceResolution,
    ParsedSourcePath,
    QdpxContainer,
    SourceScheme,
    parse_source_path,
    resolve_external_sources,
)
from refi_qda.exceptions import ContainerError, ExternalSourceError
from refi_qda.parser import parse_qde


class TestParseSourcePath:
    def test_internal_scheme_has_no_leading_slash_stripped(self) -> None:
        result = parse_source_path("internal://0616fddd-8dd6-42a0-b5b0-ab7c89729219.mp4")
        assert result == ParsedSourcePath(
            scheme=SourceScheme.INTERNAL, value="0616fddd-8dd6-42a0-b5b0-ab7c89729219.mp4"
        )

    def test_relative_scheme_strips_one_leading_slash(self) -> None:
        result = parse_source_path("relative:///AR/John Interview.mp4")
        assert result.scheme is SourceScheme.RELATIVE
        assert result.value == "AR/John Interview.mp4"

    def test_absolute_scheme_strips_one_leading_slash(self) -> None:
        result = parse_source_path("absolute:///C:/PROJECT/Sources/Group Interview.mp4")
        assert result.scheme is SourceScheme.ABSOLUTE
        assert result.value == "C:/PROJECT/Sources/Group Interview.mp4"

    def test_unrecognised_scheme_raises(self) -> None:
        with pytest.raises(ExternalSourceError):
            parse_source_path("ftp://example.com/file.mp4")

    def test_no_scheme_at_all_raises(self) -> None:
        with pytest.raises(ExternalSourceError):
            parse_source_path("/just/a/path.mp4")


class TestQdpxContainer:
    def test_open_reads_qde_bytes(self, sample_qdpx_path: Path) -> None:
        with QdpxContainer.open(sample_qdpx_path) as container:
            qde_bytes = container.read_qde()
        assert b"<Project" in qde_bytes
        assert b"Sample Study" in qde_bytes

    def test_list_internal_sources(self, sample_qdpx_path: Path) -> None:
        with QdpxContainer.open(sample_qdpx_path) as container:
            names = container.list_internal_sources()
        assert names == sorted(names)  # sanity: no surprises in ordering
        assert "11111111-1111-1111-1111-111111111111.txt" in names
        assert "22222222-2222-2222-2222-222222222222.jpg" in names
        assert "33333333-3333-3333-3333-333333333333.pdf" in names
        assert len(names) == 3

    def test_read_internal_source(self, sample_qdpx_path: Path) -> None:
        with QdpxContainer.open(sample_qdpx_path) as container:
            data = container.read_internal_source("11111111-1111-1111-1111-111111111111.txt")
        assert data.decode("utf-8").startswith("Diet and health")

    def test_read_internal_source_missing_raises(self, sample_qdpx_path: Path) -> None:
        with QdpxContainer.open(sample_qdpx_path) as container, pytest.raises(ContainerError):
            container.read_internal_source("does-not-exist.txt")

    def test_missing_project_qde_raises(self, missing_qde_qdpx_path: Path) -> None:
        with pytest.raises(ContainerError, match=r"project\.qde"):
            QdpxContainer.open(missing_qde_qdpx_path)

    def test_nested_sources_folder_raises(self, nested_sources_qdpx_path: Path) -> None:
        with pytest.raises(ContainerError, match="non-flat"):
            QdpxContainer.open(nested_sources_qdpx_path)

    def test_not_a_zip_file_raises(self, tmp_path: Path) -> None:
        bogus = tmp_path / "not_a_zip.qdpx"
        bogus.write_bytes(b"this is definitely not a zip file")
        with pytest.raises(ContainerError):
            QdpxContainer.open(bogus)

    def test_context_manager_closes_underlying_zip(self, sample_qdpx_path: Path) -> None:
        with QdpxContainer.open(sample_qdpx_path) as container:
            pass
        # The underlying zipfile.ZipFile should now be closed; reading from
        # it should fail rather than silently succeed on stale state.
        with pytest.raises(ValueError, match="closed"):
            container.read_qde()


class TestResolveExternalSources:
    def test_reports_relative_and_absolute_but_not_internal(self, sample_qde_bytes: bytes) -> None:
        project = parse_qde(sample_qde_bytes)
        resolutions = resolve_external_sources(project)

        by_scheme = {r.scheme for r in resolutions}
        assert by_scheme == {SourceScheme.RELATIVE, SourceScheme.ABSOLUTE}
        # Internal TextSource/PictureSource/PDFSource must not appear.
        source_guids = {r.source_guid for r in resolutions}
        assert "40000000-0000-0000-0000-000000000001" not in source_guids  # TextSource

    def test_relative_source_not_found_is_reported_not_raised(
        self, sample_qde_bytes: bytes
    ) -> None:
        project = parse_qde(sample_qde_bytes)
        resolutions = resolve_external_sources(project)
        relative = next(r for r in resolutions if r.scheme is SourceScheme.RELATIVE)
        assert isinstance(relative, ExternalSourceResolution)
        assert relative.exists is False
        assert relative.resolved_path is not None
        assert relative.declared_path == "relative:///Audio/interview.m4a"

    def test_absolute_source_not_found_is_reported_not_raised(
        self, sample_qde_bytes: bytes
    ) -> None:
        project = parse_qde(sample_qde_bytes)
        resolutions = resolve_external_sources(project)
        absolute = next(r for r in resolutions if r.scheme is SourceScheme.ABSOLUTE)
        assert absolute.exists is False
        assert absolute.declared_path == "absolute:///Users/example/ExternalMedia/clip.mp4"

    def test_base_path_override(self, sample_qde_bytes: bytes, tmp_path: Path) -> None:
        project = parse_qde(sample_qde_bytes)
        resolutions = resolve_external_sources(project, base_path=str(tmp_path))
        relative = next(r for r in resolutions if r.scheme is SourceScheme.RELATIVE)
        assert relative.resolved_path == tmp_path / "Audio/interview.m4a"

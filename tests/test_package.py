"""Tests for the top-level public API in refi_qda/__init__.py."""

from __future__ import annotations

from pathlib import Path

import refi_qda
from refi_qda.model import Project
from refi_qda.parser import parse_qdpx


def test_open_qdpx_is_an_alias_for_parse_qdpx() -> None:
    assert refi_qda.open_qdpx is parse_qdpx


def test_open_qdpx_end_to_end(sample_qdpx_path: Path) -> None:
    project = refi_qda.open_qdpx(sample_qdpx_path)
    assert isinstance(project, Project)
    assert project.name == "Sample Study"


def test_version_is_a_string() -> None:
    assert isinstance(refi_qda.__version__, str)
    assert refi_qda.__version__ != ""

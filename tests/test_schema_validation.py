"""Validate the hand-authored fixture (and the writer's output) against the
real REFI-QDA XSD, when one is available.

This library does not vendor the schema (see conformance/README.md and
schema/README.md for why), so these tests are conditional on
``schema/refi-qda-project-1.0.xsd`` existing on disk -- populated by
running ``scripts/fetch_schema.py`` locally, not by CI. Skipping cleanly
here, rather than failing, follows the same pattern
``conformance/tests/test_conformance.py`` uses for absent vendor fixtures:
this suite is green on a clean checkout and starts doing something real
the moment the schema is present.

``tests/fixtures/hand_authored/project.qde`` is this project's canonical
conformance seed -- everything else in the unit test suite is built on
top of it. A fixture that fails real schema validation would silently
undermine that, so this is a load-bearing test, not a nice-to-have.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from refi_qda.exceptions import SchemaValidationError
from refi_qda.parser import parse_qdpx
from refi_qda.validator import validate
from refi_qda.writer import to_qde

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "refi-qda-project-1.0.xsd"


def _skip_unless_schema_present() -> None:
    if not SCHEMA_PATH.is_file():
        pytest.skip(
            f"{SCHEMA_PATH} not present -- run `python scripts/fetch_schema.py` "
            "to recover it locally (CI does not run that script)."
        )


def test_hand_authored_fixture_validates_against_recovered_schema(
    sample_qde_bytes: bytes,
) -> None:
    _skip_unless_schema_present()
    try:
        validate(sample_qde_bytes, schema_path=SCHEMA_PATH)
    except SchemaValidationError as exc:
        pytest.fail(
            "tests/fixtures/hand_authored/project.qde, this project's canonical "
            "conformance seed, does not validate against the real schema:\n" + "\n".join(exc.errors)
        )


def test_writer_output_validates_against_recovered_schema(sample_qdpx_path: Path) -> None:
    _skip_unless_schema_present()
    # A writer that round-trips through this library's own parser but emits
    # schema-invalid XML is a real defect this repo would otherwise have no
    # way to detect -- see writer.py's docstring on why element order matters.
    project = parse_qdpx(sample_qdpx_path)
    qde_bytes = to_qde(project)
    try:
        validate(qde_bytes, schema_path=SCHEMA_PATH)
    except SchemaValidationError as exc:
        pytest.fail(
            "refi_qda.writer.to_qde() output does not validate against the real "
            "schema:\n" + "\n".join(exc.errors)
        )

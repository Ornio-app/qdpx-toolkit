"""Tests for refi_qda.validator.

This library does not vendor the REFI-QDA XSD (see conformance/README.md
and schema/README.md for why), so most of what can be tested without a
real schema on disk is the "clear, actionable error" path -- the whole
point of validator.py when no schema is configured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from refi_qda.exceptions import SchemaNotConfiguredError, SchemaValidationError
from refi_qda.validator import SCHEMA_PATH_ENV_VAR, validate


def test_raises_schema_not_configured_without_argument_or_env_var(
    sample_qde_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SCHEMA_PATH_ENV_VAR, raising=False)
    with pytest.raises(SchemaNotConfiguredError, match="does not vendor"):
        validate(sample_qde_bytes)


def test_env_var_pointing_nowhere_raises_schema_not_configured(
    sample_qde_bytes: bytes, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(SCHEMA_PATH_ENV_VAR, str(tmp_path / "does_not_exist.xsd"))
    with pytest.raises(SchemaNotConfiguredError, match="does not exist"):
        validate(sample_qde_bytes)


def test_explicit_schema_path_takes_priority_over_env_var(
    sample_qde_bytes: bytes, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(SCHEMA_PATH_ENV_VAR, str(tmp_path / "env_does_not_exist.xsd"))
    explicit_missing = tmp_path / "explicit_does_not_exist.xsd"
    with pytest.raises(SchemaNotConfiguredError, match="explicit_does_not_exist"):
        validate(sample_qde_bytes, schema_path=explicit_missing)


def test_malformed_schema_file_raises_schema_not_configured(
    sample_qde_bytes: bytes, tmp_path: Path
) -> None:
    bogus_schema = tmp_path / "not_actually_an_xsd.xsd"
    bogus_schema.write_text("this is not XML at all")
    with pytest.raises(SchemaNotConfiguredError, match="does not parse"):
        validate(sample_qde_bytes, schema_path=bogus_schema)


def test_valid_document_against_a_trivial_permissive_schema(tmp_path: Path) -> None:
    # A minimal XSD that only requires a <Project> root -- enough to prove
    # the success path (schema.validate() returning True) works end to
    # end, without needing the real (unvendored) REFI-QDA schema.
    schema_path = tmp_path / "trivial.xsd"
    schema_path.write_text(
        """<?xml version="1.0"?>
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    xmlns="urn:QDA-XML:project:1.0"
                    targetNamespace="urn:QDA-XML:project:1.0"
                    elementFormDefault="qualified">
          <xsd:element name="Project">
            <xsd:complexType>
              <xsd:sequence>
                <xsd:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
              </xsd:sequence>
              <xsd:attribute name="name" type="xsd:string" use="required"/>
              <xsd:anyAttribute processContents="skip"/>
            </xsd:complexType>
          </xsd:element>
        </xsd:schema>"""
    )
    valid_doc = b'<Project xmlns="urn:QDA-XML:project:1.0" name="OK"/>'
    validate(valid_doc, schema_path=schema_path)  # must not raise


def test_invalid_document_raises_schema_validation_error_with_details(tmp_path: Path) -> None:
    schema_path = tmp_path / "trivial.xsd"
    schema_path.write_text(
        """<?xml version="1.0"?>
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    xmlns="urn:QDA-XML:project:1.0"
                    targetNamespace="urn:QDA-XML:project:1.0"
                    elementFormDefault="qualified">
          <xsd:element name="Project">
            <xsd:complexType>
              <xsd:attribute name="name" type="xsd:string" use="required"/>
            </xsd:complexType>
          </xsd:element>
        </xsd:schema>"""
    )
    # Missing the required "name" attribute.
    invalid_doc = b'<Project xmlns="urn:QDA-XML:project:1.0"/>'
    with pytest.raises(SchemaValidationError) as exc_info:
        validate(invalid_doc, schema_path=schema_path)
    assert len(exc_info.value.errors) >= 1

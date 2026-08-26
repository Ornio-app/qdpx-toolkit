"""XSD schema validation for REFI-QDA XML documents.

This library does not vendor the REFI-QDA XSD -- its redistribution
licence is not clearly stated by qdasoftware.org, and the schema files
there sit behind a JS-gated download that is not straightforward to
mirror cleanly. See ``conformance/README.md`` and ``schema/README.md``
for where to obtain a copy.

Validation here is therefore opt-in and explicit: callers supply a schema
path (directly, or via the ``REFI_QDA_SCHEMA_PATH`` environment variable),
and :func:`validate` raises a clear, actionable
:class:`refi_qda.exceptions.SchemaNotConfiguredError` when neither is
present, rather than silently skipping validation.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from lxml import etree

from refi_qda.exceptions import SchemaNotConfiguredError, SchemaValidationError

__all__ = ["SCHEMA_PATH_ENV_VAR", "validate"]

#: Environment variable :func:`validate` falls back to when no
#: ``schema_path`` argument is given.
SCHEMA_PATH_ENV_VAR = "REFI_QDA_SCHEMA_PATH"

_NOT_CONFIGURED_MESSAGE = (
    "No REFI-QDA XSD schema is configured. This library does not vendor the "
    "schema (its redistribution licence is not clearly stated by "
    "qdasoftware.org) -- you need to supply your own copy. Pass "
    "schema_path=... explicitly, or set the "
    f"{SCHEMA_PATH_ENV_VAR} environment variable to point at Project.xsd. "
    "See conformance/README.md and schema/README.md for where to get one."
)


def _resolve_schema_path(schema_path: str | Path | None) -> Path:
    if schema_path is not None:
        return Path(schema_path)
    env_value = os.environ.get(SCHEMA_PATH_ENV_VAR)
    if env_value:
        return Path(env_value)
    raise SchemaNotConfiguredError(_NOT_CONFIGURED_MESSAGE)


@lru_cache(maxsize=8)
def _load_schema(schema_path_str: str) -> etree.XMLSchema:
    schema_path = Path(schema_path_str)
    if not schema_path.is_file():
        raise SchemaNotConfiguredError(
            f"Configured schema path {schema_path} does not exist or is not a file.\n"
            + _NOT_CONFIGURED_MESSAGE
        )
    try:
        schema_doc = etree.parse(str(schema_path))
        return etree.XMLSchema(schema_doc)
    except (etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
        raise SchemaNotConfiguredError(
            f"{schema_path} does not parse as a valid XML Schema: {exc}"
        ) from exc


def validate(xml: bytes | str | Path, schema_path: str | Path | None = None) -> None:
    """Validate REFI-QDA XML (a ``project.qde`` or ``.qdc`` document) against an XSD.

    :param xml: the XML to validate: raw ``bytes``/``str`` content, or a
        :class:`pathlib.Path` to an XML file on disk.
    :param schema_path: path to the ``.xsd`` file to validate against. If
        omitted, falls back to the ``REFI_QDA_SCHEMA_PATH`` environment
        variable.
    :raises refi_qda.exceptions.SchemaNotConfiguredError: no schema is
        available (neither argument nor environment variable is set), or
        the configured path does not exist or is not a well-formed schema.
    :raises refi_qda.exceptions.SchemaValidationError: the XML is
        well-formed but does not conform to the schema; ``.errors`` holds
        each individual validation error as a human-readable string.
    """
    resolved_schema_path = _resolve_schema_path(schema_path)
    schema = _load_schema(str(resolved_schema_path))

    if isinstance(xml, Path):
        tree = etree.parse(str(xml))
    else:
        data = xml if isinstance(xml, bytes) else xml.encode("utf-8")
        try:
            tree = etree.fromstring(data).getroottree()
        except etree.XMLSyntaxError as exc:
            raise SchemaValidationError(
                f"XML is not well-formed: {exc}", errors=[str(exc)]
            ) from exc

    if not schema.validate(tree):
        errors = [str(error) for error in schema.error_log]  # type: ignore[attr-defined]
        raise SchemaValidationError(
            f"XML does not validate against schema {resolved_schema_path}: {len(errors)} error(s).",
            errors=errors,
        )

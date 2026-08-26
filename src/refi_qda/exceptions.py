"""Exception hierarchy for :mod:`refi_qda`.

Every error this library raises deliberately, on purpose, subclasses
:class:`QdpxError`. Errors that come from underlying libraries (``zipfile``,
``lxml``) are wrapped rather than left to propagate raw, so callers can
catch ``QdpxError`` and know they have covered everything this package can
throw intentionally.

This library would rather raise :class:`UnsupportedFeatureError` than
silently drop part of a project during parsing. If you see this exception,
the input contained something real that this reader does not yet turn into
model objects -- it is not a bug report asking you to work around it
quietly, it is the library being honest about a gap. See ``SPEC.md`` for
current format coverage.
"""

from __future__ import annotations

__all__ = [
    "ContainerError",
    "ExternalSourceError",
    "ParseError",
    "QdpxError",
    "SchemaNotConfiguredError",
    "SchemaValidationError",
    "UnsupportedFeatureError",
]


class QdpxError(Exception):
    """Base class for all exceptions raised deliberately by ``refi_qda``."""


class ContainerError(QdpxError):
    """The ``.qdpx``/``.qde`` container itself is malformed.

    Raised for things like: not a valid ZIP file, no ``project.qde`` at the
    archive root, or a ``sources/`` folder that is not flat (REFI-QDA
    section 8.1 requires internal sources to sit directly under
    ``sources/`` with no subfolders).
    """


class ExternalSourceError(QdpxError):
    """Raised when an external source reference cannot be used as given.

    External sources (``relative://`` and ``absolute://`` paths, see
    REFI-QDA section 8.3) are a well-known interoperability trap: an
    absolute path recorded on the exporting machine is frequently
    meaningless on the importing one. This library never fails silently on
    that mismatch -- callers get a structured
    :class:`refi_qda.container.ExternalSourceResolution` back describing
    the mismatch. This exception is reserved for cases where the *reference
    itself* is malformed (e.g. an unrecognised URL scheme), not merely
    for a file that happens not to exist on this machine.
    """


class ParseError(QdpxError):
    """The ``project.qde`` XML could not be parsed into the object model.

    This covers XML that is not well-formed, uses an unrecognised
    namespace/root element, or is missing an attribute the schema marks as
    required (``use="required"``). It deliberately does *not* cover schema
    validity beyond that -- for full XSD conformance checking, use
    :mod:`refi_qda.validator`.
    """


class UnsupportedFeatureError(QdpxError, NotImplementedError):
    """A recognised but not-yet-implemented part of REFI-QDA was found.

    Subclasses both :class:`QdpxError` (so callers who only catch this
    library's errors still catch it) and the built-in
    :class:`NotImplementedError` (so it behaves like one everywhere else).
    Always carries a precise message naming the exact element/feature, per
    the project's "no silent partial parse" policy.
    """


class SchemaNotConfiguredError(QdpxError):
    """XSD validation was requested but no schema is available.

    This library does not vendor the REFI-QDA XSD (its redistribution
    licence is not clearly stated by qdasoftware.org). See
    ``conformance/README.md`` and ``schema/README.md`` for how to obtain a
    copy and point this library at it, either via the ``schema_path``
    argument or the ``REFI_QDA_SCHEMA_PATH`` environment variable.
    """


class SchemaValidationError(QdpxError):
    """XML failed validation against the configured XSD schema.

    ``self.errors`` holds the individual ``lxml`` error log entries
    (as strings) so callers can report exactly which lines/elements
    failed, rather than just "invalid".
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors if errors is not None else []

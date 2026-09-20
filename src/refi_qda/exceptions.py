"""Exception and warning hierarchy for :mod:`refi_qda`.

Every error this library raises deliberately, on purpose, subclasses
:class:`QdpxError`. Errors that come from underlying libraries (``zipfile``,
``lxml``) are wrapped rather than left to propagate raw, so callers can
catch ``QdpxError`` and know they have covered everything this package can
throw intentionally.

Warnings get the same treatment, in the same module, for the same reason:
every warning this library emits deliberately subclasses
:class:`QdpxWarning`. They live here rather than in a separate module
because :class:`Warning` is itself a subclass of :class:`Exception` -- this
is one hierarchy of "things this library reports", not two.

Warnings, not logging, are used for recoverable spec deviations. This is a
library, not an application, so it has no business configuring logging
handlers; and :mod:`warnings` gives the caller something logging cannot --
the ability to escalate a deviation into a hard error::

    import warnings
    from refi_qda.exceptions import ContainerNamingWarning

    warnings.simplefilter("error", ContainerNamingWarning)

which is exactly what a conformance-checking caller wants, while a
researcher just trying to read their data gets a message and their
project.

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
    "ContainerNamingWarning",
    "ExternalSourceError",
    "ParseError",
    "QdpxError",
    "QdpxWarning",
    "SchemaNotConfiguredError",
    "SchemaValidationError",
    "UnsupportedFeatureError",
]


class QdpxError(Exception):
    """Base class for all exceptions raised deliberately by ``refi_qda``."""


class QdpxWarning(UserWarning):
    """Base class for all warnings emitted deliberately by ``refi_qda``.

    Subclasses :class:`UserWarning` rather than :class:`Warning` directly so
    that Python's default filters actually show it: bare ``Warning`` and
    ``DeprecationWarning`` are hidden by default in many contexts, and a
    deviation nobody sees is no better than silence.
    """


class ContainerNamingWarning(QdpxWarning):
    """A ``.qdpx`` archive's XML file is not named ``project.qde``.

    REFI-QDA v1.5 p.21 and section 8.1 require the project XML inside the
    archive to be named exactly ``project.qde``. Real exports from at least
    one major tool are not: ATLAS.ti 26 names it after the project instead
    (``Trial.qde``), and the name tracks the project rather than the
    archive, so it cannot be predicted.

    This library reads such an archive anyway -- refusing would make it
    useless against a large share of real data -- but says so rather than
    normalising the deviation silently. See
    ``conformance/fixtures/atlasti/README.md`` for the full decision.

    Note that :func:`refi_qda.writer.write_qdpx` always writes a
    conformant ``project.qde``, so reading a non-conformant archive and
    writing it back out repairs this defect.
    """


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

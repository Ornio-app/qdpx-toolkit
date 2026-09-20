"""refi_qda: a reference implementation of the REFI-QDA (.qdpx) standard.

REFI-QDA is the "Rotterdam Exchange Format Initiative" qualitative-data
exchange standard (v1.5, 2019), used by NVivo, ATLAS.ti, MAXQDA and others
to move coded interview/document projects between tools. This package
implements both the reader and writer halves of that standard -- see
``SPEC.md`` in the repository root for exactly what is and is not yet
covered, and ``README.md`` for why this project exists.

The public API is deliberately small:

* :func:`open_qdpx` -- parse a ``.qdpx`` file straight into a
  :class:`refi_qda.model.Project`. The main entry point for most callers
  reading a project.
* :func:`write_qdpx` -- the inverse: write a :class:`refi_qda.model.Project`
  out as a complete ``.qdpx`` file. The main entry point for most callers
  producing one.
* :func:`refi_qda.parser.parse_qde` / :func:`to_qde` -- parse or serialise
  raw ``project.qde`` XML (bytes) directly, if you are working with an
  already-extracted/not-yet-zipped container.
* :func:`refi_qda.validator.validate` -- validate ``project.qde``/``.qdc``
  XML against the REFI-QDA XSD (which you must supply yourself; see
  ``conformance/README.md``).
* :mod:`refi_qda.model` -- the typed dataclasses parsed results are made
  of (``Project``, ``Code``, the six selection types, etc.).
* :mod:`refi_qda.container` -- lower-level ``.qdpx`` ZIP access, including
  explicit external-source resolution (:func:`refi_qda.container.resolve_external_sources`).
* :mod:`refi_qda.exceptions` -- the exception hierarchy every deliberate
  error in this package subclasses, and the :class:`QdpxWarning` hierarchy
  every deliberate warning subclasses. Notably
  :class:`ContainerNamingWarning`, emitted when a ``.qdpx`` names its
  project XML something other than ``project.qde`` (as real ATLAS.ti
  exports do); filter or escalate it with :mod:`warnings` as you prefer.

Everything else (the leading-underscore helpers in :mod:`refi_qda.parser`
and :mod:`refi_qda.writer`) is an implementation detail and may change
without notice.
"""

from __future__ import annotations

from importlib import metadata as _metadata

from refi_qda.container import (
    ExternalSourceResolution,
    QdpxContainer,
    SourceScheme,
    resolve_external_sources,
)
from refi_qda.exceptions import ContainerNamingWarning, QdpxWarning
from refi_qda.model import Project
from refi_qda.parser import parse_qde, parse_qdpx
from refi_qda.writer import to_qde, write_qdpx

try:
    __version__ = _metadata.version("qdpx-toolkit")
except _metadata.PackageNotFoundError:  # pragma: no cover - editable/unbuilt checkout
    __version__ = "0.0.0"

#: Friendly alias for :func:`refi_qda.parser.parse_qdpx` -- open a
#: ``.qdpx`` file and get back a parsed :class:`refi_qda.model.Project`.
open_qdpx = parse_qdpx

__all__ = [
    "ContainerNamingWarning",
    "ExternalSourceResolution",
    "Project",
    "QdpxContainer",
    "QdpxWarning",
    "SourceScheme",
    "__version__",
    "open_qdpx",
    "parse_qde",
    "parse_qdpx",
    "resolve_external_sources",
    "to_qde",
    "write_qdpx",
]

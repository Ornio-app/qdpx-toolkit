"""Reading the ``.qdpx`` ZIP container (REFI-QDA section 8).

A ``.qdpx`` file is a ZIP archive containing exactly one ``project.qde``
XML file at its root and, optionally, a flat ``sources/`` folder holding
"internal" source files named by GUID. This module deals only with that
container-level structure -- opening the archive, finding ``project.qde``,
listing/reading internal sources, and resolving the ``internal://`` /
``relative://`` / ``absolute://`` source path scheme (section 8.3) -- and
knows nothing about the XML inside ``project.qde``; see
:mod:`refi_qda.parser` for that.

External sources are treated as a first-class concern here, not an
afterthought: an absolute path recorded by the exporting machine is one of
the most common ways a REFI-QDA project silently breaks when moved to
another computer. :func:`resolve_external_sources` never raises for a
missing file -- it reports the mismatch in a structured
:class:`ExternalSourceResolution` so a caller can decide what to do (prompt
the user, as REFI-QDA section 8.3 recommends, or otherwise).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from refi_qda.exceptions import ContainerError, ExternalSourceError

if TYPE_CHECKING:
    from refi_qda.model import Guid, Project

__all__ = [
    "QDE_FILENAME",
    "SOURCES_DIRNAME",
    "ExternalSourceResolution",
    "ParsedSourcePath",
    "QdpxContainer",
    "SourceScheme",
    "parse_source_path",
    "resolve_external_sources",
]

QDE_FILENAME = "project.qde"
SOURCES_DIRNAME = "sources"


class SourceScheme(Enum):
    """The three source-path URL schemes defined by REFI-QDA section 8.3."""

    INTERNAL = "internal"
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


@dataclass(slots=True, frozen=True)
class ParsedSourcePath:
    """A source ``path``/``currentPath`` attribute, split into scheme + value.

    ``value`` is the scheme-specific remainder with its leading slash(es)
    stripped: for :attr:`SourceScheme.INTERNAL` this is just a filename
    (e.g. ``"876dca5e-....pdf"``); for :attr:`SourceScheme.RELATIVE` and
    :attr:`SourceScheme.ABSOLUTE` it is a forward-slash-delimited path
    (e.g. ``"AR/John Interview.mp4"`` or ``"C:/PROJECT/Sources/..."``).
    """

    scheme: SourceScheme
    value: str


def parse_source_path(raw: str) -> ParsedSourcePath:
    """Parse a REFI-QDA source ``path``/``currentPath`` attribute.

    Raises :class:`refi_qda.exceptions.ExternalSourceError` if ``raw`` does
    not use one of the three schemes REFI-QDA defines (``internal://``,
    ``relative://``, ``absolute://``).
    """
    scheme_str, sep, rest = raw.partition("://")
    if not sep:
        raise ExternalSourceError(
            f"Source path {raw!r} has no recognised scheme "
            "(expected one of 'internal://', 'relative://', 'absolute://')."
        )
    try:
        scheme = SourceScheme(scheme_str)
    except ValueError as exc:
        raise ExternalSourceError(
            f"Source path {raw!r} uses unrecognised scheme {scheme_str!r} "
            "(expected one of 'internal', 'relative', 'absolute')."
        ) from exc
    # relative:// and absolute:// paths carry an extra leading '/' before
    # the actual path components (REFI-QDA's examples: 'relative:///AR/John
    # Interview.mp4'); internal:// does not.
    value = rest[1:] if scheme is not SourceScheme.INTERNAL and rest.startswith("/") else rest
    return ParsedSourcePath(scheme=scheme, value=value)


@dataclass(slots=True)
class ExternalSourceResolution:
    """The result of trying to locate one external source on this machine.

    ``resolved_path`` is a best-effort local filesystem candidate; it is
    *not* guaranteed to be correct, especially for ``absolute://`` paths
    recorded on a different OS (a Windows path like ``C:/PROJECT/...``
    cannot be faithfully resolved on macOS/Linux at all -- this is
    reported via ``exists=False`` and ``resolved_path`` still set to the
    best-effort candidate, rather than raised as an error, so callers can
    show the user exactly what was recorded).
    """

    source_guid: Guid
    source_name: str | None
    scheme: SourceScheme
    declared_path: str
    resolved_path: Path | None
    exists: bool


def resolve_external_sources(
    project: Project, *, base_path: str | None = None
) -> list[ExternalSourceResolution]:
    """Resolve every external (``relative://``/``absolute://``) source in ``project``.

    Internal sources are omitted from the result -- they live inside the
    ``.qdpx`` archive itself and are resolved via
    :meth:`QdpxContainer.read_internal_source`, not this function.

    :param base_path: overrides ``project.base_path`` (REFI-QDA's
        ``Project/@basePath``) as the root that ``relative://`` paths are
        joined against. Pass this when the project was exported with a
        base path that does not exist on this machine but you know the
        equivalent local root.
    """
    effective_base = base_path if base_path is not None else project.base_path
    results: list[ExternalSourceResolution] = []
    for source in project.sources:
        path_attr = getattr(source, "path", None)
        if not path_attr:
            continue
        parsed = parse_source_path(path_attr)
        if parsed.scheme is SourceScheme.INTERNAL:
            continue
        resolved: Path | None
        if parsed.scheme is SourceScheme.RELATIVE:
            if effective_base:
                resolved = Path(effective_base) / PurePosixPath(parsed.value)
            else:
                resolved = None
        else:  # ABSOLUTE
            resolved = Path(PurePosixPath(parsed.value))
        exists = resolved is not None and resolved.exists()
        results.append(
            ExternalSourceResolution(
                source_guid=source.guid,
                source_name=getattr(source, "name", None),
                scheme=parsed.scheme,
                declared_path=path_attr,
                resolved_path=resolved,
                exists=exists,
            )
        )
    return results


class QdpxContainer:
    """An open ``.qdpx`` archive.

    Use as a context manager::

        with QdpxContainer.open("interview_study.qdpx") as container:
            qde_bytes = container.read_qde()
            for filename in container.list_internal_sources():
                data = container.read_internal_source(filename)

    This class only deals with the ZIP/container layer. To get a parsed
    :class:`refi_qda.model.Project`, use :func:`refi_qda.parser.parse_qdpx`,
    which wraps this class.
    """

    def __init__(self, zip_file: zipfile.ZipFile, *, path: Path | None = None) -> None:
        self._zip = zip_file
        self._path = path
        self._sources_prefix = f"{SOURCES_DIRNAME}/"
        self._validate_structure()

    @classmethod
    def open(cls, path: str | Path) -> QdpxContainer:
        """Open a ``.qdpx`` file from disk.

        Raises :class:`refi_qda.exceptions.ContainerError` if it is not a
        readable ZIP file, or if its internal structure violates REFI-QDA
        section 8.1 (missing ``project.qde``, or a non-flat ``sources/``
        folder).
        """
        path = Path(path)
        try:
            zip_file = zipfile.ZipFile(path, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise ContainerError(f"{path} is not a readable .qdpx (ZIP) file: {exc}") from exc
        return cls(zip_file, path=path)

    def __enter__(self) -> QdpxContainer:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._zip.close()

    def _validate_structure(self) -> None:
        names = self._zip.namelist()
        if QDE_FILENAME not in names:
            raise ContainerError(
                f"{self._label()} does not contain a {QDE_FILENAME!r} file at its root "
                "(REFI-QDA section 8.1 requires exactly one)."
            )
        for name in names:
            if not name.startswith(self._sources_prefix):
                continue
            remainder = name[len(self._sources_prefix) :]
            if remainder == "":
                continue  # the sources/ directory entry itself
            if "/" in remainder.rstrip("/"):
                raise ContainerError(
                    f"{self._label()} has a non-flat sources/ folder ({name!r}); "
                    "REFI-QDA section 8.1 requires internal sources to sit directly "
                    "under sources/ with no subfolders."
                )

    def _label(self) -> str:
        return str(self._path) if self._path is not None else "this .qdpx archive"

    def read_qde(self) -> bytes:
        """Read the raw bytes of ``project.qde``."""
        return self._zip.read(QDE_FILENAME)

    def list_internal_sources(self) -> list[str]:
        """List filenames (not full paths) present under ``sources/``."""
        prefix = self._sources_prefix
        names = []
        for name in self._zip.namelist():
            if name.startswith(prefix) and name != prefix:
                names.append(name[len(prefix) :])
        return names

    def read_internal_source(self, filename: str) -> bytes:
        """Read one internal source's raw bytes by its filename under ``sources/``.

        ``filename`` is the GUID-based filename as it appears in
        ``sources/`` (i.e. the ``value`` of a :class:`ParsedSourcePath`
        with :attr:`SourceScheme.INTERNAL`), not the original filename
        recorded in ``currentPath``.
        """
        member = f"{self._sources_prefix}{filename}"
        try:
            return self._zip.read(member)
        except KeyError as exc:
            raise ContainerError(
                f"Internal source {filename!r} is referenced but not present in "
                f"{self._label()}'s sources/ folder."
            ) from exc

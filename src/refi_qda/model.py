"""Domain model for the REFI-QDA project exchange format.

This module is a fairly direct, typed translation of the ``Project.xsd``
schema referenced by REFI-QDA v1.5 section 8 ("urn:QDA-XML:project:1.0"),
built from the schema listing reproduced in the published standard rather
than the (Tresorit-gated) XSD file itself. Where the XSD reuses one complex
type in several places (most notably ``TextSourceType``, which is reused
for plain-text sources, PDF/picture text representations, *and* memos),
this module reuses one dataclass too, rather than inventing parallel types
that would drift out of sync.

The one deliberate exception to "mirror the XSD's type reuse" is
selections. REFI-QDA defines six distinct selection complex types
(``PlainTextSelectionType``, ``PDFSelectionType``, ``PictureSelectionType``,
``AudioSelectionType``, ``VideoSelectionType``, ``TranscriptSelectionType``)
because their coordinate systems are genuinely different -- Unicode
codepoint offsets, PDF page + point coordinates, pixel rectangles,
millisecond ranges, and synchronisation-point references, respectively.
This module keeps them as six distinct dataclasses rather than one
``Selection`` blob with a pile of optional fields, because collapsing them
is exactly how these coordinate systems end up silently misapplied to the
wrong source type.

Nothing in this module reads or writes XML; see :mod:`refi_qda.parser`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

__all__ = [
    "AudioSelection",
    "AudioSource",
    "Case",
    "Code",
    "Coding",
    "Edge",
    "Graph",
    "Guid",
    "LineStyle",
    "Link",
    "LinkDirection",
    "Memo",
    "PDFSelection",
    "PDFSource",
    "PictureSelection",
    "PictureSource",
    "PlainTextSelection",
    "Project",
    "Selection",
    "SetObject",
    "Shape",
    "Source",
    "SyncPoint",
    "TextSource",
    "Transcript",
    "TranscriptSelection",
    "User",
    "Variable",
    "VariableType",
    "VariableValue",
    "VariableValueScalar",
    "Vertex",
    "VideoSelection",
    "VideoSource",
]

#: REFI-QDA GUIDs are free-form tokens matching either the bare
#: ``8-4-4-4-12`` hex form or the same wrapped in braces. This library does
#: not normalise them (case and brace-wrapping are preserved as read) --
#: see :func:`refi_qda.parser.normalize_guid` for a comparison helper.
Guid = str


# --------------------------------------------------------------------------
# Users, codebook
# --------------------------------------------------------------------------


@dataclass(slots=True)
class User:
    """A REFI-QDA ``User`` -- an author/editor identity, not an app account."""

    guid: Guid
    name: str | None = None
    id: str | None = None


@dataclass(slots=True)
class Code:
    """A single code, possibly with nested child codes (REFI-QDA section 11).

    Hierarchy is represented directly by nesting, mirroring the XSD's
    recursive ``<xsd:element name="Code" type="CodeType" .../>`` inside
    ``CodeType`` itself. A code with ``is_codable=False`` is a folder/group
    used purely for organisation and is never itself applied to a
    selection.
    """

    guid: Guid
    name: str
    is_codable: bool
    color: str | None = None
    description: str | None = None
    note_refs: list[Guid] = field(default_factory=list)
    children: list[Code] = field(default_factory=list)

    def iter_all(self) -> list[Code]:
        """Return this code and every descendant, depth-first."""
        result = [self]
        for child in self.children:
            result.extend(child.iter_all())
        return result


# --------------------------------------------------------------------------
# Coding (the act of applying a code to a selection or source)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Coding:
    """A single application of one code to a selection or whole source.

    Multiple ``Coding`` entries may exist on the same selection (that is
    how REFI-QDA represents several codes applied to one span) and multiple
    selections may overlap on the same source -- both are ordinary, not
    edge cases, and this model does not attempt to merge or deduplicate
    them.
    """

    guid: Guid
    code_ref: Guid
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    note_refs: list[Guid] = field(default_factory=list)


# --------------------------------------------------------------------------
# Selections -- six distinct coordinate systems, six distinct types
# --------------------------------------------------------------------------


@dataclass(slots=True)
class PlainTextSelection:
    """A span of a plain-text source, in Unicode codepoints (REFI-QDA 10.2).

    ``start_position``/``end_position`` count codepoints from 0 at the
    start of the associated plain-text file -- *not* bytes, and not UTF-16
    code units.
    """

    guid: Guid
    start_position: int
    end_position: int
    name: str | None = None
    description: str | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class PDFSelection:
    """A selection within a PDF page (REFI-QDA 10.3).

    PDF selections are *not* character offsets into the PDF: they are
    ``(firstX, firstY)``-``(secondX, secondY)`` rectangles in PDF points,
    treating the page as an image, measured from the bottom-left of the
    page's media box, on a specific zero-based ``page``. A PDF selection
    may additionally carry a ``representation`` -- an inline or referenced
    plain-text transcription of that region -- which is itself modelled as
    a full :class:`TextSource` because that is what ``Representation``
    reuses in the schema.
    """

    guid: Guid
    page: int
    first_x: int
    first_y: int
    second_x: int
    second_y: int
    name: str | None = None
    description: str | None = None
    representation: TextSource | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class PictureSelection:
    """A rectangular region of a still image (REFI-QDA 10.4).

    ``(firstX, firstY)`` is the upper-left corner and ``(secondX,
    secondY)`` the lower-right corner, in pixels of the image's *final
    rotated space* (i.e. after applying any EXIF/metadata rotation) --
    there is no page number, unlike :class:`PDFSelection`.
    """

    guid: Guid
    first_x: int
    first_y: int
    second_x: int
    second_y: int
    name: str | None = None
    description: str | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class AudioSelection:
    """A time range of an audio source, in milliseconds (REFI-QDA 10.4)."""

    guid: Guid
    begin: int
    end: int
    name: str | None = None
    description: str | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class VideoSelection:
    """A time range of a video source, in milliseconds (REFI-QDA 10.4)."""

    guid: Guid
    begin: int
    end: int
    name: str | None = None
    description: str | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class TranscriptSelection:
    """A span of a :class:`Transcript`, anchored to sync points.

    Unlike the other five selection kinds, this is not a self-contained
    coordinate: ``from_sync_point``/``to_sync_point`` are GUID references
    to :class:`SyncPoint` entries on the owning ``Transcript``, which are
    what actually tie transcript text to a media timestamp.
    """

    guid: Guid
    name: str | None = None
    description: str | None = None
    from_sync_point: Guid | None = None
    to_sync_point: Guid | None = None
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


Selection = (
    PlainTextSelection
    | PDFSelection
    | PictureSelection
    | AudioSelection
    | VideoSelection
    | TranscriptSelection
)


# --------------------------------------------------------------------------
# Transcripts (audio/video <-> text synchronisation)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class SyncPoint:
    """One synchronisation point between transcript text and media time.

    ``position`` is a character offset into the transcript's plain text;
    ``timeStamp`` is milliseconds into the associated audio/video. Either
    may be absent per the schema (``xsd:integer`` with no ``use`` set),
    though a sync point with neither is not useful.
    """

    guid: Guid
    position: int | None = None
    time_stamp: int | None = None


@dataclass(slots=True)
class Transcript:
    """A text transcription of an audio/video source, with sync points.

    A single audio or video source may have more than one ``Transcript``
    (e.g. a verbatim transcript and a translated one); REFI-QDA does not
    otherwise distinguish them.
    """

    guid: Guid
    name: str | None = None
    description: str | None = None
    plain_text_content: str | None = None
    plain_text_path: str | None = None
    rich_text_path: str | None = None
    sync_points: list[SyncPoint] = field(default_factory=list)
    selections: list[TranscriptSelection] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


@dataclass(slots=True)
class TextSource:
    """A plain-text source, per REFI-QDA 9.1.2/9.1.3.

    The schema's ``TextSourceType`` is reused in four places in REFI-QDA,
    and this dataclass is reused the same way in this model:

    * as a top-level ``<TextSource>`` in ``Project/Sources``;
    * as ``PictureSource.text_description`` (a textual description of an
      image, itself selectable and codable);
    * as ``PDFSource.representation`` / ``PDFSelection.representation``
      (the plain-text transcription a PDF or PDF region is selected
      against -- see REFI-QDA 10.3); and
    * as every entry in ``Project.notes`` -- memos are, structurally,
      ``TextSourceType`` too. See the :data:`Memo` alias below.

    Exactly one of ``plain_text_content`` / ``plain_text_path`` should be
    set for a "real" source (inline text vs. a reference into
    ``sources/``); this library does not enforce that XOR at parse time,
    it only reports what was present.

    Rich text: ``rich_text_path`` records a reference to an accompanying
    DOCX/RTF file, but this library does not parse DOCX/RTF *content* --
    only the plain-text sibling and its character-offset selections are
    modelled, because that is what REFI-QDA selections are actually
    defined against (REFI-QDA 9.1.3).
    """

    guid: Guid
    name: str | None = None
    description: str | None = None
    plain_text_content: str | None = None
    plain_text_path: str | None = None
    rich_text_path: str | None = None
    selections: list[PlainTextSelection] = field(default_factory=list)
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


#: A memo/note is, per the schema, structurally identical to a
#: :class:`TextSource` (``NotesType`` is a sequence of elements of
#: ``TextSourceType``). This alias exists purely for readability at call
#: sites (``Project.notes: list[Memo]``); it is not a distinct runtime
#: type. Memos are attached to sources, codes, cases, selections, links
#: and sets alike via ``NoteRef`` (a GUID reference), which this model
#: represents as ``note_refs: list[Guid]`` fields throughout.
Memo = TextSource


@dataclass(slots=True)
class PictureSource:
    """A still-image source (JPEG/PNG per REFI-QDA 9.1.5)."""

    guid: Guid
    name: str | None = None
    description: str | None = None
    path: str | None = None
    current_path: str | None = None
    text_description: TextSource | None = None
    selections: list[PictureSelection] = field(default_factory=list)
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class PDFSource:
    """A PDF document source (REFI-QDA 9.1.4).

    ``representation`` is the plain-text transcription of the whole PDF
    that character-offset-based selections on the document (as opposed to
    the page/point-based :class:`PDFSelection`) are measured against.
    """

    guid: Guid
    name: str | None = None
    description: str | None = None
    path: str | None = None
    current_path: str | None = None
    representation: TextSource | None = None
    selections: list[PDFSelection] = field(default_factory=list)
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class AudioSource:
    """An audio source (REFI-QDA 9.1.6). May have multiple transcripts."""

    guid: Guid
    name: str | None = None
    description: str | None = None
    path: str | None = None
    current_path: str | None = None
    transcripts: list[Transcript] = field(default_factory=list)
    selections: list[AudioSelection] = field(default_factory=list)
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


@dataclass(slots=True)
class VideoSource:
    """A video source (REFI-QDA 9.1.6). May have multiple transcripts."""

    guid: Guid
    name: str | None = None
    description: str | None = None
    path: str | None = None
    current_path: str | None = None
    transcripts: list[Transcript] = field(default_factory=list)
    selections: list[VideoSelection] = field(default_factory=list)
    codings: list[Coding] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    creating_user: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user: Guid | None = None
    modified_datetime: datetime | None = None


Source = TextSource | PictureSource | PDFSource | AudioSource | VideoSource


# --------------------------------------------------------------------------
# Variables & cases
# --------------------------------------------------------------------------


class VariableType(Enum):
    """The six variable data types defined by REFI-QDA's ``typeOfVariableType``."""

    TEXT = "Text"
    BOOLEAN = "Boolean"
    INTEGER = "Integer"
    FLOAT = "Float"
    DATE = "Date"
    DATE_TIME = "DateTime"


@dataclass(slots=True)
class Variable:
    """A variable/attribute definition (REFI-QDA section 13).

    This is the *definition* (name + type); actual values live on
    :class:`VariableValue`, attached to whichever :class:`Case` or source
    carries them.
    """

    guid: Guid
    name: str
    type_of_variable: VariableType
    description: str | None = None


#: The typed value carried by a single ``VariableValue``. REFI-QDA's
#: ``VariableValueType`` is an ``xsd:choice`` of exactly one of six typed
#: elements (or none, representing a null/unset value for that variable on
#: that case/source).
VariableValueScalar = str | bool | int | Decimal | date | datetime


@dataclass(slots=True)
class VariableValue:
    """One variable's value on a particular case or source.

    ``variable_ref`` is the GUID of the :class:`Variable` this value is
    for; resolve it via :meth:`Project.find_variable`.
    """

    variable_ref: Guid
    value: VariableValueScalar | None = None


@dataclass(slots=True)
class Case:
    """A case: the subject/object/topic sources and selections are grouped by
    (REFI-QDA section 13), e.g. a single interviewee across several
    interviews.
    """

    guid: Guid
    name: str | None = None
    description: str | None = None
    code_refs: list[Guid] = field(default_factory=list)
    variable_values: list[VariableValue] = field(default_factory=list)
    source_refs: list[Guid] = field(default_factory=list)
    selection_refs: list[Guid] = field(default_factory=list)


# --------------------------------------------------------------------------
# Sets
# --------------------------------------------------------------------------


@dataclass(slots=True)
class SetObject:
    """A named, freeform grouping of sources, codes and/or memos (REFI-QDA 12).

    Named ``SetObject`` (not ``Set``) to avoid colliding with the builtin
    ``set`` type at import sites that do ``from refi_qda.model import *``.
    """

    guid: Guid
    name: str
    description: str | None = None
    member_codes: list[Guid] = field(default_factory=list)
    member_sources: list[Guid] = field(default_factory=list)
    member_notes: list[Guid] = field(default_factory=list)


# --------------------------------------------------------------------------
# Links
# --------------------------------------------------------------------------


class LinkDirection(Enum):
    """Directionality of a :class:`Link` or :class:`Edge`."""

    ASSOCIATIVE = "Associative"
    ONE_WAY = "OneWay"
    BIDIRECTIONAL = "Bidirectional"


@dataclass(slots=True)
class Link:
    """A relation between two arbitrary REFI-QDA objects, by GUID.

    REFI-QDA does not constrain what ``origin_guid``/``target_guid`` point
    at -- in practice, codes, sources, selections, memos and cases have all
    been observed as link endpoints across vendor exports. This model does
    not attempt to resolve them to a specific type; use
    :meth:`Project.find_by_guid` if you need to.
    """

    guid: Guid
    name: str | None = None
    direction: LinkDirection | None = None
    color: str | None = None
    origin_guid: Guid | None = None
    target_guid: Guid | None = None
    note_refs: list[Guid] = field(default_factory=list)


# --------------------------------------------------------------------------
# Graphs
# --------------------------------------------------------------------------


class Shape(Enum):
    """Vertex shapes defined by REFI-QDA's ``ShapeType``."""

    PERSON = "Person"
    OVAL = "Oval"
    RECTANGLE = "Rectangle"
    ROUNDED_RECTANGLE = "RoundedRectangle"
    STAR = "Star"
    LEFT_TRIANGLE = "LeftTriangle"
    RIGHT_TRIANGLE = "RightTriangle"
    UP_TRIANGLE = "UpTriangle"
    DOWN_TRIANGLE = "DownTriangle"
    NOTE = "Note"


class LineStyle(Enum):
    """Edge line styles defined by REFI-QDA's ``LineStyleType``."""

    DOTTED = "dotted"
    DASHED = "dashed"
    SOLID = "solid"


@dataclass(slots=True)
class Vertex:
    """A node in a :class:`Graph`, optionally representing another object."""

    guid: Guid
    first_x: int
    first_y: int
    represented_guid: Guid | None = None
    name: str | None = None
    second_x: int | None = None
    second_y: int | None = None
    shape: Shape | None = None
    color: str | None = None


@dataclass(slots=True)
class Edge:
    """A connection between two :class:`Vertex` entries in a :class:`Graph`."""

    guid: Guid
    source_vertex: Guid
    target_vertex: Guid
    represented_guid: Guid | None = None
    name: str | None = None
    color: str | None = None
    direction: LinkDirection | None = None
    line_style: LineStyle | None = None


@dataclass(slots=True)
class Graph:
    """A two-dimensional visualisation of vertices and edges (REFI-QDA 14).

    This library parses graphs structurally (vertices, edges, and what
    they represent/connect) but does not interpret or render them -- see
    ``SPEC.md`` for what "in scope" means for graphs here.
    """

    guid: Guid
    name: str | None = None
    vertices: list[Vertex] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


# --------------------------------------------------------------------------
# Project (the root object)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Project:
    """The root REFI-QDA project object, as parsed from ``project.qde``.

    Provides a handful of GUID lookup helpers because almost everything in
    this model refers to almost everything else purely by GUID (codings to
    codes, sets to sources/codes/notes, cases to sources/selections, links
    to arbitrary objects, ...) and re-implementing that traversal at every
    call site is exactly the kind of thing that quietly rots.
    """

    name: str
    origin: str | None = None
    creating_user_guid: Guid | None = None
    creation_datetime: datetime | None = None
    modifying_user_guid: Guid | None = None
    modified_datetime: datetime | None = None
    base_path: str | None = None
    description: str | None = None
    users: list[User] = field(default_factory=list)
    codebook: list[Code] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    notes: list[Memo] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    sets: list[SetObject] = field(default_factory=list)
    graphs: list[Graph] = field(default_factory=list)
    note_refs: list[Guid] = field(default_factory=list)

    def iter_codes(self) -> list[Code]:
        """All codes in the codebook, flattened depth-first (folders included)."""
        result: list[Code] = []
        for top in self.codebook:
            result.extend(top.iter_all())
        return result

    def find_code(self, guid: Guid) -> Code | None:
        """Find a code anywhere in the codebook hierarchy by GUID."""
        for code in self.iter_codes():
            if code.guid == guid:
                return code
        return None

    def find_source(self, guid: Guid) -> Source | None:
        """Find a top-level source by GUID.

        Does not search nested ``TextSource``-shaped content (PDF/picture
        representations, transcripts) -- those are reached via the owning
        source, since their GUIDs are only meaningful in that context.
        """
        for source in self.sources:
            if source.guid == guid:
                return source
        return None

    def find_case(self, guid: Guid) -> Case | None:
        """Find a case by GUID."""
        for case in self.cases:
            if case.guid == guid:
                return case
        return None

    def find_variable(self, guid: Guid) -> Variable | None:
        """Find a variable definition by GUID."""
        for variable in self.variables:
            if variable.guid == guid:
                return variable
        return None

    def find_set(self, guid: Guid) -> SetObject | None:
        """Find a set by GUID."""
        for set_object in self.sets:
            if set_object.guid == guid:
                return set_object
        return None

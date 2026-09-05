"""Serialising a :class:`refi_qda.model.Project` to ``project.qde``/``.qdpx``.

This module is the exact mirror image of :mod:`refi_qda.parser`: for every
``_parse_x`` function there, this module has a ``_write_x`` function that
produces precisely the XML shape the parser reads back. Element order
follows REFI-QDA v1.5 section 5.3's ``Project.xsd`` ``xsd:sequence``
declarations (obtained from the published standard, not guessed), because
XSD sequences are order-sensitive even though :mod:`refi_qda.parser` itself
is order-agnostic (it locates children by tag via ``.find()``/``.findall()``
rather than by position). Writing in schema order is what makes the output
of this module validatable against the real XSD, not just readable by this
library's own parser.

Nothing in this module knows how to *read* XML; see :mod:`refi_qda.parser`.
The ZIP container layer is handled by :func:`write_qdpx` in terms of
:mod:`refi_qda.container`'s existing internal/external source-path
machinery, not a second implementation of it.
"""

from __future__ import annotations

import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lxml import etree

from refi_qda.container import (
    QDE_FILENAME,
    SOURCES_DIRNAME,
    SourceScheme,
    parse_source_path,
)
from refi_qda.exceptions import ExternalSourceError
from refi_qda.model import (
    AudioSelection,
    AudioSource,
    Case,
    Code,
    Coding,
    Edge,
    Graph,
    Guid,
    Link,
    PDFSelection,
    PDFSource,
    PictureSelection,
    PictureSource,
    PlainTextSelection,
    Project,
    SetObject,
    Source,
    SyncPoint,
    TextSource,
    Transcript,
    TranscriptSelection,
    User,
    Variable,
    VariableValue,
    VariableValueScalar,
    Vertex,
    VideoSelection,
    VideoSource,
)
from refi_qda.parser import NS_URI

if TYPE_CHECKING:
    from pathlib import Path

    from lxml.etree import _Element

__all__ = ["to_qde", "write_qdpx"]

_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_NSMAP = {None: NS_URI, "xsi": _XSI_NS}
#: Matches the schemaLocation this library's own hand-authored fixture and
#: REFI-QDA v1.5 section 5.3 both point at; purely advisory to consumers,
#: not required for this library's own round trip.
_PROJECT_XSD_LOCATION = f"{NS_URI} http://schema.qdasoftware.org/versions/Project/v1.0/Project.xsd"


# --------------------------------------------------------------------------
# Generic element/attribute helpers
# --------------------------------------------------------------------------


def _qn(tag: str) -> str:
    return f"{{{NS_URI}}}{tag}"


def _sub(parent: _Element, tag: str) -> _Element:
    return etree.SubElement(parent, _qn(tag))


def _sub_text(parent: _Element, tag: str, text: str) -> _Element:
    el = _sub(parent, tag)
    el.text = text
    return el


def _set_attr(el: _Element, name: str, value: str | None) -> None:
    # None means "attribute absent", not "attribute empty" -- see the
    # parser's own None/absent distinction (el.get() returns None for an
    # absent attribute), which this must mirror exactly for round-tripping.
    if value is not None:
        el.set(name, value)


def _set_int_attr(el: _Element, name: str, value: int | None) -> None:
    if value is not None:
        el.set(name, str(value))


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _dt_str(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _write_ref(parent: _Element, tag: str, target_guid: Guid) -> None:
    el = _sub(parent, tag)
    el.set("targetGUID", target_guid)


def _write_refs(parent: _Element, tag: str, target_guids: list[Guid]) -> None:
    for guid in target_guids:
        _write_ref(parent, tag, guid)


def _write_audit_attrs(
    el: _Element,
    creating_user: Guid | None,
    creation_datetime: datetime | None,
    modifying_user: Guid | None,
    modified_datetime: datetime | None,
) -> None:
    """Write the (creatingUser, creationDateTime, modifyingUser, modifiedDateTime)
    attribute quartet nearly every REFI-QDA element carries -- the inverse
    of the parser's ``_audit()`` helper."""
    _set_attr(el, "creatingUser", creating_user)
    _set_attr(el, "creationDateTime", _dt_str(creation_datetime))
    _set_attr(el, "modifyingUser", modifying_user)
    _set_attr(el, "modifiedDateTime", _dt_str(modified_datetime))


# --------------------------------------------------------------------------
# Users, codebook, variables
# --------------------------------------------------------------------------


def _write_user(parent: _Element, user: User) -> None:
    el = _sub(parent, "User")
    el.set("guid", user.guid)
    _set_attr(el, "name", user.name)
    _set_attr(el, "id", user.id)


def _write_code(parent: _Element, code: Code) -> None:
    # CodeType sequence: Description?, NoteRef*, Code* (children) -- REFI-QDA 1.5 §5.3.
    el = _sub(parent, "Code")
    el.set("guid", code.guid)
    el.set("name", code.name)
    el.set("isCodable", _bool_str(code.is_codable))
    _set_attr(el, "color", code.color)
    if code.description is not None:
        _sub_text(el, "Description", code.description)
    _write_refs(el, "NoteRef", code.note_refs)
    for child in code.children:
        _write_code(el, child)


def _write_variable(parent: _Element, variable: Variable) -> None:
    el = _sub(parent, "Variable")
    el.set("guid", variable.guid)
    el.set("name", variable.name)
    el.set("typeOfVariable", variable.type_of_variable.value)
    if variable.description is not None:
        _sub_text(el, "Description", variable.description)


def _write_variable_value_scalar(el: _Element, value: VariableValueScalar) -> None:
    # bool before int (bool is an int subclass) and datetime before date
    # (datetime is a date subclass) -- mirrors the choice order in
    # VariableValueType, REFI-QDA 1.5 §5.3.
    if isinstance(value, bool):
        _sub_text(el, "BooleanValue", _bool_str(value))
    elif isinstance(value, datetime):
        _sub_text(el, "DateTimeValue", value.isoformat())
    elif isinstance(value, date):
        _sub_text(el, "DateValue", value.isoformat())
    elif isinstance(value, int):
        _sub_text(el, "IntegerValue", str(value))
    elif isinstance(value, Decimal):
        _sub_text(el, "FloatValue", str(value))
    elif isinstance(value, str):
        _sub_text(el, "TextValue", value)
    else:  # pragma: no cover - VariableValueScalar is a closed union
        raise TypeError(f"Unsupported VariableValue scalar type: {type(value)!r}")


def _write_variable_value(parent: _Element, variable_value: VariableValue) -> None:
    el = _sub(parent, "VariableValue")
    _write_ref(el, "VariableRef", variable_value.variable_ref)
    if variable_value.value is not None:
        _write_variable_value_scalar(el, variable_value.value)


def _write_variable_values(parent: _Element, variable_values: list[VariableValue]) -> None:
    for variable_value in variable_values:
        _write_variable_value(parent, variable_value)


# --------------------------------------------------------------------------
# Codings
# --------------------------------------------------------------------------


def _write_coding(parent: _Element, coding: Coding) -> None:
    el = _sub(parent, "Coding")
    el.set("guid", coding.guid)
    _set_attr(el, "creatingUser", coding.creating_user)
    _set_attr(el, "creationDateTime", _dt_str(coding.creation_datetime))
    _write_ref(el, "CodeRef", coding.code_ref)
    _write_refs(el, "NoteRef", coding.note_refs)


def _write_codings(parent: _Element, codings: list[Coding]) -> None:
    for coding in codings:
        _write_coding(parent, coding)


# --------------------------------------------------------------------------
# Selections (six distinct coordinate systems -- see model.py)
# --------------------------------------------------------------------------


def _write_plain_text_selection(parent: _Element, selection: PlainTextSelection) -> None:
    el = _sub(parent, "PlainTextSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    el.set("startPosition", str(selection.start_position))
    el.set("endPosition", str(selection.end_position))
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


def _write_pdf_selection(parent: _Element, selection: PDFSelection) -> None:
    el = _sub(parent, "PDFSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    el.set("page", str(selection.page))
    el.set("firstX", str(selection.first_x))
    el.set("firstY", str(selection.first_y))
    el.set("secondX", str(selection.second_x))
    el.set("secondY", str(selection.second_y))
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    if selection.representation is not None:
        _write_text_source_type(el, "Representation", selection.representation)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


def _write_picture_selection(parent: _Element, selection: PictureSelection) -> None:
    el = _sub(parent, "PictureSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    el.set("firstX", str(selection.first_x))
    el.set("firstY", str(selection.first_y))
    el.set("secondX", str(selection.second_x))
    el.set("secondY", str(selection.second_y))
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


def _write_audio_selection(parent: _Element, selection: AudioSelection) -> None:
    el = _sub(parent, "AudioSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    el.set("begin", str(selection.begin))
    el.set("end", str(selection.end))
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


def _write_video_selection(parent: _Element, selection: VideoSelection) -> None:
    el = _sub(parent, "VideoSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    el.set("begin", str(selection.begin))
    el.set("end", str(selection.end))
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


def _write_transcript_selection(parent: _Element, selection: TranscriptSelection) -> None:
    el = _sub(parent, "TranscriptSelection")
    el.set("guid", selection.guid)
    _set_attr(el, "name", selection.name)
    _set_attr(el, "fromSyncPoint", selection.from_sync_point)
    _set_attr(el, "toSyncPoint", selection.to_sync_point)
    _write_audit_attrs(
        el,
        selection.creating_user,
        selection.creation_datetime,
        selection.modifying_user,
        selection.modified_datetime,
    )
    if selection.description is not None:
        _sub_text(el, "Description", selection.description)
    _write_codings(el, selection.codings)
    _write_refs(el, "NoteRef", selection.note_refs)


# --------------------------------------------------------------------------
# Transcripts
# --------------------------------------------------------------------------


def _write_sync_point(parent: _Element, sync_point: SyncPoint) -> None:
    el = _sub(parent, "SyncPoint")
    el.set("guid", sync_point.guid)
    _set_int_attr(el, "timeStamp", sync_point.time_stamp)
    _set_int_attr(el, "position", sync_point.position)


def _write_transcript(parent: _Element, transcript: Transcript) -> None:
    el = _sub(parent, "Transcript")
    el.set("guid", transcript.guid)
    _set_attr(el, "name", transcript.name)
    _set_attr(el, "richTextPath", transcript.rich_text_path)
    _set_attr(el, "plainTextPath", transcript.plain_text_path)
    _write_audit_attrs(
        el,
        transcript.creating_user,
        transcript.creation_datetime,
        transcript.modifying_user,
        transcript.modified_datetime,
    )
    if transcript.description is not None:
        _sub_text(el, "Description", transcript.description)
    if transcript.plain_text_content is not None:
        _sub_text(el, "PlainTextContent", transcript.plain_text_content)
    for sync_point in transcript.sync_points:
        _write_sync_point(el, sync_point)
    for selection in transcript.selections:
        _write_transcript_selection(el, selection)
    _write_refs(el, "NoteRef", transcript.note_refs)


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


def _write_text_source_type(parent: _Element, tag: str, text_source: TextSource) -> _Element:
    """Write anything shaped like the schema's ``TextSourceType``.

    Reused for top-level ``<TextSource>``, ``<Representation>`` (on PDF
    sources/selections), ``<TextDescription>`` (on picture sources) and
    ``<Note>`` (memos) alike -- mirrors :func:`refi_qda.parser._parse_text_content`,
    which reads all four the same way because they are the same XSD complex
    type. See :data:`refi_qda.model.Memo`.
    """
    el = _sub(parent, tag)
    el.set("guid", text_source.guid)
    _set_attr(el, "name", text_source.name)
    _set_attr(el, "richTextPath", text_source.rich_text_path)
    _set_attr(el, "plainTextPath", text_source.plain_text_path)
    _write_audit_attrs(
        el,
        text_source.creating_user,
        text_source.creation_datetime,
        text_source.modifying_user,
        text_source.modified_datetime,
    )
    if text_source.description is not None:
        _sub_text(el, "Description", text_source.description)
    if text_source.plain_text_content is not None:
        _sub_text(el, "PlainTextContent", text_source.plain_text_content)
    for selection in text_source.selections:
        _write_plain_text_selection(el, selection)
    _write_codings(el, text_source.codings)
    _write_refs(el, "NoteRef", text_source.note_refs)
    _write_variable_values(el, text_source.variable_values)
    return el


def _write_picture_source(parent: _Element, source: PictureSource) -> None:
    el = _sub(parent, "PictureSource")
    el.set("guid", source.guid)
    _set_attr(el, "name", source.name)
    _set_attr(el, "path", source.path)
    _set_attr(el, "currentPath", source.current_path)
    _write_audit_attrs(
        el,
        source.creating_user,
        source.creation_datetime,
        source.modifying_user,
        source.modified_datetime,
    )
    if source.description is not None:
        _sub_text(el, "Description", source.description)
    if source.text_description is not None:
        _write_text_source_type(el, "TextDescription", source.text_description)
    for selection in source.selections:
        _write_picture_selection(el, selection)
    _write_codings(el, source.codings)
    _write_refs(el, "NoteRef", source.note_refs)
    _write_variable_values(el, source.variable_values)


def _write_pdf_source(parent: _Element, source: PDFSource) -> None:
    # PDFSourceType sequence: Description?, PDFSelection*, Representation?,
    # Coding*, NoteRef*, VariableValue* -- note Representation comes AFTER
    # the selections in the schema, unlike PDFSelectionType (below), where
    # it comes before Coding.
    el = _sub(parent, "PDFSource")
    el.set("guid", source.guid)
    _set_attr(el, "name", source.name)
    _set_attr(el, "path", source.path)
    _set_attr(el, "currentPath", source.current_path)
    _write_audit_attrs(
        el,
        source.creating_user,
        source.creation_datetime,
        source.modifying_user,
        source.modified_datetime,
    )
    if source.description is not None:
        _sub_text(el, "Description", source.description)
    for selection in source.selections:
        _write_pdf_selection(el, selection)
    if source.representation is not None:
        _write_text_source_type(el, "Representation", source.representation)
    _write_codings(el, source.codings)
    _write_refs(el, "NoteRef", source.note_refs)
    _write_variable_values(el, source.variable_values)


def _write_audio_source(parent: _Element, source: AudioSource) -> None:
    el = _sub(parent, "AudioSource")
    el.set("guid", source.guid)
    _set_attr(el, "name", source.name)
    _set_attr(el, "path", source.path)
    _set_attr(el, "currentPath", source.current_path)
    _write_audit_attrs(
        el,
        source.creating_user,
        source.creation_datetime,
        source.modifying_user,
        source.modified_datetime,
    )
    if source.description is not None:
        _sub_text(el, "Description", source.description)
    for transcript in source.transcripts:
        _write_transcript(el, transcript)
    for selection in source.selections:
        _write_audio_selection(el, selection)
    _write_codings(el, source.codings)
    _write_refs(el, "NoteRef", source.note_refs)
    _write_variable_values(el, source.variable_values)


def _write_video_source(parent: _Element, source: VideoSource) -> None:
    el = _sub(parent, "VideoSource")
    el.set("guid", source.guid)
    _set_attr(el, "name", source.name)
    _set_attr(el, "path", source.path)
    _set_attr(el, "currentPath", source.current_path)
    _write_audit_attrs(
        el,
        source.creating_user,
        source.creation_datetime,
        source.modifying_user,
        source.modified_datetime,
    )
    if source.description is not None:
        _sub_text(el, "Description", source.description)
    for transcript in source.transcripts:
        _write_transcript(el, transcript)
    for selection in source.selections:
        _write_video_selection(el, selection)
    _write_codings(el, source.codings)
    _write_refs(el, "NoteRef", source.note_refs)
    _write_variable_values(el, source.variable_values)


def _write_sources(parent: _Element, sources: list[Source]) -> None:
    for source in sources:
        if isinstance(source, TextSource):
            _write_text_source_type(parent, "TextSource", source)
        elif isinstance(source, PictureSource):
            _write_picture_source(parent, source)
        elif isinstance(source, PDFSource):
            _write_pdf_source(parent, source)
        elif isinstance(source, AudioSource):
            _write_audio_source(parent, source)
        elif isinstance(source, VideoSource):
            _write_video_source(parent, source)
        else:  # pragma: no cover - Source is a closed union
            raise TypeError(f"Unrecognised source type: {type(source)!r}")


# --------------------------------------------------------------------------
# Cases, sets, links, graphs
# --------------------------------------------------------------------------


def _write_case(parent: _Element, case: Case) -> None:
    el = _sub(parent, "Case")
    el.set("guid", case.guid)
    _set_attr(el, "name", case.name)
    if case.description is not None:
        _sub_text(el, "Description", case.description)
    _write_refs(el, "CodeRef", case.code_refs)
    _write_variable_values(el, case.variable_values)
    _write_refs(el, "SourceRef", case.source_refs)
    _write_refs(el, "SelectionRef", case.selection_refs)


def _write_set(parent: _Element, set_object: SetObject) -> None:
    el = _sub(parent, "Set")
    el.set("guid", set_object.guid)
    el.set("name", set_object.name)
    if set_object.description is not None:
        _sub_text(el, "Description", set_object.description)
    _write_refs(el, "MemberCode", set_object.member_codes)
    _write_refs(el, "MemberSource", set_object.member_sources)
    _write_refs(el, "MemberNote", set_object.member_notes)


def _write_link(parent: _Element, link: Link) -> None:
    el = _sub(parent, "Link")
    el.set("guid", link.guid)
    _set_attr(el, "name", link.name)
    _set_attr(el, "direction", link.direction.value if link.direction is not None else None)
    _set_attr(el, "color", link.color)
    _set_attr(el, "originGUID", link.origin_guid)
    _set_attr(el, "targetGUID", link.target_guid)
    _write_refs(el, "NoteRef", link.note_refs)


def _write_vertex(parent: _Element, vertex: Vertex) -> None:
    el = _sub(parent, "Vertex")
    el.set("guid", vertex.guid)
    _set_attr(el, "representedGUID", vertex.represented_guid)
    _set_attr(el, "name", vertex.name)
    el.set("firstX", str(vertex.first_x))
    el.set("firstY", str(vertex.first_y))
    _set_int_attr(el, "secondX", vertex.second_x)
    _set_int_attr(el, "secondY", vertex.second_y)
    _set_attr(el, "shape", vertex.shape.value if vertex.shape is not None else None)
    _set_attr(el, "color", vertex.color)


def _write_edge(parent: _Element, edge: Edge) -> None:
    el = _sub(parent, "Edge")
    el.set("guid", edge.guid)
    _set_attr(el, "representedGUID", edge.represented_guid)
    _set_attr(el, "name", edge.name)
    el.set("sourceVertex", edge.source_vertex)
    el.set("targetVertex", edge.target_vertex)
    _set_attr(el, "color", edge.color)
    _set_attr(el, "direction", edge.direction.value if edge.direction is not None else None)
    _set_attr(el, "lineStyle", edge.line_style.value if edge.line_style is not None else None)


def _write_graph(parent: _Element, graph: Graph) -> None:
    el = _sub(parent, "Graph")
    el.set("guid", graph.guid)
    _set_attr(el, "name", graph.name)
    for vertex in graph.vertices:
        _write_vertex(el, vertex)
    for edge in graph.edges:
        _write_edge(el, edge)


# --------------------------------------------------------------------------
# Project (root)
# --------------------------------------------------------------------------


def _write_project(project: Project) -> _Element:
    # ProjectType sequence, REFI-QDA 1.5 §5.3: Users?, CodeBook?, Variables?,
    # Cases?, Sources?, Notes?, Links?, Sets?, Graphs?, Description?, NoteRef*.
    # Each *Type wrapping a list (UsersType, VariablesType, ...) requires at
    # least one child element, so an empty list omits the wrapper entirely
    # rather than writing e.g. an empty <Users/> -- matching what the parser
    # treats as equivalent to "no such element".
    # lxml-stubs types nsmap as Mapping[str, str], but lxml itself accepts
    # (and this needs) a None key to declare the default namespace.
    root = etree.Element(_qn("Project"), nsmap=_NSMAP)  # type: ignore[arg-type]
    root.set(f"{{{_XSI_NS}}}schemaLocation", _PROJECT_XSD_LOCATION)
    root.set("name", project.name)
    _set_attr(root, "origin", project.origin)
    _set_attr(root, "creatingUserGUID", project.creating_user_guid)
    _set_attr(root, "creationDateTime", _dt_str(project.creation_datetime))
    _set_attr(root, "modifyingUserGUID", project.modifying_user_guid)
    _set_attr(root, "modifiedDateTime", _dt_str(project.modified_datetime))
    _set_attr(root, "basePath", project.base_path)

    if project.users:
        users_el = _sub(root, "Users")
        for user in project.users:
            _write_user(users_el, user)

    if project.codebook:
        codebook_el = _sub(root, "CodeBook")
        codes_el = _sub(codebook_el, "Codes")
        for code in project.codebook:
            _write_code(codes_el, code)

    if project.variables:
        variables_el = _sub(root, "Variables")
        for variable in project.variables:
            _write_variable(variables_el, variable)

    if project.cases:
        cases_el = _sub(root, "Cases")
        for case in project.cases:
            _write_case(cases_el, case)

    if project.sources:
        sources_el = _sub(root, "Sources")
        _write_sources(sources_el, project.sources)

    if project.notes:
        notes_el = _sub(root, "Notes")
        for note in project.notes:
            _write_text_source_type(notes_el, "Note", note)

    if project.links:
        links_el = _sub(root, "Links")
        for link in project.links:
            _write_link(links_el, link)

    if project.sets:
        sets_el = _sub(root, "Sets")
        for set_object in project.sets:
            _write_set(sets_el, set_object)

    if project.graphs:
        graphs_el = _sub(root, "Graphs")
        for graph in project.graphs:
            _write_graph(graphs_el, graph)

    if project.description is not None:
        _sub_text(root, "Description", project.description)

    _write_refs(root, "NoteRef", project.note_refs)

    return root


def to_qde(project: Project) -> bytes:
    """Serialise a :class:`Project` into raw ``project.qde`` XML bytes.

    The exact inverse of :func:`refi_qda.parser.parse_qde`: every element
    and attribute this writes is exactly what that function reads, in the
    element order given by ``ProjectType``'s ``xsd:sequence`` (REFI-QDA
    v1.5 section 5.3), and encoded as UTF-8 so non-ASCII content (this
    library's first consumer's data is Greek) round-trips byte-for-byte
    rather than being escaped into numeric character references.
    """
    root = _write_project(project)
    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True, pretty_print=True
    )


def write_qdpx(
    project: Project,
    path: str | Path,
    *,
    source_files: dict[Guid, Path] | None = None,
) -> None:
    """Write a complete ``.qdpx`` file for ``project`` (REFI-QDA v1.5 section 8.1).

    Produces a ZIP containing ``project.qde`` (via :func:`to_qde`) and,
    optionally, a flat ``sources/`` folder.

    :param source_files: maps a top-level source's GUID to a file on disk
        to bundle into ``sources/``. This function does not decide or
        rewrite which sources are internal vs. external -- that is already
        recorded in ``project`` itself, exactly as
        :func:`refi_qda.container.parse_source_path` reads it back (an
        ``internal://<filename>`` ``path``/``plainTextPath`` means
        internal). ``source_files`` only supplies the bytes for whichever
        of those internal references you want physically embedded; a GUID
        naming a source declared ``relative://``/``absolute://`` is a
        caller error, not silently written as internal.
        Sources with no entry here are written exactly as ``project``
        already records them -- untouched external references, per REFI-QDA
        section 8.3.
    :raises refi_qda.exceptions.ExternalSourceError: a ``source_files`` key
        does not name a top-level source in ``project``, or that source is
        not declared ``internal://``.
    """
    qde_bytes = to_qde(project)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(QDE_FILENAME, qde_bytes)
        for guid, disk_path in (source_files or {}).items():
            source = project.find_source(guid)
            if source is None:
                raise ExternalSourceError(
                    f"write_qdpx: source_files references GUID {guid!r}, which is not "
                    "a top-level source in this project."
                )
            path_attr = source.plain_text_path if isinstance(source, TextSource) else source.path
            if not path_attr:
                raise ExternalSourceError(
                    f"write_qdpx: source {guid!r} has no path/plainTextPath recorded to "
                    "bundle against; give it an internal:// reference before calling "
                    "write_qdpx with it in source_files."
                )
            parsed = parse_source_path(path_attr)
            if parsed.scheme is not SourceScheme.INTERNAL:
                raise ExternalSourceError(
                    f"write_qdpx: source {guid!r} is declared {parsed.scheme.value}:// "
                    f"({path_attr!r}), not internal://; source_files only bundles sources "
                    "the project itself already declares internal -- see this function's "
                    "docstring."
                )
            zf.write(disk_path, f"{SOURCES_DIRNAME}/{parsed.value}")

"""Parsing ``project.qde`` XML into the :mod:`refi_qda.model` object model.

This module knows the REFI-QDA v1.5 XML shape (namespace
``urn:QDA-XML:project:1.0``) and nothing about ZIP containers -- see
:mod:`refi_qda.container` for that layer, and :func:`parse_qdpx` below for
the convenience function that combines both.

Parsing is deliberately strict rather than forgiving: a required attribute
that is missing, an unrecognised source/selection element, or a root
element in a namespace this library does not know raises a typed exception
from :mod:`refi_qda.exceptions` rather than being skipped quietly. See each
module's docstring for the project's rationale ("no silent partial
parse").
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from refi_qda.container import QdpxContainer
from refi_qda.exceptions import ParseError, UnsupportedFeatureError
from refi_qda.model import (
    AudioSelection,
    AudioSource,
    Case,
    Code,
    Coding,
    Edge,
    Graph,
    Guid,
    LineStyle,
    Link,
    LinkDirection,
    PDFSelection,
    PDFSource,
    PictureSelection,
    PictureSource,
    PlainTextSelection,
    Project,
    SetObject,
    Shape,
    Source,
    SyncPoint,
    TextSource,
    Transcript,
    TranscriptSelection,
    User,
    Variable,
    VariableType,
    VariableValue,
    VariableValueScalar,
    Vertex,
    VideoSelection,
    VideoSource,
)

if TYPE_CHECKING:
    from lxml.etree import _Element

__all__ = ["NS_URI", "normalize_guid", "parse_qde", "parse_qdpx"]

#: The REFI-QDA v1.5 project exchange XML namespace. This is the only
#: namespace this parser understands; anything else (a hypothetical future
#: schema version, or a codebook-only ``urn:QDA-XML:codebook:1.0`` root) is
#: rejected explicitly rather than parsed partially/incorrectly.
NS_URI = "urn:QDA-XML:project:1.0"


def normalize_guid(guid: str) -> str:
    """Normalize a GUID for comparison: strip ``{}`` wrapping, lowercase.

    REFI-QDA allows GUIDs both bare (``8-4-4-4-12`` hex) and brace-wrapped
    (``{8-4-4-4-12}``) -- see the schema's ``GUIDType`` pattern. This
    library stores GUIDs exactly as read (see :data:`refi_qda.model.Guid`)
    and does not normalize them automatically, since doing so silently
    could mask real data-quality problems in an export; use this function
    explicitly when you need to compare GUIDs that may differ only in
    formatting.
    """
    return guid.strip("{}").lower()


def _qn(tag: str) -> str:
    return f"{{{NS_URI}}}{tag}"


def _required_attr(el: _Element, name: str) -> str:
    value = el.get(name)
    if value is None:
        localname = etree.QName(el).localname
        raise ParseError(f"<{localname}> is missing required attribute {name!r}.")
    return value


def _child_text(el: _Element, tag: str) -> str | None:
    child = el.find(_qn(tag))
    return child.text if child is not None else None


def _note_refs(el: _Element) -> list[Guid]:
    return [_required_attr(ref, "targetGUID") for ref in el.findall(_qn("NoteRef"))]


def _target_guids(el: _Element, tag: str) -> list[Guid]:
    return [_required_attr(ref, "targetGUID") for ref in el.findall(_qn(tag))]


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ParseError(f"Invalid xsd:dateTime value {value!r}: {exc}") from exc


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        # xsd:date permits an optional trailing timezone offset which
        # date.fromisoformat() does not accept; the date itself is always
        # the first 10 characters (YYYY-MM-DD).
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ParseError(f"Invalid xsd:date value {value!r}: {exc}") from exc


def _audit(el: _Element) -> tuple[str | None, datetime | None, str | None, datetime | None]:
    """Extract the (creatingUser, creationDateTime, modifyingUser, modifiedDateTime)
    attribute quartet that nearly every REFI-QDA element carries."""
    return (
        el.get("creatingUser"),
        _parse_datetime(el.get("creationDateTime")),
        el.get("modifyingUser"),
        _parse_datetime(el.get("modifiedDateTime")),
    )


# --------------------------------------------------------------------------
# Users, codebook, variables
# --------------------------------------------------------------------------


def _parse_user(el: _Element) -> User:
    return User(guid=_required_attr(el, "guid"), name=el.get("name"), id=el.get("id"))


def _parse_code(el: _Element) -> Code:
    is_codable_raw = _required_attr(el, "isCodable")
    return Code(
        guid=_required_attr(el, "guid"),
        name=_required_attr(el, "name"),
        is_codable=is_codable_raw.strip().lower() == "true",
        color=el.get("color"),
        description=_child_text(el, "Description"),
        note_refs=_note_refs(el),
        children=[_parse_code(child) for child in el.findall(_qn("Code"))],
    )


def _parse_variable(el: _Element) -> Variable:
    type_raw = _required_attr(el, "typeOfVariable")
    try:
        variable_type = VariableType(type_raw)
    except ValueError as exc:
        guid = el.get("guid", "<unknown>")
        raise ParseError(
            f"Variable {guid!r} has unrecognised typeOfVariable {type_raw!r}; "
            "REFI-QDA defines Text, Boolean, Integer, Float, Date, DateTime."
        ) from exc
    return Variable(
        guid=_required_attr(el, "guid"),
        name=_required_attr(el, "name"),
        type_of_variable=variable_type,
        description=_child_text(el, "Description"),
    )


def _parse_variable_value(el: _Element) -> VariableValue:
    ref_el = el.find(_qn("VariableRef"))
    if ref_el is None:
        raise ParseError("<VariableValue> is missing its required <VariableRef> child.")
    variable_ref = _required_attr(ref_el, "targetGUID")

    value: VariableValueScalar | None = None
    text_el = el.find(_qn("TextValue"))
    bool_el = el.find(_qn("BooleanValue"))
    int_el = el.find(_qn("IntegerValue"))
    float_el = el.find(_qn("FloatValue"))
    date_el = el.find(_qn("DateValue"))
    datetime_el = el.find(_qn("DateTimeValue"))

    if text_el is not None:
        value = text_el.text or ""
    elif bool_el is not None:
        value = (bool_el.text or "").strip().lower() == "true"
    elif int_el is not None:
        try:
            value = int((int_el.text or "").strip())
        except ValueError as exc:
            raise ParseError(f"Invalid IntegerValue {int_el.text!r}: {exc}") from exc
    elif float_el is not None:
        try:
            value = Decimal((float_el.text or "").strip())
        except InvalidOperation as exc:
            raise ParseError(f"Invalid FloatValue {float_el.text!r}: {exc}") from exc
    elif date_el is not None:
        value = _parse_date(date_el.text)
    elif datetime_el is not None:
        value = _parse_datetime(datetime_el.text)

    return VariableValue(variable_ref=variable_ref, value=value)


def _parse_variable_values(el: _Element) -> list[VariableValue]:
    return [_parse_variable_value(v) for v in el.findall(_qn("VariableValue"))]


# --------------------------------------------------------------------------
# Codings
# --------------------------------------------------------------------------


def _parse_coding(el: _Element) -> Coding:
    code_ref_el = el.find(_qn("CodeRef"))
    if code_ref_el is None:
        raise ParseError("<Coding> is missing its required <CodeRef> child.")
    creating_user = el.get("creatingUser")
    creation_datetime = _parse_datetime(el.get("creationDateTime"))
    return Coding(
        guid=_required_attr(el, "guid"),
        code_ref=_required_attr(code_ref_el, "targetGUID"),
        creating_user=creating_user,
        creation_datetime=creation_datetime,
        note_refs=_note_refs(el),
    )


def _parse_codings(el: _Element) -> list[Coding]:
    return [_parse_coding(c) for c in el.findall(_qn("Coding"))]


# --------------------------------------------------------------------------
# Selections (six distinct coordinate systems -- see model.py)
# --------------------------------------------------------------------------


def _parse_plain_text_selection(el: _Element) -> PlainTextSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return PlainTextSelection(
        guid=_required_attr(el, "guid"),
        start_position=int(_required_attr(el, "startPosition")),
        end_position=int(_required_attr(el, "endPosition")),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_pdf_selection(el: _Element) -> PDFSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    representation_el = el.find(_qn("Representation"))
    return PDFSelection(
        guid=_required_attr(el, "guid"),
        page=int(_required_attr(el, "page")),
        first_x=int(_required_attr(el, "firstX")),
        first_y=int(_required_attr(el, "firstY")),
        second_x=int(_required_attr(el, "secondX")),
        second_y=int(_required_attr(el, "secondY")),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        representation=_parse_text_content(representation_el)
        if representation_el is not None
        else None,
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_picture_selection(el: _Element) -> PictureSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return PictureSelection(
        guid=_required_attr(el, "guid"),
        first_x=int(_required_attr(el, "firstX")),
        first_y=int(_required_attr(el, "firstY")),
        second_x=int(_required_attr(el, "secondX")),
        second_y=int(_required_attr(el, "secondY")),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_audio_selection(el: _Element) -> AudioSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return AudioSelection(
        guid=_required_attr(el, "guid"),
        begin=int(_required_attr(el, "begin")),
        end=int(_required_attr(el, "end")),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_video_selection(el: _Element) -> VideoSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return VideoSelection(
        guid=_required_attr(el, "guid"),
        begin=int(_required_attr(el, "begin")),
        end=int(_required_attr(el, "end")),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_transcript_selection(el: _Element) -> TranscriptSelection:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return TranscriptSelection(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        from_sync_point=el.get("fromSyncPoint"),
        to_sync_point=el.get("toSyncPoint"),
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


# --------------------------------------------------------------------------
# Transcripts
# --------------------------------------------------------------------------


def _parse_sync_point(el: _Element) -> SyncPoint:
    position_raw = el.get("position")
    time_stamp_raw = el.get("timeStamp")
    return SyncPoint(
        guid=_required_attr(el, "guid"),
        position=int(position_raw) if position_raw is not None else None,
        time_stamp=int(time_stamp_raw) if time_stamp_raw is not None else None,
    )


def _parse_transcript(el: _Element) -> Transcript:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return Transcript(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        plain_text_content=_child_text(el, "PlainTextContent"),
        plain_text_path=el.get("plainTextPath"),
        rich_text_path=el.get("richTextPath"),
        sync_points=[_parse_sync_point(s) for s in el.findall(_qn("SyncPoint"))],
        selections=[_parse_transcript_selection(s) for s in el.findall(_qn("TranscriptSelection"))],
        note_refs=_note_refs(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


def _parse_text_content(el: _Element) -> TextSource:
    """Parse anything shaped like the schema's ``TextSourceType``.

    Reused for top-level ``<TextSource>`` elements, ``<Representation>``
    (on PDF sources/selections), ``<TextDescription>`` (on picture
    sources) and ``<Note>`` (memos) alike -- they are all literally the
    same complex type in the XSD. See :data:`refi_qda.model.Memo`.
    """
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return TextSource(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        plain_text_content=_child_text(el, "PlainTextContent"),
        plain_text_path=el.get("plainTextPath"),
        rich_text_path=el.get("richTextPath"),
        selections=[_parse_plain_text_selection(s) for s in el.findall(_qn("PlainTextSelection"))],
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        variable_values=_parse_variable_values(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_picture_source(el: _Element) -> PictureSource:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    text_description_el = el.find(_qn("TextDescription"))
    return PictureSource(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        path=el.get("path"),
        current_path=el.get("currentPath"),
        text_description=_parse_text_content(text_description_el)
        if text_description_el is not None
        else None,
        selections=[_parse_picture_selection(s) for s in el.findall(_qn("PictureSelection"))],
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        variable_values=_parse_variable_values(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_pdf_source(el: _Element) -> PDFSource:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    representation_el = el.find(_qn("Representation"))
    return PDFSource(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        path=el.get("path"),
        current_path=el.get("currentPath"),
        representation=_parse_text_content(representation_el)
        if representation_el is not None
        else None,
        selections=[_parse_pdf_selection(s) for s in el.findall(_qn("PDFSelection"))],
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        variable_values=_parse_variable_values(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_audio_source(el: _Element) -> AudioSource:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return AudioSource(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        path=el.get("path"),
        current_path=el.get("currentPath"),
        transcripts=[_parse_transcript(t) for t in el.findall(_qn("Transcript"))],
        selections=[_parse_audio_selection(s) for s in el.findall(_qn("AudioSelection"))],
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        variable_values=_parse_variable_values(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


def _parse_video_source(el: _Element) -> VideoSource:
    creating_user, creation_dt, modifying_user, modified_dt = _audit(el)
    return VideoSource(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        path=el.get("path"),
        current_path=el.get("currentPath"),
        transcripts=[_parse_transcript(t) for t in el.findall(_qn("Transcript"))],
        selections=[_parse_video_selection(s) for s in el.findall(_qn("VideoSelection"))],
        codings=_parse_codings(el),
        note_refs=_note_refs(el),
        variable_values=_parse_variable_values(el),
        creating_user=creating_user,
        creation_datetime=creation_dt,
        modifying_user=modifying_user,
        modified_datetime=modified_dt,
    )


_SOURCE_PARSERS: dict[str, Callable[[_Element], Source]] = {
    "TextSource": _parse_text_content,
    "PictureSource": _parse_picture_source,
    "PDFSource": _parse_pdf_source,
    "AudioSource": _parse_audio_source,
    "VideoSource": _parse_video_source,
}


def _parse_sources(el: _Element) -> list[Source]:
    sources: list[Source] = []
    for child in el:
        localname = etree.QName(child).localname
        parse_fn = _SOURCE_PARSERS.get(localname)
        if parse_fn is None:
            raise UnsupportedFeatureError(
                f"Unrecognised source element <{localname}> in <Sources>. REFI-QDA v1.5 "
                "defines TextSource, PictureSource, PDFSource, AudioSource and VideoSource only."
            )
        sources.append(parse_fn(child))
    return sources


# --------------------------------------------------------------------------
# Cases, sets, links, graphs
# --------------------------------------------------------------------------


def _parse_case(el: _Element) -> Case:
    return Case(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        description=_child_text(el, "Description"),
        code_refs=_target_guids(el, "CodeRef"),
        variable_values=_parse_variable_values(el),
        source_refs=_target_guids(el, "SourceRef"),
        selection_refs=_target_guids(el, "SelectionRef"),
    )


def _parse_set(el: _Element) -> SetObject:
    return SetObject(
        guid=_required_attr(el, "guid"),
        name=_required_attr(el, "name"),
        description=_child_text(el, "Description"),
        member_codes=_target_guids(el, "MemberCode"),
        member_sources=_target_guids(el, "MemberSource"),
        member_notes=_target_guids(el, "MemberNote"),
    )


def _parse_link(el: _Element) -> Link:
    direction_raw = el.get("direction")
    return Link(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        direction=LinkDirection(direction_raw) if direction_raw else None,
        color=el.get("color"),
        origin_guid=el.get("originGUID"),
        target_guid=el.get("targetGUID"),
        note_refs=_note_refs(el),
    )


def _parse_vertex(el: _Element) -> Vertex:
    second_x_raw = el.get("secondX")
    second_y_raw = el.get("secondY")
    shape_raw = el.get("shape")
    return Vertex(
        guid=_required_attr(el, "guid"),
        first_x=int(_required_attr(el, "firstX")),
        first_y=int(_required_attr(el, "firstY")),
        represented_guid=el.get("representedGUID"),
        name=el.get("name"),
        second_x=int(second_x_raw) if second_x_raw is not None else None,
        second_y=int(second_y_raw) if second_y_raw is not None else None,
        shape=Shape(shape_raw) if shape_raw else None,
        color=el.get("color"),
    )


def _parse_edge(el: _Element) -> Edge:
    direction_raw = el.get("direction")
    line_style_raw = el.get("lineStyle")
    return Edge(
        guid=_required_attr(el, "guid"),
        source_vertex=_required_attr(el, "sourceVertex"),
        target_vertex=_required_attr(el, "targetVertex"),
        represented_guid=el.get("representedGUID"),
        name=el.get("name"),
        color=el.get("color"),
        direction=LinkDirection(direction_raw) if direction_raw else None,
        line_style=LineStyle(line_style_raw) if line_style_raw else None,
    )


def _parse_graph(el: _Element) -> Graph:
    return Graph(
        guid=_required_attr(el, "guid"),
        name=el.get("name"),
        vertices=[_parse_vertex(v) for v in el.findall(_qn("Vertex"))],
        edges=[_parse_edge(e) for e in el.findall(_qn("Edge"))],
    )


# --------------------------------------------------------------------------
# Project (root)
# --------------------------------------------------------------------------


def _parse_project(root: _Element) -> Project:
    users_el = root.find(_qn("Users"))
    users = [_parse_user(u) for u in users_el.findall(_qn("User"))] if users_el is not None else []

    codebook: list[Code] = []
    codebook_el = root.find(_qn("CodeBook"))
    if codebook_el is not None:
        codes_el = codebook_el.find(_qn("Codes"))
        if codes_el is not None:
            codebook = [_parse_code(c) for c in codes_el.findall(_qn("Code"))]

    variables_el = root.find(_qn("Variables"))
    variables = (
        [_parse_variable(v) for v in variables_el.findall(_qn("Variable"))]
        if variables_el is not None
        else []
    )

    cases_el = root.find(_qn("Cases"))
    cases = [_parse_case(c) for c in cases_el.findall(_qn("Case"))] if cases_el is not None else []

    sources_el = root.find(_qn("Sources"))
    sources = _parse_sources(sources_el) if sources_el is not None else []

    notes_el = root.find(_qn("Notes"))
    notes = (
        [_parse_text_content(n) for n in notes_el.findall(_qn("Note"))]
        if notes_el is not None
        else []
    )

    links_el = root.find(_qn("Links"))
    links = (
        [_parse_link(link) for link in links_el.findall(_qn("Link"))]
        if links_el is not None
        else []
    )

    sets_el = root.find(_qn("Sets"))
    sets = [_parse_set(s) for s in sets_el.findall(_qn("Set"))] if sets_el is not None else []

    graphs_el = root.find(_qn("Graphs"))
    graphs = (
        [_parse_graph(g) for g in graphs_el.findall(_qn("Graph"))] if graphs_el is not None else []
    )

    return Project(
        name=_required_attr(root, "name"),
        origin=root.get("origin"),
        creating_user_guid=root.get("creatingUserGUID"),
        creation_datetime=_parse_datetime(root.get("creationDateTime")),
        modifying_user_guid=root.get("modifyingUserGUID"),
        modified_datetime=_parse_datetime(root.get("modifiedDateTime")),
        base_path=root.get("basePath"),
        description=_child_text(root, "Description"),
        users=users,
        codebook=codebook,
        variables=variables,
        cases=cases,
        sources=sources,
        notes=notes,
        links=links,
        sets=sets,
        graphs=graphs,
        note_refs=_note_refs(root),
    )


def parse_qde(xml: bytes | str) -> Project:
    """Parse raw ``project.qde`` XML content into a :class:`refi_qda.model.Project`.

    :param xml: the XML document, as ``bytes`` or ``str``.
    :raises refi_qda.exceptions.ParseError: the XML is not well-formed, or
        its root element is not a REFI-QDA v1.5 ``<Project>``.
    :raises refi_qda.exceptions.UnsupportedFeatureError: the root element
        is a codebook-only ``<CodeBook>`` (``.qdc``), which this reader
        does not yet support, or the document contains a source/selection
        element this version of the library does not recognise.
    """
    data = xml if isinstance(xml, bytes) else xml.encode("utf-8")
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise ParseError(f"project.qde is not well-formed XML: {exc}") from exc

    root_qname = etree.QName(root)
    if root_qname.namespace == NS_URI and root_qname.localname == "Project":
        return _parse_project(root)

    if root_qname.localname == "CodeBook":
        raise UnsupportedFeatureError(
            "This document's root element is <CodeBook> -- a REFI-QDA codebook-only "
            "exchange (.qdc). refi_qda currently parses full project exchanges "
            "(<Project> root, .qde/.qdpx) only; codebook-only import is not yet "
            "implemented. See SPEC.md section 1.1."
        )

    raise ParseError(
        f"Unsupported root element {{{root_qname.namespace}}}{root_qname.localname}; "
        f"expected {{{NS_URI}}}Project (REFI-QDA v1.5 project exchange)."
    )


def parse_qdpx(path: str | Path) -> Project:
    """Open a ``.qdpx`` file and parse its ``project.qde`` into a :class:`Project`.

    This is a convenience wrapper around :class:`refi_qda.container.QdpxContainer`
    and :func:`parse_qde`. It does not resolve external sources or read
    internal source file contents -- use :class:`QdpxContainer` directly,
    or :func:`refi_qda.container.resolve_external_sources`, for that.
    """
    with QdpxContainer.open(path) as container:
        return parse_qde(container.read_qde())

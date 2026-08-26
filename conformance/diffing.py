"""Structural diffing between two parsed REFI-QDA projects.

Built for this repository's conformance-testing methodology (SPEC.md
§1.2 step 6): "not just pass/fail, but exactly what is lost and where."
:func:`diff_projects` compares a seed project against a project that has
been round-tripped through a vendor tool (or through this library itself)
and reports what was added, removed, or changed, grouped by object kind.

**Objects are matched by name, not by GUID.** A project re-exported by a
different tool is not expected to preserve GUIDs -- vendor tools routinely
assign fresh ones on import (this is not a hypothetical: it is the reason
this module exists rather than a five-line "compare two dicts keyed by
GUID"). Codes are matched by their full hierarchical path (e.g. ``"Topics
> Health > Diet"``) since code names can repeat at different levels of a
codebook; sources, cases, sets and memos are matched by their ``name``
field. This is a real limitation, not a hidden one: a same-named object
that changed *purpose* between seed and export will be silently matched
as "the same" object here.

Links and graphs are compared by count only -- see the module-level
``README`` in ``conformance/`` for why a precise match is not attempted
for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from refi_qda.model import (
    AudioSelection,
    Case,
    Code,
    Coding,
    PDFSelection,
    PictureSelection,
    Project,
    Source,
    TextSource,
    TranscriptSelection,
    VideoSelection,
)

if TYPE_CHECKING:
    from refi_qda.model import Selection, SetObject

__all__ = ["ConformanceReport", "diff_projects"]


def _code_paths(codes: list[Code], prefix: str = "") -> dict[str, Code]:
    """Map each code's full hierarchical path (e.g. "A > B > C") to itself."""
    result: dict[str, Code] = {}
    for code in codes:
        path = f"{prefix} > {code.name}" if prefix else code.name
        result[path] = code
        result.update(_code_paths(code.children, path))
    return result


def _by_name(
    items: list[Source] | list[Case] | list[SetObject] | list[TextSource],
) -> dict[str, object]:
    """Map each item's name to itself, falling back to a GUID-based key when unnamed."""
    result: dict[str, object] = {}
    for item in items:
        name = getattr(item, "name", None) or f"<unnamed:{item.guid}>"
        result[name] = item
    return result


def _selection_key(selection: Selection) -> tuple[object, ...]:
    """A coordinate-based key identifying a selection independent of its GUID."""
    if isinstance(selection, PDFSelection):
        return (
            "pdf",
            selection.page,
            selection.first_x,
            selection.first_y,
            selection.second_x,
            selection.second_y,
        )
    if isinstance(selection, PictureSelection):
        return (
            "picture",
            selection.first_x,
            selection.first_y,
            selection.second_x,
            selection.second_y,
        )
    if isinstance(selection, AudioSelection):
        return ("audio", selection.begin, selection.end)
    if isinstance(selection, VideoSelection):
        return ("video", selection.begin, selection.end)
    if isinstance(selection, TranscriptSelection):
        return ("transcript", selection.from_sync_point, selection.to_sync_point)
    # PlainTextSelection and anything else with start/end positions.
    return ("text", selection.start_position, selection.end_position)


def _applied_code_paths(codings: list[Coding], guid_to_path: dict[str, str]) -> set[str]:
    return {
        guid_to_path.get(coding.code_ref, f"<unknown code {coding.code_ref}>") for coding in codings
    }


@dataclass(slots=True)
class ConformanceReport:
    """What survived, what changed, and what was lost between two projects."""

    missing_codes: list[str] = field(default_factory=list)
    extra_codes: list[str] = field(default_factory=list)
    changed_codes: list[str] = field(default_factory=list)

    missing_sources: list[str] = field(default_factory=list)
    extra_sources: list[str] = field(default_factory=list)

    missing_selections: list[str] = field(default_factory=list)
    missing_codings: list[str] = field(default_factory=list)

    missing_cases: list[str] = field(default_factory=list)
    missing_variable_values: list[str] = field(default_factory=list)

    missing_memos: list[str] = field(default_factory=list)
    missing_sets: list[str] = field(default_factory=list)

    #: Coarse count-only comparisons for object kinds (links, graphs) whose
    #: GUID-based cross-references make precise matching unreliable across
    #: a round trip -- see the module docstring.
    count_notes: list[str] = field(default_factory=list)

    @property
    def is_lossless(self) -> bool:
        """True if nothing was found missing or changed (ignores ``extra_*`` and count notes)."""
        return not any(
            [
                self.missing_codes,
                self.changed_codes,
                self.missing_sources,
                self.missing_selections,
                self.missing_codings,
                self.missing_cases,
                self.missing_variable_values,
                self.missing_memos,
                self.missing_sets,
            ]
        )

    def render(self) -> str:
        """A human-readable Markdown report, per SPEC.md §1.2 step 6."""
        lines = ["# Conformance report", ""]
        lines.append(
            "No loss detected by this comparison."
            if self.is_lossless
            else "Data loss and/or changes detected:"
        )
        sections: list[tuple[str, list[str]]] = [
            ("Missing codes", self.missing_codes),
            ("Extra codes (present in export, not in seed)", self.extra_codes),
            ("Changed codes", self.changed_codes),
            ("Missing sources", self.missing_sources),
            ("Extra sources (present in export, not in seed)", self.extra_sources),
            ("Missing selections", self.missing_selections),
            ("Missing codings", self.missing_codings),
            ("Missing cases", self.missing_cases),
            ("Missing or changed variable values", self.missing_variable_values),
            ("Missing memos", self.missing_memos),
            ("Missing sets", self.missing_sets),
            ("Count-only comparisons (links, graphs)", self.count_notes),
        ]
        for title, items in sections:
            if items:
                lines.append(f"\n## {title} ({len(items)})")
                lines.extend(f"- {item}" for item in items)
        return "\n".join(lines)


def diff_projects(seed: Project, other: Project) -> ConformanceReport:
    """Structurally compare ``other`` against ``seed``, matching objects by name.

    See the module docstring for the name-matching rationale and its
    known limitations.
    """
    report = ConformanceReport()

    # --- Codes -----------------------------------------------------------
    seed_code_paths = _code_paths(seed.codebook)
    other_code_paths = _code_paths(other.codebook)
    report.missing_codes = sorted(seed_code_paths.keys() - other_code_paths.keys())
    report.extra_codes = sorted(other_code_paths.keys() - seed_code_paths.keys())
    for path in sorted(seed_code_paths.keys() & other_code_paths.keys()):
        seed_code, other_code = seed_code_paths[path], other_code_paths[path]
        if seed_code.is_codable != other_code.is_codable:
            report.changed_codes.append(
                f"{path}: isCodable {seed_code.is_codable!r} -> {other_code.is_codable!r}"
            )
        if seed_code.color != other_code.color:
            report.changed_codes.append(
                f"{path}: color {seed_code.color!r} -> {other_code.color!r}"
            )

    seed_guid_to_path = {code.guid: path for path, code in seed_code_paths.items()}
    other_guid_to_path = {code.guid: path for path, code in other_code_paths.items()}

    # --- Sources, selections, codings -------------------------------------
    seed_sources = _by_name(seed.sources)
    other_sources = _by_name(other.sources)
    report.missing_sources = sorted(seed_sources.keys() - other_sources.keys())
    report.extra_sources = sorted(other_sources.keys() - seed_sources.keys())

    for name in sorted(seed_sources.keys() & other_sources.keys()):
        seed_source = seed_sources[name]
        other_source = other_sources[name]

        source_codings_missing = _applied_code_paths(
            seed_source.codings,
            seed_guid_to_path,  # type: ignore[attr-defined]
        ) - _applied_code_paths(other_source.codings, other_guid_to_path)  # type: ignore[attr-defined]
        for code_path in sorted(source_codings_missing):
            report.missing_codings.append(f"{name} (whole source): {code_path!r}")

        seed_selections = {_selection_key(s): s for s in getattr(seed_source, "selections", [])}
        other_selections = {_selection_key(s): s for s in getattr(other_source, "selections", [])}

        for key in sorted(seed_selections.keys() - other_selections.keys(), key=repr):
            report.missing_selections.append(f"{name}: {key[0]} selection {key[1:]!r}")

        for key in sorted(seed_selections.keys() & other_selections.keys(), key=repr):
            seed_selection = seed_selections[key]
            other_selection = other_selections[key]
            missing = _applied_code_paths(
                seed_selection.codings, seed_guid_to_path
            ) - _applied_code_paths(other_selection.codings, other_guid_to_path)
            for code_path in sorted(missing):
                report.missing_codings.append(
                    f"{name}: {key[0]} selection {key[1:]!r} coded {code_path!r}"
                )

    # --- Cases and variable values ----------------------------------------
    seed_var_names = {v.guid: v.name for v in seed.variables}
    other_var_names = {v.guid: v.name for v in other.variables}

    seed_cases = _by_name(seed.cases)
    other_cases = _by_name(other.cases)
    report.missing_cases = sorted(seed_cases.keys() - other_cases.keys())

    for name in sorted(seed_cases.keys() & other_cases.keys()):
        seed_case: Case = seed_cases[name]  # type: ignore[assignment]
        other_case: Case = other_cases[name]  # type: ignore[assignment]
        other_values_by_name = {
            other_var_names.get(vv.variable_ref, vv.variable_ref): vv.value
            for vv in other_case.variable_values
        }
        for variable_value in seed_case.variable_values:
            var_name = seed_var_names.get(variable_value.variable_ref, variable_value.variable_ref)
            if var_name not in other_values_by_name:
                report.missing_variable_values.append(
                    f"Case {name!r}: variable {var_name!r} missing"
                )
            elif other_values_by_name[var_name] != variable_value.value:
                report.missing_variable_values.append(
                    f"Case {name!r}: variable {var_name!r} changed "
                    f"{variable_value.value!r} -> {other_values_by_name[var_name]!r}"
                )

    # --- Memos and sets ------------------------------------------------
    seed_memos = _by_name(seed.notes)
    other_memos = _by_name(other.notes)
    report.missing_memos = sorted(seed_memos.keys() - other_memos.keys())

    seed_sets = _by_name(seed.sets)
    other_sets = _by_name(other.sets)
    report.missing_sets = sorted(seed_sets.keys() - other_sets.keys())

    # --- Links and graphs (count-only; see module docstring) -----------
    if len(seed.links) != len(other.links):
        report.count_notes.append(f"Links: {len(seed.links)} in seed, {len(other.links)} in export")
    if len(seed.graphs) != len(other.graphs):
        report.count_notes.append(
            f"Graphs: {len(seed.graphs)} in seed, {len(other.graphs)} in export"
        )

    return report

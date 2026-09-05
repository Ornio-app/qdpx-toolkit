"""Structural, order-sensitive comparison between two ``Project`` trees.

Used by the writer's round-trip tests (``tests/test_writer.py``) to report
*where* two ``Project`` objects first diverge, instead of a bare
``assert a == b`` on a deep dataclass tree (which pytest can usually show
reasonably for dataclasses, but "reasonably" gets unreadable fast once
lists of nested dataclasses -- selections inside sources inside a project
-- are involved).

This is deliberately a separate tool from ``conformance/diffing.py``'s
``diff_projects()``, not a reuse of it: that function matches objects by
*name* because it compares a seed project against an independent vendor
tool's re-export, which is not expected to preserve GUIDs (see its module
docstring). A round trip through this library's own writer *is* expected
to preserve GUIDs, list order and every field exactly -- so this helper
walks both trees position-for-position instead of name-matching them.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = ["first_divergence"]


def first_divergence(a: Any, b: Any, path: str = "project") -> str | None:
    """Return a description of the first field where ``a`` and ``b`` differ.

    Recurses into dataclasses field-by-field and lists element-by-element,
    so the returned path (e.g. ``"project.sources[2].selections[0].codings[0].code_ref"``)
    points directly at the divergent leaf rather than just reporting that
    two big objects are unequal. Returns ``None`` if the trees are equal.
    """
    if dataclasses.is_dataclass(a) and dataclasses.is_dataclass(b):
        if type(a) is not type(b):
            return f"{path}: type {type(a).__name__!r} != {type(b).__name__!r}"
        for f in dataclasses.fields(a):
            diff = first_divergence(getattr(a, f.name), getattr(b, f.name), f"{path}.{f.name}")
            if diff is not None:
                return diff
        return None

    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)} ({a!r} != {b!r})"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            diff = first_divergence(x, y, f"{path}[{i}]")
            if diff is not None:
                return diff
        return None

    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None

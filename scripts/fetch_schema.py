#!/usr/bin/env python3
"""Recover the REFI-QDA v1.5 XSD schemas from the published specification PDF.

This script does not download the *canonical* schema files. Those sit
behind a JS-gated Tresorit share link on qdasoftware.org whose
redistribution licence is not clearly stated, so this project does not
mirror them (see ``conformance/README.md`` and ``schema/README.md``).
What it does instead: the REFI-QDA v1.5 specification PDF -- itself
freely downloadable -- contains both schemas printed in full, as text,
in section 5. This script downloads that PDF, extracts the two schema
blocks from its text layer, repairs the mangling that PDF text
extraction introduces, and writes the result to ``schema/``. What comes
out is a *recovered* schema, not a vendored copy of the original file --
worth stating plainly, since "the XSD" implies more provenance than a
PDF-text reconstruction can honestly claim.

Two independent kinds of damage need repairing, found by trial and
error against REFI-QDA v1.5 (ed. Fred van Blommestein, 25-09-2019):

1. Page furniture. Page breaks inject running headers/footers and bare
   page numbers into the extracted text stream, mid-schema.

2. Whitespace injected inside wrapped attribute values. When the PDF's
   layout wraps a long line, pypdf's extraction inserts a space at the
   wrap point even mid-token. Schema attribute values here are always
   regex patterns or enumerations, where whitespace is never
   meaningful, so it is safe to strip unconditionally within
   ``value="..."`` -- but it is NOT cosmetic: a wrapped GUID pattern
   ``[0-9a-fA-F]`` comes back as ``[0- 9a-fA-F]``, which parses as a
   different (and wrong) character class rather than failing loudly.

3. (Codebook schema only.) Page 10 of the PDF places Figure 3, a UML
   box diagram, in the same page region as the schema text column.
   pypdf's extraction interleaves the diagram's box labels into the
   text stream between the ``Codes`` and ``Sets`` element declarations.
   The fix is anchored to that specific span; it is a no-op against the
   project schema (verified below), so applying it unconditionally to
   both blocks is safe.

After all repairs, ``lxml.etree.XMLSchema(etree.parse(path))`` must
succeed on both recovered files -- this script asserts that and fails
loudly, with the underlying parse error, if a future spec revision
changes the text layout enough to break this recipe. Silent corruption
would be worse than a loud failure here, since this repo's entire
conformance-testing claim rests on this schema being real.

Usage:

    python scripts/fetch_schema.py                  # fetch, repair, write to schema/
    python scripts/fetch_schema.py --dest DIR        # write elsewhere
    python scripts/fetch_schema.py --pdf-url URL     # use a different spec PDF

Requires ``pypdf``, which is deliberately NOT a runtime dependency of
this package (it is only ever needed here, once, by a contributor
regenerating the schema). Install it with:

    pip install pypdf
    # or: uv run --with pypdf scripts/fetch_schema.py
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

from lxml import etree

#: REFI-QDA v1.5, ed. Fred van Blommestein, 25-09-2019. Published alongside
#: https://openqda.github.io/refi-tools/docs/standard/ (MIT-licensed docs
#: per that repository); this is the spec *document*, not the schema file
#: whose licence is in question -- see the module docstring.
DEFAULT_PDF_URL = "https://openqda.github.io/refi-tools/docs/standard/REFI-QDA-1-5.pdf"

DEFAULT_DEST = Path(__file__).resolve().parent.parent / "schema"

#: Maps each schema's targetNamespace to the output filename it is written
#: as. Matching on the namespace found *inside* each block (rather than
#: assuming a fixed order) survives the spec reordering the two schemas in
#: a future revision.
NAMESPACE_TO_FILENAME = {
    "urn:QDA-XML:codebook:1.0": "refi-qda-codebook-1.0.xsd",
    "urn:QDA-XML:project:1.0": "refi-qda-project-1.0.xsd",
}

# Bare page numbers and running headers/footers injected at page breaks.
_FURNITURE_LINE_RE = re.compile(r"^\s*(\d{1,3}|REFI-QDA.*|Date:.*|Editor:.*|Page \d+.*)\s*$")

# See docstring point 2: whitespace inside a regex/enumeration attribute
# value is never meaningful in this schema, so collapsing it is safe.
_ATTR_VALUE_RE = re.compile(r'value="([^"]*)"')

# See docstring point 3: Figure 3's diagram-box text leaks in between these
# two element declarations on PDF page 10. Nothing of schema value sits
# between them in the corrected structure (Sets follows Codes directly), so
# the whole span is excised. Anchored on literal text unique to the
# codebook schema, so this is inert against the project schema.
_DIAGRAM_LEAK_RE = re.compile(
    r'(<xsd:element name="Codes" type="CodesType"/>\s*).*?(?=<xsd:element name="Sets")',
    re.DOTALL,
)


class SchemaRecoveryError(RuntimeError):
    """Raised when the PDF-recovery recipe fails to produce a valid schema.

    Deliberately fatal rather than a warning: a broken recovered schema
    would silently undermine every conformance claim this repo makes.
    """


def _import_pypdf():  # type: ignore[no-untyped-def]
    try:
        import pypdf
    except ImportError as exc:
        raise SchemaRecoveryError(
            "pypdf is required to recover the schema from the spec PDF, but is not "
            "installed. It is deliberately not a runtime dependency of this package "
            "(see the module docstring). Install it with `pip install pypdf`, or run "
            "this script with `uv run --with pypdf scripts/fetch_schema.py`."
        ) from exc
    return pypdf


def _download_pdf(url: str) -> bytes:
    print(f"Downloading spec PDF from {url} ...")
    with urllib.request.urlopen(url) as response:
        return response.read()


def _extract_text(pdf_bytes: bytes) -> str:
    pypdf = _import_pypdf()
    import io

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def _split_schema_blocks(text: str) -> list[str]:
    """Carve the raw extracted text into ``<?xml ...?>...</xsd:schema>`` blocks.

    The spec PDF's text contains more ``<?xml`` declarations than schema
    blocks (some appear in example instance documents elsewhere in the
    spec), but exactly as many ``</xsd:schema>`` closing tags as there are
    schemas. Pairing starts to ends in encounter order works because every
    real schema block's ``<?xml`` declaration is immediately followed by
    its content with no intervening ``</xsd:schema>`` from something else.
    """
    starts = [m.start() for m in re.finditer(r"<\?xml version", text)]
    ends = [m.end() for m in re.finditer(r"</xsd:schema>", text)]
    if not ends:
        raise SchemaRecoveryError(
            "Found no '</xsd:schema>' closing tags in the extracted PDF text -- "
            "the spec's text layout has apparently changed enough that this "
            "recipe no longer applies. See scripts/fetch_schema.py's docstring."
        )
    return [text[s:e] for s, e in zip(starts, ends, strict=False)]


def _repair_block(block: str) -> str:
    lines = block.splitlines()
    kept = [line for line in lines if not _FURNITURE_LINE_RE.match(line)]
    repaired = "\n".join(kept)
    repaired = _DIAGRAM_LEAK_RE.sub(r"\1", repaired)
    repaired = _ATTR_VALUE_RE.sub(
        lambda m: 'value="' + re.sub(r"\s+", "", m.group(1)) + '"', repaired
    )
    return repaired


def _verify_written_schema(path: Path) -> None:
    """Confirm ``etree.XMLSchema(etree.parse(path))`` succeeds, exactly as run
    against the recovered project schema during development of this recipe.
    """
    try:
        etree.XMLSchema(etree.parse(str(path)))
    except etree.XMLSyntaxError as exc:
        raise SchemaRecoveryError(
            f"Recovered {path.name} is not well-formed XML after repair: {exc}\n"
            "The PDF-recovery recipe in scripts/fetch_schema.py needs updating for "
            "this spec revision."
        ) from exc
    except etree.XMLSchemaParseError as exc:
        raise SchemaRecoveryError(
            f"Recovered {path.name} is well-formed XML but not a valid XML "
            f"Schema: {exc}\nThe PDF-recovery recipe in scripts/fetch_schema.py "
            "needs updating for this spec revision."
        ) from exc


def recover_schemas(pdf_bytes: bytes) -> dict[str, str]:
    """Return ``{target_namespace: repaired_xsd_text}`` for both schemas."""
    text = _extract_text(pdf_bytes)
    blocks = _split_schema_blocks(text)

    recovered: dict[str, str] = {}
    for block in blocks:
        repaired = _repair_block(block)
        namespace_match = re.search(r'targetNamespace="([^"]+)"', repaired)
        if namespace_match is None:
            raise SchemaRecoveryError(
                "A recovered schema block has no targetNamespace attribute after "
                "repair -- extraction likely produced garbage. First 200 chars:\n"
                f"{repaired[:200]!r}"
            )
        namespace = namespace_match.group(1)
        if namespace not in NAMESPACE_TO_FILENAME:
            raise SchemaRecoveryError(
                f"Recovered a schema block with unexpected targetNamespace "
                f"{namespace!r} -- expected one of {sorted(NAMESPACE_TO_FILENAME)}. "
                "The spec may have changed; update scripts/fetch_schema.py."
            )
        recovered[namespace] = repaired

    missing = set(NAMESPACE_TO_FILENAME) - set(recovered)
    if missing:
        raise SchemaRecoveryError(
            f"Only recovered {sorted(recovered)}, missing {sorted(missing)}. "
            "Expected exactly two schema blocks in the spec PDF."
        )
    return recovered


def write_schemas(recovered: dict[str, str], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for namespace, xsd_text in recovered.items():
        filename = NAMESPACE_TO_FILENAME[namespace]
        path = dest / filename
        path.write_text(xsd_text, encoding="utf-8")
        # Verify the file actually written to disk, not the in-memory string,
        # so this also catches encoding/write mistakes.
        _verify_written_schema(path)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"directory to write recovered .xsd files into (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--pdf-url",
        default=DEFAULT_PDF_URL,
        help="URL (or file:// path) of the REFI-QDA spec PDF to recover schemas from",
    )
    args = parser.parse_args(argv)

    try:
        _import_pypdf()  # fail fast, before spending a network request
        pdf_bytes = _download_pdf(args.pdf_url)
        recovered = recover_schemas(pdf_bytes)
        written = write_schemas(recovered, args.dest)
    except SchemaRecoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for path in written:
        print(f"Recovered and verified: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

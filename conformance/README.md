# Conformance testing

This directory implements the conformance-testing methodology from
`SPEC.md` §1.2, with one deliberate change from how that section reads
literally -- see "Deviation from SPEC.md §1.2" below.

## Status

This is a scaffold. It is green today (everything skips cleanly) because
no real vendor exports exist in this repository yet, and it becomes
meaningful the moment `conformance/fixtures/seed/seed.qdpx` and at least
one vendor export exist -- see each `conformance/fixtures/<tool>/README.md`
for exactly what to drop where.

## How it works

`conformance/tests/test_conformance.py` auto-discovers `*.qdpx` files
under `conformance/fixtures/{seed,nvivo,atlasti,maxqda}/` at collection
time:

* If a directory has no fixtures, its tests report as **skipped** with a
  reason naming the missing directory -- not silently absent from the
  test run, so it's obvious from `pytest -v` output what's missing.
* Every fixture found is parsed with `refi_qda.parser.parse_qdpx`. A
  vendor export that doesn't parse at all is itself a conformance
  finding, not a scaffold bug -- the test fails loudly.
* If both `fixtures/seed/seed.qdpx` and a given tool's export exist, they
  are structurally diffed with `conformance/diffing.py` and the report is
  attached to the test output (see "The diff helper" below). Per SPEC.md
  §1.2 step 6, this always runs and always produces a report; it does not
  by itself fail the test merely because data was lost, since some loss
  is expected and the point of this suite is to document it precisely,
  not to gate CI on vendors' own conformance.

## The diff helper

`conformance/diffing.py` exposes `diff_projects(seed, other) ->
ConformanceReport`, which compares two parsed `refi_qda.model.Project`
objects and reports codes, sources, selections, codings, cases, variable
values, memos and sets that are missing, added, or changed between them --
not just a pass/fail verdict.

**Objects are matched by name, not by GUID.** A project re-exported by a
different tool (or re-imported after a round trip) is not expected to
preserve GUIDs -- vendor tools routinely assign fresh ones on import. Name
is the only practical stable identifier across a cross-tool round trip,
so codes are matched by their full hierarchical path (e.g. `Topics >
Health > Diet`) and sources/cases/sets/memos by name. This means a
same-named-but-different-purpose object *will* be misattributed by this
diff -- documented here as a known limitation of name-based matching, not
hidden.

Links and graphs are compared by count only, not matched item-by-item: both
routinely lack stable names and their GUIDs are exactly the kind of
reference this diff cannot rely on surviving a round trip, so a precise
match would be more misleading than an honest "N in seed, M in export."

## Deviation from SPEC.md §1.2

SPEC.md §1.2 step 1, read literally, has the seed project built three
separate times by hand, once directly inside each of NVivo, ATLAS.ti and
MAXQDA. That conflates two different things: how well each tool's
*exporter* implements REFI-QDA, and how consistently a human operator
reproduces the same project by hand three times in three different UIs.

This scaffold instead treats **one project as the single independent
variable**: `conformance/fixtures/seed/seed.qdpx` is built once, imported
into each tool, and re-exported. Same file in, three files out. Any
divergence between the three exports is then attributable to the
exporters, not to operator variance in how faithfully the seed project
was reconstructed three times.

The per-tool fixture directories (`fixtures/nvivo/`, `fixtures/atlasti/`,
`fixtures/maxqda/`) still accept hand-built projects too -- see each
directory's README -- because that data has value (e.g. it's the only way
to test a tool's *importer* independent of its exporter, by hand-building
in tool A and importing into tool B). It's just not the primary path, and
this suite treats it accordingly: hand-built fixtures get parsed and
sanity-checked, but are never diffed against the seed, because there is
no seed-equivalent baseline to diff them against.

## Getting the REFI-QDA XSD (optional, for schema validation)

Neither this conformance suite nor `refi_qda.validator` vendors the
REFI-QDA XSD -- its redistribution licence is not clearly stated by
qdasoftware.org, and the canonical download
(https://www.qdasoftware.org/project-implementation-files) sits behind a
JS-gated (Tresorit) link this project does not attempt to scrape.

To validate a fixture against the schema:

1. Obtain `Project.xsd` yourself. As of this writing, a mirror exists at
   https://github.com/openqda/refi-tools (`docs/schemas/project/v1.0/Project.xsd`,
   AGPL-3.0-licensed per that repository -- read its licence before
   redistributing anything derived from it further). The REFI-QDA
   standard's specification *documents* are separately stated by that
   same repository to be MIT-licensed; the schema *file* is not
   unambiguously covered by that statement, which is exactly the
   ambiguity this project is declining to resolve on your behalf.
2. Save it somewhere on disk -- conventionally `schema/Project.xsd` in
   this repository (already gitignored; see `schema/README.md`).
3. Either pass it explicitly:

   ```python
   from refi_qda.validator import validate

   validate(qde_xml_bytes, schema_path="schema/Project.xsd")
   ```

   or set it once for a whole session:

   ```sh
   export REFI_QDA_SCHEMA_PATH=schema/Project.xsd
   ```

Without either, `validate()` raises
`refi_qda.exceptions.SchemaNotConfiguredError` with these same
instructions, rather than silently skipping validation.

# ATLAS.ti export fixtures

## What is here now

Two real ATLAS.ti exports, both produced by **ATLAS.ti 26.1.2 (build
34883) on macOS 26.5.1**, both hand-built rather than derived from
`conformance/fixtures/seed/seed.qdpx` (which does not exist yet). They are
therefore parsed and characterised, not structurally diffed against a
baseline -- see "Also acceptable" below and `conformance/README.md`.

They are small on purpose: neither contains media. ATLAS.ti exported the
video as an **external** source sitting outside the archive, so what is
committed here is only the XML. The `.mov` files they reference
(533,948,057 bytes each, byte-identical to one another) are **not** in this
repository and the fixtures will never resolve their media on any machine
but the one that produced them. That is itself part of what fixture 01
documents.

| Fixture | Archive | Inner XML | Exercises |
|---|---|---|---|
| `atlasti_26_handbuilt_01_baseline.qdpx` | 767 B | 1,429 B | Container naming, schema conformance, external-media handling |
| `atlasti_26_handbuilt_02_codes_memos.qdpx` | 1,431 B | 4,788 B | Memo downgrade, GUID instability, multi-coding, degenerate selections |

Both are exports of **the same ATLAS.ti project** ("Trial", identical
project `creationDateTime` and user GUIDs), taken minutes apart. That is
what makes the pair useful: it is a controlled test of what ATLAS.ti keeps
stable across two exports of one project. The answer is "less than you
would expect" -- see fixture 02.

### `atlasti_26_handbuilt_01_baseline.qdpx`

The minimum viable export: one video source, one uncoded selection
(`begin=7241 end=14243`, milliseconds), two users, **no codebook at all**.

What it pins:

- **Container filename non-conformance.** The archive contains `Trial.qde`,
  not `project.qde`. This is the one thing that stops `parse_qdpx` from
  opening either fixture -- see `../../tests/test_atlasti_container_naming.py`
  and the open design question below.
- **Schema conformance.** Despite the filename, the payload validates
  cleanly against the REFI-QDA Project v1.0 XSD. Useful as a control: it
  establishes that the container check, not the XML, is what fails.
- **External media handling.** `path="relative:///<GUID>.mov"` resolved
  against `basePath` -- and `currentPath` is omitted entirely, so the
  source's original location is unrecoverable from the export. The `name`
  attribute says `Christos vagias-2.MP4` while the referenced file is a
  `.mov`, so even the extension does not survive.
- **`basePath` leaking local filesystem layout** (an absolute path under a
  user's home directory, including their name).

### `atlasti_26_handbuilt_02_codes_memos.qdpx`

The same project after adding a codebook and coding. Two codes (`hello`,
`test`), eight video selections, four codings, three comments.

What it pins:

- **Memos are structurally downgraded.** Three quotation comments are
  exported as bare `<Description>` strings on the selection. REFI-QDA
  models a memo as a `<Note>` of type `TextSourceType` (spec §3.9: "A note
  is a text source"), referenced via `<NoteRef targetGUID>` -- carrying a
  GUID, author and timestamps. This export contains **zero `<Notes>` and
  zero `<NoteRef>`**, so authorship and date of every comment are lost.
  This is the concrete instance of SPEC.md §1.3's memo risk area.
- **GUIDs are not stable across exports.** Same project, same video, but
  the `VideoSource` GUID and the media's GUID filename both differ from
  fixture 01. Two exports of one project cannot be matched by identity.
  This is the empirical justification for `conformance/diffing.py` matching
  on names and coordinates rather than GUIDs.
- **Multi-coding.** Two selections carry two codes each -- correctly
  parsed. Note this is *not* the same as overlapping selections (see gaps
  below).
- **A degenerate zero-length selection.** `begin == end == 21477`, a
  0-millisecond selection that nonetheless carries a comment. Schema-legal
  (`xsd:integer`, unconstrained) and exactly the shape that breaks naive
  importers computing a duration.
- **Duplicate selection names.** Two selections are both named `29s`
  (ATLAS.ti names quotations by start second). Harmless here, but it
  confirms names are not unique and validates `diffing.py` keying video
  selections on `(begin, end)` instead.
- **Code colours absent.** The XSD defines `color` (RGBType) on codes;
  neither code carries one.

## Known gaps -- what these two fixtures do NOT test

Stated explicitly so nobody mistakes this directory for adequate coverage.
None of SPEC.md §1.3's three named risk areas are exercised:

- **Overlapping selections.** All 28 pairs in fixture 02 were checked:
  **zero overlapping pairs.** All eight selections are disjoint in time.
- **Nested codes.** Both codes are flat, `isCodable="true"`, no hierarchy
  and no folders.
- **Character offsets.** Neither fixture contains a text, PDF or transcript
  source, so no character-position selection exists to test.

Also absent from both: cases, case attributes/variables, sets, links,
graphs, transcripts, and internal (embedded) sources.

Closing these needs a project with a 3+ level code hierarchy, two genuinely
overlapping selections on one source, and at least one text document --
i.e. the seed project described in `../seed/README.md`.

## Open design question: should the reader require `project.qde`?

**Do not "fix" the container check without settling this first.** The test
that pins it is marked `xfail(strict=True)` precisely so that making it
pass fails the suite and forces this conversation.

The spec is unambiguous. REFI-QDA v1.5 p.21:

> "The XML instance files for exchanging projects **must be named
> "project"** and have the extension .QDE"

and §8.1:

> "a compressed (zipped) folder structure containing a single
> **'project.qde'** file"

So `refi_qda.container` is correct as written, and ATLAS.ti 26 is
non-conformant. The question is what a *reference implementation* should do
about a vendor that a large fraction of real users depend on.

The naming is also unpredictable, which rules out the obvious workaround:
fixture 02 was exported to a file called `Project.qdpx` and still contains
`Trial.qde`. ATLAS.ti names the inner file after the **project name inside
ATLAS.ti**, not after the export filename, so a reader cannot derive the
expected name from the archive name.

Options, none yet chosen:

1. **Keep requiring `project.qde`.** Spec-pure; cannot open real ATLAS.ti
   exports; arguably useless as a practical tool.
2. **Accept any single `*.qde` at the archive root**, and require exactly
   one so the choice is never ambiguous. Pragmatic, and the failure mode
   (two `.qde` files) is still a hard error rather than a guess.
3. **Accept it but report it.** Parse, and surface the deviation through a
   structured warning or a field on the returned `Project`, so a caller can
   tell a conformant file from a tolerated one. Most informative; most API
   surface.
4. **Strict/lenient modes.** A `strict=True` default with an opt-out. Puts
   the choice on the caller, at the cost of two code paths to maintain.

One implementation note, found by actually trying it: the name is
hardcoded in **two** places in `refi_qda.container`, not one --
`QdpxContainer._validate_structure` rejects the archive, and
`QdpxContainer.read_qde` then reads `QDE_FILENAME` by name. Relaxing only
the first turns a clean `ContainerError` into a raw `KeyError` from
`zipfile`, which is strictly worse than the current behaviour. Whoever
takes this on should change both together.

Whichever is chosen, the deviation should stay *visible* rather than being
silently normalised -- documenting exactly this kind of divergence is the
point of the project (see `README.md`, "Why this exists"). Note that
`refi_qda.writer.write_qdpx` already emits a correctly named `project.qde`,
so the toolkit can already act as a normaliser for this defect.

## What to drop here in future

`.qdpx` files produced by **importing `conformance/fixtures/seed/seed.qdpx`
into ATLAS.ti and re-exporting it as REFI-QDA**. This is the canonical
path (see `conformance/README.md`) -- it isolates ATLAS.ti's exporter
behaviour from operator variance, because the input is the same file
every time, not a project built by hand a second time in ATLAS.ti's UI.

Name each file to record the ATLAS.ti version that produced it, e.g.:

```
atlasti_23_export.qdpx
atlasti_24_export.qdpx
```

## Also acceptable

A project built directly in ATLAS.ti by hand (rather than imported from
the seed) is still useful data and will still be picked up by the
discovery logic in `conformance/tests/` -- it just cannot be compared
against the seed project structurally, only parsed and sanity-checked,
since there is no baseline to diff it against. Name these clearly, e.g.
`atlasti_handbuilt_2024-06.qdpx`. The two fixtures above follow this
convention.

## What happens once files are here

`conformance/tests/test_conformance.py` auto-discovers every `*.qdpx` in
this directory and:

1. Parses it with `refi_qda.parser.parse_qdpx` (fails loudly if ATLAS.ti's
   export doesn't parse at all -- that is itself a conformance finding).
   Fixtures whose archive has no `project.qde` are auto-detected at
   collection time and marked `xfail`, so this known vendor defect does not
   masquerade as a suite failure.
2. If `conformance/fixtures/seed/seed.qdpx` is also present, runs
   `conformance.diffing.diff_projects` against it and writes a structured
   report of exactly what survived, what changed, and what was lost.

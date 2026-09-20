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
  not `project.qde`. This used to stop `parse_qdpx` from opening either
  fixture; as of the accept-and-warn decision below it opens and emits a
  `ContainerNamingWarning` instead -- see
  `../../tests/test_atlasti_container_naming.py`.
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

## Resolved: the reader accepts any single `.qde`, and warns

**Decision taken. Option 3, accept-and-warn.** Recorded here rather than
only in a commit message, because the reasoning matters more than the
change.

The spec is unambiguous. REFI-QDA v1.5 p.21:

> "The XML instance files for exchanging projects **must be named
> "project"** and have the extension .QDE"

and §8.1:

> "a compressed (zipped) folder structure containing a single
> **'project.qde'** file"

So `refi_qda.container` was correct as written, and ATLAS.ti 26 is
non-conformant. The question was what a *reference implementation* should
do about a vendor that a large share of real users depend on.

The naming is also unpredictable, which ruled out the obvious workaround:
fixture 02 was exported to a file called `Project.qdpx` and still contains
`Trial.qde`. ATLAS.ti names the inner file after the **project name inside
ATLAS.ti**, not after the export filename, so a reader cannot derive the
expected name from the archive name.

### What the reader does now

- Accepts **any single root-level `.qde`**, whatever it is called.
- Emits `refi_qda.exceptions.ContainerNamingWarning` when that name is not
  `project.qde`, naming the file it found and citing §8.1.
- Exposes `QdpxContainer.qde_filename` so a caller can record *which* file
  was used, not merely be told something was off.
- Still raises `ContainerError` for **zero** or **more than one** `.qde` at
  the root. Only the naming requirement was relaxed, not "exactly one" --
  with two project files there is no unambiguous answer, and guessing
  would be worse than failing.

### Why a warning rather than a log line

`warnings.warn` lets the *caller* decide how strict to be, which logging
cannot:

```python
import warnings
from refi_qda.exceptions import ContainerNamingWarning

warnings.simplefilter("error", ContainerNamingWarning)  # now a hard error
```

A conformance-checking consumer escalates it; a researcher trying to read
their own data gets a message and their project. This library is also a
library, not an application, so it has no business configuring logging
handlers. There was no existing warning or logging convention anywhere in
the codebase, so `QdpxWarning` was added to `refi_qda.exceptions`,
mirroring the existing `QdpxError` hierarchy.

### The deviation stays visible

Documenting divergence rather than papering over it is the point of this
project (see `README.md`, "Why this exists"). Accept-and-warn keeps the
deviation observable in three ways at once: the warning, the
`qde_filename` accessor, and these fixtures.

`refi_qda.writer.write_qdpx` deliberately still emits a conformant
`project.qde`, so **the toolkit repairs this defect**: read a
non-conformant ATLAS.ti export, write it back out, and the result opens
silently anywhere. That round trip is pinned by
`test_reading_then_writing_repairs_the_filename`.

### If you are tempted to change this again

The tests guard both directions. `test_atlasti_export_now_opens_and_warns`
fails if the fixtures stop opening *or* if the warning disappears (it
matches the warning's content, not just its presence);
`test_conformant_archive_emits_no_warning` fails if correct files start
warning. Both were verified to fail when deliberately broken.

One implementation note, found by trying it the wrong way first: the name
was hardcoded in **two** places -- `_validate_structure` and `read_qde`.
Relaxing only the first turned a clean `ContainerError` into a raw
`KeyError` from `zipfile`. Both now route through a single
`_resolve_qde_member`, called once at open time so the warning fires once
per archive rather than once per read.

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
   A non-conformant `.qde` filename no longer blocks this; it surfaces as a
   `ContainerNamingWarning` in the test output instead.
2. If `conformance/fixtures/seed/seed.qdpx` is also present, runs
   `conformance.diffing.diff_projects` against it and writes a structured
   report of exactly what survived, what changed, and what was lost.

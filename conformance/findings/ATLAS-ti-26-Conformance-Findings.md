# ATLAS.ti 26 REFI-QDA Conformance Findings

**Subject:** ATLAS.ti 26.1.2 (build 34883), macOS 26.5.1
**Standard:** REFI-QDA v1.5 (Project schema v1.0)
**Tested with:** `qdpx-toolkit` 0.1.0
**Date:** 13 September 2026
**Fixtures:** [`conformance/fixtures/atlasti/`](../fixtures/atlasti/)

---

## What this document is

The REFI-QDA standard exists so qualitative researchers can move a coded
project — interviews, codes, analytic memos — between ATLAS.ti, NVivo and
MAXQDA without being locked into one vendor. This report records what
actually happens when a real ATLAS.ti export meets a standards-conformant
reader.

Two exports of the same small video-coding project were examined
attribute-by-attribute against the published specification. **Six
divergences were found.** None of them is visible to the researcher doing
the export: in every case ATLAS.ti reports success.

This is a report about one vendor at one version, on a deliberately small
project. It is a documented starting point, not a survey. Section
["What these fixtures do not cover"](#what-these-fixtures-do-not-cover)
states its limits plainly.

---

## Summary for a non-specialist reader

> We pointed a REFI-QDA reader, written to follow the published standard,
> at two real ATLAS.ti exports. Neither would open.
>
> The cause is a filename. The standard requires the data file inside the
> export to be called `project.qde`; ATLAS.ti names it after the project
> instead. A reader that follows the standard rejects a file that a major
> commercial package routinely produces.
>
> Once past that one check, the reader recovered **every single data point
> in both files without loss** — verified by writing the data back out and
> re-reading it. So the exports are not corrupt. They are precise, valid,
> and unopenable.
>
> Two deeper problems then emerged, both silent:
>
> **Analytic memos lose their authorship.** The researcher's written
> comments on the video survive as anonymous, undated text. The standard
> has a proper mechanism for memos that records who wrote each one and
> when; ATLAS.ti does not use it. In team research, that record is part of
> the audit trail.
>
> **Nothing has a stable identity.** Exporting the same project twice
> produced entirely different internal identifiers for the same video, plus
> a second half-gigabyte copy of the file on disk. Two archived exports of
> one project cannot be matched to each other afterwards.
>
> Every one of these is invisible at export time. The software says it
> worked.

---

## How this was tested

Stated so the findings can be checked rather than taken on trust.

1. **A primary-source copy of the specification.** The REFI-QDA v1.5 PDF
   was downloaded from the [OpenQDA REFI-tools
   mirror](https://openqda.github.io/refi-tools/docs/standard/REFI-QDA-1-5.pdf)
   and quoted directly. No claim below rests on the reader's own comments
   about what the standard says.
2. **The official XML schema**, recovered from that PDF by
   [`scripts/fetch_schema.py`](../../scripts/fetch_schema.py), used to
   validate both exports independently of the reader.
3. **Attribute-level auditing.** Every element and attribute in the raw XML
   was enumerated and compared against what the reader produced, rather
   than spot-checking fields.
4. **Round-trip testing** (SPEC.md §1.2 step 4): parse → write → re-parse,
   comparing the result to the original.
5. **A controlled pair.** Both exports come from the same ATLAS.ti project,
   taken minutes apart, which is what makes the identity-stability finding
   possible.

All six findings are pinned by tests in
[`conformance/tests/test_atlasti_container_naming.py`](../tests/test_atlasti_container_naming.py).

### The two exports

| | Fixture 01 — baseline | Fixture 02 — codes & memos |
|---|---|---|
| Archive size | 767 bytes | 1,431 bytes |
| Inner XML | 1,429 bytes | 4,788 bytes |
| Codes | none | 2 (`hello`, `test`) |
| Selections | 1 | 8 |
| Codings | 0 | 4 |
| Comments | 0 | 3 |
| Media included | no | no |

Both reference the same 533,948,057-byte video, held **outside** the
archive. The two `.mov` files on disk are byte-identical copies.

---

## Findings

### 1. A standards-conformant reader cannot open either export

**Severity: blocking. Resolved in this toolkit — see [Resolution](#resolution-accept-and-warn).**
Both fixtures.

> **Status:** this reader now opens both files and reports the deviation
> rather than refusing them. The finding itself stands: ATLAS.ti 26 is
> non-conformant, and any tool built strictly to the written standard
> still rejects these exports.

```
ContainerError: Project.qdpx does not contain a 'project.qde' file at its
root (REFI-QDA section 8.1 requires exactly one).
```

A `.qdpx` file is a ZIP archive. The standard is unambiguous about what
the XML inside it is called — REFI-QDA v1.5, p.21:

> "The XML instance files for exchanging projects **must be named
> "project"** and have the extension .QDE"

and §8.1:

> "a compressed (zipped) folder structure containing a single
> **'project.qde'** file"

ATLAS.ti names it after the project: `Trial.qde`.

**The naming is unpredictable, which is what makes this more than a
nuisance.** Fixture 02 was exported to a file the user named
`Project.qdpx` and *still* contains `Trial.qde`. The inner name tracks the
project name inside ATLAS.ti, which an importing tool has no way to know.
A reader cannot derive the expected filename from the archive it is
holding.

**Why it matters.** Any tool built to the written standard — an archive
ingesting deposits, a university repository, an independent analysis
script — rejects real ATLAS.ti exports on contact. The failure is at least
clear and immediate rather than silent, which is the one merciful thing
about it.

This toolkit no longer refuses them; see
[Resolution](#resolution-accept-and-warn) below for what it does instead
and why.

---

### 2. Analytic memos lose their author and date

**Severity: high — silent data loss.** Fixture 02.

The researcher wrote three comments on video segments. ATLAS.ti exported
them like this:

```xml
<VideoSelection begin="21477" end="21477" name="21s">
  <Description>Hello Trying this out</Description>
</VideoSelection>
```

This is schema-legal, but it is not how REFI-QDA models a memo. The
standard defines one (§3.9):

> "A free text comment made by the user on a project, source, selection or
> code. **A note is a text source.**"

In the schema, `<Note>` is a `TextSourceType` — a real object carrying its
own identifier, author, creation timestamp and modification timestamp,
attached to a selection by reference. The export contains **zero `<Notes>`
and zero `<NoteRef>` elements.**

What is destroyed, concretely:

| | In the standard's model | In this export |
|---|---|---|
| Who wrote the comment | recorded (author) | **lost** |
| When it was written | recorded (timestamp) | **lost** |
| Stable identity | recorded (GUID) | **lost** |
| Formatting | optional rich text | flattened to plain |

**Why it matters.** SPEC.md §1.3 anticipated that memo *formatting* might
degrade to plain text. The real behaviour is worse in kind, not just
degree: the memo stops being an object at all and becomes an anonymous
string welded to a timestamp range. Every other object in this file —
every code, every selection, every coding — carries a creation date and an
author. The memos, alone, carry neither.

For qualitative research this is not cosmetic. Analytic memos are where
interpretation is recorded, and in team coding "who wrote this, and when"
is part of the evidence chain. A project archived through this route
cannot answer that question afterwards.

---

### 3. Identifiers are reassigned on every export

**Severity: high — affects archiving and reproducibility.** Both fixtures.

The two exports are the same ATLAS.ti project (identical project creation
timestamp, identical user identifiers) holding the same video (identical
name, byte-identical file).

| | Fixture 01 | Fixture 02 | Stable? |
|---|---|---|---|
| Video source ID | `EF48EB94-…` | `241BA0AA-…` | **no** |
| Media filename | `7D9415B0-….mov` | `DD148A4A-….mov` | **no** |

Every export mints fresh identifiers and writes a fresh copy of the media.
Both 533 MB files persist on disk — 1.07 GB of byte-identical video from
two exports of one small project.

**Why it matters.** Two consequences follow directly:

- **Archived exports cannot be reconciled.** If a repository holds an
  export and the researcher later deposits an updated one, nothing
  connects the two records. The standard's identifiers exist precisely to
  make that possible.
- **Storage cost scales with export count**, not project size, because
  each export duplicates the media rather than referencing it.

This finding also validates a design decision already taken in this
toolkit: [`conformance/diffing.py`](../diffing.py) deliberately matches
objects by name and by coordinates rather than by identifier. That
looked like over-caution when it was written. It is not.

---

### 4. The original media file becomes unfindable

**Severity: medium — breaks portability.** Both fixtures.

Neither export contains the video. Each references it as an external file:

```
path      = "relative:///DD148A4A-B28B-4BC0-90D8-3D1FB587C8E5.mov"
basePath  = "/Users/<user>/Desktop/Trial Media/Project Media"
```

Three problems compound here:

- **`currentPath` is omitted.** The standard (§8.3) reserves this
  attribute for "the original path and filename of the source". Without
  it, and with the file renamed to an identifier, the source's real
  location is unrecoverable from the export.
- **Even the file type disagrees.** The source is named
  `Christos vagias-2.MP4`, but the file referenced is a `.mov`. The video
  was converted and renamed; the export records neither fact.
- **`basePath` is an absolute local path.** It resolves only on the
  machine that produced it.

**Why it matters.** A 767-byte file that claims to be a video-coding
project is portable in name only. Sent to a collaborator, it arrives
referencing a file that does not exist for them, under a name that gives
no clue what to look for. The standard anticipates this — it instructs
importing software to "prompt the user for the new file location" — but
the prompt can only ask for a file the user can still identify.

There is also a **privacy dimension**: `basePath` embeds the researcher's
name and home directory layout. For a format whose purpose is moving
human-participant research between institutions, that is worth flagging
on its own.

---

### 5. A zero-length selection

**Severity: low — an edge case worth knowing about.** Fixture 02.

One selection has `begin == end == 21477` — a coded segment of zero
milliseconds' duration, which nonetheless carries one of the three
comments.

This is schema-legal: the standard types these positions as plain
integers with no constraint that one exceed the other. It is exactly the
shape that breaks importing software written on the reasonable assumption
that a segment has a duration — division by zero, a zero-width rendering,
a segment silently dropped as empty.

Recorded here because a conformance corpus is most useful when it contains
the awkward cases, not just the tidy ones.

---

### 6. Code colours are not exported

**Severity: low.** Fixture 02.

The schema defines a `color` attribute on codes. Neither exported code
carries one. In ATLAS.ti's own interface codes are colour-coded, and
colour frequently carries analytic meaning in a coding scheme — grouping
by theme, marking provisional codes. That layer does not survive.

---

## What the reader got right

Reporting only failures would misrepresent the result. Once past the
container check, the reader's fidelity was exact:

- **Complete recovery.** 105 attributes in fixture 02's XML; 105 after a
  full write-and-re-read cycle. Element counts identical across all
  twelve element types. Fixture 01: all 26 semantic attributes recovered.
- **Round-trip lossless.** Both fixtures produce an object identical to
  the original after parse → write → re-parse.
- **Both exports are schema-valid**, before and after round-tripping. The
  filename is genuinely the only defect in either file.
- **Timestamps handled correctly.** The standard specifies milliseconds
  for media selections (§10.4); the reader treats them as such. ATLAS.ti
  names each segment by its start second — `begin="2274"` → `"2s"` —
  which corroborates the interpretation independently.
- **Multi-coding handled correctly.** Two selections carry two codes each;
  all four code references resolved to real codes.

The honest summary is that the reader is in good shape and the ecosystem
is not.

---

## What these fixtures do not cover

Stated explicitly so this report is not mistaken for broader coverage than
it has. **None of the three risk areas named in SPEC.md §1.3 is exercised
by either fixture:**

| Risk area | Covered? | Why not |
|---|---|---|
| Overlapping selections | **no** | All 28 pairs checked; zero overlap. All eight selections are disjoint in time. |
| Nested code hierarchies | **no** | Both codes are flat. No parent/child, no folders. |
| Character-offset fidelity | **no** | No text, PDF or transcript source in either export. |

Also absent: cases, case attributes, sets, links, graphs, transcripts, and
embedded (internal) sources.

Fixture 02 does contain **multi-coding** — two codes on one selection —
which is a real result, but it is a different thing from two selections
overlapping on the same source, and it is the latter that the standard's
implementers diverge on.

Closing these gaps requires a project with a three-or-more-level code
hierarchy, two genuinely overlapping selections, and at least one text
document — the seed project described in
[`conformance/fixtures/seed/README.md`](../fixtures/seed/README.md) — put
through all three vendor tools. That is the next piece of work, and this
report should not be read as a substitute for it.

---

## Resolution: accept and warn

**Finding 1 is now resolved in this toolkit.** Findings 2–6 are vendor-side
and cannot be resolved here; they are reported, not repaired.

The reader was changed to **accept any single `.qde` file at the archive
root, whatever it is named, and emit a structured warning when that name
deviates from the standard**:

```
ContainerNamingWarning: ...atlasti_26_handbuilt_02_codes_memos.qdpx contains
its project XML as 'Trial.qde', not 'project.qde' as REFI-QDA v1.5
p.21/section 8.1 require. Reading it anyway.
```

Three properties of that choice are worth stating, because the alternative
readings are all defensible and one was nearly taken instead:

- **The deviation stays visible.** Silently normalising it would have made
  this toolkit complicit in the interoperability problem it exists to
  document. The warning is also *escalatable* — a conformance-checking
  caller can turn it into a hard error with one line of standard-library
  `warnings` configuration, which a log message could not offer.
- **"Exactly one project file" was not relaxed.** Zero or several `.qde`
  files at the root remain a hard error. Only the *name* was relaxed;
  guessing between two candidate project files would be worse than
  failing.
- **Writing is unchanged.** Exports produced by this toolkit are still
  named `project.qde`. That makes it a **repair tool**: read a
  non-conformant ATLAS.ti export, write it back out, and the result is
  spec-correct and opens silently anywhere. This round trip is covered by
  a test.

The three rejected alternatives — staying strict, accepting silently, or
offering strict/lenient modes — are recorded with their reasoning in
[`conformance/fixtures/atlasti/README.md`](../fixtures/atlasti/README.md),
along with an implementation note for anyone revisiting it.

## Reproducing this

```sh
uv run --with pypdf scripts/fetch_schema.py   # recover the XSD
python -m pytest conformance/tests/test_atlasti_container_naming.py -v
```

Expected: everything passes, with `ContainerNamingWarning` surfacing in
the output for both ATLAS.ti fixtures. The tests guard the resolution in
both directions — they fail if the fixtures stop opening, and equally if
the warning is dropped and silent acceptance is left behind.

---

## Correction

An earlier draft of these findings described fixture 01 as "1,429 bytes".
That is the size of the XML inside the archive; the archive itself is 767
bytes. The distinction does not affect any conclusion — both are tiny
because neither contains media — but the figures in this report are the
corrected ones.

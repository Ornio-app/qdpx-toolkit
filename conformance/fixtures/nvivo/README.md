# NVivo export fixtures

## What to drop here

`.qdpx` files produced by **importing `conformance/fixtures/seed/seed.qdpx`
into NVivo and re-exporting it as REFI-QDA**. This is the canonical path
(see `conformance/README.md`) -- it isolates NVivo's exporter behaviour
from operator variance, because the input is the same file every time,
not a project built by hand a second time in NVivo's UI.

Name each file to record the NVivo version that produced it, e.g.:

```
nvivo_14_export.qdpx
nvivo_15_export.qdpx
```

## Also acceptable

A project built directly in NVivo by hand (rather than imported from the
seed) is still useful data and will still be picked up by the discovery
logic in `conformance/tests/` -- it just cannot be compared against the
seed project structurally, only parsed and sanity-checked, since there is
no baseline to diff it against. Name these clearly, e.g.
`nvivo_handbuilt_2024-06.qdpx`, so it is obvious from the filename which
category a given fixture is in.

## What happens once files are here

`conformance/tests/test_conformance.py` auto-discovers every `*.qdpx` in
this directory and:

1. Parses it with `refi_qda.parser.parse_qdpx` (fails loudly if NVivo's
   export doesn't parse at all -- that is itself a conformance finding).
2. If `conformance/fixtures/seed/seed.qdpx` is also present, runs
   `conformance.diffing.diff_projects` against it and writes a structured
   report of exactly what survived, what changed, and what was lost.

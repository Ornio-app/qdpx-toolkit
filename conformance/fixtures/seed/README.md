# Seed fixture

This directory holds the **one canonical seed project** used for all
conformance testing. See `conformance/README.md` for why there is exactly
one of these, imported into each vendor tool, rather than three separately
hand-built projects (one per tool) as REFI-QDA's methodology template
(SPEC.md §1.2 step 1) literally describes.

## What to drop here

A single file named:

```
seed.qdpx
```

It should be a REFI-QDA project with representative complexity per
SPEC.md §1.2 step 1: nested codes at 3+ levels, overlapping code
assignments, memos on multiple object types (sources, codes, cases),
case attributes with mixed data types (text/boolean/integer/float/date),
and timestamped audio segments.

`tests/fixtures/hand_authored/` (used by the unit test suite, not this
conformance suite) already has a small example of this shape; the seed
project used here should be more complete, since it is what gets imported
into NVivo, ATLAS.ti and MAXQDA to generate the fixtures in
`conformance/fixtures/nvivo/`, `atlasti/` and `maxqda/`.

## What happens once it's here

`conformance/tests/` auto-discovers `seed.qdpx` and runs it through this
library's reader as a baseline sanity check. It does not by itself compare
anything -- that happens once a matching tool export also exists (see the
other fixture directories' READMEs).

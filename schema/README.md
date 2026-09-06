# schema/

Drop the REFI-QDA XSD here yourself. This project does not vendor it --
see `conformance/README.md` ("Getting the REFI-QDA XSD") for why, and for
where to find a copy.

## What to drop here

```
schema/Project.xsd
```

(Optionally `schema/Codebook.xsd` too, if you also want to validate
codebook-only `.qdc` exchanges -- note that `refi_qda.parser` does not
yet parse `.qdc` files either way; see `SPEC.md`.)

Everything in this directory except this README is gitignored
(`schema/*.xsd`, see the repository root `.gitignore`), so it is safe to
drop a local copy here without accidentally committing it.

## How to use it

```python
from refi_qda.validator import validate

validate(qde_xml_bytes, schema_path="schema/Project.xsd")
```

or set `REFI_QDA_SCHEMA_PATH=schema/Project.xsd` in your environment and
omit `schema_path` entirely.

## Or: recover it from the published spec PDF

`scripts/fetch_schema.py` gives an alternative to hunting down the
Tresorit-gated canonical file: the REFI-QDA v1.5 specification PDF
(freely downloadable, unlike the schema files themselves) prints both
schemas in full as text. The script downloads that PDF, extracts the two
schema blocks, repairs the mangling PDF text-extraction introduces, and
writes the result here as `refi-qda-project-1.0.xsd` and
`refi-qda-codebook-1.0.xsd`.

This is schema *recovery*, not a vendored copy -- see the script's
docstring for exactly what that means and why it matters here. It
requires `pypdf`, which is not a dependency of this package; install it
with `pip install ".[scripts]"`, or run:

```sh
uv run --with pypdf scripts/fetch_schema.py
```

The script asserts that what it writes actually parses as a valid XML
Schema, and fails loudly (rather than writing something silently broken)
if a future spec revision changes the PDF's text layout enough to break
the recipe.

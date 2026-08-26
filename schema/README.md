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

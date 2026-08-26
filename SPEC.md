# Technical specification (skeleton)

Status: draft. This document defines scope precisely enough for NLnet reviewers and future contributors to evaluate the project; implementation details will be filled in as work proceeds.

## 1. REFI-QDA module

### 1.1 Format coverage

- [ ] Project structure (`project.qde` XML schema)
- [ ] Sources: text, audio, video, PDF, image
- [ ] Codes and code hierarchy (nested/parent-child)
- [ ] Coded selections, including overlapping selections on the same source
- [ ] Cases and case attributes
- [ ] Sets
- [ ] Memos (linked to sources, codes, and cases)
- [ ] Links / relations between codes
- [ ] Media timestamp references (audio/video coded segments)
- [ ] Notes on graphs / models, if in scope

### 1.2 Conformance testing methodology

1. Build one seed project with representative complexity: nested codes at 3+ levels, overlapping code assignments, memos on multiple object types, case attributes with mixed data types, timestamped audio segments.
2. Export the seed project from NVivo, ATLAS.ti, and MAXQDA as `.qdpx`.
3. Import each into this library's reader; diff against the seed project's intended structure.
4. Round-trip: read → write → re-read; diff against original.
5. Cross-tool: import Tool A's export into Tool B (manually, for reference) vs. import Tool A's export into this library, to isolate whether divergence is spec ambiguity or vendor-specific non-conformance.
6. Publish results as a structured, versioned report — not just pass/fail, but exactly what is lost and where.

### 1.3 Known risk areas (to verify, not assumed)

- Overlapping code selections: REFI-QDA's handling of this is a common divergence point across tools.
- Character offset encoding across different text encodings.
- Whether memo formatting (rich text) survives round-trip or degrades to plain text.

## 2. Transcription pipeline module

### 2.1 Architecture

```
audio input → on-device ASR (language-specific model) → diarisation (if available)
→ timestamp alignment → REFI-QDA source + transcript output
```

### 2.2 Language onboarding process

For each new language:

1. Identify existing open acoustic/language models or corpora (check SALTMIL, Common Voice, national language institutes first — do not train from zero if a usable base model exists).
2. Assemble or source a small evaluation set (never real participant data — synthetic or public-domain recordings only).
3. Fine-tune / adapt as needed.
4. Measure and publish word error rate honestly, including on dialectal variation where relevant.
5. Document known limitations per language explicitly (e.g. "not tested on regional accents of X").

### 2.3 Initial languages

See README for the Phase 1 list and rationale. This section will track per-language status (in progress / usable / documented limitations) as work lands.

## 3. Explicit non-goals

- Not a QDA application. No UI, no coding workflow.
- Not a general-purpose transcription tool for high-resource languages already well served (e.g. no reason to prioritise English).
- Not attempting real-time transcription in Phase 1 — batch processing of recorded interviews only.

## 4. Relationship to funding scope

Work under this specification is the scope of the NLnet Restack proposal. The Ornio application (UI, AI orchestration, licensing) is explicitly out of scope for that funding and is developed separately.

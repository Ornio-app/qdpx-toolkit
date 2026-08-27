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

See README for the Phase 1 list. Per-language status, now grounded in primary-source numbers read directly from Vakirtzian et al. (2024), *Speech Recognition for Greek Dialects: A Challenging Benchmark*, Interspeech 2024 — not secondhand citations. This is the correct primary source for Cretan and Griko; a note on the earlier, incorrect attribution is below the table.

| Language | Verified numbers (Vakirtzian et al., 2024) | Expected difficulty |
|---|---|---|
| Standard Modern Greek | Reference point, not a dialect in this study: XLS-R-greek 11.62% WER, Whisper Large-v3 13.7% WER on Common Voice | Low — existing models perform adequately |
| Cretan | Corpus: 2h1m (1h21m processed), 12,921 tokens, from Radio Mires broadcasts, 1998–2001. Zero-shot Whisper Large-v3: **58.42% WER / 26.44% CER**. Fine-tuned XLS-R-greek (35 epochs): **28.27% WER / 7.88% CER** — the dialect-low result in the whole study. Fine-tuned Whisper-medium: 47.87% WER / 17.83% CER, worse than fine-tuned XLS-R but still better than zero-shot. | Moderate — closest of the four studied dialects to Standard Greek; fine-tuning shows the strongest absolute results in the paper |
| Pontic | Not covered by this paper. A separate, later paper exists — Konstantinidou et al. 2026, DialRes workshop — confirmed to report zero-shot results but the actual WER/CER table has not yet been obtained by this project (PDF access pending). **Do not cite unverified figures for Pontic.** | Unknown until the 2026 paper's table is read directly. The abstract alone confirms results "remain challenging" and flags the added complication of no standardized orthography. |
| Griko | Corpus: 20 minutes, 2,374 tokens, 9 speakers across 4 villages in Salento, collected 2013, evaluated zero-shot only (dataset too small to fine-tune). Whisper Large-v3, Greek-script output: **108.29% WER / 99.68% CER**. Best achievable configuration found in the paper — romanizing the Greek-flagged output — still only reaches **98.62% WER / 54.29% CER**. Every tested configuration exceeds 98% WER. | High, confirmed directly rather than inferred — the paper attributes this to the combination of Italo-Romance lexical influence, Latin-script orthography (unlike the other three dialects, which use Greek script), and heavy stress-diacritic usage uncommon in Italian, worth roughly 8–10 CER points on its own when mismatched |

**Correction to an earlier draft of this document:** an earlier version of this table cited Griko's difficulty through a secondary reference to a different, later paper. The verified primary source is Vakirtzian et al. (2024) above, read directly, not cited secondhand. The 2024 paper's own dialect scope is Aivaliot, Cretan, Griko, and Messenian — Pontic is not covered by it at all.

**One structural finding from the 2024 paper worth designing around directly:** Griko's core problem is not just data scarcity, it's orthography. The paper's Section 6 states plainly that the absence of a standardized orthography is itself a modeling problem, not just a data-collection inconvenience — the same spoken form gets written multiple valid ways, which corrupts what "correct" even means for WER purposes. Any transcription pipeline work on Griko should budget for an orthography-normalization step as a first-class problem, not an afterthought, and the paper explicitly floats "ASR systems that robustly handle multiple orthographies for the same language" as an open research direction (Section 6) — worth citing directly in the NLnet proposal's technical-challenges section, since it hands you language the funder's own reviewers may recognize as a real open problem rather than something this project invented to sound hard.

### 2.4 Griko: flagship work package, not a Phase 1 side-line

The 2024 paper's Griko evaluation was zero-shot **only** because the corpus was too small to fine-tune: 20 minutes of audio, 2,374 tokens, 9 speakers. This is a documented, named ceiling in a published paper, not a guess — nobody has fine-tuned a model on Griko because nobody has had enough data to do it. That is the specific, citable gap this project proposes to close, and it is precise enough to budget separately from Cretan and Pontic rather than being folded into a generic "transcription pipeline" line.

**The work package has two halves, in order, and the second does not work without the first:**

1. **Data collection.** More transcribed, time-aligned Griko speech — ideally from the same or nearby villages as the 2024 corpus (Calimera, Sternatia, Martano, Corigliano) for direct comparability with the existing baseline. This is fieldwork-adjacent work: recruiting speakers, recording, manual transcription and alignment. It is the slower, harder half, and the proposal should say so rather than imply this is primarily an engineering task.
2. **Orthography normalization, before or alongside fine-tuning, not after.** Because Griko has no standardized spelling, more training data on inconsistently transcribed references will not improve WER in any meaningful way — the paper is explicit that this corrupts what "correct" even means as a metric. A normalization pass or a documented, consistent transcription convention (following the same logic the 2024 paper applied when choosing how to romanize output) has to exist before fine-tuning is worth running at all.
3. **Only then, fine-tuning**, on whichever model family the data volume supports — likely XLS-R-greek or Whisper-medium, following the same architecture choices the 2024 paper made for Cretan, since those are the ones shown to actually benefit from limited-data fine-tuning in this exact language family.

**Why this is a stronger proposal than "we'll support four languages":** it names a specific blocker from a specific published paper and proposes to remove it, rather than asserting a general commitment to under-resourced languages that a reviewer has no way to evaluate. "First fine-tuned Griko ASR model, publicly released" is also a genuinely citable, dissemination-worthy outcome in its own right — Griko has fewer than 20,000 speakers, mostly over 60, and is UNESCO-listed as seriously endangered, so a released model is a real contribution to language documentation, not just a tooling milestone.

This project does not claim uniform feasibility across all four languages, and the proposal and any public reporting should not imply otherwise. Cretan is the safest near-term deliverable, with a real, demonstrated best-case WER of 28%, achievable through fine-tuning alone on existing techniques. Griko is scoped explicitly as a flagship research effort — data collection plus orthography normalization plus first-ever fine-tuning — rather than production-stage work, and its budget and timeline should reflect that it is doing something no one has done yet, not repeating a known recipe on a fourth language.

## 3. Explicit non-goals

- Not a QDA application. No UI, no coding workflow.
- Not a general-purpose transcription tool for high-resource languages already well served (e.g. no reason to prioritise English).
- Not attempting real-time transcription in Phase 1 — batch processing of recorded interviews only.

## 4. Relationship to funding scope

Work under this specification is the scope of the NLnet Restack proposal. The Ornio application (UI, AI orchestration, licensing) is explicitly out of scope for that funding and is developed separately.

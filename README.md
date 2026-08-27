# qdpx-toolkit

**A reference implementation of the REFI-QDA (.qdpx) exchange standard, plus an offline transcription pipeline for under-resourced European languages and dialects.**

Independent of, and usable without, any particular qualitative data analysis application. Built as part of a project to make qualitative research data portable across tools and off proprietary clouds.

## Why this exists

Qualitative researchers accumulate years of coded interview data inside proprietary QDA tools. The REFI-QDA standard (.qdpx) exists to make that data portable between NVivo, ATLAS.ti, MAXQDA and others, but existing implementations are partial, undocumented, and largely untested against one another. In practice, migration loses data: overlapping codes, nested codes, memos, and attribute records do not survive a round trip.

Separately, transcription of interview audio is increasingly an ethics and GDPR problem when it depends on non-EU cloud services, and it is close to unusable for European languages and dialects that large commercial transcription models were never trained on.

This project addresses both, as a single open commons: a well-tested exchange format implementation, and an offline transcription pipeline for languages that mainstream tools underserve.

## What this is not

This is not a qualitative analysis application. It has no interface, no coding workflow, no AI orchestration. It is infrastructure that any QDA tool, including proprietary ones, can build on. The proprietary application this project was originally built to support (Ornio) is maintained separately and is out of scope here.

## Scope

### 1. REFI-QDA (.qdpx) reference implementation

- Reader, writer, and schema validator for the REFI-QDA exchange format.
- A conformance test suite, run against real exports from NVivo, ATLAS.ti, and MAXQDA.
- A published, citable conformance report documenting where each tool's actual output diverges from the published specification, and from each other.
- Round-trip fidelity testing for: overlapping codes, nested/hierarchical codes, memos, case and source attributes, and media (audio/video) timestamp references.

### 2. Offline transcription for under-resourced European languages

"Under-resourced" is used here in the sense established by the [META-NET Language White Paper series](https://arxiv.org/pdf/2010.12433), which classified EU languages by the maturity of their speech and text NLP support on a five-point scale (Excellent / Good / Moderate / Fragmentary / Weak-No-Support). By that classification, **eighteen of the twenty-four official EU languages** rate Fragmentary or Weak/No-Support in speech processing, speech resources, or both, including Greek, Croatian, Estonian, Irish, Latvian, Lithuanian, Maltese, and others not usually thought of as "small."

This project scopes "under-resourced" deliberately wider than the twenty-four official languages, because the research communities most likely to need this tool work well below that line too:

- **Regional and minority languages** recognised under the [European Charter for Regional or Minority Languages](https://www.coe.int/en/web/european-charter-regional-or-minority-languages) — e.g. Basque, Breton, Sámi, Sorbian, Frisian, Occitan, Welsh, Scottish Gaelic.
- **Non-standard dialects of well-resourced languages**, which mainstream ASR models are typically not trained on at all even when the standard language is well supported — e.g. Bavarian, Swiss German, and multiple varieties of Modern Greek including Cretan, Pontic, and Cypriot, which remain largely absent from production ASR despite growing NLP research interest.
- **Severely endangered minority languages with almost no digital resources** — e.g. Griko (Italiot Greek), spoken by a shrinking, aging community in Salento, southern Italy, and listed by UNESCO as seriously endangered since 1999.
- **Language isolates and small communities** with active NLP research groups but minimal commercial tooling — Basque via the [Ixa group](https://www.ixa.eus/) and [SALTMIL](https://saltmil.eu/) being the clearest precedent for what this project follows.

**Initial target languages (Phase 1):**

| Language | Category | Why first |
|---|---|---|
| Standard Modern Greek | METANET Fragmentary | Home language of the lead maintainer; existing test corpus available; reference point for dialect comparisons (11.62–13.7% WER on Common Voice) |
| Cretan Greek | Dialect, under-resourced | Verified, directly-read baseline: zero-shot Whisper Large-v3 at 58.42% WER, dropping to 28.27% WER / 7.88% CER after fine-tuning XLS-R-greek (Vakirtzian et al., 2024) — the strongest demonstrated result of any Greek dialect studied to date |
| Pontic Greek | Dialect, under-resourced | A dedicated 2026 speech resource and baseline paper exists (Konstantinidou et al.); this project has not yet obtained the paper's actual WER/CER table and does not cite unverified figures |
| Griko (Italiot Greek) | UNESCO-listed severely endangered minority language | Confirmed hardest case in the literature: every tested model/configuration exceeds 98% WER (Vakirtzian et al., 2024), driven by Italo-Romance contact, Latin (not Greek) script, and stress-diacritic mismatch — the clearest case for urgency of any language on this list |

This trio is deliberately not arbitrary. Cretan has a directly verified low-resource ASR baseline: Vakirtzian et al. (2024) report zero-shot Whisper Large-v3 at 58.42% WER, dropping to a dialect-low 28.27% WER / 7.88% CER after fine-tuning XLS-R-greek for 35 epochs — the strongest result of any dialect in that study. Griko is separately confirmed, in the same paper, as the hardest case: every tested model and configuration exceeds 98% WER, driven by a combination of Italo-Romance lexical contact, Latin (not Greek) orthography, and heavy use of stress diacritics uncommon in Italian. The same paper identifies Griko's lack of a standardized orthography as a first-class modeling problem, not just a data-scarcity one — this project treats that as a design constraint from the start, not an afterthought. Pontic has a dedicated 2026 speech resource and baseline paper (Konstantinidou et al.), whose exact figures this project has not yet obtained directly and does not cite unverified (see SPEC.md for full details and primary sources).

Additional languages after Phase 1 are prioritised by contributor and research-community interest, not decided unilaterally — see Contributing.

Output is REFI-QDA-compatible: timestamped, speaker-attributable where diarisation is available, and directly importable into the coding workflow of any conformant QDA tool.

## Design principles

- **Local-first.** Transcription runs entirely on-device. No audio leaves the machine at any point. This is a hard requirement, not a configurable option.
- **Standards-first.** Output conforms to REFI-QDA, not to any one application's internal format.
- **Honest about accuracy.** Word error rates for under-resourced languages and dialects will not match commercial models for English. This is documented per-language, with real numbers, not hidden or glossed over.
- **A commons, not a feature.** This project must be independently useful to a researcher who has never heard of any specific QDA application, and independently useful to any tool vendor who wants to consume it.

## Status

Early. See open issues for current priorities. Conformance testing against the three major commercial tools is the current focus, because it is both the fastest path to a usable exchange library and the evidence base for language-pipeline funding decisions.

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome, particularly from speakers of, or researchers working with, under-resourced European languages and dialects — priority for Phase 2 language support will be guided by who shows up here, not decided in isolation.

## Relationship to Ornio

This project originated from work on [Ornio](https://ornio.app), a local-first qualitative analysis application, and is maintained by the same author. It is licensed and developed independently, and is designed to be useful to any REFI-QDA-conformant tool, not only Ornio.

## Installation

Not yet published to PyPI. From a clone:

```
pip install -e ".[dev]"
```

On release the distribution will be `qdpx-toolkit`, while the importable package is `refi_qda`:

```python
from refi_qda import open_qdpx

project = open_qdpx("interviews.qdpx")
```

This mismatch is intentional: the library implements the REFI-QDA *standard*, not the `.qdpx` *file extension* specifically, so the import name follows the name of the standard rather than the archive suffix — the same pattern as installing `pillow` and importing `PIL`.

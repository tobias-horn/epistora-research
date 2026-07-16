# Wiki Architecture Pilot Report

## Decision

Advance **V2: proposition-centric Markdown plus a derived JSONL index**.

Markdown remains the editable source of truth for Obsidian. Source claims and wiki propositions receive stable block IDs and claim-level links. A deterministic validator rejects structural provenance failures and emits a compact index for agent retrieval. Do not advance a normalized graph as the canonical authoring layer until human editing and update behavior are tested.

## Pilot corpus

The pilot question was how AI-generated explanations affect understanding, trust, calibration, reliance, and human–AI decision quality.

- 9 search or citation-expansion operations produced 137 unique candidate records.
- 35 reports were selected across primary studies, meta-analyses, systematic reviews, measurement work, formal accounts, conceptual foundations, qualitative studies, null/counterevidence, and intervention studies.
- The selected set spanned 2010–2025; 20 of 35 were primary studies.
- All 35 PDFs were acquired. OpenAlex reported XML for 24; 23 XML files downloaded and one XML endpoint returned 404. The affected report remained eligible through its validated PDF.
- All 35 reports parsed successfully: 23 by XML and 12 by PDF fallback. No output was flagged for review.
- Total parse time was 365.2 seconds; median per-report time was 0.018 seconds. The PDF fallback range was roughly 3–156 seconds, while most XML conversions took about 0.01–0.03 seconds.

This was an exploratory, accessible-full-text pilot, not a systematic review. It does not establish absolute recall, and source-set balance metrics do not establish relevance or evidential quality.

## Retrieval observations

Terminology reconnaissance added substantial unique material: the three searches contributed 26, 16, and 24 new records in sequence. Frontier queries saturated rapidly: successive strands added 26, 5, 4, and 0 new records. The last two frontier result sets had Jaccard overlap 0.939. Citation expansion around two meta-analytic anchors then added 17 and 19 new records, but also introduced method references and off-topic studies requiring screening.

Implications:

1. Query reformulation needs a marginal-yield and overlap stopping rule.
2. Exact field phrases improve precision but suppress historical terminology.
3. Citation expansion should remain a separately screened channel, not receive an automatic relevance bonus.
4. Accessibility must be an explicit policy, not a hidden quality weight. Systematic modes must discover inaccessible records and record them as access gaps.

## Architecture comparison

Seven source reports were converted into 14 claim-addressable source blocks. Two concepts—appropriate reliance and the trust/reliance distinction—were represented under three architectures using the same evidence. Seven fixed questions corresponded to the seven adjudicated propositions.

| Metric | V0 narrative | V1 proposition Markdown | V2 hybrid index |
|---|---:|---:|---:|
| Source claims with stable IDs and locators | 14/14 | 14/14 | 14/14 |
| Wiki propositions | 0 | 7 | 7 |
| Propositions with stable IDs | 0 | 7/7 | 7/7 |
| Propositions with source-claim citations | 0 | 7/7 | 7/7 |
| Broken wiki links | 0 | 0 | 0 |
| Source-property drift | 2 pages | 0 | 0 |
| Typed-connection ratio | 0% | 100% | 100% |
| Mean evidence-retrieval context proxy | 2,984 bytes | 2,442 bytes | 1,981 bytes |

V1 fixed the addressability, provenance, and relation problems without sacrificing readable pages. V2 preserved the same Markdown and reduced the small-pilot retrieval context proxy by about 19% relative to V1. The complete V2 index was 13,291 bytes compared with 9,146 bytes of wiki Markdown, so the index is not a storage optimization; its value is selective retrieval and deterministic validation.

## Design rationale

The hybrid applies the assertion/provenance separation found in [PROV-O](https://www.w3.org/TR/prov-o/), [nanopublications](https://doi.org/10.1109/eScience.2015.10), and [micropublications](https://doi.org/10.1371/journal.pone.0112598) while retaining ordinary Markdown as the human interface. This matches Obsidian's strengths: atomic flat [properties](https://obsidian.md/help/properties), human-readable [block links](https://obsidian.md/help/links), and automatically derived [backlinks](https://obsidian.md/help/plugins/backlinks).

The selected workflow also separates reports from studies and narrative synthesis from structured quantitative extraction. That is necessary for meta-analysis readiness and is consistent with Cochrane's separation of [study selection](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04), [data collection](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05), and [preparation for synthesis](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-09).

## What this pilot did not establish

- Structural citation links were validated, but citation entailment was not independently adjudicated.
- The fixed questions measured deterministic context size, not model answer accuracy, latency, or variance.
- No representative human completed an Obsidian task study.
- The corpus was one interdisciplinary topic with accessible full text; mature clinical, rapidly changing technical, and multilingual topics may behave differently.
- Forecasting accuracy and pooled meta-analytic reproducibility were specified but not evaluated.

Before calling the design universally best, run the full benchmark on at least three evidence ecologies and perform withheld-source update tests, human navigation tasks, citation-entailment adjudication, and a small reproducible meta-analysis.

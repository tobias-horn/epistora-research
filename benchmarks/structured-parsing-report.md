# Research Vault Structured Parsing Evaluation

Date: 2026-07-15
Scope: 80 OpenAlex XML papers, including 50 newly acquired cross-domain XML papers and 20 newly acquired PDF/XML pairs

## Recommendation

Use a hybrid pipeline, not a single parser:

1. Run the custom XML parser first for every available OpenAlex XML.
2. Run Docling when XML is missing, empty, truncated, or identity-mismatched.
3. Choose a canonical variant per paper and retain its checksums and diagnostics.
4. Flag ambiguous cases for inspection instead of silently merging variants.

This is stronger than choosing XML or PDF globally. XML is extremely fast and exposes useful document objects, but OpenAlex XML can be a wrapper, a truncated fragment, or even content for a different work. Docling is materially more complete on average and extracts images, but costs far more time, memory, disk, and model setup. The implemented skill makes XML the structural fast path and Docling the completeness/visual backstop.

## What was built

The benchmark prototype retained per-parser artifacts for measurement. The published skill uses the simpler storage contract requested for normal vault use:

```text
raw/works/W123/paper.pdf
raw/works/W123/fulltext.tei.xml
markdown/W123.md
state/parsing.json
```

Raw downloads and clean Markdown are separate. Parser versions, checksums, source-selection evidence, timing, and unresolved issues live centrally in `state/parsing.json` rather than in per-paper bundles. Docling images use placeholders, avoiding a third asset layer.

The custom XML parser:

- handles canonical TEI and HTML-wrapped/lowercase/flat OpenAlex TEI without relying on namespaces or capitalization;
- disables entity resolution and network access, retries malformed XML with an explicit recovery flag, and passed an external-entity regression test;
- preserves sections, blocks, citations, bibliography records, tables/cells, figure captions/coordinates, and raw formulas;
- never labels raw GROBID formula text as validated LaTeX;
- maps known publisher glyphs, marks unknown private-use glyphs as `⟦U+XXXX⟧`, and flags replacement characters;
- detects empty/short main text, missing structure, metadata-title disagreement, and probable content-identity mismatch;
- writes resumable parsing state and reuses Docling output only when the PDF checksum matches.

The Docling bootstrap pins Docling 2.111.0 and lxml 6.1.1 in `.research-vault/parser-env`, with model caches under `.research-vault/cache`. It prefers Python 3.12 through `uv` and falls back to a supported `venv`; nothing is installed into system Python. The official Docling installation guidance supports isolated `pip`/`uv` installation on macOS, Linux, and Windows, and Docling's document model supports Markdown/JSON export: [installation](https://docling-project.github.io/docling/getting_started/installation/), [document export](https://docling-project.github.io/docling/reference/docling_document/).

## Corpus and acquisition

The new 50-paper corpus contains five papers in each of ten strata: clinical medicine, molecular biology, ecology, climate science, physics, mathematics, computer science, engineering, economics, and psychology/neuroscience. All 50 retained papers had a downloaded XML; 20 had a validated downloaded PDF as well.

Acquisition exposed two important metadata/retrieval disagreements:

- `W3139510216`: OpenAlex advertised cached XML, but the content endpoint repeatedly returned HTTP 404. It was excluded and replaced by `W3012264837`.
- `W2146512944`: XML downloaded, but its only planned external OA PDF returned HTTP 403. It remained in the XML corpus and was replaced by `W2791581835` in the paired subset.

Availability flags therefore cannot be treated as successful acquisition. The skill records success only after file validation.

## XML structure and speed across 80 papers

All 80 XML files parsed successfully with the production parser. The 50 new files were all well-formed; the recovery path was separately tested with malformed fixtures. Across the original and new corpora, 30 were canonical TEI and 50 were HTML-wrapped/lowercase/flat OpenAlex XML.

| Metric | Result |
|---|---:|
| XML papers | 80 |
| Total parser time | 1.32 s |
| Mean per paper | 0.0165 s |
| Median per paper | 0.0112 s |
| P90 per paper | 0.0318 s |
| Sections | 1,557 |
| Blocks | 13,087 |
| Citations | 14,164 |
| Bibliography records | 7,668 |
| Figures | 756 |
| Tables | 263 |
| Raw formula objects | 2,868 |

The main cross-corpus warnings were expected and informative:

- 73/80 XMLs had figure records but needed PDF image assets;
- 52/80 had raw formula text requiring PDF or MathML/LaTeX validation;
- 50/80 used the wrapped/flat OpenAlex shape;
- 11/80 retained explicit unknown-glyph markers;
- 6/80 had XML/metadata title disagreement and 4 were probable content-identity mismatches;
- one new XML was empty, one was very short, and two lacked section structure.

This supports using XML as structured text, not as a self-sufficient visual/equation representation.

## Paired PDF/XML comparison

The paired corpus contains 20 papers and 559 PDF pages (median 21; range 6–94). Text fidelity was measured against native PDF text using multiset token precision/recall/F1. This metric is useful for coverage but is not semantic ground truth: native PDF reading order can itself be imperfect.

| Metric | Custom XML | Docling PDF |
|---|---:|---:|
| Mean precision | 0.9589 | 0.9597 |
| Mean recall | 0.7822 | 0.9029 |
| Mean F1 | 0.8476 | 0.9275 |
| Median F1 | 0.8781 | 0.9363 |
| Minimum F1 | 0.3014 | 0.6981 |
| Mean time/paper | 0.0180 s | 47.65 s |
| Median time/paper | 0.0141 s | 24.91 s |
| P90 time/paper | 0.0345 s | 163.89 s |
| Total time | 0.36 s | 953.03 s |

Docling delivered about 0.08 higher mean F1 and substantially higher recall. XML parsing was roughly 2,645× faster by total paired runtime. The high Docling tail came from long or figure-heavy papers: three took about 164–169 seconds. The published pipeline skips unchanged papers by comparing retained-source checksums.

After manual adjudication for the evaluation, 17/20 paired papers used XML as canonical and 3/20 used Docling PDF:

- `W3132661792`: PDF had materially better coverage;
- `W1967011851`: XML was a short/truncated book fragment;
- `W2007221293`: the 94-page PDF had much better coverage and figure representation.

Both formats produced zero broken internal links and zero replacement characters in the paired Markdown outputs. The benchmark exported images to assess Docling, but the published pipeline uses image placeholders to keep its output limited to one Markdown file per paper.

## Installation and operating cost

The clean local install resolved 101 packages. After first-run model warmup:

- parser environment: about 1.2 GB;
- isolated model/cache data: about 1.6 GB;
- combined local runtime footprint: about 2.8 GB;
- observed peak process memory during the 20-paper run: roughly 3–4.2 GB;
- first-run OCR/layout model initialization was included in the slow first paper.

This is acceptable for a deliberate research-vault ingestion step, but too heavy to install before parsing is requested. The skill therefore installs only when the parsing stage starts, isolates all files inside the vault, records resolved versions, and keeps the runtime out of Git.

## Manual edge-case audit

Deterministic parsing marked seven ambiguous works for inspection. Manual comparison of both retained variants:

- resolved `W3150595609` to XML after confirming that a misplaced XML title node did not indicate a body mismatch;
- resolved `W4323655724` to XML after confirming that the title node was only the genre fragment “A Position” while the abstract/body matched;
- resolved `W2007221293` to PDF because its 94-page Docling extraction was materially more complete;
- added an evidence-backed `Introduction` boundary to `W2766856748` without altering source prose;
- abstained on `W4382362038`, `W2014172170`, and `W1556059214` because the only available XML was empty or belonged to different content and no source supported reconstruction.

The audit was useful for validating the routing rules, but it is not part of the packaged runtime. The published pipeline simply records `review_required`; a user can inspect the retained evidence without maintaining a second automated editing protocol.

## Manual audit of the 50 new XMLs

Every new XML was manually reviewed through its root/body shape, title/authors/abstract, first section sequence, main-text length, references, tables/figures/formulas, parser warnings, and rendered Markdown opening. “XML+check” means usable text whose metadata, figures, formulas, or coverage should be verified against PDF. “Unresolved” means the available XML cannot safely represent the shortlisted work.

| ID | Domain | XML shape | Decision | Manual finding |
|---|---|---|---|---|
| W3012264837 | engineering | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2970563066 | molecular-biology | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W3150595609 | clinical-medicine | flat/wrapped | Review→XML | Misplaced XML title node; body identity confirmed against PDF. |
| W2773928770 | climate-science | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W3160537436 | economics | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2757803490 | physics | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2054275187 | molecular-biology | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2791581835 | molecular-biology | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2145808843 | climate-science | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2220861217 | climate-science | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2598701004 | ecology | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2462689321 | economics | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2328573691 | climate-science | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2130509491 | ecology | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W4323655724 | computer-science | canonical | Review→XML | Genre fragment in title node; body and abstract match the work. |
| W4382362038 | ecology | flat/wrapped | Unresolved | XML has no main text; obtain/use PDF. |
| W4224947065 | engineering | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2525748878 | mathematics | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2014172170 | mathematics | canonical | Unresolved | XML content identity does not match the shortlisted work. |
| W2057550180 | psychology-neuroscience | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2127125241 | clinical-medicine | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2103317434 | ecology | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2112796928 | computer-science | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W3010408268 | engineering | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2154433795 | ecology | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W3132661792 | molecular-biology | flat/wrapped | PDF | Docling PDF has materially better coverage than XML. |
| W3177318507 | computer-science | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2087987337 | economics | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2146512944 | molecular-biology | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2425644022 | clinical-medicine | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W3196819979 | engineering | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2155163959 | economics | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2032568924 | clinical-medicine | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W1963721320 | physics | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W1556059214 | mathematics | canonical | Unresolved | XML content identity does not match the shortlisted book. |
| W1967011851 | mathematics | flat/wrapped | PDF | XML is a short/truncated book fragment. |
| W2105824687 | psychology-neuroscience | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2982169647 | physics | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2784368966 | physics | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W3121385028 | economics | flat/wrapped | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2983762108 | engineering | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2160654481 | psychology-neuroscience | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2066525901 | psychology-neuroscience | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W1593442063 | clinical-medicine | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2970771982 | computer-science | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2147195941 | physics | canonical | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2261645655 | climate-science | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |
| W2162809807 | psychology-neuroscience | canonical | XML+check | Usable text; verify metadata, figures, formulas, or coverage with PDF. |
| W2007221293 | mathematics | canonical | Review→PDF | 94-page paper; Docling coverage and figures are materially better. |
| W2964110616 | computer-science | flat/wrapped | XML | Usable structured text; retain PDF for figures/formulas when present. |

## Final operational policy

For normal vault ingestion, run `python3 scripts/process_sources.py .`. It gains XML's speed and structure while invoking Docling for missing or unusable XML. Raw PDFs are still retained when XML is selected, so a user can inspect figures or formulas without paying the Docling cost for every paper.

Do not let an LLM silently fuse variants. The practical representation is one clean Markdown file per paper, retained raw inputs, centralized parser provenance, and explicit unresolved cases.

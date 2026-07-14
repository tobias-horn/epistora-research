# Research Vault Instructions

This vault separates evidence records from living synthesis. Use `templates/source-note.md` for source notes in `sources/` and `templates/wiki-entry.md` for wiki pages in `wiki/`. Keep Obsidian properties flat, quote wikilinks stored in YAML lists, and keep link properties synchronized with meaningful links in the note body.

## Initial seeding

Use `scripts/seed_openalex.py` to build the initial paper list. Let the agent interpret the topic, judge relevance, refine independent search strands, and choose anchors; use the script for OpenAlex requests, raw-response storage, exact search logging, candidate merging, version deduplication, and final queue validation. Aim for 80–100 unique papers unless the topic clearly warrants a different size. Do not download papers or create source notes during seeding. `state/candidates.json` is working state, `state/search-log.jsonl` is the search audit trail, and the finalized list belongs in `state/queue.json`.

## Source acquisition

After the queue is finalized, use `scripts/acquire_openalex.py` to plan and download complete work metadata, OpenAlex-cached PDFs and GROBID TEI XML, and direct external PDFs from OpenAlex Locations marked open access when no cached PDF exists. Review the plan before running paid content requests and always set an explicit maximum cost. Acquisition progress is resumable in `state/acquisition.json`; raw files belong under `raw/works/<OPENALEX_ID>/`. Do not scrape landing pages, bypass access controls, convert full text, or create notes during acquisition.

## Source notes

A source note represents one bibliographic work or report and records what that source contributes to the research topic. Ground it in the raw source, pair each important claim with its evidence or reasoning, scope, and locator, and keep the authors' conclusions distinct from the vault's assessment. Multiple reports of one underlying study may share a `study_id`. `openalex_topics` are imported classifications; `concepts` are curated links to wiki pages.

## Wiki pages

A wiki page is a living synthesis of one reusable idea, not a summary of papers. Search existing pages before creating one, integrate evidence across source notes, preserve material disagreements and uncertainty, and express connections as relational statements rather than loose link lists. Label novel hypotheses as speculative synthesis and explain their grounding. Use `kind` as a lightweight, extensible label such as `concept`, `relationship`, `method`, `claim`, `tension`, `design-principle`, or `open-question`; it is not a hierarchy. Adapt or remove optional template blocks rather than leaving empty scaffolding.

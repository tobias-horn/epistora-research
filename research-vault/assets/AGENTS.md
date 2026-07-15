# Research Vault Instructions

This vault separates evidence records from living synthesis. Use `templates/source-note.md` for source notes in `sources/` and `templates/wiki-entry.md` for wiki pages in `wiki/`. Keep Obsidian properties flat, quote wikilinks stored in YAML lists, and keep link properties synchronized with meaningful links in the note body.

## OpenAlex credential

Never ask the user to paste an API key into chat or place one in the vault. Seeding and acquisition automatically discover the user-level credential at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`. If it is missing, tell the user to run `python3 scripts/configure_openalex.py` in their own terminal; it prompts without echoing the key and stores it with user-only permissions. Resume after they confirm completion.

## Initial seeding

Use `scripts/seed_openalex.py` to build the initial shortlist. First test the user's wording against accessible literature, then record the field's core phrase and combine it with focused strand operators. Let the agent judge terminology, relevance, frontier and foundational balance, strands, and anchors; use the script for OpenAlex requests, PDF/XML availability filtering, logging, candidate merging, and version deduplication. Aim for 80–100 relevant papers, weighted toward frontier work. Do not download papers or create source notes during seeding. `state/candidates.json` is working state, `state/search-log.jsonl` is the audit trail, and selected records belong in `state/shortlist.json`.

## Source acquisition

After shortlisting, use `scripts/acquire_openalex.py` to plan and download complete metadata plus every available PDF and XML for each paper. Review the plan, set an explicit maximum cost, and use the acquisition `finalize` command to write `state/queue.json` only for papers with at least one validated PDF or downloaded XML. Retain non-empty XML returned by OpenAlex even when its TEI structure is imperfect. If fewer than 80 qualify, add targeted replacements instead of retaining metadata-only papers. Acquisition progress is resumable in `state/acquisition.json`; raw files belong under `raw/works/<OPENALEX_ID>/`. Do not scrape landing pages, bypass access controls, convert full text, or create notes during acquisition.

## Structured parsing

After acquisition is finalized, read `PARSING.md` and run `python3 scripts/process_sources.py .`. It creates an ignored vault-local environment and installs the pinned XML and Docling dependencies there; never install them into system Python. Keep raw XML/PDF immutable. Prefer usable XML and run Docling when XML is missing, broken, very short, structurally empty, or likely belongs to the wrong paper.

Keep the two content layers separate: original files under `raw/works/<OPENALEX_ID>/` and exactly one selected conversion per paper under `markdown/<OPENALEX_ID>.md`. Keep source selection, checksums, parser versions, warnings, and timing in `state/parsing.json`; do not create per-paper artifact bundles. Review every item marked `review_required` and every failure; never invent missing prose, equations, citations, table cells, or image content.

## Source notes

A source note represents one bibliographic work or report and records what that source contributes to the research topic. Ground it in the raw source, pair each important claim with its evidence or reasoning, scope, and locator, and keep the authors' conclusions distinct from the vault's assessment. Multiple reports of one underlying study may share a `study_id`. `openalex_topics` are imported classifications; `concepts` are curated links to wiki pages.

## Wiki pages

A wiki page is a living synthesis of one reusable idea, not a summary of papers. Search existing pages before creating one, integrate evidence across source notes, preserve material disagreements and uncertainty, and express connections as relational statements rather than loose link lists. Label novel hypotheses as speculative synthesis and explain their grounding. Use `kind` as a lightweight, extensible label such as `concept`, `relationship`, `method`, `claim`, `tension`, `design-principle`, or `open-question`; it is not a hierarchy. Adapt or remove optional template blocks rather than leaving empty scaffolding.

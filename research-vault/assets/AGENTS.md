# Research Vault Instructions

This vault separates evidence records from living synthesis. Use `templates/source-note.md` for source notes in `sources/` and `templates/wiki-entry.md` for wiki pages in `wiki/`. Keep Obsidian properties flat, quote wikilinks stored in YAML lists, and keep link properties synchronized with meaningful links in the note body.

## End-to-end execution

Act as the workflow orchestrator. The scripts perform deterministic operations; the agent frames the research, screens sources, judges stage completion, creates source notes, and synthesizes the wiki. When asked to build the complete vault, continue through discovery, acquisition, parsing, source-note extraction, batched wiki synthesis, validation, and final audit. Do not stop merely because one command succeeded.

Inspect the topic charter, active campaign, and existing artifacts first, then resume at the earliest incomplete stage. Preserve completed work and use the scripts' resumable behavior. Start a new campaign for a distinct discovery pass. Stop early only when the user limited the requested scope or progress genuinely requires user action.

## OpenAlex credential

Never ask the user to paste an API key into chat or place one in the vault. Seeding and acquisition automatically discover the user-level credential at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`. If it is missing, tell the user to run `python3 scripts/configure_openalex.py` in their own terminal; it prompts without echoing the key and stores it with user-only permissions. Resume after they confirm completion.

## Initial seeding

Use `scripts/seed_openalex.py` to build each campaign's candidate set and shortlist. Every vault starts with a `baseline` campaign; create or select another campaign only for a distinct discovery pass. First bound the topic in `state/topic.md`, test the user's wording, then record the campaign's core phrase and combine it with focused strand operators. Use `content-qualified` access for a bounded, immediately downloadable exploratory vault and disclose its access bias; use `comprehensive` discovery whenever evidential eligibility must not depend on access. Let the agent judge terminology, relevance, strands, anchors, source roles, counterevidence, concentration, and stopping; use the script for campaign records, requests, logging, candidate merging, access routes, and version deduplication. Do not combine citation count, venue, recency, relevance, and access into one quality score. Aim for 80–100 retained sources only when that adequately covers the declared topic facets. Do not download papers or create source notes during seeding. `state/candidates.json` holds campaign and candidate state, `state/search-log.jsonl` is the audit trail, `state/shortlist.json` is the current campaign's acquisition set, and `state/access-gaps.json` records selected evidence that lacks a current content route.

## Source acquisition

After shortlisting, use `scripts/acquire_openalex.py` to plan and download complete metadata plus every available PDF and XML for each paper. Review the plan, set an explicit maximum cost, and use the acquisition `finalize` command to write `state/queue.json` only for papers with at least one validated PDF or downloaded XML. Retain non-empty XML returned by OpenAlex even when its TEI structure is imperfect. If fewer than 80 qualify, add targeted replacements instead of retaining metadata-only papers. Acquisition progress is resumable in `state/acquisition.json`; raw files belong under `raw/works/<OPENALEX_ID>/`. Do not scrape landing pages, bypass access controls, convert full text, or create notes during acquisition.

## Structured parsing

After acquisition is finalized, read `PARSING.md` and run `python3 scripts/process_sources.py .`. It creates an ignored vault-local environment, reuses a compatible invoking Python when available, keeps parser dependencies, package/model caches, and any Python downloaded by `uv` under `.research-vault/`, and removes OpenAlex credentials from the parser subprocess environment; never install parser dependencies into system Python. Keep raw XML/PDF immutable. Prefer usable XML and run Docling when XML is missing, broken, very short, structurally empty, or likely belongs to the wrong paper.

Keep the two content layers separate: original files under `raw/works/<OPENALEX_ID>/` and exactly one selected conversion per paper under `markdown/<OPENALEX_ID>.md`. Keep source selection, checksums, parser versions, warnings, and timing in `state/parsing.json`; do not create per-paper artifact bundles. Review every item marked `review_required` and every failure; never invent missing prose, equations, citations, table cells, or image content.

## Source notes

A source note represents one bibliographic work or report and records what that source contributes to the topic. Compare successfully parsed OpenAlex IDs with source-note `openalex_id` properties and create one note for each missing report. Ground it in the parsed full text and verify consequential claims against the raw source. Pair each important claim with evidence or reasoning, scope, a resolvable locator, an evidence type, and a stable block ID such as `^c-w1234567890-01`. Add only a small set of useful topic-charter `facets`. Keep results, author interpretations, and the vault's assessment distinct. Multiple reports of one underlying study must share a `study_id`; never count reports as independent studies. `openalex_topics` are imported classifications, `concepts` are curated wiki links, and `facets` are broad retrieval labels from the topic charter.

## Wiki pages

Read `WIKI.md` completely before creating or updating source claims, wiki pages, or the derived wiki index.

A wiki page is a living synthesis of one reusable idea, not a paper summary. Markdown is canonical. `state/wiki-index.jsonl` is a rebuildable retrieval index, never a second editable knowledge base.

Work in coherent source batches rather than rebuilding after every ingest. Extract scoped source-claim blocks first, normalize terms and aliases, search existing page identities and propositions, then decide whether to update, create, merge, redirect, or leave a paper-specific idea in its source note. Normally create a mature empirical page only when at least two plausibly independent studies support its usefulness; named methods, foundational definitions, consequential open questions, and explicitly marked single-source results are valid exceptions.

Write proposition blocks before the narrative. Every proposition needs one independently updateable statement, a stable `^p-<wiki-id>-NN` block ID, a descriptive evidence pattern, reasoned assessment, scope, claim-level support/challenge/qualification links, and update triggers. Do not use citation count, venue, recency, or paper count as truth weights. Preserve null results, disagreement, dependence, and construct differences.

Use `kind` as a lightweight label such as `concept`, `relationship`, `method`, `tension`, `design-principle`, or `open-question`; it is not a hierarchy. Express connections with the controlled typed relations in `WIKI.md`, one justified edge per line. Body links provide Obsidian backlinks; do not maintain manual backlinks.

After each batch run `python3 scripts/build_wiki_index.py . --check`, repair every error, then run `python3 scripts/build_wiki_index.py .`. Check duplicates, orphans, access gaps, study/report double counting, unsupported propositions, missing counterevidence, and declared topic-coverage gaps before calling the batch complete. Then continue with the next parsed reports lacking source notes.

The validator checks existing notes; it does not prove coverage or completion. Before calling the full vault complete, reconcile the finalized queue with parsed Markdown, parsed OpenAlex IDs with source-note `openalex_id` values, and every completed source-note batch with a wiki synthesis pass. The absence of a wiki page for a paper-specific claim is not an error; failing to consider the batch against the existing wiki is incomplete work.

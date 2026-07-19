---
name: research-vault
description: Initialize, seed, acquire, parse, and synthesize an Obsidian-compatible scholarly research vault. Use when the user needs to create a research second brain, literature vault, source-note collection, or connected concept wiki; discover and screen relevant OpenAlex works; download every available PDF and XML under a cost cap; convert imperfect OpenAlex XML and scholarly PDFs into clean Markdown; or build claim-addressable wiki pages and a derived agent retrieval index with explicit provenance, disagreement, and uncertainty.
---

# Research Vault

Create a self-contained vault, build its scholarly source set, acquire and parse available reports, extract claim-addressable source notes, and synthesize a connected wiki with provenance. Use bundled scripts for filesystem, API, environment, parsing, validation, and index-building operations instead of reproducing them manually.

## Orchestrate the complete workflow

Act as the workflow orchestrator. The bundled scripts perform deterministic operations; they do not run the research process themselves. For a request to build a complete vault, continue through initialization, discovery and screening, shortlisting, acquisition, parsing, source-note creation, batched wiki synthesis, validation, and final audit. A successful command completes one operation, not the whole task.

Stop only when the requested scope is complete or progress requires user action, such as configuring a credential, approving acquisition cost, supplying inaccessible material, or resolving a consequential scope decision. If the user requests only one stage, perform only that stage and its necessary validation.

Before acting in an existing vault, inspect the topic charter, active discovery campaign, existing state, Markdown, source notes, wiki pages, and derived index. Resume at the earliest incomplete stage. Preserve completed work; do not reinitialize, reacquire, or force reparsing unless its state is invalid. Start a new campaign when the topic needs another discovery pass.

Use the existing artifacts as progress state. Move forward when:

- discovery has a bounded topic charter and a campaign with a screened source set, coverage assessment, and stopping rationale;
- shortlisting preserves both the accessible acquisition set and selected access gaps;
- acquisition has attempted the intended routes and finalized a non-empty retained queue;
- every queued work is parsed or explicitly unresolved and every review flag has been handled;
- every successfully parsed work has one source note with the matching OpenAlex ID and usable claim blocks;
- every completed source-note batch has been compared with the existing wiki and relevant pages have been created or updated;
- validation passes, the index is rebuilt, access gaps remain explicit, and known topic-coverage gaps are recorded.

## Initialize a vault

1. Obtain the research topic and destination path from the request or context. Ask only when either cannot be inferred safely.
2. Run:

   ```bash
   python3 <skill-directory>/scripts/init_vault.py <destination> --topic <topic>
   ```

3. Report the created path and Obsidian opening instruction printed by the initializer.

Never overwrite, merge into, or delete an existing destination. Do not bypass the initializer's validation or atomic installation.

## Configure OpenAlex access

Never ask a user to paste an API key into chat or include one in a command argument. The seeding and acquisition scripts automatically check the process environment, local `.env` files, and the user-level credential at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`.

If a script reports that the key is missing, pause and tell the user to run this command in their own terminal:

```bash
python3 <vault>/scripts/configure_openalex.py
```

The command prompts without echoing the key and stores it with user-only permissions. After the user confirms completion, resume the failed command. Use `--env-file` only when the user deliberately prefers a task-specific credential file.

## Seed the initial paper list

Read `references/seeding.md` completely before starting or resuming OpenAlex seeding.

Use agent judgment for topic interpretation, terminology reconnaissance, campaign definition, core-phrase choice, relevance screening, query refinement, anchor selection, source-set balance, and stopping decisions. Use `<vault>/scripts/seed_openalex.py` for every campaign record, OpenAlex request, raw response, search-log entry, candidate update, core-phrase record, screening decision, status calculation, version deduplication, and shortlist write.

Every vault starts with a `baseline` campaign. Create or select another campaign only for a distinct discovery pass. First test the user's wording and field terminology, then record the phrase actually used by the literature for that campaign. Build strand queries by combining that core phrase with one focused operator. Use `content-qualified` access for an immediately downloadable exploratory vault and explicitly disclose its access bias. Use `comprehensive` discovery when evidential eligibility must not depend on full-text access; selected access gaps then require lawful user-supplied files or explicit unresolved-gap reporting. Aim for roughly 80–100 retained sources only when that adequately covers the declared topic facets; systematic modes use protocol-defined sensitivity and stopping rules instead.

During this stage:

- do not download PDFs or full text;
- do not create source notes or wiki entries;
- do not interpret OpenAlex's raw match count as eligible literature;
- do not select solely by citation count, rank, or recency;
- do not collapse relevance, design, recency, citations, venue, and access into one quality score;
- preserve exact search rationale and exclusion reasons.

## Acquire the finalized sources

Read `references/acquisition.md` completely before starting or resuming acquisition.

Use `<vault>/scripts/acquire_openalex.py plan <vault>` to refresh the shortlist metadata and calculate PDF/XML routes. Review its cost estimate, then use `run` with an explicit `--max-cost-usd`; by default it attempts every available PDF and XML for each paper. Use `status` to check progress and `finalize` to write `state/queue.json` using only papers with at least one validated PDF or downloaded XML.

Prefer OpenAlex-cached content. When no cached PDF exists, allow only a direct PDF URL from an OpenAlex Location explicitly marked open access. Do not scrape landing pages, bypass access controls, add provider-specific extraction, convert text, run OCR, create source notes, or generate graphs during this stage. Never treat a recorded license or open-access flag as permission beyond the source's original terms.

Validate PDFs before retaining them. Decompress XML when needed and retain every non-empty response from the OpenAlex XML endpoint, including noncanonical or imperfect TEI.

## Parse papers into clean Markdown

Read `references/parsing.md` completely before installing parser dependencies, parsing papers, or evaluating parser output.

Run one command from the initialized vault:

```bash
python3 scripts/process_sources.py .
```

The command creates an ignored vault-local environment, installs the pinned parser dependencies there, reuses a compatible invoking Python when available, keeps package/model caches and any Python downloaded by `uv` inside `.research-vault/`, removes OpenAlex credentials from the parser subprocess environment, and processes `state/queue.json`. Never install Docling or XML dependencies into system Python.

Prefer usable XML because it is much faster and usually has better semantic structure. Invoke Docling when XML is absent, cannot be parsed, is very short, lacks section structure, or appears to contain the wrong paper. Preserve original downloads under `raw/` and write exactly one selected representation per paper to `markdown/<OPENALEX_ID>.md`. Keep checksums, parser versions, routing reasons, warnings, and timing in `state/parsing.json`, not beside the Markdown. Inspect every failed or review-recommended work; never invent missing text or call raw GROBID formula text validated LaTeX.

## Build source notes and the wiki

Read `references/wiki-building.md` completely before creating or updating source claims, wiki pages, or the derived claim index.

Compare successfully parsed OpenAlex IDs with the `openalex_id` properties in `sources/`. Select a manageable group without source notes, read each parsed paper, and consult the raw source for consequential or ambiguous passages. Create one source note per report with `templates/source-note.md`; use `study_id` to join reports from the same underlying study. Extract topic-relevant claims and give every claim its evidence or reasoning, scope, resolvable locator, evidence type, and stable block ID. Add a small set of topic-charter facets when they improve retrieval.

After a coherent batch—normally 10–20 completed source notes or one finished search strand—compare its claims with the existing wiki. Search identities, aliases, definitions, and propositions before deciding to update, create, merge, redirect, or leave a paper-specific idea in its source note. A wiki page represents one independently reusable idea. Draft scoped proposition blocks with claim-level evidence links before writing the readable narrative. Preserve counterevidence, construct differences, study dependence, boundary conditions, and uncertainty; do not weight truth by paper count, citations, venue, or recency.

Validate and rebuild the index after each batch, then continue with the next parsed works lacking source notes. Repeat until every successfully parsed report has a source note and every completed source-note batch has received a wiki synthesis pass.

Markdown remains canonical and human-editable in Obsidian. Validate it and build the agent-native, derived JSONL retrieval index with:

```bash
python3 scripts/build_wiki_index.py . --check
python3 scripts/build_wiki_index.py .
```

Repair every validation error. Agents may use `state/wiki-index.jsonl` to retrieve candidate propositions and claim blocks, but must open the Markdown for context before making consequential claims. Keep structured effect-size extractions and forecast records in separate analytical layers; narrative wiki pages are not substitutes for reproducible meta-analysis data or append-only forecasts.

The validator checks the notes that exist; it does not prove that all parsed reports have source notes, that the knowledge layer is non-empty, or that synthesis is complete. Before calling a full vault complete, reconcile the finalized queue with parsed Markdown, successfully parsed OpenAlex IDs with source-note `openalex_id` values, and completed source-note batches with wiki synthesis passes.

## Bundled resources

- `scripts/init_vault.py`: Validate, create, render, verify, and atomically install a vault.
- `scripts/configure_openalex.py`: Prompt locally and securely store a reusable user-level OpenAlex credential.
- `scripts/seed_openalex.py`: Define discovery campaigns, deterministically retrieve results, log searches and campaign core phrases, review, label, deduplicate, and write the current campaign's shortlist.
- `scripts/acquire_openalex.py`: Refresh shortlist metadata, download OpenAlex-cached content or a direct external OA PDF, and finalize the retained queue under an explicit cost cap.
- `scripts/process_sources.py`: Create the local parser runtime and run the complete parsing stage.
- `scripts/parse_sources.py`: Parse imperfect XML, run Docling PDF fallback, choose the clean Markdown variant, and record diagnostics.
- `scripts/build_wiki_index.py`: Validate stable source claims, wiki propositions, evidence links, source-property synchronization, and typed relations; build a derived JSONL retrieval index.
- `references/seeding.md`: Agent workflow, command examples, judgment boundaries, and stopping guidance.
- `references/acquisition.md`: Acquisition commands, storage contract, cost guardrail, and retry guidance.
- `references/parsing.md`: Parser behavior, output layout, validation, and recovery guidance.
- `references/wiki-building.md`: Epistemic design, page-creation rules, source/report/study distinctions, proposition workflow, uncertainty, typed relations, validation, and downstream meta-analysis/forecasting boundaries.
- `assets/`: Files copied into each vault. The initializer renders the topic charter and creates a baseline discovery campaign.

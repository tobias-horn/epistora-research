---
name: research-vault
description: Initialize, seed, and acquire sources for an Obsidian-compatible scientific research vault. Use when Codex needs to create a research second brain, literature vault, source-note collection, or connected concept wiki; discover, screen, deduplicate, and select an initial OpenAlex paper set; or download complete OpenAlex metadata, cached PDFs, GROBID TEI XML, and direct external open-access PDFs for a finalized source queue.
---

# Research Vault

Create a self-contained vault, build its initial scientific source list, and acquire available source files. Use bundled scripts for filesystem and API operations instead of reproducing them manually.

## Initialize a vault

1. Obtain the research topic and destination path from the request or context. Ask only when either cannot be inferred safely.
2. Run:

   ```bash
   python3 <skill-directory>/scripts/init_vault.py <destination> --topic <topic>
   ```

3. Report the created path and Obsidian opening instruction printed by the initializer.

Never overwrite, merge into, or delete an existing destination. Do not bypass the initializer's validation or atomic installation.

## Seed the initial paper list

Read `references/seeding.md` completely before starting or resuming OpenAlex seeding.

Use agent judgment for topic interpretation, relevance screening, vocabulary extraction, query refinement, anchor selection, source-set balance, and stopping decisions. Use `<vault>/scripts/seed_openalex.py` for every OpenAlex request, raw response, search-log entry, candidate update, screening-decision application, status calculation, version deduplication, and final queue write.

Aim for 80–100 unique papers, adjusting only when the topic warrants it and recording the reason. Complete reconnaissance, targeted strands, anchor expansion, frontier coverage, screening, and balancing before finalizing `state/queue.json`.

During this stage:

- do not download PDFs or full text;
- do not create source notes or wiki entries;
- do not interpret OpenAlex's raw match count as eligible literature;
- do not select solely by citation count, rank, abstract availability, or open-access status;
- preserve exact search rationale and exclusion reasons.

## Acquire the finalized sources

Read `references/acquisition.md` completely before starting or resuming acquisition.

Use `<vault>/scripts/acquire_openalex.py plan <vault>` to refresh and save complete metadata and calculate cached and external PDF/XML availability. Review its source routes and cost estimate, then use `run` with an explicit `--max-cost-usd`. Use `status` to check progress or resume failures.

Prefer OpenAlex-cached content. When no cached PDF exists, allow only a direct PDF URL from an OpenAlex Location explicitly marked open access. Do not scrape landing pages, bypass access controls, add provider-specific extraction, convert text, run OCR, create source notes, or generate graphs during this stage. Never treat a recorded license or open-access flag as permission beyond the source's original terms.

## Bundled resources

- `scripts/init_vault.py`: Validate, create, render, verify, and atomically install a vault.
- `scripts/seed_openalex.py`: Deterministically retrieve, log, merge, review, label, deduplicate, and finalize OpenAlex candidates.
- `scripts/acquire_openalex.py`: Refresh complete metadata and resumably download OpenAlex-cached content plus direct external OA PDFs under an explicit OpenAlex cost cap.
- `references/seeding.md`: Agent workflow, command examples, judgment boundaries, and stopping guidance.
- `references/acquisition.md`: Acquisition commands, storage contract, cost guardrail, and retry guidance.
- `assets/`: Files copied into each vault. The initializer renders the topic and creates empty seeding state.

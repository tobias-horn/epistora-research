---
name: research-vault
description: Initialize, seed, and acquire ingestible sources for an Obsidian-compatible scientific research vault. Use when Codex needs to create a research second brain, literature vault, source-note collection, or connected concept wiki; discover and screen relevant frontier and foundational OpenAlex papers that have PDF or XML content; or download those sources under a cost cap.
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

## Configure OpenAlex access

Never ask a user to paste an API key into chat or include one in a command argument. The seeding and acquisition scripts automatically check the process environment, local `.env` files, and the user-level credential at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`.

If a script reports that the key is missing, pause and tell the user to run this command in their own terminal:

```bash
python3 <vault>/scripts/configure_openalex.py
```

The command prompts without echoing the key and stores it with user-only permissions. After the user confirms completion, resume the failed command. Use `--env-file` only when the user deliberately prefers a task-specific credential file.

## Seed the initial paper list

Read `references/seeding.md` completely before starting or resuming OpenAlex seeding.

Use agent judgment for topic interpretation, terminology reconnaissance, core-phrase choice, relevance screening, query refinement, anchor selection, source-set balance, and stopping decisions. Use `<vault>/scripts/seed_openalex.py` for every OpenAlex request, raw response, search-log entry, candidate update, core-phrase record, screening decision, status calculation, version deduplication, and shortlist write.

First test the user's wording and field terminology, then record the phrase actually used by the literature. Build strand queries by combining that core phrase with one focused operator. Search only records for which OpenAlex reports a cached PDF, cached GROBID XML, or a direct open-access PDF URL. Aim for an 80–100-paper shortlist weighted toward frontier work with only the foundational background needed to understand it.

During this stage:

- do not download PDFs or full text;
- do not create source notes or wiki entries;
- do not interpret OpenAlex's raw match count as eligible literature;
- do not select solely by citation count, rank, or recency;
- preserve exact search rationale and exclusion reasons.

## Acquire the finalized sources

Read `references/acquisition.md` completely before starting or resuming acquisition.

Use `<vault>/scripts/acquire_openalex.py plan <vault>` to refresh the shortlist metadata and calculate PDF/XML routes. Review its cost estimate, then use `run` with an explicit `--max-cost-usd`; by default it attempts every available PDF and XML for each paper. Use `status` to check progress and `finalize` to write `state/queue.json` using only papers with at least one validated PDF or downloaded XML.

Prefer OpenAlex-cached content. When no cached PDF exists, allow only a direct PDF URL from an OpenAlex Location explicitly marked open access. Do not scrape landing pages, bypass access controls, add provider-specific extraction, convert text, run OCR, create source notes, or generate graphs during this stage. Never treat a recorded license or open-access flag as permission beyond the source's original terms.

Validate PDFs before retaining them. Decompress XML when needed and retain every non-empty response from the OpenAlex XML endpoint, including noncanonical or imperfect TEI.

## Bundled resources

- `scripts/init_vault.py`: Validate, create, render, verify, and atomically install a vault.
- `scripts/configure_openalex.py`: Prompt locally and securely store a reusable user-level OpenAlex credential.
- `scripts/seed_openalex.py`: Deterministically retrieve content-qualified results, log searches and the core phrase, review, label, deduplicate, and write the shortlist.
- `scripts/acquire_openalex.py`: Refresh shortlist metadata, download OpenAlex-cached content or a direct external OA PDF, and finalize the retained queue under an explicit cost cap.
- `references/seeding.md`: Agent workflow, command examples, judgment boundaries, and stopping guidance.
- `references/acquisition.md`: Acquisition commands, storage contract, cost guardrail, and retry guidance.
- `assets/`: Files copied into each vault. The initializer renders the topic and creates empty seeding state.

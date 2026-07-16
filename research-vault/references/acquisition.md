# Source acquisition

Acquire `state/shortlist.json`, then write `state/queue.json` using only papers with a validated PDF or downloaded XML. Do not convert text, scrape landing pages, bypass access controls, or create notes during this stage.

The script checks `OPEN_ALEX`, `OPENALEX_API_KEY`, local `.env` files, and `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`. Never ask for or put a key in chat, a command argument, a log, or the vault. If missing, tell the user to run `python3 <vault>/scripts/configure_openalex.py` in their own terminal and resume after confirmation.

## 1. Plan

Refresh complete metadata and calculate cached and external routes:

```bash
python3 <vault>/scripts/acquire_openalex.py plan <vault>
```

Planning makes metadata requests but no paid content requests. It prefers OpenAlex-cached PDF content, otherwise a direct PDF URL from an OpenAlex Location marked open access; cached XML is planned independently.

## 2. Download every available format

```bash
python3 <vault>/scripts/acquire_openalex.py run <vault> \
  --formats pdf,xml \
  --max-cost-usd 2.00
```

The default is also `--formats pdf,xml`. The command attempts every available PDF and XML route for each shortlisted paper and skips unavailable or already valid files. OpenAlex-cached files currently cost $0.01 per file, so a paper with both cached formats can cost $0.02. External direct PDFs do not count toward the OpenAlex cap. If the plan exceeds the chosen ceiling, increase the explicit cap or reduce the shortlist before running.

Files are stored under:

```text
raw/works/W123/
├── metadata.openalex.json
├── paper.pdf
└── fulltext.tei.xml
```

PDFs are validated before retention. XML is decompressed when needed and retained whenever OpenAlex returns a non-empty file, even if its TEI structure is noncanonical or imperfect. Downloads are checksummed, written atomically, and recorded after each attempt in `state/acquisition.json`. Existing files are skipped. A failed file does not stop the remaining downloads; rerun under a new explicit cost cap when appropriate.

External retrieval is deliberately limited to the first direct `http` or `https` PDF URL that OpenAlex marks open access. If it returns HTML, blocks automation, or exposes only a landing page, leave that paper unqualified. Do not add provider-specific scraping.

## 3. Finalize the retained queue

Check progress:

```bash
python3 <vault>/scripts/acquire_openalex.py status <vault>
```

Finalize when 80–100 shortlisted papers have at least one retained artifact:

```bash
python3 <vault>/scripts/acquire_openalex.py finalize <vault>
```

If fewer than 80 qualify, return to seeding, add targeted replacements, rebuild the shortlist, and refresh the acquisition plan. Do not retain metadata-only papers in the final queue. Use `--allow-outside-target` only when the topic genuinely has fewer accessible relevant sources and record the reason in `state/research.md`.

Downloaded files retain their original copyright. License and open-access fields are provenance, not additional permission.

## Handoff

After the intended routes have been attempted, inspect failures and access gaps and finalize the retained queue. Unless the user requested acquisition only, continue to parsing when the queue is non-empty and remaining acquisition failures are understood.

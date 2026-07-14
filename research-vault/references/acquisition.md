# Source acquisition

Acquire content only after `state/queue.json` has been finalized. Store complete OpenAlex metadata and prefer OpenAlex-cached PDFs and GROBID TEI XML. When OpenAlex has no cached PDF, use a direct PDF URL from an OpenAlex Location explicitly marked open access. Do not convert text, scrape landing pages, bypass access controls, or create notes.

The script reads `OPEN_ALEX` or `OPENALEX_API_KEY` from the environment. It also checks `.env` in the current directory, vault, and vault parent; use `--env-file` when needed. Never put a key in a command, log, or vault file.

## 1. Plan

Refresh complete metadata, save it under `raw/works/<OPENALEX_ID>/`, and calculate cached and external PDF/XML availability:

```bash
python3 <vault>/scripts/acquire_openalex.py plan <vault>
```

Planning makes metadata requests but no paid content requests. For PDFs, it chooses an OpenAlex-cached file first; otherwise it checks `best_oa_location.pdf_url` and then other open-access `locations[].pdf_url` values. Review the reported source routes and estimated cost before continuing.

## 2. Download

Download both directly available formats with an explicit maximum cost:

```bash
python3 <vault>/scripts/acquire_openalex.py run <vault> \
  --formats pdf,xml \
  --max-cost-usd 2.00
```

OpenAlex currently prices each cached content file separately. Direct external open-access PDF requests are not included in that OpenAlex cost. The command refuses to start if its paid OpenAlex requests exceed the supplied cap. To split downloads across allowance periods, run one format at a time with `--formats pdf` or `--formats xml`.

Each paper is stored as:

```text
raw/works/W123/
├── metadata.openalex.json
├── paper.pdf                 # OpenAlex cache or an external OA location
└── fulltext.tei.xml          # when OpenAlex has a GROBID parse
```

Downloads are validated, checksummed, written atomically, and recorded after every attempt in `state/acquisition.json`. The state records whether a file came from the OpenAlex content API or an external OA location without copying temporary external URLs out of the saved metadata. Valid existing files are skipped. A failed file does not stop the remaining requests; rerun the command to retry it under a new cost cap.

External fallback is deliberately limited to direct `http` or `https` PDF URLs that OpenAlex marks open access. If a host returns HTML, blocks automated access, or exposes only a landing page, record the failure and leave the paper unavailable; do not add provider-specific scraping.

## 3. Check status

```bash
python3 <vault>/scripts/acquire_openalex.py status <vault>
```

Run `plan` again if the finalized queue changes or when current availability needs to be refreshed. Downloaded PDFs retain their original copyright; a recorded license or open-access flag is provenance information, not a grant of additional rights.

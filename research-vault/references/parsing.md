# Source processing

Process papers only after `acquire_openalex.py finalize` has written a non-empty `state/queue.json`.

## Run

From the initialized vault, run:

```bash
python3 scripts/process_sources.py .
```

This creates `.research-vault/parser-env`, installs the tested Docling and lxml versions, isolates model caches under `.research-vault/cache`, and processes the finalized queue. The local runtime is ignored by Git. The first PDF can take longer because Docling downloads its models. Use `--force` only to rebuild unchanged Markdown.

## Storage contract

Keep downloaded and converted content separate:

```text
raw/works/W123/paper.pdf
raw/works/W123/fulltext.tei.xml
markdown/W123.md
state/parsing.json
state/parsing-summary.json
```

`raw/` contains immutable originals. `markdown/` contains exactly one selected Markdown file per retained work, named by OpenAlex ID. Do not create per-paper output bundles or place diagnostics beside Markdown. Keep checksums, parser versions, routing, quality warnings, and timing in `state/parsing.json`.

## Format choice

- Parse XML first when it exists.
- Keep XML when it has usable main text and section structure.
- Run Docling when only a PDF exists or XML is unparseable, very short, structurally empty, or likely contains a different work.
- If one parser fails, keep using the other format when possible.
- Render Docling images as Markdown placeholders so conversion does not create a separate asset bundle.

The XML parser accepts canonical TEI and OpenAlex's wrapped, lowercase, or flat variants. It disables entity and network resolution, flags recovery mode, keeps table cells and reference anchors, marks unknown private-use glyphs, and records raw formulas without describing them as validated LaTeX.

## Validate

Inspect `state/parsing-summary.json` and `state/parsing.json`. Investigate every failed work and every work with `review_required: true`. Sample Markdown across publishers, especially tables, formulas, headings, citations, and figure captions. Do not silently repair uncertain text or merge XML and PDF into an untraceable third version.

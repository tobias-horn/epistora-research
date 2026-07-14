# Epistora Research Vault

A Codex skill for building an Obsidian-compatible research vault from scientific literature.

The skill initializes a vault, develops and logs an iterative OpenAlex search strategy, screens and selects roughly 80–100 relevant works, and downloads available metadata, PDFs, and GROBID TEI XML. When OpenAlex has no cached PDF, it can use direct external PDF locations marked open access by OpenAlex.

## Requirements

- Codex with skill support
- Python 3.10 or newer
- An OpenAlex API key in `OPEN_ALEX` or `OPENALEX_API_KEY`

## Install

Copy or symlink `research-vault/` into your user skill directory:

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/epistora-research/research-vault ~/.agents/skills/research-vault
```

Restart Codex if the skill does not appear automatically.

## Use

```text
Use $research-vault to create a research vault at ~/research/my-topic about
"my research topic". Seed 80–100 sources and acquire the available files.
Allow up to $2.00 of OpenAlex content requests.
```

The current workflow stops after raw source acquisition. Source-note generation, wiki synthesis, and graph projections are not implemented yet.

Downloaded papers retain their original copyright and should not be redistributed with this skill.

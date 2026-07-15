# Epistora Research Vault

A Codex skill for building an Obsidian-compatible research vault from scientific literature.

The skill initializes a vault, tests the user's terminology, builds focused OpenAlex searches, and screens roughly 80–100 relevant works. It downloads every available PDF and XML, excludes metadata-only records, and converts the retained sources into clean Markdown. A tolerant XML parser handles imperfect OpenAlex TEI; Docling is used when XML is missing or unusable.

## Requirements

- Codex with skill support
- Python 3.10–3.14, or `uv` (recommended)
- An OpenAlex API key

## Install

Copy or symlink `research-vault/` into your user skill directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s /absolute/path/to/epistora-research/research-vault \
  "${CODEX_HOME:-$HOME/.codex}/skills/research-vault"
```

Restart Codex if the skill does not appear automatically.

## Configure OpenAlex

Store the API key once with the included secure prompt:

```bash
python3 research-vault/scripts/configure_openalex.py
```

The prompt does not echo the key. It stores the credential with `0600` permissions at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`, where future research-vault tasks discover it automatically. Do not paste API keys into Codex chat or include them directly in shell commands.

## Use

```text
Use $research-vault to create a research vault at ~/research/my-topic about
"my research topic". Seed 80–100 sources, acquire every available PDF and XML,
and parse the retained papers into clean Markdown. Allow up to $2.00 of
OpenAlex content requests.
```

After acquisition is finalized, parsing can also be run directly from inside the generated vault:

```bash
python3 scripts/process_sources.py .
```

The command creates an ignored vault-local environment, installs pinned parser dependencies there, and writes each selected paper to `markdown/<OPENALEX_ID>.md`. Original PDF/XML files remain separate under `raw/`. See [the parser evaluation](benchmarks/structured-parsing-report.md) for the benchmark behind the XML-first, Docling-fallback choice.

Source-note generation, wiki synthesis, and graph projections are not implemented yet.

Downloaded papers retain their original copyright and should not be redistributed with this skill.

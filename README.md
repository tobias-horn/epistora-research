# Epistora Research Vault

A Codex skill for building an Obsidian-compatible research vault from scientific literature.

The skill initializes a vault, tests the user's terminology, records the field's core phrase, and builds focused OpenAlex search strands. It screens roughly 80–100 relevant works with PDF or XML availability, downloads every available PDF and XML, and excludes metadata-only records from the final queue. PDFs are validated; non-empty XML is retained even when its TEI structure is imperfect. The set is weighted toward frontier research while retaining necessary accessible foundations.

## Requirements

- Codex with skill support
- Python 3.10 or newer
- An OpenAlex API key

## Install

Copy or symlink `research-vault/` into your user skill directory:

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/epistora-research/research-vault ~/.agents/skills/research-vault
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
"my research topic". Seed 80–100 sources and acquire every available PDF and XML.
Allow up to $2.00 of OpenAlex content requests.
```

The current workflow stops after raw source acquisition. Source-note generation, wiki synthesis, and graph projections are not implemented yet.

Downloaded papers retain their original copyright and should not be redistributed with this skill.

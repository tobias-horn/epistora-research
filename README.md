# Epistora Research Vault

An agent skill for building an Obsidian-compatible research vault from scholarly literature. Runs in both Codex and Claude Code.

The skill initializes a vault, tests the user's terminology, builds focused OpenAlex searches, and screens roughly 80–100 relevant works. It downloads every available PDF and XML, excludes metadata-only records, and converts the retained sources into clean Markdown. A tolerant XML parser handles imperfect OpenAlex TEI; Docling is used when XML is missing or unusable.

## Requirements

- Codex or Claude Code, with skill support
- Python 3.10–3.14, or `uv` (recommended)
- An OpenAlex API key

## Install

Copy or symlink `research-vault/` into your agent's user skill directory.

**Codex:**

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s /absolute/path/to/epistora-research/research-vault \
  "${CODEX_HOME:-$HOME/.codex}/skills/research-vault"
```

**Claude Code:**

```bash
mkdir -p ~/.claude/skills
ln -s /absolute/path/to/epistora-research/research-vault \
  ~/.claude/skills/research-vault
```

Use `.claude/skills/` inside a project instead of `~/.claude/skills/` to scope the skill to that project. Restart the agent if the skill does not appear automatically.

## Configure OpenAlex

Store the API key once with the included secure prompt:

```bash
python3 research-vault/scripts/configure_openalex.py
```

The prompt does not echo the key. It stores the credential with `0600` permissions at `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`, where future research-vault tasks discover it automatically. Do not paste API keys into agent chat or include them directly in shell commands.

## Use

Describe the task in chat. Codex addresses the skill as `$research-vault`; Claude Code triggers it from the description or an explicit `/research-vault`.

```text
Use $research-vault to create a research vault at ~/research/my-topic about
"my research topic". Seed 80–100 sources, acquire every available PDF and XML,
and parse the retained papers into clean Markdown. Allow up to $2.00 of
OpenAlex content requests.
```

The same request works in Claude Code with the `$research-vault` reference dropped.

Each vault starts with a minimal `state/topic.md` charter and an active `baseline` discovery campaign. Later discovery passes can use a small named campaign while the accumulated source notes and wiki remain shared:

```bash
python3 scripts/seed_openalex.py campaign . \
  --id recent-methods \
  --name "Recent methods" \
  --purpose "Extend method coverage after the baseline search"
```

After acquisition is finalized, parsing can also be run directly from inside the generated vault:

```bash
python3 scripts/process_sources.py .
```

The command creates an ignored vault-local environment, installs pinned parser dependencies there, and writes each selected paper to `markdown/<OPENALEX_ID>.md`. It reuses a compatible invoking Python when possible; package caches, Docling models, and any Python runtime downloaded by `uv` remain under the vault's `.research-vault/` directory. OpenAlex credentials are not passed to the parser subprocess. Original PDF/XML files remain separate under `raw/`. See [the parser evaluation](benchmarks/structured-parsing-report.md) for the benchmark behind the XML-first, Docling-fallback choice.

The agent performs source-note generation and wiki synthesis from the parsed papers using the bundled templates and validation rules. `scripts/build_wiki_index.py` validates claim-level provenance and builds the derived retrieval index; Obsidian renders backlinks and graph views from the Markdown links.

Downloaded papers retain their original copyright and should not be redistributed with this skill.

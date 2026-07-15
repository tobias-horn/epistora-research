# Initial OpenAlex seeding

Build a relevant, content-qualified shortlist before downloading papers. Aim for 80–100 unique papers, weighted toward the research frontier with only the foundational work needed to understand it.

Use agent judgment for topic interpretation, terminology, relevance, strands, anchors, balance, and stopping. Use `scripts/seed_openalex.py` for OpenAlex requests, availability filtering, logging, candidate state, decisions, version grouping, and shortlist creation.

Never ask for or put an API key in chat, a command argument, a log, or the vault. The script checks `OPEN_ALEX`, `OPENALEX_API_KEY`, local `.env` files, and `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`. If missing, tell the user to run `python3 <vault>/scripts/configure_openalex.py` in their own terminal and resume after confirmation.

## 1. Frame the topic

Update `state/research.md` with the intended question, breadth, important mechanisms or outcomes, counterevidence worth seeking, and justified exclusions. Treat this as provisional search guidance.

## 2. Discover the field's terminology

Do not assume the user's wording is the literature's main term. Run approximately three reconnaissance queries of 20 results per availability lane:

1. the user's wording;
2. a plausible technical or historical synonym;
3. a named mechanism, method, population, or application associated with the topic.

```bash
python3 <vault>/scripts/seed_openalex.py search <vault> \
  --stage terminology \
  --strand user-wording \
  --rationale "Test the user's wording and identify the field's terminology" \
  --query "partial cellular reprogramming rejuvenation aging"
```

Every search runs three deterministic lanes and merges them: cached PDF, cached GROBID XML, and open-access records with a direct PDF URL. Landing-page-only and metadata-only records are not added as candidates.

Review the relevant titles, abstracts, keywords, and recurring phrases. Choose a core phrase that is specific enough for precision but common enough to retrieve the field. Record why it was chosen:

```bash
python3 <vault>/scripts/seed_openalex.py set-core-phrase <vault> \
  --phrase "partial cellular reprogramming" \
  --rationale "This is the recurring term used by directly relevant recent and review papers."
```

Also record the phrase in `state/research.md`.

## 3. Build focused strands

Construct 3–6 strands with one purpose each. Pass only the strand operator; the script combines it with the recorded core phrase:

```bash
python3 <vault>/scripts/seed_openalex.py search <vault> \
  --stage frontier \
  --strand recent-mechanisms \
  --rationale "Find recent mechanism work" \
  --from-year 2022 \
  --operator '"cell identity" OR rejuvenation OR epigenetic'
```

This produces a query of the form:

```text
"<core phrase>" AND (<strand operator>)
```

The script also requires the core phrase in the title or abstract for strand searches, reducing papers that only mention the topic somewhere in their full text.

Start frontier coverage with roughly the last five years and adjust when the field moves unusually quickly or slowly. Keep relevance ranking for normal searches. Use newest-first only for a tightly scoped recent strand.

Retain a strand when it finds at least five new core or supporting papers or fills a clear gap. Reformulate or retire it when fewer than roughly 20 percent of reviewed results are relevant or it adds almost no unique work.

## 4. Screen candidates

Request manageable batches:

```bash
python3 <vault>/scripts/seed_openalex.py review <vault> --limit 20 --format json
```

Use these labels:

- `core`: directly answers or defines the topic;
- `supporting`: supplies a necessary mechanism, method, comparison, or context;
- `contextual`: potentially useful but not necessary initially;
- `exclude`: outside scope;
- `uncertain`: relevance cannot yet be established.

Select only `core` and `supporting` records for the shortlist; keep contextual records in candidate state only.

Apply decisions through a JSON file:

```json
{
  "decisions": [
    {
      "openalex_id": "https://openalex.org/W123",
      "label": "core",
      "roles": ["frontier", "primary-study", "mechanism"],
      "reason": "Directly tests the target mechanism in the intended system.",
      "terms": ["maturation-phase transient reprogramming"],
      "selected": true
    }
  ]
}
```

```bash
python3 <vault>/scripts/seed_openalex.py apply-decisions <vault> <decisions.json>
```

## 5. Expand a small anchor set

Choose 2–4 relevant, content-qualified anchors: a recent review, an influential foundation, a recent primary study, and critical or contradictory evidence when available.

```bash
python3 <vault>/scripts/seed_openalex.py expand-anchor <vault> \
  --id W4392348348 \
  --strand review-citation-neighborhood \
  --rationale "Recover accessible landmarks and recent citing work" \
  --from-year 2022 \
  --recent-citing 20
```

The script retains only references and citing works with a PDF or XML route. An inaccessible anchor may guide discovery but cannot enter the shortlist.

## 6. Balance and shortlist

For a typical vault, use roughly 55–65 percent frontier work, 20–30 percent current core or connective evidence, and 10–20 percent foundations. Adapt this to the topic rather than forcing quotas. Prefer an accessible preprint or working-paper version when a published version is unavailable.

Stop when 80–100 relevant papers cover the intended strands and two successive refinements produce little unique relevant work. Do not pad the set. Check progress with:

```bash
python3 <vault>/scripts/seed_openalex.py status <vault>
```

Then write the acquisition shortlist:

```bash
python3 <vault>/scripts/seed_openalex.py shortlist <vault>
```

This writes `state/shortlist.json` and clears `state/queue.json`. The final queue is created only after acquisition validates at least one PDF or XML per paper.

## Audit expectations

Preserve exact queries, availability lanes, filters, sort, rationale, timestamps, result counts, candidate IDs, the chosen core phrase, screening decisions, version relationships, coverage, and stopping rationale. Use `state/search-log.jsonl` for the machine trail and `state/research.md` for the concise human-readable strategy.

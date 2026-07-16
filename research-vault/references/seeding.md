# Initial OpenAlex seeding

Build an auditable candidate universe before downloading papers. For an exploratory vault, aim for roughly 80–100 retained full-text sources when that is enough to cover the competency questions. For systematic or living evidence work, protocol-defined eligibility and sensitivity take precedence over a source-count target.

Use agent judgment for topic interpretation, terminology, relevance, strands, anchors, balance, and stopping. Use `scripts/seed_openalex.py` for OpenAlex requests, availability filtering, logging, candidate state, decisions, version grouping, and shortlist creation.

Never ask for or put an API key in chat, a command argument, a log, or the vault. The script checks `OPEN_ALEX`, `OPENALEX_API_KEY`, local `.env` files, and `${XDG_CONFIG_HOME:-~/.config}/research-vault/.env`. If missing, tell the user to run `python3 <vault>/scripts/configure_openalex.py` in their own terminal and resume after confirmation.

## 1. Frame the topic

Update `state/research.md` with the evidence mode, intended question, competency questions, breadth, important mechanisms or outcomes, counterevidence worth seeking, and justified exclusions. Treat this as provisional search guidance.

Choose the access policy explicitly:

- `content-qualified` retrieves only records with an OpenAlex-cached PDF/XML or a direct open-access PDF. Use it for a bounded exploratory vault that must be immediately downloadable, and disclose the resulting access bias.
- `comprehensive` discovers records regardless of current full-text access. Use it when evidential eligibility must not depend on access, including systematic-review-like work. Selected inaccessible records are written to `state/access-gaps.json` at shortlisting and require a lawful user-supplied copy or an explicitly documented unresolved gap.

Do not combine relevance, citation count, venue, recency, and access into one quality score. Use relevance for screening and treat the remaining fields as separate constraints or diagnostics. Venue and citations may help locate landmarks but are not evidence-quality labels.

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
  --query "partial cellular reprogramming rejuvenation aging" \
  --access-policy content-qualified
```

With `content-qualified`, every search runs three deterministic lanes and merges them: cached PDF, cached GROBID XML, and open-access records with a direct PDF URL. With `comprehensive`, one unqualified discovery lane is used and access is recorded as metadata rather than an eligibility rule.

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

Retain a strand when it finds new relevant studies or fills a competency-question, design, population, temporal, or counterevidence gap. Reformulate or retire it when screened precision is persistently poor. Stop repeating near-equivalent queries when marginal relevant yield is low and pairwise overlap is high; log both the new-study yield and the reason the remaining gaps are acceptable.

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
  --recent-citing 20 \
  --access-policy content-qualified
```

The script retains only references and citing works with a PDF or XML route. An inaccessible anchor may guide discovery but cannot enter the shortlist.

## 6. Balance and shortlist

Define minimum coverage constraints from the research frame rather than using a universal weighted score or fixed literature quotas. Inspect at least:

- every competency question and search strand;
- primary studies, syntheses, methods, foundations, frontier work, and critical/counterevidence where relevant;
- study-design, population, setting, outcome, and disciplinary diversity;
- author, institution, venue, and topic concentration;
- temporal coverage and terminology drift;
- duplicate versions, reports of one study, shared datasets, and overlapping samples;
- accessible versus selected-but-inaccessible evidence.

Adapt the balance to the evidence ecology. A mature intervention question may need older primary trials and risk-of-bias material; a fast technical topic may need recent preprints; a conceptual question may rely more on foundational and critical work. Prefer a published version when available, but retain an accessible preprint or working-paper version when it is the only lawful full text and record the version relationship.

For exploratory work, stop when the competency questions and declared constraints are covered and two successive refinements produce little unique relevant work. Do not pad the set to reach 80–100. For systematic work, use a protocol-defined search and screening stopping rule; search saturation alone does not establish recall. Check progress with:

```bash
python3 <vault>/scripts/seed_openalex.py status <vault>
```

Then write the acquisition shortlist:

```bash
python3 <vault>/scripts/seed_openalex.py shortlist <vault>
```

This writes `state/shortlist.json` and clears `state/queue.json`. The final queue is created only after acquisition validates at least one PDF or XML per paper.

The command also writes `state/access-gaps.json`. In comprehensive mode, this file is part of the evidence audit: inaccessible studies remain relevant to the assessment even though they cannot enter the parsing queue until a lawful full text is supplied.

## Audit expectations

Preserve exact queries, availability lanes, filters, sort, rationale, timestamps, result counts, candidate IDs, the chosen core phrase, screening decisions, version relationships, coverage, and stopping rationale. Use `state/search-log.jsonl` for the machine trail and `state/research.md` for the concise human-readable strategy.

## Handoff

After screening, coverage assessment, and a justified stopping decision, write the shortlist. Unless the user requested discovery only, continue to acquisition; candidate retrieval by itself does not complete a vault build.

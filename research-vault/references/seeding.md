# Initial OpenAlex seeding

Build a screened metadata list before downloading or ingesting any paper. Aim for 80–100 unique papers by default, but prefer a defensible smaller or larger set when the literature genuinely warrants it.

## Division of responsibility

Use agent judgment for:

- interpreting the user's topic and intended breadth;
- deciding what is core, supporting, contextual, or irrelevant;
- extracting terminology from relevant records;
- defining and revising search strands;
- selecting anchors and balancing the final set;
- deciding when marginal discovery is low enough to stop.

Use `scripts/seed_openalex.py` for:

- authenticated OpenAlex requests;
- stable filters and request retries;
- sanitized raw-response storage;
- append-only search logging;
- candidate metadata merging and provenance;
- screening-decision validation;
- version grouping and final queue creation.

Never put an API key in a command, log, or vault file. The script reads `OPEN_ALEX` or `OPENALEX_API_KEY` from the environment. It also checks `.env` in the current directory, vault, and vault parent; use `--env-file` when needed.

## 1. Frame the topic

Update `state/research.md` with a short interpretation of:

- central phenomenon or intervention;
- intended breadth;
- relevant populations, systems, applications, or contexts;
- outcomes and mechanisms of interest;
- risks, failure modes, disagreement, or counterevidence worth seeking;
- justified exclusions.

Treat these as provisional search guidance, not a permanent taxonomy.

## 2. Run reconnaissance

Start with approximately four searches of 20 relevance-ranked records each:

1. the user's natural-language formulation;
2. a quoted core phrase;
3. a plausible synonym or historical term;
4. an abbreviation, named method, mechanism, or application.

Add another search only when the topic clearly has competing terminology. Keep relevance ranking; do not sort broad searches newest-first.

```bash
python3 <vault>/scripts/seed_openalex.py search <vault> \
  --stage reconnaissance \
  --strand natural-language \
  --rationale "Test the user's formulation and discover field vocabulary" \
  --query "partial cellular reprogramming rejuvenation aging"
```

The script always excludes retracted records and limits results to articles, books, book chapters, preprints, reports, reviews, and dissertations. Do not initially require open access, a PDF, or an abstract.

## 3. Review and apply decisions

Request a manageable batch:

```bash
python3 <vault>/scripts/seed_openalex.py review <vault> --limit 20 --format json
```

Read titles and abstracts. Use these labels:

- `core`: directly answers or defines the research topic;
- `supporting`: supplies a necessary mechanism, method, comparison, or context;
- `contextual`: potentially useful but not necessary for the initial seed;
- `exclude`: clearly outside scope;
- `uncertain`: insufficient metadata or unresolved relevance;
- `unreviewed`: no judgment yet.

Extract terminology only from core and supporting records. Keep terms short and retain them on the record that supplied them.

Write a temporary decisions file:

```json
{
  "decisions": [
    {
      "openalex_id": "https://openalex.org/W123",
      "label": "core",
      "roles": ["primary-study", "mechanism"],
      "reason": "Directly tests the intervention and measures the target outcome.",
      "terms": ["maturation-phase transient reprogramming"],
      "selected": true
    },
    {
      "openalex_id": "https://openalex.org/W456",
      "label": "exclude",
      "reason": "Uses the same phrase for an unrelated biological process.",
      "selected": false
    }
  ]
}
```

Apply it deterministically:

```bash
python3 <vault>/scripts/seed_openalex.py apply-decisions <vault> <decisions.json>
```

Roles are agent-defined kebab-case descriptors. Useful examples include `foundational`, `review`, `primary-study`, `method`, `mechanism`, `safety`, `negative-result`, `contradictory`, and `frontier`.

## 4. Build independent strands

Construct 3–6 strands from relevant terminology. Give each strand one retrieval purpose, such as a mechanism, application, risk, named theory, population, or outcome. Prefer several interpretable searches to one large Boolean expression.

Retain a strand when it finds at least five new core or supporting records, fills a planned coverage gap, or recovers a landmark. Reformulate or retire it when most of the top 20 are irrelevant or when it adds almost no unique relevant work. Treat these as starting heuristics, not rigid rules.

Log the reason for every refinement in `--rationale`. Use `--from-year` with relevance ranking for a frontier strand:

```bash
python3 <vault>/scripts/seed_openalex.py search <vault> \
  --stage frontier \
  --strand recent-mechanisms \
  --rationale "Find recent work while retaining relevance ranking" \
  --from-year 2024 \
  --query '"partial reprogramming" AND "cell identity"'
```

Avoid `--sort newest` for broad searches. It is available for exceptional cases but commonly destroys precision.

## 5. Expand anchors

Choose 2–4 anchors when available:

- a recent, high-quality review;
- a seminal or influential primary study;
- a recent primary study;
- a critical, safety, negative, or contradictory source.

Retrieve every indexed reference and a recent-citing slice:

```bash
python3 <vault>/scripts/seed_openalex.py expand-anchor <vault> \
  --id W4392348348 \
  --strand review-citation-neighborhood \
  --rationale "Recover landmarks and recent work missed by keyword ranking" \
  --from-year 2024 \
  --recent-citing 20
```

The script batches and retrieves all reference metadata before local screening. Do not truncate an anchor's references to the API's first page. Generic related-work expansion is intentionally omitted because it produced weak precision in testing.

## 6. Assemble a balanced selection

Select papers explicitly in decision files. Use roles to monitor balance rather than allowing citation counts or one search ranking to define the seed. For a typical 80–100-paper seed, seek representation from:

- foundational and field-defining work;
- primary evidence and central mechanisms;
- methods and measurement;
- recent frontier work;
- safety, limitations, negative evidence, and disagreement;
- useful reviews that organize or connect the field.

These categories may overlap and their proportions must follow the topic. Do not select a paper merely because a PDF is available.

Check progress:

```bash
python3 <vault>/scripts/seed_openalex.py status <vault>
```

Continue until the intended dimensions are represented and additional searches produce little new core or supporting literature. A practical stopping signal is two successive refinements yielding fewer than five new relevant papers or less than roughly ten percent unique relevant yield, provided no obvious landmark or coverage gap remains.

## 7. Finalize

Finalize only after screening and selection:

```bash
python3 <vault>/scripts/seed_openalex.py finalize <vault>
```

The command groups duplicate title versions, prefers a published scholarly version, and writes the unique selected list to `state/queue.json`. It enforces the vault's 80–100 target by default. If the topic defensibly requires another size, pass an explicit range or `--allow-outside-target` and record the rationale in `state/research.md`.

The completed queue is metadata only. Do not download files, create source notes, or begin wiki synthesis during this stage.

## Audit expectations

Treat OpenAlex `meta.count` as a raw match count, not an eligible-paper count. Preserve:

- exact query, filters, sort, stage, strand, rationale, timestamp, counts, IDs, and raw response;
- relevance label and reason for selected and excluded records;
- discovered terminology with source provenance;
- duplicate/version relationships;
- final coverage and stopping rationale.

Use `state/search-log.jsonl` for the machine audit trail and `state/research.md` for the concise human-readable strategy and conclusions.

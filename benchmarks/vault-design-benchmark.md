# Research Vault Design Benchmark

## Purpose

Evaluate research-vault workflows as end-to-end research systems rather than as
collections of attractive Markdown files. The benchmark separates source
discovery, source processing, synthesis quality, graph quality, question
answering, human usability, and downstream analytical readiness.

Do not collapse these measures into one score until a concrete use case supplies
defensible priorities. Report a metric vector and compare systems on a Pareto
frontier. A workflow that is best for exploratory learning may be unsafe for a
systematic review, while a highly normalized evidence store may be unpleasant to
read in Obsidian.

## Design principles

1. Measure outcomes on tasks, not template conformance alone.
2. Keep correctness measures separate from structural proxies.
3. Evaluate both initial construction and incremental updates.
4. Count independent studies separately from reports.
5. Preserve abstention as a valid outcome when evidence is absent or conflicting.
6. Freeze the corpus and task set before comparing architecture variants.
7. Retain raw answers, citations, traces, timings, and model/version metadata.

## Evaluation modes

### Exploratory vault

Optimize useful coverage under a source and cost budget. Evaluate relevance,
conceptual breadth, methodological diversity, frontier/foundation balance,
counterevidence, and reading utility. Absolute literature recall is not claimed.

### Systematic evidence synthesis

Optimize sensitivity against a protocol-defined eligibility set. Use a known
reference set and report recall, precision, records screened, work saved at a
specified recall, study/report deduplication, risk-of-bias completeness, and
reproducibility. Do not restrict inclusion eligibility to open full text.

### Living vault

Evaluate update latency, affected-page recall, unnecessary-page rewrite rate,
stale-claim detection, idempotence, and whether corrections/retractions propagate.

## Benchmark suites

### A. Source discovery and selection

Use at least three topics with different evidence ecologies:

- a mature intervention topic with an existing systematic review;
- a fast-moving technical topic with preprints and rapid terminology drift;
- a contested interdisciplinary topic with heterogeneous methods.

For each topic, create a blinded reference set from an existing review, expert
adjudication, or pooled retrieval followed by screening. Measure:

| Dimension | Metric |
|---|---|
| Eligibility | Precision among screened and selected records |
| Coverage | Relative recall of the blinded reference set |
| Effort | Records screened; minutes; API and acquisition cost |
| Screening efficiency | RRF@10, WSS@95 where a complete labeled pool exists |
| Conceptual coverage | Recall across protocol strands or competency questions |
| Role coverage | Primary, synthesis, method, foundation, frontier, and critical evidence |
| Design diversity | Distribution and normalized entropy of study designs |
| Temporal balance | Frontier lag, recent share, and foundation coverage |
| Concentration | Maximum share and HHI for authors, institutions, venues, and topics |
| Redundancy | Duplicate reports, versions, overlapping study populations, semantic near-duplicates |
| Counterevidence | Recall of known negative, null, critical, or contradictory evidence |
| Acquisition | Valid full-text yield by route and cost per retained work |

Treat citation count, venue, recency, and OpenAlex relevance as candidate features,
not quality labels. Compare at least:

1. relevance-ranked selection;
2. current role/strand heuristic selection;
3. constraint-first selection with novelty reranking;
4. sensitivity-first retrieval followed by active-learning screening.

### B. Parsing and source-note extraction

Retain the existing parser benchmark and add source-note tests:

- bibliographic identity accuracy;
- claim recall and precision against expert annotations;
- evidence/result extraction accuracy;
- scope and boundary-condition retention;
- locator resolvability;
- study/report linking accuracy;
- retraction/correction propagation;
- cost, latency, and review-required rate.

### C. Wiki synthesis

Create an expert-authored proposition set for a subset of concepts. Include
supported, qualified, contradicted, and genuinely unresolved propositions.

Measure:

- proposition recall and precision;
- citation correctness/entailment;
- citation completeness;
- contradiction recall;
- scope-retention accuracy;
- independent-study counting accuracy;
- unsupported inference rate;
- appropriate uncertainty and abstention;
- duplicate-concept and alias-collision rate;
- update accuracy after withheld evidence is introduced.

### D. Agent question answering

Use fixed tasks spanning:

1. direct lookup;
2. definition and distinction;
3. single-concept synthesis;
4. multi-hop relationship reasoning;
5. disagreement and boundary conditions;
6. evidence provenance;
7. missing-evidence or unanswerable questions;
8. temporal update questions;
9. study-versus-report traps;
10. quantitative extraction questions.

Score factual correctness, coverage, citation correctness, citation completeness,
abstention correctness, files opened, bytes/tokens read, latency, and run-to-run
variance. Evaluate with and without the wiki layer to measure its actual marginal
value over source-note retrieval.

### E. Human Obsidian use

Give representative users fixed tasks and measure effectiveness, efficiency, and
satisfaction:

- task completion and answer accuracy;
- time and navigation steps;
- failed searches and wrong-page visits;
- provenance verification time;
- ability to find disagreement and uncertainty;
- perceived trust, workload, and usability;
- qualitative confusion around properties, page types, and link meanings.

### F. Meta-review readiness

On a small known meta-analysis, measure:

- eligible-study recall;
- report-to-study linkage;
- PICO/PECO field accuracy;
- outcome, measure, time-point, and unit-of-analysis accuracy;
- effect estimate and uncertainty reproduction;
- risk-of-bias field completeness;
- pooled-result reproduction and sensitivity-analysis agreement;
- provenance of every transformation.

Narrative wiki pages alone cannot pass this suite; a structured extraction layer
is required.

### G. Forecasting readiness

Use resolved historical questions and measure:

- resolution-criteria validity;
- base-rate retrieval;
- relevant driver and counterindicator recall;
- forecast Brier or log score;
- calibration and resolution across question sets;
- diversity and correlation of ensemble members;
- update responsiveness and rationale provenance.

Keep forecast records separate from concept pages.

## Architecture variants for the first experiment

### V0 — Narrative baseline

Use the current wiki template. This establishes readability and token-cost
baselines but has document-level provenance and weak proposition identity.

### V1 — Proposition-centric Markdown

Use readable concept pages with stable proposition and source-claim block IDs,
typed evidence roles, scoped assessments, and typed relational sentences.
Markdown remains canonical.

### V2 — Hybrid claim ledger

Use the V1 pages plus a derived, rebuildable JSONL claim/edge index. Agents query
the index for candidate evidence and open Markdown for context and verification.

### V3 — Thin graph projection

Use normalized concept, claim, evidence, and relation records with generated
Obsidian projections. This maximizes machine structure but tests whether generated
pages become less useful or editable for humans.

## Mechanical audit

Run:

```bash
python3 benchmarks/benchmark_vault.py --vault /path/to/vault
python3 benchmarks/benchmark_vault.py \
  --vault /path/to/vault \
  --shortlist /path/to/vault/state/shortlist.json
```

The audit detects structural failures and reports shortlist balance. It does not
measure truth, citation entailment, relevance, or human usefulness. Those require
the fixed task suites and adjudicated reference data above.

## Initial decision rule

Advance an architecture only if it:

- has no regression in citation correctness or contradiction recall;
- improves at least one task-level outcome;
- does not materially worsen both human task time and agent context cost;
- remains idempotent and incrementally updateable;
- exposes its unresolved errors instead of silently repairing evidence.


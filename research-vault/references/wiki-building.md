# Evidence-backed wiki building

Build the wiki as a set of readable, claim-addressable syntheses. Markdown is the canonical knowledge layer. `state/wiki-index.jsonl` is a derived retrieval index and must always be rebuildable from the notes.

This design uses three levels:

1. **Report:** one source note for a bibliographic work.
2. **Study:** one `study_id` shared by reports that analyze the same underlying observations.
3. **Proposition:** one scoped assertion in a wiki page, supported, challenged, or qualified by source-claim blocks.

Do not count reports as independent studies. Do not infer evidential independence merely because citations, authors, or venues differ.

## Why the vault uses claim-addressable Markdown

The design borrows the useful core of nanopublications and micropublications—separating assertions from provenance and evidence—without forcing users to edit RDF. It also follows the provenance principle that an entity, the activity that produced it, and the responsible agent should remain distinguishable. See [PROV-O](https://www.w3.org/TR/prov-o/), [Nanopublications: A Growing Resource of Provenance-Centric Scientific Linked Data](https://doi.org/10.1109/eScience.2015.10), and [Micropublications: a semantic model for claims, evidence, arguments and annotations in biomedical communications](https://doi.org/10.1371/journal.pone.0112598).

Obsidian supports human-readable block identifiers and direct links to blocks. It also treats properties as small atomic values, does not support nested properties in its normal property UI, and builds backlinks and graph edges from ordinary internal links. Keep complex epistemic content in the Markdown body, keep YAML flat, and use block links for claim-level provenance. See Obsidian's official documentation for [properties](https://obsidian.md/help/properties), [internal and block links](https://obsidian.md/help/links), [backlinks](https://obsidian.md/help/plugins/backlinks), [graph view](https://obsidian.md/help/plugins/graph), and [Bases](https://obsidian.md/help/bases).

## Preconditions

Begin wiki synthesis only after:

- acquisition has been finalized;
- parsing has completed and every failure or `review_required` record has been handled;
- reports in the current synthesis batch have source notes with claim blocks, locators, scopes, and study links;
- the research frame states the intended question, exclusions, and evidence mode;
- known duplicate reports, versions, retractions, and corrections have been resolved or explicitly flagged.

Do not rebuild the wiki after every paper. Complete source notes in coherent batches—normally 10–20 reports or one completed search strand—then synthesize across the batch. Batch size is a workflow heuristic, not an evidential threshold.

## 1. Extract source claims before synthesizing

For each source, extract only claims relevant to the vault. A claim block must contain:

- an attributable claim;
- the source's evidence or reasoning;
- scope and boundary conditions;
- a resolvable locator;
- an evidence type;
- a stable block ID such as `^c-w1234567890-01`.

Distinguish a result from the authors' interpretation. Preserve null results, adverse findings, and failed replications. When a review reports another study's finding, prefer a claim from the primary report when available; keep the review claim for review-level conclusions such as pooled effects or search coverage.

After parsing, compare successfully parsed OpenAlex IDs with source-note `openalex_id` values. Create source notes for a manageable missing group, then synthesize after a coherent batch—normally 10–20 reports or one completed search strand. After validating that batch, continue with the next parsed reports lacking source notes. Repeat until every successfully parsed report has one source note and every completed batch has received a synthesis pass.

Record structured quantitative extractions separately when the intended task is a meta-analysis. Narrative claims do not replace participant, intervention/exposure, comparator, outcome, time point, effect estimate, uncertainty, unit-of-analysis, and risk-of-bias fields. Cochrane's guidance likewise separates study collection, data extraction, and preparation for synthesis; see [searching and selecting studies](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04), [collecting data](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05), and [preparing for synthesis](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-09).

## 2. Normalize terms without erasing distinctions

Build a provisional concept list from source claims, author terminology, search strands, and expected questions. For each candidate, record:

- preferred label;
- aliases and historical terms;
- definition and exclusions;
- broader, narrower, or related candidates;
- claims and studies that use the term;
- collisions where one label denotes different constructs.

Use aliases only for genuine alternate labels. Create separate pages when the same word denotes distinct constructs. Use `distinguished-from` to make the distinction explicit. The controlled relation approach is compatible with the concept-label and broader/narrower mapping principles in the [SKOS reference](https://www.w3.org/TR/skos-reference/), but the vault remains ordinary Markdown rather than an ontology.

## 3. Decide whether a page should exist

Create a page when the idea is reusable beyond one source and can be updated independently. Normally require at least two relevant, plausibly independent studies before creating a mature empirical concept page. Exceptions are allowed for:

- a named method, construct, or framework required to understand the field;
- a foundational definition;
- a consequential tension or open question;
- a single new result that must remain visible, provided the page and proposition say `single-source`.

Do not create a page for:

- a paper-specific result that belongs only in its source note;
- a synonym with no distinct meaning;
- a section heading that cannot be stated as a reusable idea;
- an unsupported possibility that can remain an open question;
- a duplicate whose scope and evidence neighborhood match an existing page.

A batch has received a synthesis pass when its claims have been compared with the existing wiki, affected pages have been updated, reusable ideas meeting the criteria have been created, and paper-specific or insufficiently reusable claims have deliberately remained in their source notes. A source claim does not need a wiki proposition merely to prove it was processed.

### Granularity tests

A good page should pass all of these tests:

1. It has a one-sentence definition.
2. Its propositions share a coherent scope and source neighborhood.
3. Contradictory evidence can be added without changing the subject.
4. It can be linked by a typed sentence from another page.
5. A likely research question would retrieve this page rather than a whole paper.

Split a page when its propositions need different populations, mechanisms, evidence standards, or update schedules. Merge pages when their definitions, aliases, and supporting claim sets substantially overlap. Typical mature pages are 300–900 words with one to five propositions; this is a readability target, not a hard limit.

## 4. Search before create

Before creating a page:

1. Search filenames, titles, `wiki_id`, aliases, definitions, and proposition text.
2. Inspect incoming and outgoing links of the closest pages.
3. Compare scopes and cited source claims.
4. Choose `update`, `create`, `merge`, or `redirect`.

Keep `wiki_id` stable when renaming a page. Let Obsidian update ordinary links. If a legacy name is semantically identical, retain it as an alias. If two pages are merged, leave a small deprecated redirect note when external or agent references may still use the old identity.

## 5. Write propositions, then the narrative

Draft proposition blocks before writing `Current synthesis`. Each proposition must be independently falsifiable or revisable and contain:

- one statement with a stable `^p-<wiki-id>-NN` ID;
- an evidence pattern;
- a reasoned assessment;
- explicit scope;
- claim-level `Supports`, `Challenges`, and `Qualifies` links;
- update triggers.

Use these evidence-pattern labels descriptively:

- `convergent`: materially different evidence sources point the same way;
- `mixed`: results differ without a clearly dominant interpretation;
- `contested`: credible positions directly conflict;
- `sparse`: too little relevant evidence for stability;
- `single-source`: only one source or underlying study currently supports it;
- `not-assessed`: evidence has not yet been appraised.

The label is not a confidence score. In `Assessment`, reason about the dimensions relevant to that proposition: study design, bias, directness, precision or information size, consistency, effect magnitude, independence, applicability, and recency. Do not import GRADE labels unless the vault is actually applying a GRADE-compatible protocol to the relevant body of evidence. GRADE assesses certainty for an outcome-level body of evidence, not the prestige of a paper; see the [GRADE guidelines](https://www.jclinepi.com/article/S0895-4356(10)00330-6/fulltext).

Write the narrative only after the proposition map is stable. It should explain the concept, integrate the propositions, and foreground mechanisms, tensions, and boundaries. Do not summarize papers sequentially and do not turn a majority of papers into a vote. Study designs answer different questions; convergence across independent methods can be more informative than raw paper counts.

## 6. Represent disagreement without forced resolution

When sources conflict:

1. Verify that they address the same construct and outcome.
2. Compare population, task, intervention, comparator, measure, time point, model quality, and analysis.
3. Check whether reports share a study, dataset, or research lineage.
4. Separate direct result from author interpretation.
5. Add the evidence to `Supports`, `Challenges`, or `Qualifies` as appropriate.
6. State whether the conflict is explained, unresolved, or potentially artifactual.

Never average away incompatible constructs. Never silently choose the newest, most cited, or highest-status source. Citation count, venue, and recency are discovery and context features, not truth weights.

## 7. Add typed connections

Use relational sentences, one edge per line:

```markdown
- **moderates** → [[Related concept]] — Explain how and under what scope.
```

Approved relations are:

- `broader-than`, `narrower-than`, `part-of`;
- `causes`, `mediates`, `moderates`;
- `supports`, `challenges`;
- `operationalized-by`, `measured-by`, `applied-in`;
- `distinguished-from`, `prerequisite-for`, `informs`.

Use causal relations only when the evidence warrants a causal interpretation. The sentence after the dash is required because the same two pages can be related in several ways. Ordinary body links supply Obsidian backlinks and graph edges; do not maintain a second manual backlink list.

## 8. Validate and build the agent index

Run:

```bash
python3 scripts/build_wiki_index.py . --check
python3 scripts/build_wiki_index.py .
```

The first command validates without writing. The second writes the derived `state/wiki-index.jsonl`. It rejects missing stable IDs, missing locators, duplicate IDs, propositions without claim-level evidence, claim-target mismatches, drift between the `sources` property and proposition citations, unknown relations, and missing relation targets.

The validator checks the source notes and wiki pages that exist. It does not prove that all parsed reports have notes, that the knowledge layer is non-empty, or that every source-note batch has been synthesized. Assess those conditions separately before declaring the full vault complete.

The index is a retrieval aid, not an independent evidence store. An agent may query it to locate candidate propositions and source claims, but must open the Markdown blocks to inspect full context before making a consequential claim.

## 9. Audit the completed batch

After every synthesis batch:

- connect new pages to existing pages in both meaningful directions where appropriate;
- merge or redirect duplicates;
- check orphan pages and broken links;
- inspect propositions with only one study or one research group;
- search for unrepresented null, negative, and contradictory claims;
- confirm `sources` properties match claim citations;
- rebuild the index and rerun fixed competency questions;
- update the human-facing index or map of content.

Use withheld-source tests periodically: build the wiki without a relevant source, add it later, and measure whether the correct propositions update while unrelated pages remain unchanged. This tests belief revision rather than one-time prose generation.

Before calling the full vault complete, reconcile the finalized queue with parsed Markdown, successfully parsed OpenAlex IDs with source-note `openalex_id` values, and completed source-note batches with wiki synthesis passes. Confirm that access gaps remain explicit and that the fixed competency questions are answerable or clearly unresolved.

## Downstream analytical layers

### Small meta-analyses

Keep effect-size data in a structured extraction table with explicit transformations and source-claim links. A wiki page may explain the construct, eligibility decisions, and synthesis, but pooled estimates must be reproducible from the extraction layer. Preserve study/report linkage to prevent double-counting.

### Forecasting

Keep forecast questions separate from concept pages. Each forecast needs resolution criteria, close and resolve dates, an append-only probability history, base-rate evidence, drivers, counterindicators, and cited rationale. Concept pages can inform forecasts; they should not be rewritten to match a forecast. Evaluate forecasts with proper scores such as Brier or log score and measure correlation before calling a set of forecasts an ensemble.

### Living updates

For a living vault, track the last evidence review separately from file modification time. New evidence should trigger candidate affected pages through claim and relation links, followed by human- or agent-reviewed changes. Retractions and corrections must propagate from source note to every cited proposition. Preserve prior states in version control rather than overwriting the history of a belief without trace.

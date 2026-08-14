# Wikipedia-Grounded Entity Identity ("wiki-linking")

*Plan written 2026-08-14. Supersedes ROADMAP_IDEAS_2026.md §12 Layer 2 (embedding
merge candidates — no longer needed) and absorbs Layer 3 (Wikidata grounding) with
a better implementation. Layers 0–1 (prompt injection, normalization + ALIASES +
weekly merge job) stay exactly as they are: they remain the floor everything falls
back to.*

## Why

Entity identity today is derived from name spelling, repaired after the fact by
normalization rules and a hand-curated alias table. A week of production evidence
shows where that leaks: 960 display-name corrections in one pass, ~400 hand aliases
and growing, and new duplicate pairs appearing within hours of a single day's batch
("Rosatom State" vs "Rosatom State Corporation"). The curation treadmill never ends
because every transliteration, typo, and suffix mints a new identity.

The fix is to stop deriving identity from labels: have the extractor emit the
**English Wikipedia article title** for each entity it already scores, validate the
titles offline against Wikipedia's redirect graph, and use the resulting **page id**
as the primary merge key. Wikipedia's redirect graph is a hand-curated alias table
with thousands of maintainers; "Zelensky", "Zelenskyy", and "Wolodymyr Selenskyj"
all resolve to the same page in any language.

Why this beats the roadmap's original Layer 3 (resolve names via the Wikidata search
API after the fact): the LLM links **with the full article context in view**, so
disambiguation comes free — a name-only API lookup can't tell which "Michael Jordan"
an article means, the model reading the article can.

What was previously rejected in §12 — full entity-linking systems (BLINK/mGENRE) as
a pipeline dependency — stays rejected. This plan adds one output field to an LLM
call we already make, plus an offline validation batch job. Nothing new sits in the
pipeline's critical path.

## Cost ("free" check)

| Item | Cost |
|---|---|
| Extra output tokens (~10–50/article for one short field) | ≈ 2–4¢ per 1,000 articles (gpt-5-nano @ $0.40/M out) ≈ $0.01/week at current volume |
| Wikipedia API (validation + backfill) | $0 — batched 50 titles/request, cached, polite User-Agent; tens of lookups/day after backfill |
| Storage (2 columns + 2 small tables) | negligible |

## Principles (carried over from §12)

- **Not a pipeline dependency.** Validation is an offline batch step. If Wikipedia
  is unreachable or a title doesn't validate, the entity simply falls through to the
  existing name machinery. Analysis never blocks on wiki.
- **Hint, not truth.** An emitted title is evidence for identity, applied through
  the same conservative, pointer-based, reversible merge machinery.
- **Identity ≠ display.** Display names stay owned by ALIASES + `normalize_name()`
  (en-wiki titles sometimes differ from our curated names: wiki "Volodymyr
  Zelenskyy" vs curated "Volodymyr Zelensky"). The page id is used for grouping
  only.
- **Default off until measured.** Same rollout pattern as `KNOWN_ENTITY_INJECTION`.

## Phase 0 — Pilot: measure before any schema change

1. Behind env flag `WIKI_TITLE_LINKING` (default off, wired like
   `KNOWN_ENTITY_INJECTION` in `analyzer/batch_analyzer.py`):
   - `analyzer/prompts.py::ENTITY_SENTIMENT_SCHEMA`: add
     `"wikipedia_title": {"type": ["string", "null"]}` to the entity item and to
     `required` (strict mode demands membership in `required`; `null` = "no
     article exists / not sure — do not guess").
   - Prompt: one instruction line — *the exact English Wikipedia article title for
     this entity itself (not its parent org or country); null if none exists or
     you are unsure.*
   - When the flag is off, the field is absent from schema and prompt, so default
     corpus behavior is byte-identical.
2. `analyzer/batch_analyzer.py::process_batch_output`: when the flag is on, append
   `(entity_id, entity_name, emitted_title)` rows to
   `batches/wiki_pilot.jsonl`. **No DB changes in this phase.**
3. Run one day's batch with the flag on (~250–350 articles ≈ a few cents).
4. Validation script (`analyzer/tools/validate_wiki_titles.py`, offline): resolve
   every distinct emitted title via the Wikipedia API
   (`action=query&redirects=1&format=json`, 50 titles per request, results cached)
   → canonical title + page id.

**Go/no-go metrics:**

- Emission: ≥ ~90% of extracted entities carry a non-null title (else tune prompt).
- Validation: ≥ ~85% of emitted titles resolve to a real page.
- Consistency: among entity pairs the *current* name machinery already merges,
  ≥ 95% share a page id (sanity check on both systems).
- Novel-merge audit: hand-review the full list of new same-page-id pairs the name
  machinery missed. Expect a small list; zero obviously-wrong pairs required.
- Effort sensitivity: we run extraction at `reasoning_effort=minimal`; if
  validation rate is poor, re-pilot the same articles at `low` and compare (still
  cents) before concluding anything.

## Phase 1 — Capture (migration 020)

- `entities.wikipedia_page_id BIGINT NULL` and `entities.wikipedia_title TEXT NULL`
  (the *validated canonical* title, for display/links — not the raw emission).
- `entity_wiki_votes (entity_id, raw_title, votes)` — per-article emissions
  disagree sometimes; votes make the disagreement visible and let a majority rule
  decide instead of first-write-wins flip-flopping.
- `wiki_title_cache (raw_title PK, canonical_title, page_id, checked_at)` — every
  Wikipedia lookup goes through this; steady-state API volume is only never-seen
  titles.
- `database/services.py::process_article_entities` upserts votes when the flag is
  on.

## Phase 2 — Validation job (offline, free)

New scheduler step after the daily pipeline (`scheduler/job_scheduler.py`):
resolve uncached raw titles via the API, then assign
`entities.wikipedia_page_id` where votes are decisive: **≥ 2 votes AND > 60%
majority** for one page id. Entities below that bar stay unlinked and keep using
the name machinery. Delta-only, batched, cached — expected volume tens of lookups
per day.

## Phase 3 — Merge on page identity

`analyzer/entity_resolution.py::run_merge_job` gains a tier *above* the current
merge-key tier:

1. Group canonical entities by `wikipedia_page_id` (strongest evidence).
2. **Guardrail — type-class compatibility** required for auto-merge on page id:
   person↔person, business/organization↔business/organization, country↔country.
   Incompatible pairs (e.g. a sloppy "Trump administration" → *Donald Trump* page
   link would otherwise merge an organization into a person) are written to a
   review report (`logs/wiki_merge_review.log`) instead of merged.
3. Everything unlinked falls through to the existing exact merge-key tier,
   unchanged. Merges stay pointer-based and reversible; the display-name rename
   pass is unchanged.

## Phase 4 — Backfill without re-analysis

Do **not** re-run articles through the LLM (score consistency; needless spend).
For existing canonical entities with ≥ 5 mentions (~a few thousand rows): resolve
the *canonical name* via Wikipedia search + redirects; auto-accept only
exact-or-redirect title matches; ambiguous names stay unlinked and are covered by
new mentions' votes over time. One-time job, roughly an hour of polite API calls,
$0.

## Phase 5 — Consequences and cleanup

- ROADMAP §12: Layer 2 (embeddings) removed — a shared validated page id answers
  "same thing?" directly, which is strictly stronger than "similar string".
- ALIASES becomes an override + long-tail tool; expected to stop growing for
  famous entities. Layer 0 injection unchanged.
- Free enrichment unlocked for later, all optional: entity pages can link to
  Wikipedia; the same API returns the Wikidata QID, which opens relationship-aware
  views (e.g. a "Meta including its leadership" rollup via P169/P488 — as an
  additive query-time grouping, never a merge).

## Rollout

Each phase ships and reverts independently. Phase 0 is an afternoon including
batch turnaround; Phases 1–3 about a day; Phase 4 an hour of runtime. The compose
default for `WIKI_TITLE_LINKING` stays off until Phase 3 has run clean on a week
of daily batches.

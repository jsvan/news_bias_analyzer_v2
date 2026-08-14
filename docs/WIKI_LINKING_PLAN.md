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

Measured baseline (2026-08-14, live probes at `reasoning_effort=minimal`, batch
rate): ~2,850 prompt + ~180 completion tokens/article after the mentions/quote
arrays were dropped from the schema (they were 58–78% of visible output; the
"$10/day" era was the pre-8/14 medium-reasoning default, not volume) —
**$0.11 per 1,000 articles**. Real scrape volume is 3,600–7,000 articles/day
(not the ~300 older estimates assumed), so total analysis spend is
**$0.40–0.80/day** before wiki-linking.

| Item | Cost |
|---|---|
| Wiki title field (~30–50 output tokens/article) | ≈ 1–2¢ per 1,000 articles; shrinks further with the KNOWN-list skip below |
| `KNOWN_ENTITY_INJECTION` (~100–300 *input* tokens/article) | ≈ 1–2¢ per 1,000 articles (input is 8× cheaper than output) |
| Wikipedia API (validation + backfill) | $0 — batched 50 titles/request, cached, polite User-Agent; tens of lookups/day after backfill |
| Storage (2 columns + 2 small tables) | negligible |

**KNOWN-list skip:** once `KNOWN_ENTITY_INJECTION` is on (validated the same
pilot day — it has waited since July), known entities already carry validated
page ids, so the prompt says: *for entities from the KNOWN list, emit `null`
for wikipedia_title.* Title tokens are then only spent on never-seen entities —
at steady state, a handful per article.

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
3. Run one day's batch with the flag on (3,600–7,000 articles ≈ well under a
   dollar at the measured rate). The same pilot day also turns on
   `KNOWN_ENTITY_INJECTION` — its long-pending validation — so one day's batch
   validates both flags against the previous day's output on every metric at
   once.
4. Validation script (`analyzer/tools/validate_wiki_titles.py`, offline): resolve
   every distinct emitted title via the Wikipedia API
   (`action=query&redirects=1&format=json`, 50 titles per request, results cached)
   → canonical title + page id. **Reject any page whose `pageprops` marks it a
   disambiguation page** (same API call returns this for free) — a title that
   resolves to a disambiguation page is not an identity.

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
- **Emission disagreement**: of entities with ≥2 emissions in the pilot, the
  fraction whose emissions resolve to more than one page id. This decides the
  Phase 2 trust rule: under ~1%, relax "≥2 votes + >60% majority" to
  first-validated-emission-links-it and lean on the guardrails + disagreement
  report (note the trade: singletons then link from one shot, and the tail's
  protection rests entirely on type-class + co-mention veto); at a few percent,
  the majority gate stays. The emission log (`entity_wiki_votes`) stays in
  either outcome — the recurring audits consume it, and it is the same three
  columns; only the one-line trust rule is at stake.

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
majority** for one page id (or the relaxed first-validated rule, per the Phase 0
emission-disagreement gate). Entities below the bar stay unlinked and keep using
the name machinery. Majority is chosen over first-write-wins deliberately: it
makes identity a pure function of the tally — same evidence, same outcome,
regardless of article arrival order — where first-write-wins lets one bad early
emission permanently fuse two entities' sentiment histories. Delta-only,
batched, cached — expected volume tens of lookups per day.

## Phase 3 — Merge on page identity

`analyzer/entity_resolution.py::run_merge_job` gains a tier *above* the current
merge-key tier:

1. Group canonical entities by `wikipedia_page_id` (strongest evidence).
2. **Guardrail — type-class compatibility** required for auto-merge on page id:
   person↔person, business/organization↔business/organization, country↔country.
   **`concept` and `event` entities are excluded from page-id auto-merge
   entirely at first** — that's where linking gets mushy ("inflation",
   "immigration" have many plausible near-miss pages). Incompatible or excluded
   pairs (e.g. a sloppy "Trump administration" → *Donald Trump* page link would
   otherwise merge an organization into a person) are written to a review report
   (`logs/wiki_merge_review.log`) instead of merged.
3. **Guardrail — co-mention veto.** Two labels for the same real thing almost
   never appear as two separately-scored entities in one article; associates do,
   constantly. Measured on this corpus (2026-08-14): of 1,695 known-good alias
   pairs, only 7 have *any* co-mention articles (max 3), while Trump + White
   House — the archetypal must-not-merge associate pair — co-occur as separate
   scored entities in **132** articles. Veto any auto-merge (page-id or
   name-key) where the pair shares **≥ 5 co-mention articles**; vetoed pairs go
   to the review report. This is the data's own testimony that a pair is two
   things, and it independently protects against wrong LLM links that pass the
   type-class check.
4. Everything unlinked falls through to the existing exact merge-key tier,
   unchanged. Merges stay pointer-based and reversible; the display-name rename
   pass is unchanged.
5. **Disagreement report** — page ids as *negative* evidence too: members of a
   name-merged group that carry *different* validated page ids are strong
   evidence of a wrong merge. Log them to the same review report; this lets
   wiki-linking audit the existing alias table, not just extend it.

## Phase 4 — Backfill without re-analysis

Do **not** re-run articles through the LLM (score consistency; needless spend).
For existing canonical entities with ≥ 5 mentions (~a few thousand rows): resolve
the *canonical name* via Wikipedia search + redirects; auto-accept only
exact-or-redirect title matches; ambiguous names stay unlinked and are covered by
new mentions' votes over time. This is exactly the name-only lookup the plan
critiques, so it gets the full guardrail set: disambiguation pages rejected, and
the Phase 3 type-class rules applied to backfill matches too (a famous ambiguous
name silently resolves to its primary-topic page — "exact match" alone doesn't
protect against that). One-time job, roughly an hour of polite API calls, $0.

## Phase 5 — Consequences and cleanup

- ROADMAP §12: Layer 2's *auto-merge-by-distance* form is measured and dead:
  on 400 ground-truth same-entity pairs vs 350 hard lookalike pairs from this
  corpus (name embeddings, text-embedding-3-small, 2026-08-14), the similarity
  distributions overlap so badly that no epsilon works — 90% same-entity recall
  costs a 28% false-merge rate on lookalikes, and identical scores carry
  opposite truth ("Richard J. Durbin"/"Dick Durbin" = same person at 0.836;
  "Anant Ambani"/"Mukesh Ambani" = father and son at 0.836). Acronyms and
  renames — the most valuable aliases — are embedding-*far* (Twitter/X at 0.257,
  NASA/full name at 0.534) while wiki redirects capture them exactly. But the
  same experiment validated embeddings as a *suggester*: the nearest-neighbor
  list surfaced 11 real unmerged duplicates the string-based fuzzy pass could
  never see (Dick Durbin, Mike DeWine, Raúl Castro…), added to ALIASES the same
  day for $0.0001. Optional follow-up: replace the SequenceMatcher fuzzy band
  with embedding kNN as the offline curation aid — suggest-only, never
  auto-merge.
- ALIASES becomes an override + long-tail tool; expected to stop growing for
  famous entities. Layer 0 injection unchanged.
- Free enrichment unlocked for later, all optional: entity pages can link to
  Wikipedia; the same API returns the Wikidata QID, which opens relationship-aware
  views (e.g. a "Meta including its leadership" rollup via P169/P488 — as an
  additive query-time grouping, never a merge).

## Duplicate suggesters (suggest-only, feed the review log)

Auto-merge is reserved for exact keys and guarded page ids. Everything below
only *proposes* — output goes to the review report for the weekly curation
pass, never straight to `canonical_id`:

- **Name-embedding kNN** (proven 2026-08-14: surfaced 11 real duplicates the
  SequenceMatcher band could never see — "Dick Durbin"/"Richard J. Durbin" is
  string-far but embedding-close — for $0.0001). Replaces the fuzzy
  SequenceMatcher band as the string-side suggester.
- **Behavioral twins × zero co-mention.** The Phase-4 `entity_embeddings`
  table (co-occurrence + sentiment-profile vectors, rebuilt weekly) already
  fingerprints how each entity behaves. Near-identical behavior + co-mention
  ≈ 0 is the signature of an uncurated rename — the "X/Twitter" case, which
  name embeddings place at 0.257 and wiki only catches once redirects update.
  A numpy pass over data we already compute; no training, no new
  infrastructure. (Training a custom embedding space was considered and
  rejected: the learnable patterns are what normalization already handles, and
  the residual — arbitrary renames — is memorization, which the ALIASES dict
  and wiki redirects already do exactly.)
- **Page-id disagreement** within name-merged groups (Phase 3, item 5) — the
  wrong-merge auditor.

## Rollout

Each phase ships and reverts independently. Phase 0 is an afternoon including
batch turnaround; Phases 1–3 about a day; Phase 4 an hour of runtime. The compose
default for `WIKI_TITLE_LINKING` stays off until Phase 3 has run clean on a week
of daily batches.

One gate does not retire at go-live: all votes come from the same model with the
same biases, so a confident majority can still be confidently wrong (same-type
collisions — two people sharing a name — pass every automated guardrail). The
novel-merge audit therefore continues as a **weekly hand spot-check for the
first month** of Phase 3, via the review report.

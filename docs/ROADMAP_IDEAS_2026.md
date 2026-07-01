# Roadmap Ideas — July 2026

The expansion ideas, written down so they don't evaporate. Core observation: we hold a
**2D coordinate (power × moral) per entity, per source, per time window** — most projects
in this space have a 1D positive/negative score. Nearly everything below is exploitation
of that structure with SQL + numpy on data we already collect. No new LLM spend except
where noted.

Computational kernels for §1–§6 live in `analyzer/narrative_metrics.py` (pure functions,
self-tested on synthetic data; DB wiring is per-feature work). Entity resolution —
load-bearing for all of this — is §12 and `analyzer/entity_resolution.py`.

## Statistical analysis

### 1. The archetype compass
The power×moral plane has natural quadrants: strong+moral = **hero**, strong+immoral =
**villain**, weak+moral = **victim**, weak+immoral = **nuisance**. Every source paints
every entity somewhere on this plane, and entities move over time. "Zelensky in BBC vs
RT, 2022→2024" as two trajectories through the same plane is the most distinctive
artifact this data can produce — narrative structure made visible.
*Kernel:* `archetype()`, `trajectory()`. *Needs:* per-source-entity-week means (SQL).

### 2. Contested-entity ranking ("the front line")
Per entity per week, Jensen–Shannon divergence between spheres' sentiment histograms.
The ranked list is the information war's current front line, computed mechanically with
zero editorial judgment. Cheap; makes the dashboard immediately interesting.
*Kernel:* `js_divergence()`, `contested_ranking()`.

### 3. Salience asymmetry (selection bias ≠ framing bias)
Same entity, different sentiment = framing. One sphere loud, the other silent =
selection — often the stronger signal. Scatter each entity: salience divergence vs
sentiment divergence. We already store mention counts; this is a query.
*Kernel:* `salience_asymmetry()`.

### 4. Synchrony and lead-lag
Cross-correlate entity-sentiment *changes* between sources at time lags.
Two products: (a) who originates sentiment shifts and who follows — narrative
propagation; (b) a synchrony score — many sources in one cluster pivoting on an entity
in the same window is a coordination fingerprint, qualitatively different from organic
drift. Pair with the changepoint detection already in todo.txt.
Honesty note: full Granger causality over-detects on noisy weekly data; lagged
correlation with a permutation test is the defensible version.
*Kernel:* `lagged_correlation()` (with permutation p-value), `synchrony_score()`.
Hardest + most novel item; the research-grade differentiator.

### 5. Data-defined ideological axes (SVD source map)
Build the source × entity sentiment matrix, run truncated SVD. The latent dimensions
are the *empirical* axes of the global information space — this delivers the "beyond
left-right" principle instead of asserting it. Interpret each dimension by its
top-loading entities. Sources become points in 2D; clusters are visible; the map is
also the substrate for §9 ("you are here").
*Kernel:* `svd_source_map()` (handles missing cells by centering + masking).

### 6. Statistical honesty at small n
Many entity-source cells have a handful of mentions; naive means there produce the
most embarrassing artifacts. Empirical-Bayes shrinkage (pool cell means toward the
group mean, weight by n) plus a minimum-n display cutoff. Ship this before anything
public.
*Kernel:* `shrunk_means()`.

### 7. Association networks
Entities co-occurring within an article form a graph per sphere; compare an entity's
neighborhood across spheres ("immigration" ↔ "crime" vs ↔ "labor market"). Emotional
association is the Pomerantsev mechanism — this measures it directly from
`entity_mentions` (article-level co-occurrence). *Not kerneled yet* — needs a
co-mention edge table or query first; design when building.

## Website / product

### 8. Auto-generated weekly report
"This week in the information war": top contested entities (§2), biggest editorial
pivots (changepoints), one trajectory of the week (§1). Generated from the stats,
published with the static-snapshot deploy — free to host, gives a reason to return,
every item shareable. A static site of dashboards is a museum; a weekly artifact is a
publication.

### 9. "You are here"
The extension knows the user's reading diet. Place it as a point in the §5 source map:
*your position in the global information space, and the three nearest sources that
most disagree with your diet on the entities you actually read about.* The
escape-the-bubble mission as a concrete feature. Requires: §5 shipped, extension
history aggregation (already stored locally by the extension).

### 10. Entity permalink pages
One page per major entity: compass position by sphere, trajectory, contested-ness
rank — with an OG preview image. The shareable/linkable unit and the SEO surface. Fits
the static-snapshot architecture (top ~1–5k entities by mentions).

## Validation (credibility layer)

### 11. Two cheap studies
(a) Run POLUSA (leaning-labeled US outlets, see `SEEDING_AND_MODELS.md`) through the
pipeline; show clustering recovers known groupings blind.
(b) Event studies: five unambiguous global events; show global sentiment moving in
lockstep — the empirical test of the project's own "global baseline" axiom. If lockstep
doesn't hold, we need to know before building on it.

## Priorities

1. **Phase 1 (one week against existing data):** §1 compass + §2 contested ranking →
   feed §8 weekly report. Visual identity of the site.
2. **Phase 2:** §5 SVD map + §9 "you are here". Mission centerpiece.
3. **Phase 3:** §4 synchrony/lead-lag, §7 association networks, §11 validation.

Deliberately rejected: minute-by-minute real-time (the extension already covers
"the article in front of you"; the pipeline's natural cadence is daily), LLM-generated
narrative summaries of patterns (neutrality principle), social features.

## 12. Entity resolution design (load-bearing for everything above)

The compass and the SVD map degrade badly if "Biden", "President Biden", and
"Джо Байден" are three entities. Current state: the extraction prompt already forces
official English names (handles most cross-lingual cases at the source), and
`Entity.canonical_id` already exists in the schema (non-destructive merge pointer);
`temp_scripts/entity_deduplication.py` merges same-name-different-type only. The
name-variant problem is unhandled.

**Layered plan (cheap → expensive), implemented in `analyzer/entity_resolution.py`:**

- **Layer 0 — in-prompt known-entity injection.** Before analysis, string-match the
  article text against the surface forms of entities we already track; inject the
  matched candidates (~10–30 names) into the prompt: "these entities are already
  tracked under these canonical names; reuse them when they appear." False positives
  are harmless (the model ignores non-appearing names); the win is stopping drift at
  the source — new variants never enter the DB. Costs ~100–300 input tokens/article
  (≈ pennies per 100k articles at nano prices). Wired into
  `batch_analyzer.prepare_batch_input()` behind `KNOWN_ENTITY_INJECTION=1`
  (default off until validated with a pilot batch).

- **Layer 1 — deterministic post-hoc normalization.** Strip honorifics/titles
  ("President Joe Biden" → "Joe Biden"), normalize whitespace/case/punctuation,
  apply a hand-curated alias table for the head entities (US ↔ United States, EU ↔
  European Union...). Run as a nightly/weekly merge job that sets `canonical_id` —
  never rewrites mentions, so merges are reversible and analysis queries just
  `COALESCE(canonical_id, id)`.

- **Layer 2 — embedding-assisted merge candidates.** Embed entity names (any cheap
  embedding API; ~$0.02/M tokens) and propose merges above a high cosine threshold;
  write a mid-confidence band to a review file instead of auto-merging. Catches
  transliteration and long-tail variants Layer 1 misses.

- **Layer 3 (optional, top entities only) — Wikidata grounding.** Resolve the top
  ~5k entities to Wikidata QIDs via the public search API (batch, offline). Gives
  canonical cross-lingual identity + free metadata (type, country). Not a pipeline
  dependency — an enrichment for the entity pages (§10).

**Explicitly rejected:** sending the *full* known-entity list to the LLM (thousands of
names = prompt bloat and confusion — the shortlist version above is the good form of
this idea); full entity-linking systems (BLINK/mGENRE) as a pipeline dependency —
heavy, and the prompt already does the cross-lingual work; destructive merges (must
stay reversible — bad merges are inevitable).

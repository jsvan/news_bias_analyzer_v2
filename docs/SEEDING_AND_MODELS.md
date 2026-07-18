# Seeding the Database & Choosing an Analysis Model

Researched July 2026. Prices and dataset sizes were verified against live sources at that
time — **re-verify prices before launching a large paid run.**

## Part 1: Bulk article datasets for seeding

Goal: backfill years of full-text articles for the sources we already track, so global
baselines don't start at "whenever the scraper was last running."

### Recommended: CC-NEWS via `stanford-oval/ccnews` (Hugging Face)

The best fit by a wide margin.

- **What**: ~461M articles, Sept 2016 – June 2024, 87+ languages, global sources.
- **Fields**: `plain_text` (full text), `title`, `publisher`, `sitename`, `published_date`,
  `requested_url`, `language`, `language_score`.
- **How**:
  ```python
  from datasets import load_dataset
  ds = load_dataset("stanford-oval/ccnews", "2023", streaming=True)
  ```
  Streaming avoids downloading the whole year. One config per year (2016–2024).
- **The key move**: filter by the publisher domains of our existing 124 sources
  (`scrapers/news_sources.py`). Extract each source's domain from its RSS feed URLs,
  match against `requested_url`/`publisher`, and insert via the same
  `insert_articles_batch` path the scraper uses (article ID = MD5 of URL, so dedup
  against live-scraped articles is automatic). This gives coherent multi-year history
  for exactly the sources we track.
- **License**: unstated on the card; underlying text is copyrighted news. Fine for
  internal research seeding — do not redistribute article text.
- **Post-June-2024 coverage**: our own scraper. Raw CC-NEWS WARCs exist for newer months
  (data.commoncrawl.org/crawl-data/CC-NEWS/) but require `news-please` processing —
  only worth it if the HF dataset stops updating.

### Secondary options

| Dataset | Size / coverage | Use for | Access |
|---|---|---|---|
| **POLUSA** | 0.9M articles, 18 US outlets, 2017–2019, **labeled by political leaning** | Validating our divergence metrics against known groupings (paper-grade sanity check) | Zenodo record 3946057, request form, research-only |
| **All The News 2.0** | 2.7M articles, 27 US outlets, 2016–2020 (2020 is thin - taper off early in the year) | US outlet depth, incl. Reuters/Washington Post which are otherwise permanently unreachable live (see Blocked Sources) | `scrapers/seed_from_all_the_news.py`, HF mirror `rjac/all-the-news-2-1-Component-one` |

### Evaluated and rejected (don't re-litigate)

- **GDELT** — no full text; only n-gram snippets you'd have to reconstruct (legally grey).
  Useful as a *free complementary signal* (see below), not as a corpus.
- **MediaCloud** — metadata only (copyright policy); 200M+ story URLs though, useful as a
  URL directory if we ever want to re-scrape historical coverage ourselves.
- **FineWeb** — no news subset; CC-NEWS already is the news filter of Common Crawl.
- **newsdata.io / NewsCatcher free tiers** — no full text on free tiers; our RSS scraper
  beats them for forward ingestion.

### Free complementary signal: GDELT GKG v2

Free, updates every 15 minutes: named entities, salience, and document-level tone across
global media. Its tone is document-level and dictionary-based, so it **cannot replace**
our entity-targeted sentiment (a story can be negative overall but positive toward a
specific entity — that's exactly our signal). Use it as a cross-check baseline and a
coverage-volume feed. Access: CSV dumps (gdeltproject.org/data.html) or BigQuery
`gdelt-bq.gdeltv2.gkg`.

## Part 2: Model choice for entity-sentiment extraction

The task is simple, high-volume extraction → optimize for cost. Current default in code
is `gpt-4.1-nano` (`analyzer/config.py`), which still works but is legacy-priced above
newer options.

### API pricing (per 1M tokens, standard tier, July 2026)

| Model | Input | Output | Batch (50% off) |
|---|---|---|---|
| **OpenAI GPT-5 nano** | $0.05 | $0.40 | $0.025 / $0.20 |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | $0.05 / $0.20 |
| OpenAI GPT-4.1 nano (current default) | $0.10 | $0.40 | $0.05 / $0.20 |
| OpenAI GPT-5.4 nano | $0.20 | $1.25 | $0.10 / $0.625 |
| Claude Haiku 4.5 | $1.00 | $5.00 | $0.50 / $2.50 |

All three providers run async batch APIs at 50% off with 24h completion windows — our
`batch_analyzer.py` architecture ports to any of them, but staying on OpenAI means zero
code changes: **just set `OPENAI_MODEL=gpt-5-nano`** (env var already wired in
`analyzer/batch_analyzer.py`).

### Cost math (1M articles)

Assume ~1.6k input tokens/article (prompt + truncated text) and ~300 output tokens:

- GPT-5 nano, batch: 1.6B in × $0.025 + 300M out × $0.20 ≈ **$100 per 1M articles**
- Gemini Flash-Lite, batch: ≈ $140 per 1M articles
- A one-year, 124-source CC-NEWS slice is likely well under 1M articles — start there,
  not with the full 461M.

Before any big run: (1) re-verify prices at developers.openai.com/api/docs/pricing,
(2) run a ~500-article pilot and compare entity/sentiment outputs against a sample of
existing gpt-4.1-nano results to confirm quality didn't regress, (3) note the
`estimate_cost()` table in `analyzer/openai_integration.py` is stale 2023 pricing —
don't trust the $50/day limiter's math.

### Structured outputs (do this when touching the analyzer)

We use `response_format: json_object` (2024-era). All providers now support strict
JSON-schema outputs, which eliminates the parse-failure handling in
`process_batch_output`. For OpenAI: `response_format: {type: "json_schema", strict: true}`.

### Local model option

Viable in 2026 for this task — extraction at this simplicity works on small open-weights
models (Qwen3 8B / Llama-class 8B / Gemma 3 12B via Ollama or vLLM, with structured
output enforced by vLLM's guided decoding or `outlines`).

Tradeoffs, honestly:
- **Cost**: electricity only. But at $100/M articles for GPT-5 nano batch, the API is
  cheap enough that local only wins if you're processing many millions of articles or
  want independence from provider ToS/rate limits.
- **Throughput**: a single consumer GPU does roughly 5–20k articles/day depending on
  model size and hardware; OpenAI batch does 1M in ~a day of queued batches. A MacBook
  Air (M-series, unified memory) can run an 8B model via Ollama but at seeding scale it
  would take weeks — fine for the daemon's daily trickle (a few hundred articles/day),
  wrong for backfill.
- **Quality**: must be validated. Run the same 500-article pilot through the local model
  and the API model; compare entity recall and sentiment agreement before committing.
- **Integration**: Ollama and vLLM expose OpenAI-compatible endpoints, so
  `openai_integration.py` works by pointing `base_url` at localhost — no rewrite. The
  Batch API path (`batch_analyzer.py`) is OpenAI-specific; for local you'd run the
  synchronous path in a loop instead.

**Recommendation**: seed with GPT-5 nano via the existing Batch API pipeline (cheapest
total effort + dollars). Consider a local 8B model later for the ongoing daily trickle
if API dependence bothers you.

## Suggested seeding pipeline (when on the target machine)

1. `./run.sh docker up && ./run.sh docker init` — database up.
2. `pip install datasets`, then `python -m scrapers.seed_from_ccnews --year 2023 --dry-run`
   to see match rates and unmatched domains (grow `DOMAIN_ALIASES` in that script if a
   big source isn't matching), then drop `--dry-run` (add `--limit` for a pilot).
   The script streams `stanford-oval/ccnews`, filters to our configured source domains,
   and inserts via the scraper's own `insert_articles_batch` (URL-MD5 ids → automatic
   dedup, lands as `unanalyzed`). `--self-test` runs its logic checks with no
   network/deps.
3. `pip install huggingface_hub pyarrow`, then
   `python -m scrapers.seed_from_all_the_news --year 2020 --dry-run` /
   `--limit N` the same way. Matches by `publication` name (no domain guessing needed)
   against a fixed 26-outlet map in the script. Downloads one parquet shard at a time
   and deletes it from the HF cache when done - streaming this dataset directly
   (`datasets.load_dataset(..., streaming=True)`) was found to stall indefinitely
   (2026-07-18), so don't reach for that pattern here even though it's what
   `seed_from_ccnews.py` uses successfully.
4. `OPENAI_MODEL=gpt-5-nano ./run.sh analyze daemon` — existing batch daemon picks up the
   backlog automatically (5 concurrent batches max, already enforced).
5. `./run.sh statistics` — rebuild weekly stats/baselines over the new history.

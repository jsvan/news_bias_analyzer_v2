"""
Seed the database with historical articles from All The News 2.0
(HuggingFace mirror: rjac/all-the-news-2-1-Component-one, 2016-2020, 27 US outlets).

Unlike CC-NEWS (matched by article URL domain), this dataset ships a `publication`
field directly, so matching is a straight name lookup - no domain-alias table needed.
Confirmed via a full scan of all 36 parquet shards (2026-07-18): 26 distinct
publication values appear (a 27th may not have surfaced in the sampled row groups).

Articles are inserted through the same insert_articles_batch() path the live
scraper uses (id = MD5 of URL), so re-runs and overlap with scraped/CC-NEWS articles
dedup automatically, and everything lands as analysis_status='unanalyzed' for
the batch analyzer to pick up.

PUBLICATION_MAP covers all 26 confirmed publications. Most (Vox, TMZ, Business
Insider, Vice, Hyperallergic, TechCrunch, Axios, Refinery 29, The Verge, Mashable,
Economist, Gizmodo, Wired, CNBC, The Hill, New Yorker, New Republic - all live-RSS-
confirmed 2026-07-18) were added to scrapers/news_sources.py for ongoing live
scraping too, plus 4 that were already tracked (CNN, Fox News, Politico, The New
York Times). Reuters and Washington Post are deliberately historical-only here -
docs/BLOCKED_SOURCES.md confirms both have hard, permanent live-scraping blocks, so
this backfill is the only way their content enters the corpus. Vice News, People,
and Buzzfeed News are also historical-only for now (no live feed found yet: Vice
News' RSS 404s, People and Buzzfeed News bot-block plain curl - worth revisiting
with a real browser session, not attempted here).

Loads one parquet shard at a time via huggingface_hub + pyarrow (not
datasets.load_dataset(..., streaming=True) - that stalled indefinitely on this
particular dataset's hosting, 2026-07-18; seed_from_ccnews.py's equivalent
streaming call is unaffected, this is specific to this dataset). Shards are
downloaded to a temporary directory and each is deleted as soon as it's been
scanned, so peak disk usage is one ~130MB shard, never the full ~5GB dataset.

Usage (see docs/SEEDING_AND_MODELS.md):
    python -m scrapers.seed_from_all_the_news --year 2020 --dry-run   # match rates only
    python -m scrapers.seed_from_all_the_news --year 2020 --limit 1000
    python -m scrapers.seed_from_all_the_news --self-test             # no deps, no network

Requires `pip install huggingface_hub pyarrow` (not in requirements.txt -
seeding is one-off, matching seed_from_ccnews.py's convention).
"""

import argparse
import hashlib

# publication name -> (source_name for our DB, country, language).
# source_name intentionally matches scrapers/news_sources.py's "name" field exactly
# for the 21 outlets tracked there, so seeded rows share the same NewsSource row
# (and source_id) as anything the live scraper picks up - no duplicate sources.
PUBLICATION_MAP = {
    "CNN": ("CNN", "USA", "en"),
    "Fox News": ("Fox News", "USA", "en"),
    "Politico": ("Politico", "USA", "en"),
    "The New York Times": ("The New York Times", "USA", "en"),
    "Vox": ("Vox", "USA", "en"),
    "TMZ": ("TMZ", "USA", "en"),
    "Business Insider": ("Business Insider", "USA", "en"),
    "Vice": ("Vice", "USA", "en"),
    "Hyperallergic": ("Hyperallergic", "USA", "en"),
    "TechCrunch": ("TechCrunch", "USA", "en"),
    "Axios": ("Axios", "USA", "en"),
    "Refinery 29": ("Refinery 29", "USA", "en"),
    "The Verge": ("The Verge", "USA", "en"),
    "Mashable": ("Mashable", "USA", "en"),
    "Economist": ("Economist", "UK", "en"),
    "Gizmodo": ("Gizmodo", "USA", "en"),
    "Wired": ("Wired", "USA", "en"),
    "CNBC": ("CNBC", "USA", "en"),
    "The Hill": ("The Hill", "USA", "en"),
    "New Yorker": ("New Yorker", "USA", "en"),
    "New Republic": ("New Republic", "USA", "en"),
    # Historical-only: no live RSS (Reuters/WaPo permanently blocked per
    # docs/BLOCKED_SOURCES.md; the other three just haven't been checked with a
    # real browser session yet). Because these aren't in scrapers/news_sources.py,
    # insert_articles_batch's country_mapping can't resolve them - ensure_sources()
    # pre-creates their NewsSource rows from this map so they don't get minted
    # with country='Unknown'.
    "Reuters": ("Reuters", "International", "en"),
    "Washington Post": ("Washington Post", "USA", "en"),
    "Vice News": ("Vice News", "USA", "en"),
    "People": ("People", "USA", "en"),
    "Buzzfeed News": ("Buzzfeed News", "USA", "en"),
}


def row_to_article(row: dict):
    """Convert an All The News 2.0 row to the article dict insert_articles_batch expects.

    Returns None if the row's publication isn't in PUBLICATION_MAP or lacks content.
    """
    pub = row.get("publication")
    matched = PUBLICATION_MAP.get(pub)
    if not matched:
        return None
    url = row.get("url") or ""
    text = row.get("article") or ""
    if not url or len(text) < 100 or not row.get("title"):
        return None
    source_name, _, language = matched
    return {
        "id": hashlib.md5(url.encode()).hexdigest(),
        "url": url,
        "title": row["title"],
        "text": text,
        "source_name": source_name,
        "publish_date": row.get("date"),
        "language": language,
        "authors": [row["author"]] if row.get("author") else None,
    }


def ensure_sources(db_manager):
    """Pre-create (or repair) NewsSource rows for every mapped publication.

    insert_articles_batch() resolves a new source's country via news_sources.py's
    country mapping and falls back to 'Unknown' - wrong for the historical-only
    publications (Reuters, Washington Post, ...) that exist only in
    PUBLICATION_MAP. Creating the rows here first, with this map's country and
    language, means insert_articles_batch finds them and never mints an
    'Unknown' row. Also repairs any 'Unknown' rows left by earlier runs.
    """
    from database.models import NewsSource

    session = db_manager.get_session()
    try:
        for source_name, country, language in sorted(set(PUBLICATION_MAP.values())):
            existing = session.query(NewsSource).filter_by(name=source_name).first()
            if existing is None:
                session.add(NewsSource(name=source_name, base_url="",
                                       country=country, language=language))
                print(f"Created source: {source_name} ({country})")
            elif existing.country in (None, "", "Unknown"):
                print(f"Repaired source country: {source_name} "
                      f"{existing.country!r} -> {country!r}")
                existing.country = country
        session.commit()
    finally:
        session.close()


def self_test():
    assert len(PUBLICATION_MAP) == 26, f"expected 26 mapped publications, got {len(PUBLICATION_MAP)}"

    row = {
        "publication": "Vox",
        "title": "Test headline",
        "article": "x" * 200,
        "url": "https://www.vox.com/2020/1/1/test",
        "date": "2020-01-01 00:00:00",
        "author": "A. Reporter",
    }
    art = row_to_article(row)
    assert art and art["source_name"] == "Vox", art
    assert art["id"] == hashlib.md5(row["url"].encode()).hexdigest()

    assert row_to_article({"publication": "Some Unrelated Blog", "title": "t",
                            "article": "x" * 200, "url": "https://example.com/x"}) is None
    assert row_to_article({"publication": "Vox", "title": "t",
                            "article": "too short", "url": "https://vox.com/x"}) is None
    print(f"self-test OK — {len(PUBLICATION_MAP)} publications mapped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2020, help="Filter to articles from this year (2016-2020)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after inserting this many articles")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count matches and report unmatched publications; no DB writes")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    # Heavy imports only when actually seeding.
    import os
    import tempfile
    from collections import Counter
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq
    from database.db import DatabaseManager
    from scrapers.scrape_to_db import insert_articles_batch

    db_manager = None if args.dry_run else DatabaseManager()
    if db_manager is not None:
        ensure_sources(db_manager)

    # This dataset's HF-hosted streaming endpoint (datasets.load_dataset(...,
    # streaming=True)) was found to stall indefinitely mid-scan (2026-07-18,
    # repeated "Bad file descriptor"/"Server disconnected" errors from the
    # underlying fsspec/httpx transport) - a problem specific to this dataset's
    # hosting, not seed_from_ccnews.py's equivalent streaming call. Downloading
    # each shard file directly and filtering locally with pyarrow proved reliable
    # and is what's used here instead. Each shard is ~75k rows / ~130MB - fine to
    # hold one at a time in memory. Shards land in a TemporaryDirectory (not the
    # global HF cache) and each file is removed as soon as it's been scanned, so
    # peak disk is one shard, never the full ~5GB - even on Ctrl-C, the tempdir
    # context manager cleans up whatever was left.
    repo_id = "rjac/all-the-news-2-1-Component-one"
    files = sorted(f for f in HfApi().list_repo_files(repo_id, repo_type="dataset")
                    if f.endswith(".parquet"))
    print(f"Scanning {repo_id} year={args.year} across {len(files)} shards; "
          f"matching {len(PUBLICATION_MAP)} publications; dry_run={args.dry_run}")

    matched, scanned, inserted = 0, 0, 0
    unmatched = Counter()
    batch = []
    with tempfile.TemporaryDirectory(prefix="atn_seed_") as tmpdir:
        for shard_num, shard_file in enumerate(files):
            local_path = hf_hub_download(repo_id, shard_file, repo_type="dataset",
                                         local_dir=tmpdir)
            table = pq.read_table(local_path, columns=["publication", "year", "title",
                                                         "article", "url", "date", "author"])
            os.remove(local_path)
            for row in table.to_pylist():
                scanned += 1
                # row["year"] comes through as a string (e.g. "2020"), not an int.
                try:
                    row_year = int(row.get("year"))
                except (TypeError, ValueError):
                    continue
                if row_year != args.year:
                    continue
                article = row_to_article(row)
                if article is None:
                    pub = row.get("publication")
                    if pub and pub not in PUBLICATION_MAP:
                        unmatched[pub] += 1
                    continue
                matched += 1
                if not args.dry_run:
                    batch.append(article)
                    if len(batch) >= args.batch_size:
                        inserted += insert_articles_batch(db_manager, batch)
                        batch = []
                if args.limit and matched >= args.limit:
                    break
            print(f"shard {shard_num + 1}/{len(files)}: scanned={scanned:,} "
                  f"matched={matched:,} inserted={inserted:,}")
            if args.limit and matched >= args.limit:
                break

    if batch:
        inserted += insert_articles_batch(db_manager, batch)

    print(f"\nDone. scanned={scanned:,} matched={matched:,} inserted={inserted:,}")
    if args.dry_run and unmatched:
        print("Unmatched publications seen (candidates for PUBLICATION_MAP):")
        for pub, count in unmatched.most_common(25):
            print(f"  {count:>8,}  {pub}")


if __name__ == "__main__":
    main()

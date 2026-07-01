"""
Seed the database with historical articles from CC-NEWS
(HuggingFace dataset: stanford-oval/ccnews, 2016–2024, full text, multilingual),
filtered to the news sources we already track in news_sources.py.

Articles are inserted through the same insert_articles_batch() path the live
scraper uses (id = MD5 of URL), so re-runs and overlap with scraped articles
dedup automatically, and everything lands as analysis_status='unanalyzed' for
the batch analyzer to pick up.

Usage (see docs/SEEDING_AND_MODELS.md):
    python -m scrapers.seed_from_ccnews --year 2023 --dry-run   # match rates only
    python -m scrapers.seed_from_ccnews --year 2023 --limit 10000
    python -m scrapers.seed_from_ccnews --self-test             # no deps, no network

Requires `pip install datasets` (not in requirements.txt — seeding is one-off).
"""

import argparse
import hashlib
import sys
from urllib.parse import urlparse

from scrapers.news_sources import get_news_sources

# Feed domains that differ from the domains articles are published on.
# ponytail: hand-curated for the big mismatches; run --dry-run and check the
# unmatched-domain report to grow this list (or swap in tldextract if needed).
DOMAIN_ALIASES = {
    "bbci.co.uk": ["bbc.co.uk", "bbc.com"],
    "cnn.com": ["cnn.com", "edition.cnn.com"],
}

# Multi-part public suffixes where "last two labels" isn't the site domain.
_TWO_LEVEL_SUFFIXES = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au",
                       "org.au", "co.jp", "or.jp", "ne.jp", "co.kr", "co.in",
                       "com.cn", "org.cn", "com.hk", "com.sg", "com.tr", "com.pk",
                       "com.br", "co.za", "co.nz", "co.il", "org.il"}


def registered_domain(url: str) -> str:
    """'https://feeds.bbci.co.uk/news/rss.xml' -> 'bbci.co.uk'"""
    host = urlparse(url).netloc.lower().split(":")[0]
    labels = [l for l in host.split(".") if l]
    if len(labels) < 2:
        return host
    if len(labels) >= 3 and ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def build_domain_map() -> dict:
    """Map article-site domain -> (source_name, language) for all configured sources."""
    domain_map = {}
    for source in get_news_sources():
        info = (source["name"], source.get("language", "en"))
        for feed in source.get("rss_feeds", []):
            feed_domain = registered_domain(feed)
            for site_domain in DOMAIN_ALIASES.get(feed_domain, [feed_domain]):
                domain_map[site_domain] = info
    return domain_map


def row_to_article(row: dict, domain_map: dict):
    """Convert a CC-NEWS row to the article dict insert_articles_batch expects.

    Returns None if the row's domain isn't one of our sources or lacks content.
    """
    url = row.get("requested_url") or ""
    matched = domain_map.get(registered_domain(url))
    if not matched:
        return None
    text = row.get("plain_text") or ""
    if len(text) < 100 or not row.get("title"):
        return None
    source_name, _ = matched
    return {
        "id": hashlib.md5(url.encode()).hexdigest(),
        "url": url,
        "title": row["title"],
        "text": text,
        "source_name": source_name,
        "publish_date": row.get("published_date"),
        "language": row.get("language") or "en",
        "authors": [row["author"]] if row.get("author") else None,
    }


def self_test():
    domain_map = build_domain_map()
    assert registered_domain("https://feeds.bbci.co.uk/news/rss.xml") == "bbci.co.uk"
    assert registered_domain("http://rss.cnn.com/rss/cnn_topstories.rss") == "cnn.com"
    assert "bbc.com" in domain_map and "cnn.com" in domain_map
    assert len(domain_map) > 100, f"only {len(domain_map)} domains mapped"

    row = {
        "requested_url": "https://www.bbc.com/news/world-12345",
        "title": "Test headline",
        "plain_text": "x" * 200,
        "published_date": "2023-05-01",
        "language": "en",
        "author": "A. Reporter",
    }
    art = row_to_article(row, domain_map)
    assert art and art["source_name"] == "BBC", art
    assert art["id"] == hashlib.md5(row["requested_url"].encode()).hexdigest()
    assert row_to_article({"requested_url": "https://unrelated-blog.example/x",
                           "title": "t", "plain_text": "x" * 200}, domain_map) is None
    print(f"self-test OK — {len(domain_map)} site domains mapped "
          f"from {len(get_news_sources())} sources")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", default="2023", help="CC-NEWS year config (2016-2024)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after inserting this many articles")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count matches and report unmatched domains; no DB writes")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    # Heavy imports only when actually seeding.
    from collections import Counter
    from datasets import load_dataset  # pip install datasets
    from database.db import DatabaseManager
    from scrapers.scrape_to_db import insert_articles_batch

    domain_map = build_domain_map()
    db_manager = None if args.dry_run else DatabaseManager()

    print(f"Streaming stanford-oval/ccnews year={args.year}; "
          f"matching {len(domain_map)} domains; dry_run={args.dry_run}")
    ds = load_dataset("stanford-oval/ccnews", args.year, streaming=True, split="train")

    matched, scanned, inserted = 0, 0, 0
    unmatched = Counter()
    batch = []
    for row in ds:
        scanned += 1
        article = row_to_article(row, domain_map)
        if article is None:
            if row.get("requested_url"):
                unmatched[registered_domain(row["requested_url"])] += 1
            continue
        matched += 1
        if not args.dry_run:
            batch.append(article)
            if len(batch) >= args.batch_size:
                inserted += insert_articles_batch(db_manager, batch)
                batch = []
        if scanned % 100_000 == 0:
            print(f"scanned={scanned:,} matched={matched:,} inserted={inserted:,}")
        if args.limit and matched >= args.limit:
            break

    if batch:
        inserted += insert_articles_batch(db_manager, batch)

    print(f"\nDone. scanned={scanned:,} matched={matched:,} inserted={inserted:,}")
    if args.dry_run:
        print("Top unmatched domains (candidates for DOMAIN_ALIASES):")
        for domain, count in unmatched.most_common(25):
            print(f"  {count:>8,}  {domain}")


if __name__ == "__main__":
    main()

"""
Export static JSON snapshots of the dashboard API for GitHub Pages.

Calls the live FastAPI handler functions directly with a DB session and dumps
their return values to files — the snapshot shapes therefore always match the
API shapes, with nothing duplicated.

Output layout (under --out, default frontend/public/snapshots/):
    meta.json                    {generated_at, most_recent_article_date, entity_count,
                                  hist_days, countries} — generated_at is snapshot build
                                  time; most_recent_article_date is the honest freshness
                                  signal (the two can diverge a lot if scraping stalls)
    entities.json                top-N entities (dashboard list + client-side search)
    sources.json                 all sources
    entity/{id}.json             {entity, distribution, historical: {days: ...},
                                  source_historical: {days: ...}}
    country/{Country}_{days}.json  top-entities page data

Run on the machine with the database:
    python -m server.export_snapshots --entities 200
Then commit frontend/public/snapshots/ so the Pages build ships it.

Logic self-test (stdlib only, no DB):
    python -m server.export_snapshots --self-test
"""

import argparse
import json
import os
from datetime import datetime, timezone

# Must mirror the frontend selectors (Dashboard.tsx time-range menu,
# CountryEntityPage.tsx availableCountries). The country endpoint caps days at 90.
HIST_DAYS = [7, 30, 90, 180, 365]
COUNTRY_DAYS = [7, 30, 90]
COUNTRIES = ["USA", "UK", "Canada", "Australia", "Germany",
             "France", "Japan", "Russia", "China", "India"]


def write_json(out_dir: str, rel_path: str, data) -> str:
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"), default=str)
    return path


def export_all(out_dir: str, n_entities: int, fetchers: dict) -> dict:
    """Drive the export given fetcher callables (injected so it's testable).

    fetchers: entities(limit), sources(), distribution(id), historical(id, days),
              source_historical(id, days), country_top(country, days),
              most_recent_article_date() — each returns a JSON-serializable value or
              raises to skip (most_recent_article_date raising just omits the field).
    """
    counts = {"entities": 0, "entity_files": 0, "country_files": 0, "skipped": 0}

    entities = fetchers["entities"](n_entities)
    write_json(out_dir, "entities.json", entities)
    write_json(out_dir, "sources.json", fetchers["sources"]())
    counts["entities"] = len(entities)

    for e in entities:
        eid = e["id"]
        bundle = {"entity": e, "historical": {}, "source_historical": {}}
        try:
            bundle["distribution"] = fetchers["distribution"](eid)
            for days in HIST_DAYS:
                bundle["historical"][str(days)] = fetchers["historical"](eid, days)
                bundle["source_historical"][str(days)] = fetchers["source_historical"](eid, days)
        except Exception as ex:
            print(f"  skip entity {eid} ({e.get('name')}): {ex}")
            counts["skipped"] += 1
            continue
        write_json(out_dir, f"entity/{eid}.json", bundle)
        counts["entity_files"] += 1

    for country in COUNTRIES:
        for days in COUNTRY_DAYS:
            try:
                data = fetchers["country_top"](country, days)
            except Exception as ex:
                print(f"  skip country {country}/{days}d: {ex}")
                counts["skipped"] += 1
                continue
            write_json(out_dir, f"country/{country}_{days}.json", data)
            counts["country_files"] += 1

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": counts["entities"],
        "hist_days": HIST_DAYS,
        "country_days": COUNTRY_DAYS,
        "countries": COUNTRIES,
    }
    try:
        # Distinct from generated_at (snapshot build time): the actual most recent
        # article date, so the frontend can honestly say "data current through X"
        # instead of implying the snapshot's build time reflects live data.
        meta["most_recent_article_date"] = fetchers["most_recent_article_date"]()
    except Exception as ex:
        print(f"  skip most_recent_article_date: {ex}")
    write_json(out_dir, "meta.json", meta)
    return counts


def live_fetchers(session):
    """Wrap the real API handlers. Imported lazily — needs the full server env."""
    import asyncio
    from fastapi.encoders import jsonable_encoder
    from sqlalchemy import func
    from database.models import NewsArticle
    from server.extension_api import (
        get_entities, get_sources, get_entity_distribution,
        get_historical_sentiment, get_source_historical_sentiment,
    )
    from server.routers.statistical_endpoints import get_country_top_entities

    def run(coro):
        return jsonable_encoder(asyncio.run(coro))

    def most_recent_article_date():
        ts = session.query(func.max(NewsArticle.scraped_at)).scalar()
        return ts.isoformat() if ts else None

    return {
        "entities": lambda limit: jsonable_encoder(
            get_entities(entity_type=None, search=None, limit=limit, db=session)),
        "sources": lambda: jsonable_encoder(get_sources(db=session)),
        "distribution": lambda eid: run(
            # days=None explicitly: called as a plain function, the FastAPI
            # Query default object would otherwise be passed through (truthy).
            get_entity_distribution(eid, country=None, source_id=None, days=None, db=session)),
        "historical": lambda eid, days: run(
            get_historical_sentiment(eid, days=days, db=session)),
        "source_historical": lambda eid, days: run(
            get_source_historical_sentiment(eid, days=days, countries=None, db=session)),
        "country_top": lambda country, days: run(
            get_country_top_entities(country, days=days, limit=10, session=session)),
        "most_recent_article_date": most_recent_article_date,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "public", "snapshots"))
    parser.add_argument("--entities", type=int, default=200)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    from database.db import DatabaseManager
    session = DatabaseManager().get_session()
    try:
        counts = export_all(args.out, args.entities, live_fetchers(session))
    finally:
        session.close()
    print(f"Exported to {args.out}: {counts}")


def self_test():
    import tempfile

    fake_entities = [{"id": 1, "name": "Ada", "type": "person", "mention_count": 9},
                     {"id": 2, "name": "Borg", "type": "org", "mention_count": 3}]
    fetchers = {
        "entities": lambda limit: fake_entities[:limit],
        "sources": lambda: [{"id": 5, "name": "Src", "country": "USA", "language": "en"}],
        "distribution": lambda eid: {"entity": {"id": eid}, "distributions": {}},
        "historical": lambda eid, days: {"daily_data": [], "days": days},
        "source_historical": lambda eid, days: (_ for _ in ()).throw(ValueError("no data"))
                             if eid == 2 else {"sources": {}, "days": days},
        "country_top": lambda country, days: {"country": country, "entities": [],
                                              "available_newspapers": [],
                                              "time_period_days": days}
                       if country != "India" else (_ for _ in ()).throw(ValueError("no data")),
        "most_recent_article_date": lambda: "2026-01-01T00:00:00+00:00",
    }

    with tempfile.TemporaryDirectory() as out:
        counts = export_all(out, 10, fetchers)
        assert counts["entities"] == 2
        assert counts["entity_files"] == 1          # entity 2 fails -> skipped whole bundle
        assert counts["country_files"] == 9 * len(COUNTRY_DAYS)
        assert counts["skipped"] == 1 + len(COUNTRY_DAYS)

        with open(os.path.join(out, "entity", "1.json")) as f:
            bundle = json.load(f)
        assert set(bundle) == {"entity", "distribution", "historical", "source_historical"}
        assert set(bundle["historical"]) == {str(d) for d in HIST_DAYS}
        assert bundle["historical"]["90"]["days"] == 90

        with open(os.path.join(out, "country", "USA_30.json")) as f:
            assert json.load(f)["time_period_days"] == 30
        assert not os.path.exists(os.path.join(out, "country", "India_30.json"))

        with open(os.path.join(out, "meta.json")) as f:
            meta = json.load(f)
        assert meta["entity_count"] == 2 and meta["hist_days"] == HIST_DAYS
        assert meta["most_recent_article_date"] == "2026-01-01T00:00:00+00:00"

    print("export_snapshots self-test OK")


if __name__ == "__main__":
    main()

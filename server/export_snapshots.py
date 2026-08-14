"""
Export static JSON snapshots of the dashboard API for GitHub Pages.

Calls the live FastAPI handler functions directly with a DB session and dumps
their return values to files — the snapshot shapes therefore always match the
API shapes, with nothing duplicated.

Output layout (under --out, default frontend/public/snapshots/):
    meta.json                    {format, generated_at, most_recent_article_date,
                                  entity_count, hist_days, countries} — generated_at is
                                  snapshot build time; most_recent_article_date is the
                                  honest freshness signal (the two can diverge a lot if
                                  scraping stalls)
    entities.json                top-N entities (dashboard list + client-side search)
    sources.json                 all sources
    entity/{id}.json             format 2: {format: 2, entity, distribution, base_days,
                                  historical, source_historical} where historical and
                                  source_historical are the single base_days(=365) API
                                  responses; the frontend (staticData.ts) slices shorter
                                  windows from the timestamped daily rows client-side.
                                  (Format 1 stored a full copy per window — 5x bloat.)
    country/{Country}_{days}.json  top-entities page data. Still one file per window:
                                  unlike the entity series, these are top-10 rankings
                                  *within* each window, so the windows genuinely differ.
    stats/trending_source_{id}.json  all-time trending scoped to one newspaper (the
                                  entity scatter's "By newspaper" overlay). Only
                                  written for sources with enough qualifying
                                  entities; meta.json's trending_sources lists the
                                  ids that exist, and the frontend clamps its
                                  newspaper picker to that list in static mode.
    stats/contested.json         cross-country contested ranking ("The front line"
                                  panel). One fixed 30-day moral-dimension file - the
                                  only shape the page requests.

All floats are rounded to 4 decimals on write (scores live on a -2..2 scale and the
UI shows 1-2 decimals; full float repr was pure bloat).

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
# EntityAnalysisPage asks for 40; export headroom so the page can grow.
TRENDING_LIMIT = 100
# A newspaper overlay with fewer entities than this can't say anything about
# divergence — skip the file and keep the paper out of the static-mode picker.
MIN_SOURCE_TRENDING = 5
# ContestedEntitiesPanel shows 8; same headroom reasoning.
CONTESTED_LIMIT = 20


def round_floats(o, ndigits: int = 4):
    if isinstance(o, float):
        return round(o, ndigits)
    if isinstance(o, dict):
        return {k: round_floats(v, ndigits) for k, v in o.items()}
    if isinstance(o, list):
        return [round_floats(v, ndigits) for v in o]
    return o


def write_json(out_dir: str, rel_path: str, data) -> str:
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(round_floats(data), f, separators=(",", ":"), default=str)
    return path


def export_all(out_dir: str, n_entities: int, fetchers: dict) -> dict:
    """Drive the export given fetcher callables (injected so it's testable).

    fetchers: entities(limit), sources(), distribution(id), historical(id, days),
              source_historical(id, days), country_top(country, days),
              trending(limit, country), trending_source(source_id), contested(),
              most_recent_article_date() —
              each returns a JSON-serializable value or raises to skip
              (most_recent_article_date raising just omits the field).
    """
    counts = {"entities": 0, "entity_files": 0, "country_files": 0,
              "trending_files": 0, "source_trending_files": 0,
              "contested_files": 0, "skipped": 0}

    entities = fetchers["entities"](n_entities)
    write_json(out_dir, "entities.json", entities)
    sources = fetchers["sources"]()
    write_json(out_dir, "sources.json", sources)
    counts["entities"] = len(entities)

    base_days = max(HIST_DAYS)
    for e in entities:
        eid = e["id"]
        # One base_days response each; staticData.ts derives shorter windows
        # from the timestamped daily rows (they're strict subsets).
        bundle = {"format": 2, "entity": e, "base_days": base_days}
        try:
            bundle["distribution"] = fetchers["distribution"](eid)
            bundle["historical"] = fetchers["historical"](eid, base_days)
            bundle["source_historical"] = fetchers["source_historical"](eid, base_days)
        except Exception as ex:
            print(f"  skip entity {eid} ({e.get('name')}): {ex}")
            counts["skipped"] += 1
            continue
        write_json(out_dir, f"entity/{eid}.json", bundle)
        counts["entity_files"] += 1

    # All-time trending (the entity scatter): one global file plus one per
    # snapshotted country. No days variants — the page only asks for all-time.
    for country in [None] + COUNTRIES:
        rel = f"stats/trending_{country or 'global'}.json"
        try:
            write_json(out_dir, rel, fetchers["trending"](TRENDING_LIMIT, country))
            counts["trending_files"] += 1
        except Exception as ex:
            print(f"  skip {rel}: {ex}")
            counts["skipped"] += 1

    # Per-newspaper trending (the scatter's "By newspaper" overlay). Most of the
    # ~150 configured sources are dead or thin — only papers that clear
    # MIN_SOURCE_TRENDING get a file, and meta.trending_sources is the picker's
    # source of truth for which those are. Thin sources are expected, not
    # errors, so they aren't counted as skips (a fetcher raising still is).
    trending_source_ids = []
    for s in sources:
        sid = s["id"]
        try:
            rows = fetchers["trending_source"](sid)
        except Exception as ex:
            print(f"  skip stats/trending_source_{sid}.json ({s.get('name')}): {ex}")
            counts["skipped"] += 1
            continue
        if len(rows) < MIN_SOURCE_TRENDING:
            continue
        write_json(out_dir, f"stats/trending_source_{sid}.json", rows)
        trending_source_ids.append(sid)
        counts["source_trending_files"] += 1

    try:
        write_json(out_dir, "stats/contested.json", fetchers["contested"]())
        counts["contested_files"] = 1
    except Exception as ex:
        print(f"  skip stats/contested.json: {ex}")
        counts["skipped"] += 1

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
        "format": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": counts["entities"],
        "hist_days": HIST_DAYS,
        "country_days": COUNTRY_DAYS,
        "countries": COUNTRIES,
        "trending_sources": trending_source_ids,
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
        get_trending_entities,
    )
    from server.routers.statistical_endpoints import get_country_top_entities
    from server.routers.narrative_endpoints import get_contested_ranking

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
        "trending": lambda limit, country: run(
            # days=None: all-time, matching the page's calls.
            get_trending_entities(limit=limit, days=None, country=country,
                                  source_id=None, db=session)),
        "trending_source": lambda sid: run(
            get_trending_entities(limit=TRENDING_LIMIT, days=None, country=None,
                                  source_id=sid, db=session)),
        "contested": lambda: run(
            get_contested_ranking(days=30, dimension="moral",
                                  limit=CONTESTED_LIMIT, session=session)),
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
        "sources": lambda: [
            {"id": 5, "name": "Src", "country": "USA", "language": "en"},
            {"id": 6, "name": "Thin", "country": "USA", "language": "en"},
            {"id": 7, "name": "Broken", "country": "USA", "language": "en"}],
        "distribution": lambda eid: {"entity": {"id": eid}, "distributions": {}},
        "historical": lambda eid, days: {
            "daily_data": [{"date": "2026-01-01", "power_score": 1.23456789}], "days": days},
        "source_historical": lambda eid, days: (_ for _ in ()).throw(ValueError("no data"))
                             if eid == 2 else {"sources": {}, "days": days},
        "country_top": lambda country, days: {"country": country, "entities": [],
                                              "available_newspapers": [],
                                              "time_period_days": days}
                       if country != "India" else (_ for _ in ()).throw(ValueError("no data")),
        "trending": lambda limit, country: (_ for _ in ()).throw(ValueError("no data"))
                    if country == "India" else [{"id": 1, "entity": "Ada", "type": "person",
                                                 "power_score": 1.0, "moral_score": 0.5,
                                                 "mention_count": 9}][:limit],
        # id 5 clears MIN_SOURCE_TRENDING, id 6 is thin (silently no file),
        # id 7 raises (counted as a skip).
        "trending_source": lambda sid: (_ for _ in ()).throw(ValueError("boom"))
                           if sid == 7 else
                           [{"id": i, "entity": f"E{i}", "type": "person",
                             "power_score": 0.5, "moral_score": -0.5,
                             "mention_count": 3}
                            for i in range(MIN_SOURCE_TRENDING if sid == 5 else 2)],
        "contested": lambda: {"days": 30, "dimension": "moral",
                              "entities": [{"entity_name": "Ada",
                                            "divergence": 0.55555555}]},
        "most_recent_article_date": lambda: "2026-01-01T00:00:00+00:00",
    }

    with tempfile.TemporaryDirectory() as out:
        counts = export_all(out, 10, fetchers)
        assert counts["entities"] == 2
        assert counts["entity_files"] == 1          # entity 2 fails -> skipped whole bundle
        assert counts["country_files"] == 9 * len(COUNTRY_DAYS)
        assert counts["trending_files"] == len(COUNTRIES)  # global + 9 (India fails)
        assert counts["source_trending_files"] == 1        # 5 written, 6 thin, 7 raises
        assert counts["skipped"] == 1 + len(COUNTRY_DAYS) + 1 + 1

        with open(os.path.join(out, "entity", "1.json")) as f:
            bundle = json.load(f)
        assert set(bundle) == {"format", "entity", "base_days",
                               "distribution", "historical", "source_historical"}
        assert bundle["format"] == 2 and bundle["base_days"] == max(HIST_DAYS)
        assert bundle["historical"]["days"] == max(HIST_DAYS)
        assert bundle["historical"]["daily_data"][0]["power_score"] == 1.2346  # rounded

        with open(os.path.join(out, "country", "USA_30.json")) as f:
            assert json.load(f)["time_period_days"] == 30
        assert not os.path.exists(os.path.join(out, "country", "India_30.json"))

        with open(os.path.join(out, "stats", "trending_global.json")) as f:
            assert json.load(f)[0]["entity"] == "Ada"
        assert os.path.exists(os.path.join(out, "stats", "trending_USA.json"))
        assert not os.path.exists(os.path.join(out, "stats", "trending_India.json"))

        assert os.path.exists(os.path.join(out, "stats", "trending_source_5.json"))
        assert not os.path.exists(os.path.join(out, "stats", "trending_source_6.json"))
        assert not os.path.exists(os.path.join(out, "stats", "trending_source_7.json"))

        assert counts["contested_files"] == 1
        with open(os.path.join(out, "stats", "contested.json")) as f:
            contested = json.load(f)
        assert contested["entities"][0]["divergence"] == 0.5556  # rounded

        with open(os.path.join(out, "meta.json")) as f:
            meta = json.load(f)
        assert meta["entity_count"] == 2 and meta["hist_days"] == HIST_DAYS
        assert meta["format"] == 2
        assert meta["trending_sources"] == [5]
        assert meta["most_recent_article_date"] == "2026-01-01T00:00:00+00:00"

    print("export_snapshots self-test OK")


if __name__ == "__main__":
    main()

"""
Export static JSON snapshots of the dashboard API for GitHub Pages.

Calls the live FastAPI handler functions directly with a DB session and dumps
their return values to files — the snapshot shapes therefore always match the
API shapes, with nothing duplicated.

Output layout (under --out, default frontend/public/snapshots/):
    meta.json                    {format, generated_at, most_recent_article_date,
                                  most_recent_analysis_date, entity_count, hist_days,
                                  countries} — generated_at is snapshot build time;
                                  most_recent_article_date is the honest freshness signal
                                  (the two can diverge a lot if scraping stalls);
                                  most_recent_analysis_date is the newest COMPLETED
                                  article (scraping can be fine while analysis stalls —
                                  the Aug 27–Sep 2 2026 OpenAI outage was invisible to
                                  the article date)
    entities.json                top-N entities (dashboard list + client-side search)
    sources.json                 all sources
    entity/{id}.json             format 2: {format: 2, entity, distribution, base_days,
                                  historical, source_historical} where historical and
                                  source_historical are the single base_days(=365) API
                                  responses; the frontend (staticData.ts) slices shorter
                                  windows from the timestamped daily rows client-side.
                                  (Format 1 stored a full copy per window — 5x bloat.)
                                  Bundles may also carry national_distributions:
                                  {country: national-layer} for snapshotted countries
                                  with >= MIN_NATIONAL_MENTIONS scored mentions — the
                                  source page's country-baseline distribution overlay —
                                  and source_scatter: the fixed 4-week per-source
                                  scatter response (every source's reading of this
                                  entity, current + previous window) for the entity
                                  page's per-source drift scatter, plus
                                  source_scatter_all: the weeks=0 all-time variant
                                  (averages only, empty previous window) — that
                                  panel's no-drift default view. Bundles also
                                  carry archetype ({global, countries:{C:...}} —
                                  the weeks=12 trajectory responses), related
                                  ({cooccurrence, sentiment} neighbor lists),
                                  and drift ({moral, power} changepoint
                                  responses) — the three entity-page panels
                                  that used to be live-API only.
    receipts/{id}.json           per-entity receipts (the evidence drawer): each
                                  source's most recent scored mentions of the
                                  entity — headline, url, publish date, both
                                  scores, matched sentence when the
                                  pre-2026-08-14 schema captured one. Fetched
                                  lazily when a drawer opens, never part of the
                                  initial page payload.
    source/{id}.json             per-newspaper bundle for the source profile page:
                                  {format: 1, source, base_days, entities} where each
                                  entity row is the paper's trending row plus its
                                  sentiment PDFs (distribution) and daily series
                                  (daily) from this paper's mentions only. Written for
                                  exactly the meta.trending_sources set.
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
    stats/drift_feed.json        {moral, power}: the precomputed drift feed
                                  (entity_drift_events, scope=all, limit 100) for
                                  the Shifts page's seismograph + table; the
                                  frontend filters scope and slices limit
                                  client-side.
    stats/symbols.json           the symbol watchlist ranked by contestation
                                  (the Symbols page) — every tracked symbol,
                                  including ones with no mentions yet.
    stats/similarity_matrix.json the latest stored weekly source-similarity matrix +
                                  cluster assignments (the Source Space page's
                                  constellations; neighbors are derived client-side
                                  from the pairs in static mode).
    stats/source_map.json        the MDS source map (one fixed 4-week moral file -
                                  the only shape the panel requests).
    stats/global_agenda.json     entities ranked by country breadth (the shared
                                  international agenda panel).
    stats/source_vectors.json    per-source entity score vectors over the matrix
                                  window, entities covered by >= 2 sources - the
                                  client intersects two sources' vectors to draw
                                  any pair scatter without n-squared pair files.
    stats/dividing_lines.json    per-cluster mean scores for the entities that
                                  best separate the constellations (the
                                  "dividing lines" panel).

All floats are rounded to 4 decimals on write (scores live on a -2..2 scale and the
UI shows 1-2 decimals; full float repr was pure bloat).

After a successful export, .json files under the managed subdirs (entity/,
receipts/, source/, country/, stats/) that this run did NOT write are deleted:
--out is reused across runs, so an entity that falls out of the top-N or a
paper that drops below the trending floor would otherwise keep serving a
snapshot that silently ages forever (rsync --delete in the daily cron then
propagates the removal to Pages).

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

from server.json_rounding import round_floats

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
# The source profile page's grid shows a paper's top 20; the bundle bakes
# distributions + daily series for exactly that set.
SOURCE_BUNDLE_ENTITIES = 20
# A national KDE over fewer mentions than this is shape-noise — prune the layer.
MIN_NATIONAL_MENTIONS = 5
# ContestedEntitiesPanel shows 8; same headroom reasoning.
CONTESTED_LIMIT = 20
# Receipts: the drawer shows each paper's most recent scored mentions. 5 per
# paper keeps a 99-source entity's file under ~100KB; the window matches
# base_days so a receipt always falls inside the charts it's evidence for.
RECEIPTS_PER_SOURCE = 5
# GlobalAgendaPanel shows 15; same headroom reasoning.
AGENDA_LIMIT = 100


def write_json(out_dir: str, rel_path: str, data) -> str:
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        # ensure_ascii=False: \uXXXX-escaping non-Latin text (Arabic/Japanese
        # headlines in receipts, accented names) inflated files ~6x for those
        # strings; JSON is UTF-8 by spec and fetch()/res.json() handle it.
        json.dump(round_floats(data), f, separators=(",", ":"), default=str,
                  ensure_ascii=False)
    return path


# Subdirs the exporter owns outright — prune_stale never looks anywhere else,
# so a hand-placed file at the snapshot root (or a new unmanaged dir) survives.
MANAGED_SUBDIRS = ("entity", "receipts", "source", "country", "stats")


def prune_stale(out_dir: str, written: set) -> int:
    """Delete managed .json files this run didn't write. See module docstring."""
    removed = 0
    for sub in MANAGED_SUBDIRS:
        for dirpath, _dirs, files in os.walk(os.path.join(out_dir, sub)):
            for name in files:
                path = os.path.join(dirpath, name)
                if name.endswith(".json") and path not in written:
                    os.remove(path)
                    removed += 1
    return removed


def export_all(out_dir: str, n_entities: int, fetchers: dict) -> dict:
    """Drive the export given fetcher callables (injected so it's testable).

    fetchers: entities(limit), sources(), distribution(id), historical(id, days),
              source_historical(id, days), country_top(country, days),
              trending(limit, country), trending_source(source_id), contested(),
              national_distribution(id, country) -> national layer or None,
              source_distribution(id, source_id) -> source layer or None,
              source_historical_country(id, days, country) -> the per-source
              response for that country (the countries=[C] endpoint branch),
              source_scatter(id) -> the per-source scatter response,
              source_scatter_all(id) -> its weeks=0 all-time variant,
              most_recent_article_date() —
              each returns a JSON-serializable value or raises to skip
              (most_recent_article_date raising just omits the field).
    """
    counts = {"entities": 0, "entity_files": 0, "receipt_files": 0,
              "country_files": 0,
              "trending_files": 0, "source_trending_files": 0,
              "source_bundles": 0, "national_layers": 0, "source_scatters": 0,
              "source_scatters_all": 0, "archetypes": 0, "related": 0,
              "drifts": 0,
              "contested_files": 0, "drift_feed_files": 0, "symbol_files": 0,
              "source_space_files": 0, "skipped": 0,
              "pruned": 0}
    # Every path written this run — the survivors' list prune_stale works from.
    written: set = set()

    def emit(rel_path: str, data):
        written.add(write_json(out_dir, rel_path, data))

    entities = fetchers["entities"](n_entities)
    emit("entities.json", entities)
    sources = fetchers["sources"]()
    emit("sources.json", sources)
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
        # Per-country sentiment PDFs (the source page's country-baseline curve).
        # Thin or absent coverage is expected for most entity x country pairs —
        # prune those silently; counts["national_layers"] in the summary line is
        # the tell if the fetcher is broken outright (it would read 0).
        national = {}
        for country in COUNTRIES:
            try:
                layer = fetchers["national_distribution"](eid, country)
            except Exception:
                continue
            if layer and layer.get("power", {}).get("count", 0) >= MIN_NATIONAL_MENTIONS:
                national[country] = layer
                counts["national_layers"] += 1
        if national:
            bundle["national_distributions"] = national
        # Per-source scatter (fixed 4-week + previous window). Degrades to an
        # absent key — the frontend panel shows its empty state, the bundle's
        # other pieces still ship. counts["source_scatters"] reading 0 in the
        # summary line is the tell if the fetcher is broken outright.
        try:
            bundle["source_scatter"] = fetchers["source_scatter"](eid)
            counts["source_scatters"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no source_scatter: {ex}")
        # weeks=0 all-time variant: the panel's default averages-only view.
        try:
            bundle["source_scatter_all"] = fetchers["source_scatter_all"](eid)
            counts["source_scatters_all"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no source_scatter_all: {ex}")
        # Archetype trajectory: the panel's one request shape (weeks=12),
        # global plus each snapshotted country that has a path to draw (an
        # absent country reads as "no scored coverage" in the panel, same as
        # the live endpoint's empty trajectory).
        try:
            arch = {"global": fetchers["archetype"](eid, None)}
            arch_countries = {}
            for country in COUNTRIES:
                try:
                    c = fetchers["archetype"](eid, country)
                except Exception:
                    continue
                if c.get("trajectory"):
                    arch_countries[country] = c
            if arch_countries:
                arch["countries"] = arch_countries
            bundle["archetype"] = arch
            counts["archetypes"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no archetype: {ex}")
        # Related entities: both vectors' neighbor lists. Baked even when empty
        # (the panel's "not enough mention volume" state needs the response).
        try:
            bundle["related"] = {
                "cooccurrence": fetchers["related"](eid, "cooccurrence"),
                "sentiment": fetchers["related"](eid, "sentiment"),
            }
            counts["related"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no related: {ex}")
        # Statistical surprise: both dimensions' changepoint responses.
        try:
            bundle["drift"] = {
                "moral": fetchers["entity_drift"](eid, "moral"),
                "power": fetchers["entity_drift"](eid, "power"),
            }
            counts["drifts"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no drift: {ex}")
        emit(f"entity/{eid}.json", bundle)
        counts["entity_files"] += 1
        # Receipts (the evidence drawer) live in their own lazily-fetched file
        # so they never weigh down the bundle; a failure degrades to the
        # drawer's own "no receipts snapshot" state, not a missing bundle.
        try:
            emit(f"receipts/{eid}.json", fetchers["receipts"](eid))
            counts["receipt_files"] += 1
        except Exception as ex:
            print(f"  entity {eid}: no receipts: {ex}")

    # All-time trending (the entity scatter): one global file plus one per
    # snapshotted country. No days variants — the page only asks for all-time.
    for country in [None] + COUNTRIES:
        rel = f"stats/trending_{country or 'global'}.json"
        try:
            emit(rel, fetchers["trending"](TRENDING_LIMIT, country))
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
    # (entity_id, country) -> per-source historical response. Papers from the
    # same country covering the same entity share one query, not one each.
    source_hist_cache: dict = {}
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
        emit(f"stats/trending_source_{sid}.json", rows)
        trending_source_ids.append(sid)
        counts["source_trending_files"] += 1

        # Source bundle: this paper's top entities with its own sentiment PDFs
        # and daily series (the source profile page's distribution overlay and
        # history line). Missing pieces degrade per entity, never the bundle.
        hist_key = f"{s['name']} ({s['country']})"
        bundle_entities = []
        for row in rows[:SOURCE_BUNDLE_ENTITIES]:
            ent = dict(row)
            try:
                dist = fetchers["source_distribution"](row["id"], sid)
                if dist:
                    ent["distribution"] = dist
            except Exception as ex:
                print(f"  source {sid}: no distribution for entity {row['id']}: {ex}")
            cache_key = (row["id"], s["country"])
            if cache_key not in source_hist_cache:
                try:
                    source_hist_cache[cache_key] = fetchers["source_historical_country"](
                        row["id"], base_days, s["country"])
                except Exception:
                    source_hist_cache[cache_key] = None
            hist = source_hist_cache[cache_key]
            daily = (((hist or {}).get("sources") or {}).get(hist_key) or {}).get("daily_data")
            if daily:
                ent["daily"] = daily
            bundle_entities.append(ent)
        emit(f"source/{sid}.json",
             {"format": 1, "source": s, "base_days": base_days,
              "entities": bundle_entities})
        counts["source_bundles"] += 1

    try:
        emit("stats/contested.json", fetchers["contested"]())
        counts["contested_files"] = 1
    except Exception as ex:
        print(f"  skip stats/contested.json: {ex}")
        counts["skipped"] += 1

    # The Shifts page: both dimensions of the precomputed drift feed in one
    # file. Near-empty until ~8 corpus weeks accrue — the page owns that copy.
    try:
        emit("stats/drift_feed.json", {
            "moral": fetchers["drift_feed"]("moral"),
            "power": fetchers["drift_feed"]("power"),
        })
        counts["drift_feed_files"] = 1
    except Exception as ex:
        print(f"  skip stats/drift_feed.json: {ex}")
        counts["skipped"] += 1

    # The Symbols page: the watchlist ranked by contestation.
    try:
        emit("stats/symbols.json", fetchers["symbols"]())
        counts["symbol_files"] = 1
    except Exception as ex:
        print(f"  skip stats/symbols.json: {ex}")
        counts["skipped"] += 1

    # The Source Space page: constellations + seriation (stored weekly matrix),
    # the MDS map, the shared international agenda, and the per-source entity
    # vectors the pair scatter intersects client-side. Independent files - one
    # failing (e.g. the weekly job hasn't populated the matrix yet) doesn't
    # take the others.
    for key in ("similarity_matrix", "source_map", "global_agenda",
                "source_vectors", "dividing_lines"):
        rel = f"stats/{key}.json"
        try:
            emit(rel, fetchers[key]())
            counts["source_space_files"] += 1
        except Exception as ex:
            print(f"  skip {rel}: {ex}")
            counts["skipped"] += 1

    for country in COUNTRIES:
        for days in COUNTRY_DAYS:
            try:
                data = fetchers["country_top"](country, days)
            except Exception as ex:
                print(f"  skip country {country}/{days}d: {ex}")
                counts["skipped"] += 1
                continue
            emit(f"country/{country}_{days}.json", data)
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
    try:
        # Scraping and analysis fail independently: articles kept arriving all
        # through the Aug 27-Sep 2 2026 OpenAI batch outage while sentiment data
        # flatlined. This is the signal the staleness banner needs for that case.
        meta["most_recent_analysis_date"] = fetchers["most_recent_analysis_date"]()
    except Exception as ex:
        print(f"  skip most_recent_analysis_date: {ex}")
    emit("meta.json", meta)
    counts["pruned"] = prune_stale(out_dir, written)
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
    from server.routers.narrative_endpoints import (
        get_contested_ranking, get_source_map, get_global_agenda,
        get_entity_source_scatter, get_entity_receipts, get_entity_archetype,
        get_symbols,
    )
    from server.routers.embeddings_endpoints import get_related_entities
    from server.routers.drift_endpoints import get_entity_drift, get_drift_feed
    from server.routers.similarity_endpoints import (
        get_similarity_matrix, get_dividing_lines,
    )
    from clustering.source_similarity import compute_source_vectors

    def run(coro):
        return jsonable_encoder(asyncio.run(coro))

    def most_recent_article_date():
        ts = session.query(func.max(NewsArticle.scraped_at)).scalar()
        return ts.isoformat() if ts else None

    def most_recent_analysis_date():
        ts = (session.query(func.max(NewsArticle.scraped_at))
              .filter(NewsArticle.analysis_status == 'completed').scalar())
        return ts.isoformat() if ts else None

    return {
        "entities": lambda limit: jsonable_encoder(
            get_entities(entity_type=None, search=None, limit=limit, db=session)),
        "sources": lambda: jsonable_encoder(get_sources(db=session)),
        "distribution": lambda eid: run(
            # days/layers=None explicitly: called as a plain function, the FastAPI
            # Query default objects would otherwise be passed through (truthy).
            get_entity_distribution(eid, country=None, source_id=None, days=None,
                                    layers=None, db=session)),
        "historical": lambda eid, days: run(
            get_historical_sentiment(eid, days=days, db=session)),
        "source_historical": lambda eid, days: run(
            get_source_historical_sentiment(eid, days=days, countries=None, db=session)),
        "country_top": lambda country, days: run(
            # limit=20 (the endpoint's cap), matching CountryEntityPage: the
            # entities split between the divergence and consensus panels.
            get_country_top_entities(country, days=days, limit=20, session=session)),
        "trending": lambda limit, country: run(
            # days=None: all-time, matching the page's calls. Scoped (country)
            # files union in the sphere's readings of the global top so every
            # global baseline dot can find its overlay partner; the global file
            # needs no union with itself. All args explicit — Query-default trap.
            get_trending_entities(limit=limit, days=None, country=country,
                                  source_id=None,
                                  include_global_top=(limit if country else 0),
                                  db=session)),
        "trending_source": lambda sid: run(
            get_trending_entities(limit=TRENDING_LIMIT, days=None, country=None,
                                  source_id=sid,
                                  include_global_top=TRENDING_LIMIT, db=session)),
        # layers= restricts the SQL fetch to the one subset asked for — without it
        # every call below would pull all of an entity's mentions and KDE a global
        # layer nobody uses.
        "national_distribution": lambda eid, country: run(
            get_entity_distribution(eid, country=country, source_id=None, days=None,
                                    layers="national", db=session)
            ).get("distributions", {}).get("national"),
        "source_distribution": lambda eid, sid: run(
            get_entity_distribution(eid, country=None, source_id=sid, days=None,
                                    layers="source", db=session)
            ).get("distributions", {}).get("source"),
        "source_historical_country": lambda eid, days, country: run(
            get_source_historical_sentiment(eid, days=days, countries=[country],
                                            db=session)),
        # weeks explicit — the same FastAPI Query-default trap as above. 4 weeks
        # matches the frontend panel's only request shape.
        "source_scatter": lambda eid: run(
            get_entity_source_scatter(eid, weeks=4, session=session)),
        "source_scatter_all": lambda eid: run(
            get_entity_source_scatter(eid, weeks=0, session=session)),
        # days matches base_days — all args explicit (Query-default trap).
        "receipts": lambda eid: run(
            get_entity_receipts(eid, days=max(HIST_DAYS),
                                per_source=RECEIPTS_PER_SOURCE, session=session)),
        # weeks=12 matches ArchetypeQuadrantPanel's only request shape.
        "archetype": lambda eid, country: run(
            get_entity_archetype(eid, weeks=12, country=country, session=session)),
        # limit=10 matches RelatedEntitiesPanel's only request shape.
        "related": lambda eid, vector: run(
            get_related_entities(eid, vector=vector, limit=10, session=session)),
        "entity_drift": lambda eid, dimension: run(
            get_entity_drift(eid, dimension=dimension, session=session)),
        # limit=100: the Shifts page shows everything; scope filtering is
        # client-side. All args explicit — the Query-default trap.
        "drift_feed": lambda dimension: run(
            get_drift_feed(dimension=dimension, limit=100, scope="all",
                           session=session)),
        "symbols": lambda: run(get_symbols(days=max(HIST_DAYS), session=session)),
        "contested": lambda: run(
            get_contested_ranking(days=30, dimension="moral",
                                  limit=CONTESTED_LIMIT, session=session)),
        # All args explicit - the same FastAPI Query-default trap as above.
        "similarity_matrix": lambda: run(get_similarity_matrix(session=session)),
        "source_map": lambda: run(
            get_source_map(weeks=4, dimension="moral", session=session)),
        "global_agenda": lambda: run(
            get_global_agenda(weeks=4, limit=AGENDA_LIMIT, session=session)),
        "source_vectors": lambda: compute_source_vectors(session),
        "dividing_lines": lambda: run(
            get_dividing_lines(weeks=4, dimension="moral", limit=20,
                               session=session)),
        "most_recent_article_date": most_recent_article_date,
        "most_recent_analysis_date": most_recent_analysis_date,
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
        # matrix + agenda write; the map raises (weekly job not run yet) and
        # must be counted as a skip without taking the other two with it.
        "similarity_matrix": lambda: {
            "window_start": "2026-01-01", "window_end": "2026-01-28",
            "sources": [{"source_id": 5, "name": "Src", "country": "USA",
                         "cluster": "2026-01-26-C0", "is_centroid": True}],
            "pairs": [{"source_id_1": 5, "source_id_2": 6,
                       "score": 0.83333333, "common_entities": 41}]},
        "source_map": lambda: (_ for _ in ()).throw(ValueError("matrix empty")),
        "source_vectors": lambda: {
            "window_start": "2026-01-01", "window_end": "2026-01-28",
            "dimension": "moral",
            "entities": {"1": "Ada"},
            "sources": {"5": {"1": [0.5, 3]}, "6": {"1": [-0.25, 2]}}},
        "global_agenda": lambda: {
            "window_start": "2026-01-01", "window_end": "2026-01-28", "weeks": 4,
            "total_entities": 100, "international_entities": 7,
            "entities": [{"entity_id": 1, "name": "Ada", "type": "person",
                          "countries": 12, "sources": 30, "mentions": 400,
                          "mean_moral": 0.12345678, "mean_power": 0.5}]},
        "dividing_lines": lambda: {
            "window_start": "2026-01-01", "window_end": "2026-01-28",
            "dimension": "moral",
            "groups": [{"cluster_id": "w-C0", "label": "Group 1", "size": 3,
                        "centroid": "Src"}],
            "entities": [{"entity_id": 1, "name": "Ada", "f": 9.1,
                          "spread": 2.5, "means": [0.5, None],
                          "support": [3, 0]}]},
        # USA clears MIN_NATIONAL_MENTIONS, UK is thin (pruned), the rest raise
        # (swallowed — thin coverage is expected, not an export error).
        "national_distribution": lambda eid, country:
            {"country": country,
             "power": {"count": 9 if country == "USA" else 2, "mean": 0.1},
             "moral": {"count": 9 if country == "USA" else 2, "mean": 0.2}}
            if country in ("USA", "UK") else (_ for _ in ()).throw(ValueError("thin")),
        "source_distribution": lambda eid, sid:
            {"source_id": sid, "source_name": "Src",
             "power": {"count": 3, "mean": 0.5}, "moral": {"count": 3, "mean": -0.5}},
        "source_historical_country": lambda eid, days, country:
            {"sources": {"Src (USA)": {"daily_data": [
                {"date": "2026-01-01", "power_score": 0.5,
                 "moral_score": -0.5, "mention_count": 3}]}}},
        "source_scatter": lambda eid: {
            "entity_id": eid, "entity_name": "Ada", "weeks": 4,
            "current": {"start": "2026-01-05", "end": "2026-02-01",
                        "sources": [{"source_id": 5, "source_name": "Src",
                                     "country": "USA",
                                     "power_score": 0.12345678,
                                     "moral_score": -0.5, "mention_count": 7}]},
            "previous": {"start": "2025-12-08", "end": "2026-01-04",
                         "sources": []}},
        "source_scatter_all": lambda eid: {
            "entity_id": eid, "entity_name": "Ada", "weeks": 0,
            "current": {"start": "2025-06-02", "end": "2026-02-01",
                        "sources": [{"source_id": 5, "source_name": "Src",
                                     "country": "USA",
                                     "power_score": 0.25,
                                     "moral_score": -0.5, "mention_count": 30}]},
            "previous": {"start": None, "end": None, "sources": []}},
        "receipts": lambda eid: {
            "entity_id": eid, "entity_name": "Ada", "days": 365, "per_source": 5,
            "sources": {"5": [{"title": "Ada wins", "url": "https://x/a",
                               "date": "2026-01-01", "power_score": 1.23456789,
                               "moral_score": 0.5, "sentence": "Ada won."}]}},
        # Global + USA have a path, UK has none (pruned), the rest raise
        # (swallowed — thin coverage is expected, not an export error).
        "archetype": lambda eid, country: (
            {"entity_id": eid, "entity_name": "Ada", "current_archetype": "hero",
             "power": 0.5, "moral": 0.5,
             "trajectory": [{"window_index": 0, "power": 0.5, "moral": 0.55555555}]}
            if country in (None, "USA") else
            {"entity_id": eid, "entity_name": "Ada", "current_archetype": "neutral",
             "power": 0.0, "moral": 0.0, "trajectory": None}
            if country == "UK" else (_ for _ in ()).throw(ValueError("thin"))),
        "related": lambda eid, vector: {
            "entity_id": eid, "entity_name": "Ada", "vector": vector,
            "neighbors": [{"entity_id": 2, "entity_name": "Borg",
                           "similarity": 0.98765432}]},
        "entity_drift": lambda eid, dimension: {
            "entity_id": eid, "entity_name": "Ada", "dimension": dimension,
            "weeks_observed": 9, "global_shift": None,
            "source_shifts": [{"source_id": 5, "source_name": "Src",
                               "week_start": "2026-01-12", "statistic": 30.0,
                               "p_value": 0.01234567, "mean_before": 0.1,
                               "mean_after": -0.4}]},
        "drift_feed": lambda dimension: {
            "dimension": dimension,
            "events": [{"entity_id": 1, "entity_name": "Ada", "source_id": 5,
                        "source_name": "Src", "dimension": dimension,
                        "week_start": "2026-01-12", "statistic": 30.0,
                        "p_value": 0.00123456, "mean_before": 0.1,
                        "mean_after": -0.4}]},
        "symbols": lambda: {
            "tracked_since": "2026-09-06", "days": 365,
            "symbols": [{"name": "The West", "entity_id": 7, "mention_count": 40,
                         "countries": 6, "mean_power": 0.5, "mean_moral": -0.3,
                         "divergence": 0.44444444}]},
        "most_recent_article_date": lambda: "2026-01-01T00:00:00+00:00",
        "most_recent_analysis_date": lambda: "2025-12-30T00:00:00+00:00",
    }

    with tempfile.TemporaryDirectory() as out:
        # Leftovers from a previous run into the same --out: managed .json
        # files must be pruned; a non-json file and root-level files survive.
        for stale in ("entity/999.json", "receipts/999.json",
                      "stats/trending_source_9.json"):
            write_json(out, stale, {"stale": True})
        write_json(out, "root_extra.json", {"unmanaged": True})
        with open(os.path.join(out, "entity", "notes.txt"), "w") as f:
            f.write("keep")

        counts = export_all(out, 10, fetchers)
        assert counts["entities"] == 2
        assert counts["entity_files"] == 1          # entity 2 fails -> skipped whole bundle
        assert counts["country_files"] == 9 * len(COUNTRY_DAYS)
        assert counts["trending_files"] == len(COUNTRIES)  # global + 9 (India fails)
        assert counts["source_trending_files"] == 1        # 5 written, 6 thin, 7 raises
        # entity 2 + India country files + India trending + source 7 + source map
        assert counts["skipped"] == 1 + len(COUNTRY_DAYS) + 1 + 1 + 1

        with open(os.path.join(out, "entity", "1.json")) as f:
            bundle = json.load(f)
        assert set(bundle) == {"format", "entity", "base_days", "distribution",
                               "historical", "source_historical",
                               "national_distributions", "source_scatter",
                               "source_scatter_all", "archetype", "related",
                               "drift"}
        assert bundle["format"] == 2 and bundle["base_days"] == max(HIST_DAYS)
        assert bundle["historical"]["days"] == max(HIST_DAYS)
        assert bundle["historical"]["daily_data"][0]["power_score"] == 1.2346  # rounded
        # USA written, UK pruned (below MIN_NATIONAL_MENTIONS), the rest raised.
        assert set(bundle["national_distributions"]) == {"USA"}
        assert counts["national_layers"] == 1
        assert counts["source_scatters"] == 1  # entity 1 only; entity 2's bundle skipped
        scatter = bundle["source_scatter"]
        assert scatter["current"]["sources"][0]["power_score"] == 0.1235  # rounded
        assert scatter["previous"]["sources"] == []
        assert counts["source_scatters_all"] == 1
        scatter_all = bundle["source_scatter_all"]
        assert scatter_all["weeks"] == 0
        assert scatter_all["previous"] == {"start": None, "end": None, "sources": []}

        # The three baked panels: global archetype + USA overlay (UK pruned,
        # the rest raised), both related vectors, both drift dimensions.
        assert counts["archetypes"] == 1 and counts["related"] == 1
        assert counts["drifts"] == 1
        assert set(bundle["archetype"]) == {"global", "countries"}
        assert set(bundle["archetype"]["countries"]) == {"USA"}
        assert bundle["archetype"]["global"]["trajectory"][0]["moral"] == 0.5556
        assert bundle["related"]["sentiment"]["neighbors"][0]["similarity"] == 0.9877
        assert bundle["drift"]["power"]["source_shifts"][0]["p_value"] == 0.0123
        assert bundle["drift"]["moral"]["weeks_observed"] == 9

        # Receipts: entity 1 only (entity 2's whole bundle was skipped first).
        assert counts["receipt_files"] == 1
        with open(os.path.join(out, "receipts", "1.json")) as f:
            receipts = json.load(f)
        assert receipts["sources"]["5"][0]["power_score"] == 1.2346  # rounded
        assert not os.path.exists(os.path.join(out, "receipts", "2.json"))

        # Stale managed files pruned; the .txt and the root file untouched.
        assert counts["pruned"] == 3
        assert not os.path.exists(os.path.join(out, "entity", "999.json"))
        assert not os.path.exists(os.path.join(out, "receipts", "999.json"))
        assert not os.path.exists(os.path.join(out, "stats", "trending_source_9.json"))
        assert os.path.exists(os.path.join(out, "entity", "notes.txt"))
        assert os.path.exists(os.path.join(out, "root_extra.json"))

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

        # Source bundles track the trending_source set exactly.
        assert counts["source_bundles"] == 1
        with open(os.path.join(out, "source", "5.json")) as f:
            sb = json.load(f)
        assert sb["format"] == 1 and sb["base_days"] == max(HIST_DAYS)
        assert sb["source"]["id"] == 5
        assert len(sb["entities"]) == MIN_SOURCE_TRENDING  # all 5 rows, under the 20 cap
        assert sb["entities"][0]["distribution"]["source_name"] == "Src"
        assert sb["entities"][0]["daily"][0]["mention_count"] == 3
        assert not os.path.exists(os.path.join(out, "source", "6.json"))
        assert not os.path.exists(os.path.join(out, "source", "7.json"))

        assert counts["contested_files"] == 1
        with open(os.path.join(out, "stats", "contested.json")) as f:
            contested = json.load(f)
        assert contested["entities"][0]["divergence"] == 0.5556  # rounded

        assert counts["drift_feed_files"] == 1
        with open(os.path.join(out, "stats", "drift_feed.json")) as f:
            feed = json.load(f)
        assert set(feed) == {"moral", "power"}
        assert feed["power"]["events"][0]["p_value"] == 0.0012  # rounded

        assert counts["symbol_files"] == 1
        with open(os.path.join(out, "stats", "symbols.json")) as f:
            syms = json.load(f)
        assert syms["symbols"][0]["divergence"] == 0.4444  # rounded

        # Source space: matrix + agenda + vectors + dividing lines written,
        # the raising map skipped.
        assert counts["source_space_files"] == 4
        assert os.path.exists(os.path.join(out, "stats", "dividing_lines.json"))
        with open(os.path.join(out, "stats", "similarity_matrix.json")) as f:
            assert json.load(f)["pairs"][0]["score"] == 0.8333  # rounded
        with open(os.path.join(out, "stats", "global_agenda.json")) as f:
            agenda = json.load(f)
        assert agenda["entities"][0]["mean_moral"] == 0.1235  # rounded
        with open(os.path.join(out, "stats", "source_vectors.json")) as f:
            assert json.load(f)["sources"]["5"]["1"] == [0.5, 3]
        assert not os.path.exists(os.path.join(out, "stats", "source_map.json"))

        with open(os.path.join(out, "meta.json")) as f:
            meta = json.load(f)
        assert meta["entity_count"] == 2 and meta["hist_days"] == HIST_DAYS
        assert meta["format"] == 2
        assert meta["trending_sources"] == [5]
        assert meta["most_recent_article_date"] == "2026-01-01T00:00:00+00:00"
        assert meta["most_recent_analysis_date"] == "2025-12-30T00:00:00+00:00"

    print("export_snapshots self-test OK")


if __name__ == "__main__":
    main()

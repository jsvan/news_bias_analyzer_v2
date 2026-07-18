"""
Convergent-validity check against Pew Research opinion polls (extends the
founding-axiom test in analyzer/event_study.py; same shape: a standalone,
READ-ONLY, self-testing script - it queries the corpus, never writes, and is
not imported by anything else).

Question: does this instrument's media sentiment correlate with independently
measured public opinion? Framing matters and is not optional (CLAUDE.md):
media sentiment and public opinion are DIFFERENT constructs - one measures how
US outlets frame an entity, the other what US adults tell a pollster. A
correlation is evidence the instrument measures something real about the
information environment; it is NOT proof of accuracy. A null result is a
reportable finding, not a failure to bury.

Data: data/validation/pew_toplines.csv - hand-transcribed Pew *published
topline* values (one row per series x field period, source_url per row; no
scraping, no microdata). Corpus side: mean moral_score of the entity's
mentions from US sources in a window around each Pew field period, canonical
entities via COALESCE(canonical_id, id), windows below MIN_MENTIONS dropped
(the min_mentions=10 convention from contested_ranking).

Analysis, in order of importance:
  1. Within-entity over-time Spearman between each Pew series and windowed
     media sentiment - the headline number. Pew series here measure
     UNFAVORABILITY / NO-confidence, so the axiom predicts a NEGATIVE
     correlation with moral score.
  2. Cross-entity sanity check in the best-covered shared field period: does
     the entity Pew ranks most unfavorable also rank lowest in media moral?
  3. Optional lead/lag scan (shift media windows +/-1..6 months, report where
     |Spearman| peaks) - an interesting finding if it appears, not a gate.

Run:
    python -m analyzer.pew_validation              # against the live DB
    python -m analyzer.pew_validation --self-test  # synthetic, no DB
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

CSV_PATH = Path(__file__).parent.parent / "data" / "validation" / "pew_toplines.csv"
MIN_MENTIONS = 10          # per-window floor, contested_ranking's convention
WINDOW_PAD_DAYS = 30       # corpus window = field period +/- this many days
MIN_POINTS_FOR_RHO = 4     # fewer paired points than this -> report, don't correlate


def spearman(x, y):
    """Spearman rank correlation, no scipy needed (ties get average ranks)."""
    x, y = np.asarray(x, float), np.asarray(y, float)

    def ranks(v):
        order = np.argsort(v)
        r = np.empty(len(v), float)
        r[order] = np.arange(1, len(v) + 1)
        # average ranks for ties
        for val in np.unique(v):
            mask = v == val
            if mask.sum() > 1:
                r[mask] = r[mask].mean()
        return r

    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def load_toplines(path=CSV_PATH):
    """[{series, entity_name, field_start, field_end, value_pct, source_url}]"""
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append({
                "series": row["series"],
                "entity_name": row["entity_name"],
                "field_start": date.fromisoformat(row["field_start"]),
                "field_end": date.fromisoformat(row["field_end"]),
                "value_pct": float(row["value_pct"]),
                "source_url": row["source_url"],
            })
    return rows


def media_moral_in_window(session, entity_name: str, start: date, end: date):
    """(mean moral_score, n) over US-source mentions of the canonical entity
    in [start-pad, end+pad]. Returns (None, n) below the mention floor."""
    from sqlalchemy import text
    lo = start - timedelta(days=WINDOW_PAD_DAYS)
    hi = end + timedelta(days=WINDOW_PAD_DAYS)
    row = session.execute(text("""
        SELECT AVG(em.moral_score) AS mean_moral, COUNT(*) AS n
        FROM entity_mentions em
        JOIN entities e ON e.id = em.entity_id
        JOIN news_articles na ON na.id = em.article_id
        JOIN news_sources ns ON ns.id = na.source_id
        WHERE COALESCE(e.canonical_id, e.id) = (
                SELECT COALESCE(e2.canonical_id, e2.id) FROM entities e2
                WHERE LOWER(e2.name) = LOWER(:name)
                ORDER BY (e2.canonical_id IS NULL) DESC, e2.id LIMIT 1
              )
          AND ns.country = 'USA'
          AND em.moral_score IS NOT NULL
          AND na.publish_date BETWEEN :lo AND :hi
    """), {"name": entity_name, "lo": lo, "hi": hi}).fetchone()
    n = int(row.n or 0)
    if n < MIN_MENTIONS:
        return None, n
    return float(row.mean_moral), n


def series_table(session, toplines):
    """Per series: paired (pew value, media moral, n) rows for windows above
    the floor; returns {series: {"entity": ..., "points": [(date, pew, moral, n)],
    "dropped": [(date, n)]}}."""
    out = {}
    for row in toplines:
        entry = out.setdefault(row["series"], {"entity": row["entity_name"],
                                               "points": [], "dropped": []})
        moral, n = media_moral_in_window(session, row["entity_name"],
                                         row["field_start"], row["field_end"])
        mid = row["field_start"] + (row["field_end"] - row["field_start"]) / 2
        if moral is None:
            entry["dropped"].append((mid, n))
        else:
            entry["points"].append((mid, row["value_pct"], moral, n))
    return out


def lead_lag_scan(session, entity_name, toplines_for_series, months=(1, 2, 3, 4, 5, 6)):
    """|Spearman| for media windows shifted by +/-N months; + = media leads
    (media window earlier than the poll). Returns [(shift_months, rho, k_points)]."""
    results = []
    for m in [-x for x in months[::-1]] + [0] + list(months):
        pew_vals, moral_vals = [], []
        for row in toplines_for_series:
            shift = timedelta(days=30 * m)
            moral, _ = media_moral_in_window(
                session, entity_name,
                row["field_start"] - shift, row["field_end"] - shift)
            if moral is not None:
                pew_vals.append(row["value_pct"])
                moral_vals.append(moral)
        if len(pew_vals) >= MIN_POINTS_FOR_RHO:
            results.append((m, spearman(pew_vals, moral_vals), len(pew_vals)))
    return results


def run(session):
    toplines = load_toplines()
    table = series_table(session, toplines)

    print("=" * 74)
    print("Pew convergent-validity check  (media moral score vs published toplines)")
    print("Pew values measure UNFAVORABILITY/NO-confidence -> prediction: rho < 0")
    print("=" * 74)

    headline = {}
    for series, entry in table.items():
        pts = entry["points"]
        print(f"\n## {series}  ({entry['entity']}, US sources, "
              f"window = field period +/-{WINDOW_PAD_DAYS}d, floor n>={MIN_MENTIONS})")
        print(f"{'window mid':>12s} {'pew %':>6s} {'media moral':>12s} {'n':>6s}")
        for mid, pew, moral, n in sorted(pts):
            print(f"{mid.isoformat():>12s} {pew:6.0f} {moral:12.3f} {n:6d}")
        for mid, n in sorted(entry["dropped"]):
            print(f"{mid.isoformat():>12s} {'-':>6s} {'below floor':>12s} {n:6d}")
        if len(pts) >= MIN_POINTS_FOR_RHO:
            rho = spearman([p[1] for p in pts], [p[2] for p in pts])
            headline[series] = (rho, len(pts))
            print(f"   -> Spearman rho = {rho:+.3f} over {len(pts)} field periods")
        else:
            print(f"   -> only {len(pts)} usable field periods "
                  f"(< {MIN_POINTS_FOR_RHO}); no correlation reported")

    # Cross-entity sanity check: use the most recent field period with >= 2
    # entities above the floor.
    print("\n## cross-entity sanity check")
    by_period = {}
    for series, entry in table.items():
        for mid, pew, moral, n in entry["points"]:
            by_period.setdefault(mid.year, []).append((entry["entity"], series, pew, moral))
    checked = False
    for year in sorted(by_period, reverse=True):
        rows = [r for r in by_period[year] if "unfavorable" in r[1]]
        if len(rows) >= 2:
            rows.sort(key=lambda r: -r[2])  # most unfavorable first
            worst_pew = rows[0]
            rows.sort(key=lambda r: r[3])   # lowest media moral first
            worst_media = rows[0]
            agree = worst_pew[0] == worst_media[0]
            print(f"   {year}: Pew's most unfavorable = {worst_pew[0]} "
                  f"({worst_pew[2]:.0f}%), media's lowest moral = {worst_media[0]} "
                  f"({worst_media[3]:+.3f}) -> {'AGREE' if agree else 'DISAGREE'}")
            checked = True
            break
    if not checked:
        print("   no field period with >= 2 entities above the floor")

    # Optional lead/lag on the richest series.
    richest = max(table, key=lambda s: len(table[s]["points"]))
    if len(table[richest]["points"]) >= MIN_POINTS_FOR_RHO:
        print(f"\n## lead/lag scan ({richest}; + months = media leads the poll)")
        rows = [r for r in load_toplines() if r["series"] == richest]
        for m, rho, k in lead_lag_scan(session, table[richest]["entity"], rows):
            print(f"   shift {m:+d}mo: rho = {rho:+.3f}  (k={k})")

    print("\n" + "-" * 74)
    print("Read honestly: media sentiment and public opinion are different")
    print("constructs. Correlation here is evidence the instrument tracks something")
    print("real; it is not proof of accuracy. A null result is itself a finding.")
    return headline


def self_test():
    """Kernel checks on synthetic data - no DB, no network."""
    # Perfectly anti-correlated fixture (unfavorability up, moral down).
    pew = [40, 50, 60, 70, 80]
    moral = [0.5, 0.3, 0.1, -0.2, -0.6]
    assert np.isclose(spearman(pew, moral), -1.0)
    # Perfectly correlated.
    assert np.isclose(spearman(pew, [-m for m in moral]), 1.0)
    # Uncorrelated fixture: |rho| well below the perfect-correlation cases.
    # (n=8 noise; the exact value 0.503 is deterministic for this fixture)
    rho = spearman([1, 2, 3, 4, 5, 6, 7, 8], [3, 1, 4, 1, 5, 9, 2, 6])
    assert abs(rho) < 0.6, rho
    # Constant series -> nan, not a crash.
    assert np.isnan(spearman([1, 1, 1, 1], [1, 2, 3, 4]))
    # CSV loads and has the documented shape.
    rows = load_toplines()
    assert all(set(r) == {"series", "entity_name", "field_start", "field_end",
                          "value_pct", "source_url"} for r in rows)
    assert all(r["source_url"].startswith("https://www.pewresearch.org") for r in rows)
    assert len({r["series"] for r in rows}) >= 2
    print("pew_validation self-test: all assertions passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        sys.exit(0)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=create_engine(os.environ["DATABASE_URL"]))()
    try:
        run(session)
    finally:
        session.close()

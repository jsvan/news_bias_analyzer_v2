"""
Run migration 018: remap legacy entity_type values onto the 6-value enum.

New extraction is constrained to ["country", "person", "business",
"organization", "event", "concept"] via Structured Outputs (analyzer/prompts.py
ENTITY_TYPES), but 14,125 pre-fix rows (counted 2026-07-18) still carry ~439
legacy types (political_leader, sovereign_state, people, ...). Those pollute
every type filter and the archetype panels.

Mapping = an explicit table for the head types plus ordered keyword rules for
the long tail, matching analyzer/prompts.py's own definitions (identity groups
and demographic cohorts are organization; industry sectors are organization;
place metonyms are country - the live extractor already types Moscow as
country). Deterministic by design: no hand-review, per the project's
no-human-in-the-loop constraint.

Reversible: old values are copied to entity_type_remap_backup before the
UPDATE. Roll back with:
    UPDATE entities e SET entity_type = b.old_type
    FROM entity_type_remap_backup b WHERE e.id = b.entity_id;

Name-level mistypes (Barcelona the city recorded as a country-like entity)
are out of scope here - that is entity_resolution.py's merge territory, and
same-name duplicates are already funneled by canonical_id.

Usage:
    python -m database.run_migration_018 --dry-run   # print the mapping table
    python -m database.run_migration_018             # execute
    python -m database.run_migration_018 --self-test # no DB needed
"""

import argparse
import logging
import os
import sys
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ENUM = ("country", "person", "business", "organization", "event", "concept")

# Explicit head map - the ~40 most common legacy types (covers ~95% of rows).
EXPLICIT = {
    "political_leader": "person",
    "sovereign_state": "country",
    "people": "organization",          # identity groups per prompts.py
    "political_organization": "organization",
    "major_corporation": "business",
    "government": "country",           # prompts.py: governments = the country itself
    "symbolic_individual": "person",
    "international_institution": "organization",
    "media_organization": "organization",
    "educational_institution": "organization",
    "business_leader": "person",
    "specific_technology": "concept",
    "identity_group": "organization",
    "government_agency": "organization",
    "activist_movement": "organization",
    "religious_institution": "organization",
    "scientific_field": "concept",
    "individual": "person",
    "player": "person",
    "cultural_institution": "organization",
    "regional_bloc": "organization",   # BRICS, Western World per prompts.py
    "political_ideology": "concept",
    "political_faction": "organization",
    "judicial_institution": "organization",
    "company": "business",
    "industry_sector": "organization", # "Big Tech", "Wall Street" per prompts.py
    "public_figure": "person",
    "demographic_cohort": "organization",
    "infrastructure": "concept",
    "military_organization": "organization",
    "geographical_feature": "country", # place metonyms; see module docstring
    "interest_group": "organization",
    "social_movement": "organization",
    "financial_institution": "business",
    "fictional_character": "person",
    "ethnic_group": "organization",
    "species": "concept",
    "animal": "concept",
    "unknown": "concept",
}

# Ordered keyword rules for the tail; first match wins. Checked AFTER the
# explicit map. Word fragments are matched against the lowercased type name.
RULES = [
    (("bloc",), "organization"),
    (("leader", "player", "figure", "person", "individual", "athlete", "actor",
      "director", "artist", "journalist", "celebrity", "coach", "designer",
      "officer", "researcher", "author", "politician", "scientist", "hero",
      "personality", "official", "character", "criminal"), "person"),
    # 'criminal_organization' would hit "criminal" -> person, so org words win
    # for anything collective: keep this tuple ABOVE person? No - handled by
    # explicit ordering below via the pre-check in map_type().
    (("corporation", "company", "business", "brand", "airline", "platform",
      "corporate", "franchise", "bank"), "business"),
    (("event", "election", "war", "crisis", "disaster", "scandal",
      "festival"), "event"),
    (("state", "country", "nation", "city", "region", "location", "geograph",
      "territory", "province", "geological", "geopolitical"), "country"),
    (("organization", "organisation", "institution", "agency", "party",
      "union", "club", "team", "committee", "ministry", "government", "court",
      "movement", "group", "band", "force", "military", "police", "media",
      "association", "mission", "charity", "church", "think_tank", "service",
      "authority", "base", "broadcaster", "collective"), "organization"),
    (("technology", "ideology", "concept", "field", "science", "currency",
      "language", "disease", "condition", "product", "index", "legislation",
      "act", "program", "sport", "film", "series", "landmark"), "concept"),
]

FALLBACK = "concept"

# Collective words that must beat person-words when both appear
# (criminal_organization, police_officer is fine, sports_team, ...).
_COLLECTIVE = ("organization", "organisation", "institution", "agency", "party",
               "union", "club", "team", "committee", "movement", "group",
               "band", "force", "association", "mission")


def map_type(legacy: str) -> str:
    """Deterministically map one legacy entity_type onto the 6-value enum."""
    t = legacy.strip().lower().replace(" ", "_")
    if t in ENUM:
        return t
    if t in EXPLICIT:
        return EXPLICIT[t]
    if any(w in t for w in _COLLECTIVE):
        return "organization"
    for words, target in RULES:
        if any(w in t for w in words):
            return target
    return FALLBACK


def self_test():
    cases = {
        "political_leader": "person",
        "sovereign_state": "country",
        "criminal_organization": "organization",   # collective beats "criminal"
        "police_officer": "person",
        "professional_tennis_player": "person",
        "football_club": "organization",
        "tech_platform": "business",
        "natural_disaster": "event",
        "geopolitical_concept": "country",  # geo word; place metonym
        "law enforcement agency": "organization",  # space-separated legacy junk
        "stock_index": "concept",
        "regional_bloc": "organization",
        "country": "country",                       # already in enum: unchanged
        "never_seen_before_xyz": "concept",         # fallback
    }
    for legacy, expected in cases.items():
        got = map_type(legacy)
        assert got == expected, f"{legacy}: expected {expected}, got {got}"
        assert got in ENUM
    print("migration 018 self-test: all assertions passed")


def run(dry_run: bool):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    session = sessionmaker(bind=engine)()
    try:
        rows = session.execute(text("""
            SELECT entity_type, COUNT(*) AS n FROM entities
            WHERE entity_type NOT IN :enum
            GROUP BY entity_type ORDER BY n DESC
        """), {"enum": ENUM}).fetchall()
        before = sum(r.n for r in rows)
        logger.info(f"Out-of-enum rows before: {before} across {len(rows)} legacy types\n")

        target_counts = Counter()
        logger.info(f"{'legacy type':40s} {'rows':>6s}  -> target")
        for r in rows:
            target = map_type(r.entity_type)
            target_counts[target] += r.n
            logger.info(f"{r.entity_type:40s} {r.n:6d}  -> {target}")
        logger.info("\nTarget totals: " +
                    ", ".join(f"{k}={v}" for k, v in target_counts.most_common()))

        if dry_run:
            logger.info("\nDRY RUN - nothing written")
            return

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS entity_type_remap_backup (
                entity_id INTEGER PRIMARY KEY,
                old_type TEXT NOT NULL,
                new_type TEXT NOT NULL,
                migrated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        for r in rows:
            target = map_type(r.entity_type)
            session.execute(text("""
                INSERT INTO entity_type_remap_backup (entity_id, old_type, new_type)
                SELECT id, entity_type, :target FROM entities
                WHERE entity_type = :legacy
                ON CONFLICT (entity_id) DO NOTHING
            """), {"target": target, "legacy": r.entity_type})
            session.execute(text(
                "UPDATE entities SET entity_type = :target WHERE entity_type = :legacy"
            ), {"target": target, "legacy": r.entity_type})
        session.commit()

        after = session.execute(text(
            "SELECT COUNT(*) FROM entities WHERE entity_type NOT IN :enum"
        ), {"enum": ENUM}).scalar()
        backed_up = session.execute(text(
            "SELECT COUNT(*) FROM entity_type_remap_backup")).scalar()
        logger.info(f"\nOut-of-enum rows after: {after} (was {before}); "
                    f"{backed_up} rows backed up in entity_type_remap_backup")

        # Same-name rows that now share a type may be new merge candidates.
        from analyzer.entity_resolution import run_merge_job
        merged, renamed = run_merge_job(session)
        logger.info(f"entity_resolution.run_merge_job: {merged} new canonical merges, "
                    f"{renamed} canonical names normalized")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        sys.exit(0)
    self_test()  # always gate the mapping before touching the DB
    run(dry_run=args.dry_run)

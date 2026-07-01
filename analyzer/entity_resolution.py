"""
Entity resolution — layered, cheap-first (docs/ROADMAP_IDEAS_2026.md §12).

Layer 0: known-entity shortlist injected into the extraction prompt so the LLM
         reuses canonical names (stops variant drift at the source).
Layer 1: deterministic post-hoc normalization (honorifics, punctuation, alias
         table) to propose canonical_id merges — Entity.canonical_id already
         exists in the schema; merges are pointer-based and reversible.

Pure functions, stdlib only. DB job wiring comes later; self-test:

    python -m analyzer.entity_resolution
"""

import re
import unicodedata
from difflib import SequenceMatcher

# Honorifics/titles stripped from person names. Longest-match-first.
_TITLES = [
    "president-elect", "vice president", "prime minister", "chancellor",
    "president", "chairman", "chairwoman", "secretary general", "secretary",
    "senator", "governor", "minister", "ambassador", "general", "colonel",
    "king", "queen", "prince", "princess", "sheikh", "ayatollah", "pope",
    "sir", "dame", "dr", "mr", "mrs", "ms",
]
_TITLE_RE = re.compile(
    r"^(?:(?:" + "|".join(re.escape(t) for t in sorted(_TITLES, key=len, reverse=True))
    + r")\.?\s+)+", re.IGNORECASE)

# Hand-curated aliases for head entities: variant (normalized) -> canonical name.
# ponytail: grow this from merge-job reports; swap for a DB table if it gets big.
ALIASES = {
    "us": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "u.s": "United States",   # trailing-dot form after punctuation strip
    "america": "United States",
    "uk": "United Kingdom",
    "u.k": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "eu": "European Union",
    "un": "United Nations",
    "who": "World Health Organization",
    "nato": "NATO",
    "prc": "China",
    "people's republic of china": "China",
    "russian federation": "Russia",
}


def normalize_name(name: str, entity_type: str = "") -> str:
    """Canonical comparison form: unicode-normalized, title-stripped, tidied.

    Returns a display-cased canonical name (not lowercased) so it can be used
    directly as the merged entity's name.
    """
    s = unicodedata.normalize("NFKC", name).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" \"'“”‘’.,;:")
    if entity_type in ("person", "political_leader", "") :
        s = _TITLE_RE.sub("", s)
    alias = ALIASES.get(s.lower())
    if alias:
        return alias
    return s


def merge_key(name: str, entity_type: str = "") -> str:
    """Case/space-insensitive key two entities must share to be merge candidates."""
    return normalize_name(name, entity_type).lower()


def propose_merges(entities, fuzzy_threshold: float = 0.85):
    """Propose canonical_id merges over [(id, name, entity_type, mention_count)].

    Exact merge-key collisions merge automatically toward the most-mentioned
    member; near-misses above fuzzy_threshold (SequenceMatcher on merge keys)
    are returned separately for review, never auto-merged.

    Returns (auto, review):
      auto:   [(loser_id, canonical_id, reason)]
      review: [(id_a, id_b, similarity)]
    """
    normalized = [(eid, merge_key(name, etype), count)
                  for eid, name, etype, count in entities]

    groups = {}
    for eid, key, count in normalized:
        groups.setdefault(key, []).append((eid, count))

    auto = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda t: -t[1])
        canonical = members[0][0]
        auto.extend((eid, canonical, f"exact:{key}") for eid, _ in members[1:])

    # Fuzzy pass over group representatives only (keeps it near-linear in practice).
    review = []
    reps = [(members[0][0], key) for key, members in groups.items()
            if (members.sort(key=lambda t: -t[1]) or True)]
    reps.sort(key=lambda t: t[1])
    for i, (id_a, key_a) in enumerate(reps):
        for id_b, key_b in reps[i + 1:]:
            # keys are sorted; stop when even the prefix diverges too far
            if key_b[:2] != key_a[:2]:
                break
            sim = SequenceMatcher(None, key_a, key_b).ratio()
            if sim >= fuzzy_threshold:
                review.append((id_a, id_b, round(sim, 3)))
    return auto, review


def known_entity_shortlist(article_text: str, known_entities, limit: int = 30):
    """Layer 0: canonical names of tracked entities that appear in this article.

    known_entities: [(canonical_name, mention_count)], assumed pre-sorted or not.
    Substring match on the normalized text — false positives are harmless (the
    LLM ignores names not actually in the article); false negatives just mean
    no hint. Most-mentioned entities win the `limit` cut.
    """
    text = unicodedata.normalize("NFKC", article_text).lower()
    hits = [(name, count) for name, count in known_entities
            if len(name) > 2 and name.lower() in text]
    hits.sort(key=lambda t: -t[1])
    return [name for name, _ in hits[:limit]]


def format_shortlist_block(names) -> str:
    """Prompt block appended to the article text when the shortlist is non-empty."""
    if not names:
        return ""
    return (
        "\n\nKNOWN ENTITIES: These entities are already tracked under these exact "
        "canonical names. If any of them appear in this article, report them using "
        "these names verbatim (do not use variants, titles, or translations):\n- "
        + "\n- ".join(names)
    )


def self_test():
    # normalization: titles, unicode, aliases
    assert normalize_name("President Joe Biden", "person") == "Joe Biden"
    assert normalize_name("prime minister  Narendra Modi", "political_leader") == "Narendra Modi"
    assert normalize_name("  “Emmanuel Macron”. ") == "Emmanuel Macron"
    assert normalize_name("US", "sovereign_state") == "United States"
    assert normalize_name("u.s.") == "United States"
    assert normalize_name("EU") == "European Union"
    # non-person types keep leading words that merely look like titles
    assert normalize_name("General Motors", "company") == "General Motors"

    # merges: exact collisions auto-merge toward most mentions; fuzzy goes to review
    entities = [
        (1, "Joe Biden", "person", 900),
        (2, "President Joe Biden", "person", 50),
        (3, "joe biden", "person", 5),
        (4, "Joseph Biden", "person", 10),      # fuzzy candidate vs "joe biden"
        (5, "Ursula von der Leyen", "person", 300),
        (6, "US", "sovereign_state", 400),
        (7, "United States", "sovereign_state", 5000),
    ]
    auto, review = propose_merges(entities)
    merged = {(loser, canon) for loser, canon, _ in auto}
    assert (2, 1) in merged and (3, 1) in merged, auto
    assert (6, 7) in merged, auto  # alias table folds US into United States
    assert all(loser != 5 for loser, _, _ in auto)
    assert any({a, b} == {1, 4} for a, b, _ in review), review  # Joseph≈Joe -> review only

    # shortlist: present entities found, absent ones not, limit respects mentions
    text = "In Berlin, Chancellor Olaf Scholz met Emmanuel Macron to discuss the European Union."
    known = [("Emmanuel Macron", 500), ("Olaf Scholz", 400),
             ("European Union", 4000), ("Vladimir Putin", 9000)]
    hits = known_entity_shortlist(text, known, limit=2)
    assert hits == ["European Union", "Emmanuel Macron"], hits
    assert "Vladimir Putin" not in hits

    block = format_shortlist_block(hits)
    assert "canonical names" in block and "- Emmanuel Macron" in block
    assert format_shortlist_block([]) == ""

    print("entity_resolution self-test OK")


if __name__ == "__main__":
    self_test()

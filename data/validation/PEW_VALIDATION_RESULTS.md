# Pew convergent-validity check — run 2026-07-18

`python -m analyzer.pew_validation` against the live corpus.

## Result: insufficient historical coverage; no correlation reportable yet

Every Pew field period except spring 2025 fell below the 10-mention floor for
US-source coverage of the tracked entities. The corpus's article-year
distribution explains it (measured this run):

| publish year | articles | notes |
|---|---|---|
| 2017–2019 | 83 | scattered |
| 2020 | 1,001 | All The News 2.0 pilot (user-capped at 1,000) |
| 2024 | 1,161 | CC-NEWS pilot (user-capped at 1,000) |
| 2025 | 216,187 | live scraper era |
| 2026 | 3,104 | live scraper (post-outage) |

So the within-entity over-time Spearman — the headline number this check is
designed around — cannot be computed yet: it needs at least 4 field periods
above the floor, and only one (2025) qualifies.

## The one usable point, read honestly

China, spring 2025: Pew has 77% of US adults unfavorable; the corpus's
US-source mean moral score for China in the matching window is **−0.680**
(n=344) on the [−2, +2] scale. Directionally consistent (strongly unfavorable
poll year, strongly negative media framing), but a single point carries no
inferential weight and is reported only for completeness.

## What unlocks this check

The seeding follow-through (larger All The News 2.0 / CC-NEWS runs — needs the
user's disk/article budget). China alone has published Pew toplines for
2017–2026 in `pew_toplines.csv`; each backfilled spring window that crosses
the mention floor adds a usable point. Re-run the script after the analyzer
daemon drains any new backlog; it recomputes everything live.

## Framing (from CLAUDE.md, non-negotiable)

Media sentiment and public opinion are different constructs. When the
correlation becomes computable, it is evidence the instrument measures
something real about the information environment — not proof of accuracy.
A null result will be a finding, not a failure.

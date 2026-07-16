# Blocked / dead sources

Sources removed from `scrapers/news_sources.py` because they don't work, so nobody
re-adds them without knowing why. Confirmed live 2026-07-15 with plain `curl`
(both a generic bot user-agent and a real Chrome user-agent) — this isn't a
scraper-library problem, so a different extraction library won't fix any of these.

| Source | What happens | Diagnosis |
|---|---|---|
| The Wall Street Journal | Every article URL returns HTTP 401, RSS feed itself is open (200) | Hard auth-wall enforced at the HTTP layer. Needs a Dow Jones/Factiva data license or a valid subscriber session — not fixable by scraping technique. |
| The Telegraph | RSS feed and article pages return HTTP 403, even with a real browser UA | Cloudflare bot-detection (TLS/behavioral fingerprinting, not a UA-string check). |
| Washington Post | RSS feed is alive and current; article-page fetches hang and reset at the TLS handshake | Enterprise bot-detection (Akamai-style). A real fix needs a real browser session (Playwright) — an ongoing arms race and closer to WaPo's ToS line on automated access, so deliberately not built. Revisit if that tradeoff changes. |
| Reuters | Never had a working config — no feed URL was ever added | Reuters discontinued public RSS years ago; live-tested known feed URLs 2026-07-15, all 401/dead. Real Reuters content requires a paid Reuters Connect subscription. |

## What actually got their content into the DB before

The DB already had a handful of `apnews.com` (Associated Press) articles despite AP
never being configured here. `apnews.com/rss` and similar guesses are all dead
(404 / redirect to homepage) — that content arrived via historical seeding
(CC-News) or the OpenAI-batch recovery script, not live scraping. AP wire content
still enters the pipeline indirectly wherever a configured outlet republishes it.

## The realistic path to more "big name" coverage

Not by fighting these four harder. Wire-service content (AP/Reuters) already
reaches the DB via outlets that redistribute it. GDELT and additional
Hugging-Face news dumps (same pattern as `seed_from_ccnews.py`) widen the pool of
genuinely open sources. Paid data licenses (Dow Jones Factiva/DNA, WaPo Arc XP)
are real products for exactly this problem but are enterprise-sales-gated and,
from what's known of that market, priced well above this project's current scale.

-- Fix the UTC->PT publish_date shift for live-scraped articles (2026-08-12 .. 2026-08-20 10:21).
-- Bug: parallel_scraper used time.mktime() on feedparser's UTC struct_time, storing UTC
-- wall-clock digits as local time (7h late during PDT). Fixed in code at commit b862e50;
-- this backfills the rows written before the fix.
-- Scope: live-scraped rows only (extractor requests+trafilatura; recovery imports all have
-- scraped_at < 2026-08-12), excluding fallback-stamped rows where publish_date was set to
-- now() at insert (publish_date within [-2min, +15min] of scraped_at) - those are correct.
-- Rollback: table publish_date_shift_backup_20260820 holds (id, old publish_date).

BEGIN;

CREATE TABLE publish_date_shift_backup_20260820 AS
SELECT id, publish_date
FROM news_articles
WHERE scraped_at >= '2026-08-12' AND scraped_at < '2026-08-20 10:21'
  AND extraction_info->>'extractor' IN ('requests+trafilatura','wget+trafilatura')
  AND publish_date NOT BETWEEN scraped_at - interval '2 minutes' AND scraped_at + interval '15 minutes';

UPDATE news_articles a
SET publish_date = a.publish_date - interval '7 hours'
FROM publish_date_shift_backup_20260820 b
WHERE a.id = b.id;

SELECT (SELECT count(*) FROM publish_date_shift_backup_20260820) AS backed_up,
       (SELECT count(*) FROM news_articles
        WHERE scraped_at >= '2026-08-12' AND scraped_at < '2026-08-20 10:21'
          AND publish_date > scraped_at + interval '15 minutes') AS still_future;

COMMIT;

-- Junk affiliate stories pulled in by CNN's frozen feeds during today's run
-- (2022-era local-news URLs, unanalyzed, no entity mentions yet)
DELETE FROM news_articles WHERE url IN (
 'https://www.cbsnews.com/philadelphia/news/almost-200-animals-rescued-from-puppy-mill-in-ocean-county/',
 'https://www.atlantanewsfirst.com/2022/12/04/police-2-ford-mustangs-totaling-nearly-200k-stolen-upson-county-dealership/',
 'https://www.wfsb.com/2022/12/02/racoon-attack-ashford/',
 'https://6abc.com/philadelphia-eagles-tailgate-south-vietnam-veteran/12524946/'
);

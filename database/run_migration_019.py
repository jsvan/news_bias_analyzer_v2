#!/usr/bin/env python3
"""
Migration 019: OpenAI batch tracking table + per-article retry counter.

- openai_batches: DB-backed tracking of OpenAI Batch API jobs. Replaces the
  container-local analyzer/batches.txt, which was wiped on every image rebuild,
  orphaning in-flight batches (their already-paid results were never collected).
- news_articles.analysis_attempts: how many times an article has been submitted
  for analysis. The analyzer stops retrying after 3 submissions so a poison
  article can't be re-paid in every future batch forever.

Idempotent: CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
"""
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database.models import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Timestamps are naive local time (container TZ), matching last_analysis_attempt
# on news_articles - the daemon compares submitted_at against local midnight for
# the daily spend cap.
DDL = [
    """
    CREATE TABLE IF NOT EXISTS openai_batches (
        batch_id VARCHAR(64) PRIMARY KEY,
        input_file_id VARCHAR(64),
        output_file_id VARCHAR(64),
        status VARCHAR(20) NOT NULL DEFAULT 'validating',
        article_count INTEGER,
        estimated_cost_usd DOUBLE PRECISION,
        submitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        completed_at TIMESTAMP WITHOUT TIME ZONE,
        collected BOOLEAN NOT NULL DEFAULT FALSE,
        error TEXT
    )
    """,
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS analysis_attempts INTEGER NOT NULL DEFAULT 0",
]


def main():
    engine = get_db_connection()
    with engine.connect() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
        conn.commit()
    logger.info("Migration 019 applied: openai_batches table + news_articles.analysis_attempts")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Delete orphaned batch files from OpenAI file storage.

The daemon now deletes its files as batches resolve, but failures used to
leave inputs behind (the 2026-08-13 billing-limit loop uploaded ~180 junk
files/day) and nothing ever cleaned outputs before that. Files here are
expendable by design: inputs are rebuilt from our DB, outputs are ingested
into it before the daemon deletes them.

Protected (never deleted):
- files referenced by any non-terminal batch on OpenAI
- files referenced by any uncollected batch in our openai_batches table
- files uploaded in the last 2 hours (races with an in-flight submission)

Usage (inside a container with OPENAI_API_KEY + DATABASE_URL):
    python analyzer/tools/cleanup_openai_files.py            # dry run
    python analyzer/tools/cleanup_openai_files.py --delete   # actually delete
"""
import argparse
import logging
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import OpenAIBatch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NON_TERMINAL = ("validating", "in_progress", "finalizing", "cancelling")
MIN_AGE_SECONDS = 2 * 3600


def protected_file_ids(client: OpenAI) -> set:
    protected = set()

    # Everything a live batch on OpenAI still points at
    after = None
    while True:
        page = client.batches.list(limit=100, after=after) if after else client.batches.list(limit=100)
        if not page.data:
            break
        for b in page.data:
            if b.status in NON_TERMINAL:
                protected.update(filter(None, [b.input_file_id, b.output_file_id, b.error_file_id]))
        if len(page.data) < 100:
            break
        after = page.data[-1].id

    # Everything our tracking still owes action on
    engine = create_engine(os.environ["DATABASE_URL"])
    session = sessionmaker(bind=engine)()
    try:
        for row in session.query(OpenAIBatch).filter(OpenAIBatch.collected == False).all():
            protected.update(filter(None, [row.input_file_id, row.output_file_id]))
    finally:
        session.close()

    return protected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="actually delete (default: dry run)")
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    protected = protected_file_ids(client)
    logger.info(f"{len(protected)} file ids protected by live/uncollected batches")

    cutoff = time.time() - MIN_AGE_SECONDS
    candidates = []
    total_bytes = 0
    after = None
    while True:
        page = client.files.list(limit=1000, after=after) if after else client.files.list(limit=1000)
        if not page.data:
            break
        for f in page.data:
            if f.purpose not in ("batch", "batch_output"):
                continue  # only touch Batch API artifacts
            if f.id in protected or f.created_at > cutoff:
                continue
            candidates.append(f)
            total_bytes += f.bytes or 0
        if len(page.data) < 1000:
            break
        after = page.data[-1].id

    logger.info(f"{len(candidates)} orphaned files, {total_bytes / 1e6:.1f} MB")

    if not args.delete:
        logger.info("Dry run - pass --delete to remove them")
        return

    deleted = failed = 0
    for f in candidates:
        try:
            client.files.delete(f.id)
            deleted += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Could not delete {f.id}: {e}")

    logger.info(f"Deleted {deleted} files ({total_bytes / 1e6:.1f} MB freed), {failed} failures")


if __name__ == "__main__":
    main()

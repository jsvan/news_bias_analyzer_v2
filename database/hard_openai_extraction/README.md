# OpenAI Batch Data Extraction and Restoration

This directory contains scripts to download, extract, and restore article data from OpenAI batch files to the database.

## Overview

The system allows you to:

1. Download OpenAI batch files containing analysis of news articles
2. Check which articles are missing from the database
3. Restore article data and analysis to the database

## Prerequisites

- Python 3.8+
- OpenAI Python package (`pip install openai`)
- A valid OpenAI API key set as the `OPENAI_API_KEY` environment variable
- Access to the database (configured through `DATABASE_URL` environment variable)

## Scripts

### 1. `download_batches.py`

Downloads OpenAI batch files from your account.

```bash
# Download all batches from 2025
python download_batches.py

# Download to a specific directory
python download_batches.py --output-dir /path/to/batches

# Download batches from a specific year
python download_batches.py --year 2024

# Limit the number of batches
python download_batches.py --limit 10
```

### 2. `check_articles.py`

Checks the status of articles in the database compared to what's in the batch files.

```bash
# Check article status
python check_articles.py

# Check with batch files in a specific directory
python check_articles.py --batch-dir /path/to/batches

# Save the results to a JSON file
python check_articles.py --output article_status.json

# Only show missing articles
python check_articles.py --missing-only
```

### 3. `restore_articles.py`

Restores article data and analysis from batch files to the database.

```bash
# Process all batches in the default directory (dry run)
python restore_articles.py --dry-run

# Process batches in a specific directory
python restore_articles.py --batch-dir /path/to/batches

# Process a specific batch
python restore_articles.py --batch-id batch_6827a7341e9081909337b164e7ee3ae3
```

## Workflow

Here's a typical workflow to restore your data:

1. Download the batch files:
   ```bash
   python download_batches.py
   ```

2. Check which articles are missing or need processing:
   ```bash
   python check_articles.py --output article_status.json
   ```

3. Do a dry run of the restoration process:
   ```bash
   python restore_articles.py --dry-run
   ```

4. Restore the articles to the database:
   ```bash
   python restore_articles.py
   ```

## Data Format

The batch files have the following format:

- Input file (`batch_ID_input.jsonl`): Contains the original requests sent to OpenAI
- Output file (`batch_ID_output.jsonl`): Contains the responses from OpenAI

Each line in these files is a complete JSON object. The input file contains the article text and the output file contains the analysis results.

## Notes

- The scripts will extract article IDs from the batch files by parsing the `custom_id` field. The expected format is `article_HASH`.
- When restoring articles, the script will check if the article already exists in the database and update it if necessary.
- If an article doesn't exist, a new record will be created with the title and content from the batch files.
- Entity mentions will be created for each entity found in the analysis.
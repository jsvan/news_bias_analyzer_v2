# Analyzer Maintenance Tools

This directory contains utility scripts for maintaining and debugging the batch analyzer system.

## Available Tools

### 1. analyze_db_status.py

Analyzes the database status directly, bypassing the regular reporting system. Shows the full status breakdown of all articles, batch information, and entity counts.

**Usage:**
```bash
./run.sh custom analyzer/tools/analyze_db_status.py
```

### 2. reset_stuck_articles.py

Resets articles that are stuck in 'in_progress' status for longer than a specified period. This helps recover from failed or interrupted batch processing.

**Usage:**
```bash
# Do a dry run first (shows what would be reset without changing anything)
./run.sh custom analyzer/tools/reset_stuck_articles.py --dry-run

# Reset articles stuck for more than 24 hours (default)
./run.sh custom analyzer/tools/reset_stuck_articles.py

# Reset articles stuck for more than 12 hours
./run.sh custom analyzer/tools/reset_stuck_articles.py --hours 12
```

### 3. monitor_batch_analysis.py

Provides real-time monitoring of the batch analysis system. Shows active batches, processing statistics, and recent activity. Useful for tracking progress and diagnosing issues.

**Usage:**
```bash
./run.sh custom analyzer/tools/monitor_batch_analysis.py
```

### 4. recover_openai_batches.py

Recovers articles from OpenAI batches when the analyzer daemon fails. This tool retrieves previously processed OpenAI batches and updates existing articles that aren't marked as completed, while preserving their original URLs and IDs.

**Usage:**
```bash
# List options
./run.sh analyze recover-batches --help

# Basic recovery from existing batches
./run.sh analyze recover-batches --batch-dir=/path/to/batches --skip-download

# Download recent batches from OpenAI and process incomplete articles
./run.sh analyze recover-batches --year=2025 --limit=10

# Run a dry run to see what would be processed without making changes
./run.sh analyze recover-batches --dry-run
```

### 5. reset_database.py

Resets the database by clearing entity data and resetting article analysis status. This tool is useful when you want to reanalyze articles without re-scraping them.

**Usage:**
```bash
# Do a dry run first (shows what would be reset without changing anything)
./run.sh analyze reset-database --dry-run

# Reset the entire database (remove all entity data and reset all article status)
./run.sh analyze reset-database

# Only reset articles older than 48 hours
./run.sh analyze reset-database --keep-recent-hours=48

# Reset article status but keep entity data
./run.sh analyze reset-database --keep-entities
```

**Key Features:**
- Removes entity mentions and entities from the database
- Resets article analysis status to 'unanalyzed'
- Clears processed_at and batch_id fields
- Option to keep recently analyzed articles (within specified hours)
- Option to preserve entity data while still resetting article status

## Recommended Maintenance Schedule

For optimal analyzer performance, consider implementing the following maintenance schedule:

1. **Daily**:
   - Run `monitor_batch_analysis.py` to check system status
   - Run `reset_stuck_articles.py` to clear any stuck articles

2. **After System Interruptions**:
   - Run `analyze_db_status.py` to assess the database state
   - Run `reset_stuck_articles.py` to clear any stuck articles
   - If needed, run `recover_openai_batches.py` to recover any missing analysis

3. **When Troubleshooting**:
   - Run all diagnostic tools to get a complete picture of the system state
   - Compare the outputs to identify any inconsistencies

4. **Before Major Changes or Testing**:
   - Use `reset_database.py` to clear analysis data and start fresh
   - Consider using `--keep-recent-hours` to preserve recent analysis while clearing older data
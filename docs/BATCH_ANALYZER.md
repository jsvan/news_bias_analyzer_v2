# Cultural Orientation Batch Analyzer

The Batch Analyzer is a module that analyzes news articles in batches to identify how news sources implicitly establish moral direction through entity portrayal. Using OpenAI's Batch API with the gpt-4.1-nano model, this approach offers several advantages:

- **Cost Efficiency**: 50% cost reduction compared to the standard OpenAI API
- **Higher Rate Limits**: Significantly higher throughput than the synchronous API
- **Scalable Processing**: Can handle large volumes of articles efficiently

## How It Works

The Batch Analyzer maintains a workflow for processing articles in batches:

1. **Batch Creation**: Selects up to 100 unanalyzed articles and packages them into a batch
2. **Batch Management**: Only runs 5 batches at a time to avoid system overload
3. **Status Tracking**: Maintains a `batches.txt` file to keep track of active batches
4. **Polling**: Checks batch status every 5 minutes
5. **Result Processing**: Updates the database when batches complete

## Article Processing Status

Articles can have one of the following statuses:

- `unanalyzed`: New articles that haven't been processed yet
- `in_progress`: Articles that are currently in an active batch
- `completed`: Articles that have been successfully analyzed
- `failed`: Articles that failed analysis for some reason

## Running the Batch Analyzer

### One-Time Run

```bash
./run.sh analyze
```

This command will:
1. Check existing batches and process any completed ones
2. Create new batches if fewer than 5 are active
3. Exit when done

### Daemon Mode

```bash
./run.sh analyze daemon
```

This command will:
1. Check existing batches and process any completed ones
2. Create new batches if fewer than 5 are active
3. Sleep for 5 minutes
4. Repeat the process until manually terminated (Ctrl+C)

## Configuration

The Batch Analyzer uses the following environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: The model to use (defaults to "gpt-4.1-nano")
- `DATABASE_URL`: Your PostgreSQL database connection string

These values should be set in your `.env` file.

## Batch Files

The Batch Analyzer creates and maintains several files:

- `analyzer/batches.txt`: Tracks active batches
- `batches/*.jsonl`: Input files for the OpenAI Batch API
- `batches/*.articles.json`: Mapping between batch custom IDs and article IDs

## Error Handling

- Failed batches are detected and removed from the active list
- Articles in failed batches are reset to "unanalyzed" status
- A detailed log is maintained in `logs/batch_analysis.log`

## Database Schema

The analyzer uses the following columns in the `news_articles` table:

- `analysis_status`: Current processing status (unanalyzed, in_progress, completed, failed)
- `batch_id`: The OpenAI batch ID if the article is in a batch
- `last_analysis_attempt`: Timestamp of the last analysis attempt

## Alembic Migration

An Alembic migration script (`011_add_article_analysis_status.py`) is provided to update your database schema. Run it with:

```bash
cd database
alembic upgrade head
```

## Locking Mechanism

The Batch Analyzer uses a file lock (`analyzer.lock`) to ensure only one instance runs at a time. This prevents conflicts when multiple processes try to create or process batches simultaneously.

## Batch Size and Limits

- Each batch contains up to 100 articles
- A maximum of 5 batches can be active at once
- The system will automatically create new batches as older ones complete
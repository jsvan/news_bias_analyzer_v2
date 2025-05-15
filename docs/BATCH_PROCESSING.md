# Batch Processing with OpenAI

This document explains how to use the batch processing features to analyze articles more efficiently and at a 50% cost reduction compared to standard API calls.

## Overview

The News Bias Analyzer includes support for OpenAI's Batch API, which allows you to:

1. Submit large batches of article analysis requests at once
2. Save 50% on OpenAI API costs compared to synchronous processing
3. Process more articles with higher rate limits
4. Track batch job status and retrieve results when ready

## Batch Processing Workflow

The batch processing workflow consists of these steps:

1. **Prepare**: Generate a batch input file from unanalyzed articles in the database
2. **Upload**: Upload the batch file to OpenAI
3. **Create**: Create a batch job using the uploaded file
4. **Check**: Monitor the status of your batch job
5. **Fetch**: Download results once the batch is complete
6. **Process**: Save the analysis results to your database

## Command Reference

All commands are available through the `run.sh` script:

### 1. Prepare a Batch

```bash
./run.sh batch-analyze [OPTIONS]
```

Options:
- `--count N`: Maximum number of articles to include (default: all unanalyzed)
- `--max N`: Maximum batch size limit (default: 5000, max allowed: 50000)
- `--model MODEL`: OpenAI model to use (default: gpt-4.1-nano)
- `--output FILENAME`: Custom output filename

This creates a batch file in the `batches/` directory.

### 2. Upload the Batch File

```bash
./run.sh batch-upload PATH_TO_BATCH_FILE
```

Example:
```bash
./run.sh batch-upload batches/batch_20240511_123456.jsonl
```

This uploads the file to OpenAI and returns a file ID.

### 3. Create a Batch Job

```bash
./run.sh batch-create FILE_ID
```

Example:
```bash
./run.sh batch-create file-abc123
```

This creates a batch job and returns a batch ID.

### 4. Check Batch Status

```bash
./run.sh batch-check BATCH_ID
```

Example:
```bash
./run.sh batch-check batch_xyz789
```

This shows the current status, progress, and completion percentage.

### 5. Fetch Batch Results

```bash
./run.sh batch-fetch BATCH_ID [OPTIONS]
```

Options:
- `--metadata PATH`: Path to the metadata file (optional)
- `--process`: Process results immediately after downloading

Example:
```bash
./run.sh batch-fetch batch_xyz789 --process
```

### 6. Process Batch Results

```bash
./run.sh batch-process PATH_TO_RESULTS_FILE [OPTIONS]
```

Options:
- `--metadata PATH`: Path to the metadata file (optional)

Example:
```bash
./run.sh batch-process batches/results/batch_xyz789_20240511_123456.jsonl
```

## Complete Example Workflow

### Option 1: The Automated Way

```bash
# Run the entire process in one command:
./run.sh batch-auto

# Check status periodically
./run.sh batch-check batch_xyz789
# Output: Status: in_progress, Progress: 45.0% (45/100)

# When complete, fetch and process results
./run.sh batch-fetch batch_xyz789 --process
```

### Option 2: Step by Step

```bash
# 1. Prepare a batch with all unanalyzed articles (up to the default max of 5000)
./run.sh batch-analyze

# 2. Upload the generated batch file
./run.sh batch-upload batches/batch_20240511_123456.jsonl
# Output: File ID: file-abc123

# 3. Create a batch job
./run.sh batch-create file-abc123
# Output: Batch ID: batch_xyz789

# 4. Check status periodically
./run.sh batch-check batch_xyz789
# Output: Status: in_progress, Progress: 45.0% (45/100)

# 5. When complete, fetch and process results
./run.sh batch-fetch batch_xyz789 --process

# OR download first, then process separately
./run.sh batch-fetch batch_xyz789
./run.sh batch-process batches/results/batch_xyz789_20240511_123456.jsonl
```

## Cost Comparison

- **Standard API**: Full cost per token
- **Batch API**: 50% cost reduction per token

For example, analyzing 1000 articles:
- Standard API: ~$10.00
- Batch API: ~$5.00

## Best Practices

1. Use large batch sizes (50-100 articles) for maximum efficiency
2. Run batch processing in parallel with scraping:
   - `./run.sh scraper` in one terminal
   - Periodically run batch processing in another
3. Use gpt-3.5-turbo for the best balance of cost and quality
4. Keep the metadata file associated with each batch for proper tracking

## Batch vs. Streaming Analysis

- **Streaming Analysis** (`analyze-only`): Good for immediate results, full cost
- **Batch Processing**: Better for large volumes, 50% cost reduction, results delayed

For optimal efficiency, use both:
1. Run the scraper continuously
2. Use batch processing for most articles (cost savings)
3. Use streaming analysis for a small sample to get immediate feedback
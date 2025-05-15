# Deprecated Files in the Analyzer Directory

After implementing the new batch analyzer that uses OpenAI's Batch API, the following files in the `/analyzer` directory are now deprecated and can be deleted:

## Fully Deprecated Files

1. **direct_analysis.py**
   - Reason: The new batch_analyzer.py completely replaces this functionality
   - Status: Can be deleted
   - Notes: The new batch analyzer is more efficient, cost-effective, and has proper status tracking

2. **openai_processor.py**
   - Reason: Contained a single-article processing approach that is superseded by batch processing
   - Status: Can be deleted
   - Notes: The sentiment analysis functionality is now handled by the batch_analyzer.py module

3. **article_processor.py**
   - Reason: Contains older, less efficient article processing logic
   - Status: Can be deleted
   - Notes: The batch_analyzer.py module now handles all article processing needs

## Files to Keep

1. **prompts.py**
   - Reason: Contains the main prompts used by the batch analyzer
   - Status: Keep
   - Notes: This file is still used by the new batch analyzer

2. **config.py**
   - Reason: Contains configuration settings that might be useful for other components
   - Status: Keep
   - Notes: The batch analyzer currently reads environment variables directly, but might use this in the future

3. **openai_integration.py**
   - Reason: Contains some utility functions and error handling logic that could be useful
   - Status: Consider refactoring rather than deleting
   - Notes: Some parts could be integrated into the batch analyzer, but it has useful OpenAI utility functions that might be needed elsewhere

## How to Delete Safely

Before deleting any files, ensure you have:

1. Migrated the database schema using the provided migration script
2. Tested the new batch analyzer thoroughly
3. Backed up any important logic from the deprecated files

To safely delete the files:

```bash
# Make sure you have a backup or git commit
git add .
git commit -m "Implement new batch analyzer with OpenAI Batch API"

# Remove deprecated files
rm /Users/jsv/Projects/news_bias_analyzer/analyzer/direct_analysis.py
rm /Users/jsv/Projects/news_bias_analyzer/analyzer/openai_processor.py
rm /Users/jsv/Projects/news_bias_analyzer/analyzer/article_processor.py
```
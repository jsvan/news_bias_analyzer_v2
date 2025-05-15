# Quote Tracking Feature

This document explains how to use the quote tracking feature in the News Bias Analyzer.

## Overview

The quote tracking feature extracts direct quotes from political figures and public personalities in news articles. This allows you to:

1. Track what political figures say about various topics over time
2. Analyze shifts in positions and rhetoric
3. Compare quotes across different news sources
4. Build a historical record of statements by public figures

## Database Schema

The quote tracking system uses four main tables:

1. **public_figures**: Notable people whose quotes we're tracking
   - Stores name, title, country, and political party

2. **quotes**: The actual quote text and metadata
   - Links to the public figure and the article it appeared in
   - Contains the exact quote, context, and publication date
   - Includes sentiment analysis scores

3. **topics**: Categories for classifying quotes (e.g., economy, immigration)
   - Hierarchical structure (topics can have parent topics)

4. **quote_topics**: Links quotes to their relevant topics
   - Many-to-many relationship between quotes and topics
   - Includes relevance scores

## Setting Up the Quote Tables

Before using the quote tracking feature, you need to add the required tables to your database:

```bash
# Run the database migration to add quote tracking tables
./scripts/setup_quote_tables.sh
```

This migration adds the necessary tables to your existing database without affecting your current data.

## Extracting Quotes

Once the tables are set up, quotes are automatically extracted during the article analysis process. No separate command is needed:

```bash
# Analyze articles and extract quotes in one step
./run_analyzer.sh analyze --limit 10

# Run the full pipeline (scraping, analysis, and quote extraction)
./run_analyzer.sh all
```

Quotes are extracted as part of the normal article analysis process, making the pipeline simpler and more efficient.

## How It Works

During article analysis, OpenAI simultaneously:

1. Analyzes entities and their sentiment (power/moral dimensions)
2. Identifies direct quotes from public figures 

For each quote, it extracts:
1. The speaker's name and title/role
2. The exact quote text 
3. Main topics discussed in the quote
4. Overall sentiment of the quote (-2 to +2 scale)

This integrated approach is more efficient than separate processes since:
1. It requires only one API call instead of two
2. It processes the same text once rather than multiple times
3. It eliminates the need for a separate processing step

Only direct quotes with clearly identified speakers are extracted. Paraphrased statements are not included.

## Viewing Quote Data

You can see a summary of the quote data using the database summary command:

```bash
./run_analyzer.sh summary
```

This will show:
- Total number of public figures in the database
- Total number of quotes extracted
- Top public figures by quote count

## Use Cases

### Tracking Political Positioning

Monitor how politicians discuss specific topics and how their rhetoric evolves over time. For example, track a politician's statements on climate change or immigration policy across multiple years.

### Fact-Checking

When a political figure makes a claim, you can search for their previous statements on the same topic to check for consistency or contradictions.

### Content Analysis

Analyze the linguistic patterns, sentiment, and topic focus across different political figures or parties.

### Historical Record

Build a comprehensive archive of political statements that can be searched, filtered, and analyzed for historical research.

## Future Enhancements

1. **Topic Analysis**: More sophisticated classification of quote topics using a hierarchical topic model.

2. **Entity Recognition**: Better identification of entities mentioned in quotes.

3. **Quote Clustering**: Group similar quotes together to identify talking points and messaging patterns.

4. **Timeline Visualization**: Create timeline views of quotes by person, topic, or sentiment.

5. **Quote Verification**: Cross-reference quotes across multiple sources to verify accuracy.

## Technical Details

The quote extraction uses a dedicated OpenAI prompt optimized for identifying direct quotes and their attributes. The system is designed to:

- Minimize false positives (only extract clear, direct quotes)
- Properly attribute quotes to their speakers
- Identify the context in which the quote was made
- Analyze sentiment on a scale from -2 (very negative) to +2 (very positive)
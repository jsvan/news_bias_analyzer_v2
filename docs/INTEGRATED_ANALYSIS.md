# Integrated Entity and Quote Analysis

This document explains how the News Bias Analyzer performs integrated entity sentiment analysis and quote extraction in a single process.

## Overview

Originally, the News Bias Analyzer had separate processes for:
1. Analyzing entity sentiment (how entities are portrayed in articles)
2. Extracting quotes from public figures

We've now integrated these into a single streamlined process that:
- Uses one OpenAI API call instead of two
- Processes each article only once
- Stores both entity sentiment and quotes in a single transaction
- Simplifies the overall workflow

## How It Works

### 1. OpenAI Prompt

We use a carefully designed prompt that asks OpenAI to perform two tasks simultaneously:

```
TASK 1: Extract named entities and rate how they're portrayed.
Entity types: People, Organizations, Countries/Regions, Political groups
For each, provide these scores:
- Power: -2 (weak) to +2 (powerful)
- Moral: -2 (negative portrayal) to +2 (positive portrayal)

TASK 2: Extract direct quotes from public figures (politicians, officials, celebrities, etc.).
For each quote:
- Include the speaker's name and title/role
- Extract the exact quote text
- List 1-3 main topics of the quote
- Rate the sentiment (-2 negative to +2 positive)
```

### 2. Response Format

The OpenAI response includes both entity data and quotes in a single JSON structure:

```json
{
  "entities": [
    {"name": "President Smith", "type": "People", "power_score": 2, "moral_score": 1},
    {"name": "Johnson", "type": "People", "power_score": 1, "moral_score": 0},
    {"name": "Federal Reserve", "type": "Organizations", "power_score": 2, "moral_score": 0}
  ],
  "quotes": [
    {
      "speaker": "President Smith",
      "title": "President",
      "quote": "The economy needs both stability and growth. We will cut unnecessary regulations while investing in key infrastructure projects.",
      "topics": ["Economy", "Regulation", "Infrastructure"],
      "sentiment": 1
    },
    {
      "speaker": "Johnson",
      "title": "Opposition leader",
      "quote": "This plan fails to address the fundamental challenges facing working families. We need real solutions, not empty promises.",
      "topics": ["Economy", "Social Policy"],
      "sentiment": -1
    }
  ]
}
```

### 3. Database Storage

When the response is received:

1. **Entity Processing**:
   - Entities and their sentiment scores are stored in the `entities` and `entity_mentions` tables
   - Duplicate entities are handled automatically

2. **Quote Processing**:
   - Public figures are created or retrieved from the `public_figures` table
   - Quotes are stored in the `quotes` table
   - Topics are extracted and stored in the `topics` table
   - Quote-topic relationships are stored in the `quote_topics` table

3. **Transaction Management**:
   - All database operations are wrapped in a single transaction
   - If any part fails, the entire transaction is rolled back
   - The article is marked as processed only if everything succeeds

## Benefits

### 1. Efficiency

- **Reduced API Costs**: One API call instead of two means lower OpenAI costs
- **Faster Processing**: Each article is processed only once
- **Simpler Codebase**: Fewer components and processing steps

### 2. Improved Data Quality

- **Consistent Analysis**: Entity and quote analysis are performed in the same context
- **Unified View**: Entity sentiment and quotes are analyzed together, providing better context
- **Reduced Redundancy**: No need to extract the same information multiple times

### 3. Simplified User Experience

- **Fewer Commands**: No separate command for quote extraction
- **Automatic Process**: Quotes are extracted automatically during entity analysis
- **Unified Workflow**: A single pipeline handles all analytical needs

## Example OpenAI Output

Here's an example of the integrated analysis results:

```json
{
  "entities": [
    {"name": "President Smith", "type": "People", "power_score": 2, "moral_score": 1},
    {"name": "Treasury Secretary Williams", "type": "People", "power_score": 1, "moral_score": 1},
    {"name": "Johnson", "type": "People", "power_score": 1, "moral_score": -1},
    {"name": "Maria Rodriguez", "type": "People", "power_score": 1, "moral_score": 0},
    {"name": "Tom Chen", "type": "People", "power_score": 0, "moral_score": 0},
    {"name": "Federal Reserve", "type": "Organizations", "power_score": 2, "moral_score": 0},
    {"name": "Capital Investment Bank", "type": "Organizations", "power_score": 1, "moral_score": 0},
    {"name": "Environmental Action Network", "type": "Organizations", "power_score": 0, "moral_score": 0}
  ],
  "quotes": [
    {
      "speaker": "President Smith",
      "title": "President",
      "quote": "The economy needs both stability and growth. We will cut unnecessary regulations while investing in key infrastructure projects.",
      "topics": ["Economy", "Regulation", "Infrastructure"],
      "sentiment": 1
    },
    {
      "speaker": "Johnson",
      "title": "Opposition leader",
      "quote": "This plan fails to address the fundamental challenges facing working families. We need real solutions, not empty promises.",
      "topics": ["Economy", "Social Policy"],
      "sentiment": -1
    },
    {
      "speaker": "Treasury Secretary Williams",
      "title": "Treasury Secretary",
      "quote": "Our models show that this balanced strategy will reduce inflation by 2% within 18 months while adding approximately 300,000 new jobs.",
      "topics": ["Economy", "Inflation", "Employment"],
      "sentiment": 1
    },
    {
      "speaker": "Maria Rodriguez",
      "title": "Chief Economist at Capital Investment Bank",
      "quote": "This is a step in the right direction, but lacks specifics on implementation.",
      "topics": ["Economy", "Policy"],
      "sentiment": 0
    },
    {
      "speaker": "Tom Chen",
      "title": "Environmental Action Network director",
      "quote": "While we appreciate the focus on infrastructure, the plan doesn't do enough to address climate change. We cannot build a sustainable economy without addressing our reliance on fossil fuels.",
      "topics": ["Climate Change", "Infrastructure", "Environment"],
      "sentiment": -1
    }
  ]
}
```

## Usage

To use the integrated analysis, simply run:

```bash
# Analyze articles (which now includes quote extraction)
./run_analyzer.sh analyze

# Or run the full pipeline 
./run_analyzer.sh all
```

No separate command for quote extraction is needed since the process is now integrated.
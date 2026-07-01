# Cultural Orientation Analyzer Component

The analyzer component processes news articles to extract entities and analyze how news sources implicitly establish moral direction through entity portrayal. Based on principles from Peter Pomerantsev's work on information manipulation, this component reveals the implicit moral compass embedded in news narratives.

## Features
- OpenAI API integration with a cheap small model (default gpt-4.1-nano, override via OPENAI_MODEL — see docs/SEEDING_AND_MODELS.md)
- Entity extraction identifying moral anchors in news content
- Two-dimensional analysis: power portrayal and alignment with implicit societal vision
- Identification of strategic entity positioning to guide reader judgment
- Extraction of key phrases that reveal subtle moral positioning

## Key Files
- `batch_analyzer.py` - Main analysis path: OpenAI Batch API daemon
- `openai_integration.py` - Synchronous OpenAI wrapper (used by the extension API's real-time /analyze)
- `prompts.py` - Carefully crafted prompts that guide the cultural orientation analysis
- `config.py` - Configuration settings (model, cost limits)
- `process_local_batches.py` - Recover/continue partially downloaded batches
- `hotelling_t2.py` - Weekly statistics and article extremeness scoring

## Philosophical Approach

The analyzer is built on the understanding that all news sources operate from an implicit moral compass and vision for society. Our approach:

1. **Identifies Moral Anchors**: Extracts entities that serve as orientation points for readers
2. **Reveals Positioning**: Shows how entities are framed as either advancing or hindering an implicit societal direction
3. **Surfaces Word Choice**: Detects subtle linguistic choices that reveal underlying moral perspectives
4. **Traces Strategic Shifts**: Tracks how entity positioning changes over time to align with evolving strategic objectives
5. **Abstracts Individual Mentions**: Connects individual actors to their larger cultural/ideological forces
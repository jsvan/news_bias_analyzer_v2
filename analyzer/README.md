# Cultural Orientation Analyzer Component

The analyzer component processes news articles to extract entities and analyze how news sources implicitly establish moral direction through entity portrayal. Based on principles from Peter Pomerantsev's work on information manipulation, this component reveals the implicit moral compass embedded in news narratives.

## Features
- OpenAI API integration with gpt-4.1-nano for efficient analysis
- Entity extraction identifying moral anchors in news content
- Two-dimensional analysis: power portrayal and alignment with implicit societal vision
- Identification of strategic entity positioning to guide reader judgment
- Extraction of key phrases that reveal subtle moral positioning

## Key Files
- `openai_integration.py` - Core OpenAI API wrapper using gpt-4.1-nano
- `article_processor.py` - Main article processing pipeline
- `prompts.py` - Carefully crafted prompts that guide the cultural orientation analysis
- `config.py` - Configuration settings
- `direct_analysis.py` - Utility for direct article analysis
- `batch_analyzer.py` - Efficient batch processing of articles

## Philosophical Approach

The analyzer is built on the understanding that all news sources operate from an implicit moral compass and vision for society. Our approach:

1. **Identifies Moral Anchors**: Extracts entities that serve as orientation points for readers
2. **Reveals Positioning**: Shows how entities are framed as either advancing or hindering an implicit societal direction
3. **Surfaces Word Choice**: Detects subtle linguistic choices that reveal underlying moral perspectives
4. **Traces Strategic Shifts**: Tracks how entity positioning changes over time to align with evolving strategic objectives
5. **Abstracts Individual Mentions**: Connects individual actors to their larger cultural/ideological forces
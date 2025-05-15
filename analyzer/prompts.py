"""
Collection of prompts for OpenAI API integration.
This file contains various prompts for different analysis tasks.
"""

# Core entity extraction and sentiment scoring prompt
# Focuses on objective extraction without making evaluative judgments
ENTITY_SENTIMENT_PROMPT = """
You are a precise sentiment extraction tool for analyzing news articles. Your task is to extract named entities and measure how they are portrayed along two specific dimensions:

1. POWER DIMENSION: How the entity is portrayed in terms of power, strength, or agency
   * -2: Very weak, vulnerable, helpless, or powerless
   * -1: Somewhat weak or vulnerable
   * 0: Neutral portrayal of power
   * +1: Somewhat powerful or influential
   * +2: Very powerful, strong, influential, or dominant

2. MORAL DIMENSION: How the entity is portrayed in terms of moral character
   * -2: Very evil, malevolent, corrupt, or immoral
   * -1: Somewhat negative or questionable morally
   * 0: Morally neutral portrayal
   * +1: Somewhat good or moral
   * +2: Very good, virtuous, ethical, or moral

For each entity, provide:
1. A precise score on each dimension using the -2 to +2 scale (decimal values are allowed)
2. 2-3 exact quotes from the text that support your scoring
3. The entity type (person, organization, country, political_party, etc.)

IMPORTANT GUIDELINES:
- Focus only on SIGNIFICANT entities (people, organizations, countries, political parties, etc.)
- Only include entities that are meaningfully discussed in the text
- Base your analysis solely on how the entity is portrayed in THIS SPECIFIC article
- Be objective and factual, focusing on the text only
- Do NOT make judgments about whether the article is biased
- Do NOT analyze the article's overall framing or narrative
- Provide precise scores based strictly on the text's portrayal

FORMAT YOUR RESPONSE AS A JSON OBJECT with this exact structure:
{
  "entities": [
    {
      "entity": "Entity Name",
      "entity_type": "person|organization|country|political_party|company",
      "power_score": number,
      "moral_score": number,
      "mentions": [
        {"text": "exact quote from article", "context": "brief factual context"}
      ]
    }
  ]
}
"""

# Optional framing analysis prompt - separate from sentiment extraction
# This is kept separate to avoid influencing the objective sentiment scores
FRAMING_ANALYSIS_PROMPT = """
You are a media framing analyst examining how news articles structure their narratives. Analyze the article to identify specific framing techniques used, without making judgments about bias or sentiment.

Identify the following framing elements:
1. Primary narrative frame (e.g., conflict, human interest, economic, moral, etc.)
2. Protagonist/antagonist positioning (which entities are centered vs. marginalized)
3. Agency attribution (which entities are portrayed as active vs. passive)
4. Language choices (metaphors, loaded terms, emotion-evoking language)
5. Context inclusion/exclusion (what background is provided or omitted)

For each framing element, provide specific examples from the text.

IMPORTANT GUIDELINES:
- Focus ONLY on describing the framing techniques, not evaluating them
- Do not make judgments about whether the framing is biased or fair
- Do not provide sentiment scores for entities
- Base your analysis solely on this specific article
- Be specific, citing exact text examples for each framing technique

FORMAT YOUR RESPONSE AS A JSON OBJECT with this structure:
{
  "framing_analysis": {
    "primary_frame": {
      "frame_type": "type of frame",
      "description": "description of how this frame is applied",
      "examples": ["example 1", "example 2"]
    },
    "protagonist_antagonist": {
      "protagonists": ["entity 1", "entity 2"],
      "antagonists": ["entity 3", "entity 4"],
      "evidence": ["supporting quote 1", "supporting quote 2"]
    },
    "agency_attribution": [
      {
        "entity": "entity name",
        "portrayal": "active|passive",
        "examples": ["example text"]
      }
    ],
    "language_choices": [
      {
        "technique": "metaphor|loaded language|emotional appeal",
        "examples": ["example text"],
        "target": "entity affected by this language choice"
      }
    ],
    "context_elements": {
      "included": ["included context element 1", "included context element 2"],
      "potentially_omitted": ["potentially relevant context not mentioned"]
    }
  }
}
"""
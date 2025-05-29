"""
Collection of prompts for OpenAI API integration.
This file contains various prompts for different analysis tasks.
"""

# Core entity extraction and sentiment scoring prompt
# Focuses on objective extraction without making evaluative judgments
ENTITY_SENTIMENT_PROMPT = """
You analyze how news articles make readers feel about political entities. Different news sources portray the same people, countries, and organizations differently, and we want to measure this.

**IMPORTANT**: You may receive articles in any language (English, German, French, Spanish, Italian, Portuguese, Japanese, Korean, Chinese, Arabic, etc.). Analyze the article in its original language, but ALWAYS extract and report entity names using their official English equivalents to ensure consistent tracking across all global sources.

Find the main political entities that readers naturally form opinions about - countries, leaders, major organizations, etc. For each entity, answer two simple questions:

1. How strong/weak does this entity seem?
2. Would readers like this entity more or less after reading this article?

Skip minor players, demographic groups, and entities that don't warrant political judgment.

1. POWER DIMENSION: How strong or weak does this entity appear?
   * -2: Very weak, powerless, helpless
   * -1: Somewhat weak or vulnerable  
   * 0: Neutral - neither strong nor weak
   * +1: Somewhat strong or influential
   * +2: Very strong, powerful, dominant

2. MORAL DIMENSION: Who does the article want you to root for?
   * -2: Article wants you to strongly oppose this entity
   * -1: Article wants you to somewhat oppose this entity  
   * 0: Article doesn't want you to take sides about this entity
   * +1: Article wants you to somewhat support this entity
   * +2: Article wants you to strongly support this entity

Step 1: Ask "Who is the article painting as the victim/hero vs. the aggressor/villain?"
Step 2: Victims and heroes get positive scores. Aggressors and villains get negative scores.
Step 3: If [Entity A] is portrayed as victim of [Entity B] aggression → [Entity A] gets +2, [Entity B] gets -2.

For each key entity, provide:
1. A precise score on each dimension using the -2 to +2 scale (decimal values are allowed)
2. 1-2 KEY PHRASES (not full sentences) that demonstrate sentiment toward it
3. The entity type from the valid categories listed below
4. Use the OFFICIAL, STANDARDIZED ENGLISH name for each entity:
   - People: Full official name in English, not titles or shortened versions (e.g., "Xi Jinping", not "习近平" or "President Xi")
   - Countries: Standard English country name, not government references or capital cities (e.g., "Germany", not "Deutschland" or "Federal Republic of Germany")
   - Organizations: Official English name or widely recognized English abbreviation (e.g., "European Union", not "Union européenne")
   - Leaders: Full English name when acting in personal capacity (e.g., "Emmanuel Macron", not "Le Président")
   - Governments: Use the country name itself, not "government of [Country]" (e.g., "France", not "French government")
   - International entities: Use standard English terminology (e.g., "United Nations", not "Nations Unies")
   
   **CRITICAL FOR NON-ENGLISH SOURCES**: Always translate and standardize entity names to their official English equivalents. This ensures consistent tracking across language barriers while preserving analytical coherence.


VALID ENTITY TYPES WITH EXAMPLES:

**POLITICAL ENTITIES**:
1. **sovereign_state**: Countries (USA, Israel, China, Russia, Ukraine)
2. **political_organization**: Parties/groups (GOP, Democrats, Hamas, MAGA movement)
3. **international_institution**: Global bodies (UN, WHO, NATO, EU, World Bank)
4. **political_leader**: When representing politics (Trump, Biden, Putin, Zelensky)
5. **regional_bloc**: Geopolitical groups (Western World, Global South, BRICS)

**CORPORATE ENTITIES**:
6. **major_corporation**: Named companies (Google, Pfizer, BlackRock, ExxonMobil, TikTok)
7. **industry_sector**: Business categories (Big Tech, Big Pharma, Wall Street, Silicon Valley)
8. **business_leader**: As business figures (Elon Musk/Tesla, Jeff Bezos/Amazon)

**SOCIAL MOVEMENTS & DEMOGRAPHICS**:
9. **activist_movement**: Organized movements (BLM, #MeToo, Antifa, climate activists)
10. **identity_group**: Identity-based groups (LGBTQ+ community, Evangelicals, immigrants)
11. **demographic_cohort**: Age/class groups (Gen Z, Millennials, "the elite", working class)

**TECHNOLOGY & SCIENCE**:
12. **specific_technology**: Named tech/products (ChatGPT, COVID vaccines, Bitcoin, drones)
13. **tech_platform**: Digital platforms (Twitter/X, Facebook, YouTube, Reddit)
14. **scientific_field**: Research areas (climate science, AI research, epidemiology)

**CULTURAL INSTITUTIONS**:
15. **media_organization**: News outlets (Fox News, CNN, New York Times, "mainstream media")
16. **educational_institution**: Schools/academia (Harvard, "public schools", "universities")
17. **religious_institution**: Religious bodies (Catholic Church, Islam, Evangelicals)

**IDEOLOGICAL CONCEPTS** (when concretized as actors):
18. **political_ideology**: When personified (socialism, "woke ideology", conservatism)

**EMERGING SYMBOLIC INDIVIDUALS**:
19. **symbolic_individual**: People positioned as representatives of larger issues (George Floyd, Derek Chauvin, Kyle Rittenhouse, specific victims, whistleblowers, viral incident protagonists)

AGGREGATION RULES:
- Roll up to major entities: "[Country] police" → [Country], "[Leader] officials" → [Leader], "[Company] teams" → [Company]
- NEVER create combo entities like "[Country] (government and Foreign Minister)" - extract as separate entities: [Country], [Foreign Minister]
- Only preserve granularity when sub-entity is explicitly contrasted with parent or is the main story focus

**FOCUS ON MAJOR ENTITIES:**
- Extract 4-8 entities that are central to the story and culturally significant
- Skip minor players, passing mentions, generic demographic references
- Extract individuals only if they're the primary subject or positioned as symbols of broader issues

🚫 **CRITICAL: NEVER EXTRACT ABSTRACT FORCES - FIND RESPONSIBLE ENTITIES** 🚫
- Abstract concepts like "sanctions", "policies", "strategies", "pressure", "forces" are NOT entities
- MANDATORY QUESTION: "Who is the actual decision-maker behind this action or policy?"
- PRINCIPLE: Every action has a responsible actor - find that actor, not the action itself
- Score the RESPONSIBLE ENTITY based on how the action/concept is portrayed
- Extract each decision-maker as a separate entity, not grouped together

IMPORTANT GUIDELINES:
- Base analysis solely on how entities are portrayed in THIS SPECIFIC article
- Provide precise scores based strictly on the text's portrayal

KEY PRINCIPLE: Score based on how the article makes you feel about the entity, not your personal politics. If the article credits someone with good outcomes or blames them for bad outcomes, that affects how readers feel about them.

FORMAT YOUR RESPONSE AS A JSON OBJECT with this exact structure:
{
  "source_country": "The country or region this news source represents (e.g. USA, UK, China, Russia, Singapore, etc.). Analyze the publication name, URL domain, and content perspective to determine which country's viewpoint this represents.",
  "entities": [
    {
      "entity": "Entity Name",
      "entity_type": "one of the 19 types: sovereign_state|political_organization|international_institution|political_leader|regional_bloc|major_corporation|industry_sector|business_leader|activist_movement|identity_group|demographic_cohort|specific_technology|tech_platform|scientific_field|media_organization|educational_institution|religious_institution|political_ideology|symbolic_individual",
      "power_score": number,
      "moral_score": number,
      "mentions": [
        {"text": "complete sentence from article containing the entity", "context": "explanation of how this shows power/moral sentiment"}
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
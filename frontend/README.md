# Cultural Orientation Dashboard

The frontend dashboard visualizes how news sources implicitly establish moral direction through entity portrayal. It reveals the narratives, archetypes, and shifting positions that shape our perception of world events.

## Features
- Power/Moral positioning quadrant visualization (Hero, Villain, Victim, Threat archetypes)
- Temporal tracking of entity positioning shifts across sources
- Statistical comparison of entity portrayals between sources and countries
- Entity distribution visualization showing unusual vs. typical portrayals
- Comparative analysis of how different information environments frame the same events

## Key Files
### Frontend
- `pages/NewsComparisonPage.tsx` - Main comparison dashboard
- `components/SentimentChart.tsx` - Sentiment visualization
- `components/SentimentDistributionChart.tsx` - Distribution visualization
- `services/api.ts` - Backend API client
- `types/index.ts` - TypeScript type definitions

### Backend API
- `api/statistical_endpoints.py` - API endpoints for statistics
- `api/statistical_models.py` - Statistical analysis models
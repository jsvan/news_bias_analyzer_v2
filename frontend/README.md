# News Bias Analyzer Dashboard

The frontend dashboard visualizes how news sources implicitly establish moral direction through entity portrayal. It reveals the narratives, archetypes, and shifting positions that shape our perception of world events.

## Features
- Power/Moral positioning quadrant visualization (Hero, Villain, Victim, Threat archetypes)
- Temporal tracking of entity positioning shifts across sources
- Statistical comparison of entity portrayals between sources and countries
- Entity distribution visualization showing unusual vs. typical portrayals
- Comparative analysis of how different information environments frame the same events

## Getting Started

### Prerequisites
- Node.js 16+ and npm
- News Bias Analyzer backend API running (default: http://localhost:8000)

### Installation
1. Navigate to the frontend directory
   ```bash
   cd /path/to/news_bias_analyzer/frontend
   ```

2. Install dependencies
   ```bash
   npm install
   ```

3. Start the development server
   ```bash
   npm run dev
   ```

4. Open your browser to http://localhost:3000

## Dashboard Components

The dashboard is organized into several key views:

### Entity Analysis
Shows how entities are positioned in the power/moral framework, revealing which entities are portrayed as heroes, villains, victims, or threats.

### Source Comparison
Compare how different news sources cover the same entities, revealing inherent bias patterns and editorial leanings.

### Temporal Trends
Track how entity sentiment changes over time, identifying narrative shifts and changing media attitudes.

### Statistical Distributions
Analyze the statistical significance of entity portrayals, identifying unusual or standard coverage patterns.

## Data Integration

The dashboard connects to the News Bias Analyzer API to fetch:
- Entity lists and sentiment scores
- Source information and bias profiles
- Temporal trend data
- Statistical distributions

## Key Files
- `index.tsx` - Entry point for the application
- `pages/Dashboard.tsx` - Main dashboard component
- `components/SentimentChart.tsx` - Entity positioning visualization
- `components/SentimentDistributionChart.tsx` - Distribution visualization
- `components/EntityTrendChart.tsx` - Temporal trend visualization
- `components/SourceBiasChart.tsx` - Source comparison visualization
- `services/api.ts` - API client for backend communication
- `types/index.ts` - TypeScript type definitions

## Development

### Adding New Visualizations
1. Create a new visualization component in the `components` directory
2. Import and add it to the appropriate dashboard section
3. Connect it to the API data sources

### Creating New Views
1. Create a new page component in the `pages` directory
2. Add navigation to the new page in the dashboard
3. Import the necessary visualization components

## Data Analysis Flow

1. Raw news content is scraped and stored in the database
2. OpenAI analyzes content to extract entities and measure sentiment
3. Statistical models compare entity portrayals across sources
4. Frontend visualizes results through interactive charts
5. Users can filter and explore different dimensions of media bias
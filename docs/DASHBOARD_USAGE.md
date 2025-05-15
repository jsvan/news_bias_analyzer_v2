# News Bias Analyzer - Dashboard User Manual

This guide explains how to use the News Bias Analyzer dashboard to explore sentiment analysis data across news articles, sources, and entities.

## Accessing the Dashboard

### Public Dashboard

1. Navigate to `https://dashboard.newsbiasanalyzer.com` (or your custom deployment URL)
2. Use the public view for basic exploration features

### Authenticated Access

1. Click "Login" in the top-right corner
2. Enter your username and password
3. For new users, click "Register" and create an account (if public registration is enabled)

## Dashboard Overview

The News Bias Analyzer Dashboard provides a comprehensive interface for analyzing sentiment patterns across news sources, with several key sections:

### Main Dashboard

The default landing page displays:

- **Overview Statistics**: Total articles analyzed, entities tracked, sources monitored
- **Recent Trends**: Sentiment movement for major entities in the past 7 days
- **Global Distribution Map**: Worldwide sentiment visualization
- **Most Covered Entities**: Top entities by mention count and their sentiment profiles
- **Recent Articles**: Latest analyzed articles with unusual sentiment patterns

### Navigation

The left sidebar provides access to all major sections:

- **Dashboard**: Overview statistics and recent trends
- **Entities**: Browse and search all analyzed entities
- **Sources**: Explore news sources and their bias profiles
- **Trends**: Track sentiment changes over time
- **Analyze**: Submit custom articles for analysis
- **Settings**: Customize dashboard preferences (authenticated users only)

## Detailed Features

### Entities Page

Browse all entities (people, countries, organizations) mentioned in the news:

1. **Filter Options**:
   - By entity type (person, country, organization, etc.)
   - By mention count (popularity)
   - By sentiment range (power and moral scores)

2. **Entity Cards**:
   - Quick view of entity name, type, and sentiment summary
   - Trend indicator showing recent movement
   - Click any card to access detailed entity profile

3. **Search Function**:
   - Find specific entities by name
   - Autocomplete suggestions as you type

### Entity Detail Page

When you select an entity, you'll see comprehensive analysis:

1. **Entity Overview**:
   - Profile information (entity type, first appearance, mention count)
   - Recent articles mentioning this entity
   - Related entities (frequently co-mentioned)

2. **Sentiment Analysis**:
   - Current power and moral scores with historical context
   - Distribution charts comparing to typical portrayal
   - Breakdown by news source region

3. **Time-Series Analysis**:
   - Interactive chart showing sentiment trends over time
   - Configurable time range (7 days to 1 year)
   - Annotated with major news events

4. **Source Comparison**:
   - How different sources portray this entity
   - Political spectrum breakdown
   - National vs. international coverage differences

5. **Exemplar Quotes**:
   - Sample article quotes showing typical and unusual portrayals
   - Context for understanding what drives the scores

### Sources Page

Explore news sources and their sentiment patterns:

1. **Source Directory**:
   - Filterable list of all monitored news sources
   - Sortable by country, language, political leaning
   - Source reliability indicators

2. **Source Cards**:
   - Quick overview of each source
   - Article count and update frequency
   - Bias indicators for major entity categories

3. **Clustering View**:
   - Visual grouping of sources by similarity
   - Toggle between political, geographical, or sentiment-based clustering

### Source Detail Page

Detailed analysis of an individual news source:

1. **Source Profile**:
   - Basic information (country, language, founding date)
   - Update frequency and coverage scope
   - Ownership information (if available)

2. **Bias Analysis**:
   - Political bias detection with evidence
   - National/international bias patterns
   - Entity portrayal compared to global averages

3. **Historical Patterns**:
   - Sentiment trend changes over time
   - Before/after major events analysis
   - Comparison with similar sources

4. **Entity Coverage**:
   - Most frequently mentioned entities
   - Entities with unusual sentiment patterns
   - Topic and entity emphasis compared to other sources

### Trends Page

Track sentiment changes across time:

1. **Multi-Entity Tracking**:
   - Select multiple entities to compare trends
   - Normalized view to compare entities with different baseline portrayals
   - Correlation detection between entity sentiment changes

2. **Event Impact Analysis**:
   - Major news events marked on timeline
   - Sentiment shifts before and after key events
   - Configurable event categories (political, economic, disasters, etc.)

3. **Comparative Views**:
   - Source-to-source comparison
   - Country-to-country comparison
   - Historical vs. current patterns

4. **Custom Date Ranges**:
   - Select specific time periods for detailed analysis
   - Preset ranges (last week, month, year)
   - Compare different time periods side-by-side

### Analyze Page

Submit articles for custom analysis:

1. **Article Input**:
   - Paste URL for automatic fetching and analysis
   - Paste full text for direct analysis
   - Upload document (PDF, DOCX) for processing

2. **Analysis Results**:
   - Detected entities with sentiment scores
   - Comparison to typical coverage patterns
   - Statistical significance of unusual portrayals

3. **Batch Processing**:
   - Upload multiple URLs or documents
   - Comparative results across articles
   - Export analysis to PDF or Excel

## Dashboard Customization

Authenticated users can customize their experience:

### Widget Configuration

1. Click "Customize" in the top-right corner of the main dashboard
2. Add, remove, or rearrange dashboard widgets
3. Configure each widget's settings:
   - Change time range
   - Select specific entities or sources to track
   - Adjust chart types and visualization settings

### Saved Searches

Create and save frequently used searches:

1. Perform any search or filter operation
2. Click "Save Search" in the results view
3. Name and categorize your saved search
4. Access saved searches from the sidebar or your profile page

### Custom Alerts

Set up notifications for specific patterns:

1. Navigate to Settings → Alerts
2. Create a new alert with conditions:
   - Entity sentiment crosses threshold
   - Unusual source patterns detected
   - Significant changes in tracked entities
3. Configure delivery method (email, dashboard, browser notification)

## Working with Data

### Filtering Data

All data views support comprehensive filtering:

1. Use the filter panel on the left side of data views
2. Combine multiple filters (entity type, date range, source)
3. Save frequently used filter combinations

### Exporting Data

Extract data for external analysis:

1. Look for the "Export" button in data views
2. Select format (CSV, Excel, JSON)
3. Choose between current view or full dataset
4. For large datasets, scheduled exports are available

### Sharing Insights

Share your findings with others:

1. Use the "Share" button on any chart or view
2. Generate a public link (access level depends on your permissions)
3. Export as image, PDF report, or presentation slides
4. Embed charts in external websites (for authorized users)

## Advanced Features

### Statistical Models

Access detailed statistical information:

1. Click "Model Details" in any analysis view
2. See methodology explanation and model parameters
3. Confidence intervals and significance testing details
4. Toggle between simplified and advanced statistical views

### Entity Network Analysis

Explore relationships between entities:

1. Navigate to Entities → Network View
2. Visualize connections between entities based on co-mentions
3. Identify clusters and central entities
4. Track how networks evolve over time

### Content Analysis

Beyond sentiment, explore content patterns:

1. Navigate to Analysis → Content Patterns
2. See topic modeling results across sources
3. Language pattern analysis (framing, metaphors, emotional language)
4. Narrative structure identification

## API Integration

For developers and data scientists:

1. Access your API keys in Settings → API
2. View API documentation and examples
3. Set usage limits and tracking
4. Create applications that use the dashboard data

## Troubleshooting

### Common Issues

1. **Data not updating**:
   - Check the last update timestamp at the bottom of the dashboard
   - Data typically updates every 6 hours
   - For immediate updates, use the "Refresh Data" option (admin only)

2. **Charts not loading**:
   - Ensure your browser is updated
   - Try clearing your browser cache
   - Check your internet connection

3. **Search returning unexpected results**:
   - Verify spelling of entity names
   - Check that filters are not conflicting
   - Use entity IDs for precise matching

### Getting Help

If you encounter problems:

1. Click the "Help" button in the bottom-right corner
2. Check the FAQ section for common questions
3. Use the "Contact Support" form for technical issues
4. Join the user community forum for peer assistance

## Privacy and Data Usage

The dashboard adheres to strict privacy guidelines:

- No personal browsing data is collected
- User preferences are stored only for authenticated users
- Analysis is based solely on published news content
- Data retention follows our published privacy policy

## Updates and New Features

Stay informed about dashboard improvements:

1. Release notes appear upon login after updates
2. Subscribe to the feature update newsletter in Settings
3. Beta features can be enabled in Settings → Experimental Features

---

## Appendix: Understanding Sentiment Scores

### Power Score Interpretation (-2 to +2)

| Range | Interpretation | Example |
|-------|----------------|---------|
| +1.6 to +2 | Extremely powerful | "China dominates global manufacturing" |
| +0.8 to +1.6 | Significantly powerful | "The company expanded into three new markets" |
| 0 to +0.8 | Moderately powerful | "The senator introduced new legislation" |
| -0.8 to 0 | Somewhat weak | "The party struggles to attract younger voters" |
| -2 to -0.8 | Very weak/powerless | "Refugees flee with few possessions" |

### Moral Score Interpretation (-2 to +2)

| Range | Interpretation | Example |
|-------|----------------|---------|
| +1.6 to +2 | Extremely virtuous | "The foundation provided life-saving aid" |
| +0.8 to +1.6 | Significantly positive | "The company donated 30% of profits" |
| 0 to +0.8 | Moderately positive | "The country supported diplomatic talks" |
| -0.8 to 0 | Somewhat negative | "The politician was criticized for misleading statements" |
| -2 to -0.8 | Very negative/harmful | "The group was connected to human rights abuses" |
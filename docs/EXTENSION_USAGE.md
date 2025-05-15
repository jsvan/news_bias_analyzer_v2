# News Bias Analyzer - Browser Extension Guide

This guide explains how to use the News Bias Analyzer browser extension to analyze news articles as you browse the web.

## Installation

### Chrome/Chromium Installation

1. Download the extension from the Chrome Web Store (Coming Soon)
   
   OR
   
   Load the unpacked extension:
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top-right)
   - Click "Load unpacked"
   - Select the `frontend/browser_extension` directory from this project

2. Pin the extension to your toolbar for easy access

### Firefox Installation (Coming Soon)

1. Download the extension from Firefox Add-ons
   
   OR
   
   Load as a temporary extension:
   - Open Firefox and navigate to `about:debugging#/runtime/this-firefox`
   - Click "Load Temporary Add-on"
   - Select the `manifest.json` file in the `frontend/browser_extension` directory

## Basic Usage

### Analyzing an Article

1. Navigate to a news article on any supported news website
2. Click the News Bias Analyzer icon in your browser toolbar
3. Click the "Analyze Article" button in the popup
4. Wait for the analysis to complete
5. View the results showing entity sentiment analysis

### Understanding the Analysis

The analysis results show:

1. **Entity List**: Named entities (people, countries, organizations) mentioned in the article
2. **Sentiment Scores**: How each entity is portrayed along two dimensions:
   - **Power Score**: How powerful vs. weak the entity is portrayed (-2 to +2)
   - **Moral Score**: How good vs. evil the entity is portrayed (-2 to +2)
3. **Statistical Significance**: How unusual this portrayal is compared to typical coverage
4. **Composite Score**: Overall measure of how typical or unusual the article's sentiment pattern is

## Detailed Features

### Entity Analysis

For each entity detected in the article, you'll see:

- **Entity Name**: The person, country, or organization
- **Entity Type**: Classification (person, country, organization, etc.)
- **Power Score**: Slider showing where the entity falls on the power/weakness spectrum
- **Moral Score**: Slider showing where the entity falls on the good/evil spectrum
- **Statistical Significance**: Whether this portrayal is statistically unusual

Example: If an article portrays "United States" with a power score of +4.2 (very powerful) and a moral score of +3.5 (very good), the extension will show how common or uncommon this portrayal is compared to typical coverage of the United States.

### Composite Score

The composite score indicates how typical or unusual the overall sentiment pattern in the article is:

- **Very Common**: The sentiment pattern closely matches typical coverage (percentile 75-100)
- **Average**: The sentiment pattern is moderately typical (percentile 25-75)
- **Unusual**: The sentiment pattern is somewhat unusual (percentile 10-25)
- **Very Unusual**: The sentiment pattern is highly unusual (percentile 0-10)

A highly unusual pattern may indicate a unique perspective, strong bias, or novel framing of the issues.

### Detailed View

Click "View Detailed Analysis" to see more information:

#### Entities Tab
- Complete list of all entities with full details
- Sample quotes showing how each entity is mentioned
- Comparison to global and national averages

#### Distributions Tab
- Visual distribution charts showing how the current article compares to typical coverage
- National vs. global comparison
- Historical trend data for frequently mentioned entities

#### Methodology Tab
- Explanation of how the analysis works
- Information about the statistical models
- Notes about limitations of the analysis

## Advanced Features

### Framing Analysis (Optional)

If you've enabled framing analysis in the settings, you'll also see:

- **Primary Frame**: The dominant narrative structure (conflict, moral, economic, etc.)
- **Protagonist/Antagonist Structure**: Which entities are positioned as "good" vs. "bad"
- **Agency Attribution**: Which entities are portrayed as active vs. passive
- **Language Choices**: Analysis of metaphors, loaded terms, and emotional language

### Source Analysis

When viewing multiple articles from the same source:

- **Source Bias Profile**: Patterns in how this source portrays different types of entities
- **Comparative View**: How this source differs from others in the same country/region
- **Historical Trends**: How the source's sentiment patterns have changed over time

## Settings and Configuration

Access settings by clicking the gear icon in the extension popup:

### General Settings

- **Analysis Mode**: Choose between basic analysis or detailed analysis with framing
- **Default Tab**: Select which tab opens first in detailed view
- **Automatic Analysis**: Toggle whether to automatically analyze articles when you visit them

### Display Settings

- **Score Display**: Choose between numerical scores or visual sliders
- **Significance Threshold**: Adjust the p-value threshold for marking portrayals as unusual
- **Color Scheme**: Light mode, dark mode, or match browser

### API Settings

- **API Endpoint**: URL of the News Bias Analyzer API (for self-hosted installations)
- **Authentication**: Enter API key if using a private installation

## Interpreting Results

### What Makes a Portrayal "Unusual"?

The extension uses statistical models to determine what's "typical" coverage for an entity:

- Global baseline: How the entity is typically portrayed across all tracked news sources
- National baseline: How the entity is typically portrayed in the current article's country
- Source baseline: How the entity is typically portrayed by this specific news source

A portrayal is marked as "unusual" if it falls outside the expected range with statistical significance (p < 0.05).

### What the Scores Mean

#### Power Score (-2 to +2):
- **High Positive** (+1.2 to +2): Portrayed as very powerful, strong, dominant, influential
- **Moderate Positive** (+0.4 to +1.2): Portrayed as somewhat powerful, capable, effective
- **Neutral** (-0.4 to +0.4): Portrayed with neither power nor weakness emphasized
- **Moderate Negative** (-1.2 to -0.4): Portrayed as somewhat weak, struggling, limited
- **High Negative** (-2 to -1.2): Portrayed as very weak, vulnerable, helpless, ineffective

#### Moral Score (-2 to +2):
- **High Positive** (+1.2 to +2): Portrayed as very good, virtuous, ethical, benevolent
- **Moderate Positive** (+0.4 to +1.2): Portrayed as somewhat good, well-intentioned
- **Neutral** (-0.4 to +0.4): Portrayed with neither good nor bad qualities emphasized
- **Moderate Negative** (-1.2 to -0.4): Portrayed as somewhat bad, self-interested, problematic
- **High Negative** (-2 to -1.2): Portrayed as very bad, evil, malevolent, immoral

### Common Patterns to Watch For

- **Hero Framing**: Entity with high power (+) and high moral (+) scores
- **Villain Framing**: Entity with high power (+) and negative moral (-) scores
- **Victim Framing**: Entity with low power (-) and high moral (+) scores
- **Threat Framing**: Entity with moderate power and very negative moral scores

## Limitations

The News Bias Analyzer has several limitations to be aware of:

1. **Context Sensitivity**: The analysis doesn't capture the full context of complex stories
2. **Limited Sample**: Only tracks a subset of major news outlets
3. **Model Limitations**: Large language models may have their own biases
4. **Statistical Nature**: Unusual doesn't automatically mean biased - it may be novel or reflect developing events

## Troubleshooting

### Common Issues

1. **Analysis button doesn't work**:
   - Ensure you're on an actual news article page
   - Check your internet connection
   - Verify API settings in the extension options

2. **No entities detected**:
   - The article may be too short or lack named entities
   - Try scrolling to load the full article before analyzing

3. **Extension shows "API Error"**:
   - Check if the API service is running
   - Verify your API key if using authentication
   - Try again later (possible rate limiting)

### Reporting Issues

If you encounter bugs or have feature requests:

1. Check the [GitHub Issues](https://github.com/yourusername/news_bias_analyzer/issues) to see if it's already reported
2. Create a new issue with detailed reproduction steps
3. Include the article URL and extension version

## Privacy Information

The News Bias Analyzer extension:

- Only analyzes articles when you explicitly click "Analyze"
- Sends article text to the analysis API
- Does not track your browsing history
- Does not share your personal data
- Stores analysis results locally in your browser

You can clear all stored data from the extension options page.
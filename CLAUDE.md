# News Bias Analyzer: Project Philosophy & Overview

## Core Philosophy

This project provides a non-judgmental computational framework for analyzing global news sentiment patterns. Rather than imposing prescriptive labels of "bias" or "propaganda," we reveal the underlying emotional landscapes that different news ecosystems navigate.

### Key Principles

1. **Pattern Recognition Over Judgment**: We identify divergences in coverage without declaring any perspective "wrong" or "biased"
2. **Global Sentiment as Baseline**: We consider the aggregate global sentiment as a reference point - if all observers had perfect information and no bias, sentiment would move in lockstep worldwide
3. **Escape the Bubble**: We help readers understand their position within the broader information landscape by visualizing how their news diet compares to global patterns
4. **Beyond Left-Right**: We reject simplistic American-centric political spectrums in favor of multidimensional sentiment analysis

## How It Works

### Conceptual Model
- **Entities as Navigation Units**: Political figures, corporations, movements, and concepts serve as discrete points in ideological space
- **Sentiment Constellations**: Each news source creates its own emotional map by how it discusses these entities
- **Divergence Detection**: When coverage patterns differ significantly (especially within the same country), we can quantify information sphere dynamics

### Technical Implementation

1. **Data Pipeline**
   - Global news scraper collecting articles from diverse sources worldwide
   - OpenAI-powered sentiment analysis extracting entity-sentiment tuples
   - Database storing temporal patterns and relationships

2. **Chrome Extension**
   - Real-time comparison of current article against global baselines
   - Sentiment histograms showing how this week's coverage compares across sources
   - Entity "stock tickers" tracking sentiment trajectories over time

3. **Web Dashboard** (in development)
   - Macro pattern visualization
   - Cross-country and cross-source comparisons
   - Detection of anomalous divergent events
   - Quantifiable analysis without ideological framing

## Philosophical Roots

Drawing from Peter Pomerantsev's "This Is Not Propaganda," we recognize that modern information warfare operates through emotional association rather than factual debate. By mapping these emotional landscapes computationally, we make visible the usually invisible forces shaping public discourse.

### What We Measure
- **Sentiment Divergence**: How much sources differ in their emotional treatment of the same entities
- **Temporal Patterns**: How sentiment evolves and whether sources move together or apart
- **Clustering Behavior**: Which sources form echo chambers with similar sentiment patterns
- **Salience Differences**: What entities different sources choose to emphasize or ignore

## Development Guidelines

When contributing to this project:

1. **Maintain Neutrality**: The code should reveal patterns, not impose interpretations
2. **Think Globally**: Avoid assumptions based on any single country's political framework
3. **Preserve Nuance**: Entity extraction should capture the full complexity of modern discourse
4. **Focus on Comparison**: Every feature should help users understand relationships between perspectives


Remember: We're building a mirror, not a judge. The goal is to help people see the information environment they inhabit, not to tell them what to think about it. Tell the user what they need to hear; not what they want to hear. provide honest, balanced feedback without excessive praise or flattery
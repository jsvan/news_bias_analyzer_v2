# News Bias Analyzer - Documentation

Welcome to the News Bias Analyzer documentation. This index will help you navigate the comprehensive documentation available for the system.

## Overview

The News Bias Analyzer is a system for tracking how news sources implicitly establish moral direction through entity portrayal across global news articles. Inspired by Peter Pomerantsev's work on information manipulation, this tool reveals how all news sources have an implicit moral compass and vision for society - positioning some entities as advancing progress, others as regression.

The system analyzes entities along two dimensions:

1. **Power Dimension**: How powerful vs. weak entities are portrayed (-2 to +2)
2. **Moral Dimension**: How entities are positioned relative to the news source's implicit vision for society (-2 to +2)

Through this lens, we can understand how news sources use entities as orientation points to guide readers' moral judgments about world events, and track how these positions shift strategically over time.

The system includes a web dashboard, browser extension, API backend, data processing pipeline, and database components.

## Documentation Index

### Philosophical Foundation

- [**Philosophical Approach**](PHILOSOPHICAL_APPROACH.md) - Our approach to analyzing implicit moral frameworks in news

### User Documentation

- [**Browser Extension Guide**](EXTENSION_USAGE.md) - Installation and usage of the browser extension
- [**Dashboard User Manual**](DASHBOARD_USAGE.md) - Comprehensive guide to using the analytics dashboard
- [**Setup and Running**](SETUP_AND_RUNNING.md) - Instructions for setting up and running the system

### Developer Documentation

- [**API Reference**](API_REFERENCE.md) - Detailed API documentation with endpoints, parameters, and responses
- [**API Usage Examples**](API_USAGE_EXAMPLES.md) - Code examples for using the API in different languages
- [**Architecture Overview**](ARCHITECTURE.md) - System design, components, and data flow
- [**Development Guide**](DEVELOPMENT_GUIDE.md) - Setup, standards, and procedures for developers
- [**Deployment Infrastructure**](deployment_infrastructure.md) - Docker and infrastructure overview
- [**AWS Deployment**](aws_deployment.md) - AWS deployment guide for solo developers
- [**Monitoring Guide**](monitoring_guide.md) - Cost-effective monitoring solutions

### System Diagrams

- [**System Architecture Diagrams**](diagrams/system_architecture.md) - High-level system component diagrams
- [**Data Flow Diagrams**](diagrams/data_flow_diagrams.md) - How data moves through the system
- [**Implementation Diagrams**](diagrams/implementation_diagrams.md) - Technical implementation details
- [**Diagram Index**](diagrams/README.md) - Guide to all available diagrams

## Getting Started

### For Users

1. Start with [**Setup and Running**](SETUP_AND_RUNNING.md) to get the system installed
2. Install the browser extension using the [**Browser Extension Guide**](EXTENSION_USAGE.md)
3. Learn to use the dashboard with the [**Dashboard User Manual**](DASHBOARD_USAGE.md)

### For Developers

1. Begin with the [**Architecture Overview**](ARCHITECTURE.md) to understand the system
2. Set up your development environment using the [**Development Guide**](DEVELOPMENT_GUIDE.md)
3. Review the [**API Reference**](API_REFERENCE.md) for integration with other systems
4. Understand deployment options with [**Deployment Infrastructure**](deployment_infrastructure.md)

## Key Concepts

### Cultural Orientation Analysis

The News Bias Analyzer uses a novel approach to news content analysis:

- **Traditional sentiment analysis** focuses on positive/negative valence only
- **Our cultural orientation approach** reveals implicit moral direction and societal vision
- Entities are analyzed as orientation points that guide readers toward specific interpretations
- Power and moral positioning together create narrative archetypes (hero, villain, victim, threat)
- Temporal analysis tracks how entity positioning shifts strategically over time

### Statistical Significance

Analysis results include statistical measurements:

- **Percentile Rankings**: How unusual a portrayal is compared to typical coverage
- **P-Values**: Statistical significance of sentiment deviations
- **Distribution Comparisons**: How coverage varies across sources, countries, and time

### Entity Resolution

The system maintains a knowledge graph of entities:

- **Entity Normalization**: Different mentions of the same entity are consolidated
- **Entity Relationships**: Connections between entities are tracked over time
- **Historical Context**: Sentiment trends for entities are preserved for longitudinal analysis

## Additional Resources

### Administrative Tools

- **Database Maintenance**: Tools for optimizing and maintaining the database
- **User Management**: Managing dashboard access and API keys
- **Scraper Monitoring**: Tracking and troubleshooting data collection
- **Data Validation**: Ensuring data quality and consistency

### Contributing

If you'd like to contribute to the News Bias Analyzer:

1. Review the [**Development Guide**](DEVELOPMENT_GUIDE.md) for standards and procedures
2. Check the GitHub repository for open issues
3. Submit pull requests with improvements or bug fixes

## Support and Feedback

For questions, issues, or feedback:

- Use the GitHub issues page for bug reports and feature requests
- Contact the support team at support@newsbiasanalyzer.com
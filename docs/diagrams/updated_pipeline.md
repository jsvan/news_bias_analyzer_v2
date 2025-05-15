# News Bias Analyzer: Updated Data Flow Diagrams

This document provides updated flow diagrams showing the current state of the News Bias Analyzer pipeline after recent improvements.

## Main Data Flow

```mermaid
flowchart TD
    A[Start] --> B[Scrape Articles]
    B --> |Store Articles| C[PostgreSQL Database]
    C --> D[Analyze Articles in Batches]
    D --> |Single OpenAI API Call| E{OpenAI Processing}
    E --> |JSON Response| F[Parse Response]
    F --> G[Entity Sentiment Analysis]
    F --> H[Quote Extraction & Topics]
    G --> |Store Entity Data| C
    H --> |Store Quote Data| C
    C --> I[Dashboard/Browser Extension]
    I --> J[End User]
```

## Consolidated Script Architecture

```mermaid
flowchart TD
    A[run_analyzer.sh] --> B{Command}
    B --> |scrape| C[Scrape Articles]
    B --> |analyze| D[Analyze Articles]
    B --> |all| E[Full Pipeline]
    B --> |summary| F[Database Summary]
    
    C --> G[Store in Database]
    G --> |--analyze flag| D
    
    D --> H[Fetch Unprocessed Articles]
    H --> I[Process in Batches]
    I --> J[Send to OpenAI]
    J --> K[Single API Call]
    K --> L[Parse JSON Response]
    
    L --> M[Process Entities]
    L --> N[Process Quotes]
    
    E --> C
    E --> D
    
    M --> O[Store Entities]
    N --> P[Store Quotes & Topics]
    
    O --> Q[Database]
    P --> Q
    Q --> F
```

## Data Model Relationships

```mermaid
erDiagram
    NewsSource ||--o{ NewsArticle : publishes
    NewsArticle ||--o{ EntityMention : contains
    Entity ||--o{ EntityMention : referenced_in
    
    NewsArticle ||--o{ Quote : contains
    PublicFigure ||--o{ Quote : said
    Quote }o--o{ Topic : discusses
    Topic }|--o{ QuoteTopic : categorized_by
    Quote ||--o{ QuoteTopic : belongs_to
```

## Analysis Process Flow

```mermaid
flowchart TB
    A[Article Text] --> B[Create Prompt]
    B --> C[OpenAI API]
    C --> D[JSON Response]
    
    D --> E{Response Parser}
    
    E --> F[Entity Extraction]
    E --> G[Quote Extraction]
    
    F --> H[Entity Normalization]
    F --> I[Sentiment Scoring]
    I --> J[Power Score]
    I --> K[Moral Score]
    
    G --> L[Speaker Identification]
    G --> M[Quote Text Extraction]
    G --> N[Topic Classification]
    G --> O[Quote Sentiment]
    
    H --> P[Entity DB Storage]
    J --> Q[Entity Mention Storage]
    K --> Q
    
    L --> R[Public Figure Storage]
    M --> S[Quote Storage]
    N --> T[Topic Storage]
    O --> S
    
    subgraph "Database Operations"
    P --> U[(Entity Table)]
    Q --> V[(Entity Mention Table)]
    R --> W[(Public Figure Table)]
    S --> X[(Quote Table)]
    T --> Y[(Topic Table)]
    S --> Z[(Quote-Topic Table)]
    T --> Z
    end
```

## Batch Processing Flow

```mermaid
flowchart TD
    A[Start Analysis] --> B[Get Unprocessed Articles]
    B --> C{Articles Available?}
    
    C -->|No| D[End Process]
    C -->|Yes| E[Create Batch]
    
    E --> F[Process Each Article]
    F --> G[Send to OpenAI]
    G --> H[Parse Response]
    
    H --> I[Process Entities]
    H --> J[Process Quotes]
    
    I --> K[Store Entity Data]
    J --> L[Store Quote Data]
    
    K --> M[Mark Article as Processed]
    L --> M
    
    M --> N{More Articles?}
    N -->|Yes| F
    N -->|No| O{More Batches?}
    
    O -->|Yes| E
    O -->|No| P[Show Statistics]
    P --> D
```

## Key Improvements

1. **Fully Integrated Analysis**: Entity sentiment analysis and quote extraction are performed in a single OpenAI API call within a unified process, significantly reducing costs and complexity.

2. **Batch Processing**: Articles are processed in configurable batches with transaction management, improving reliability, performance, and resumability.

3. **Simplified Command Interface**: Streamlined to just 4 main commands:
   - `scrape`: Scrape articles from news sources
   - `analyze`: Analyze articles for both entities and quotes
   - `all`: Run complete pipeline 
   - `summary`: Show database summary

4. **Comprehensive Quote Tracking**: Extracts quotes with speaker attribution, topic classification, and sentiment analysis, creating a historical record of statements.

5. **Robust Error Handling**: Added multi-level error handling, transaction management, and automatic resumption of interrupted processes.

6. **Support for All News Sources**: The system can now use all available news sources (50+), not just the default 4.

7. **Improved Database Schema**: Enhanced data model with better relationships between entities, quotes, and topics.

## Typical Workflow

1. User runs `./run_analyzer.sh all`
2. System sets up Docker and PostgreSQL if needed
3. Articles are scraped from all available news sources
4. Articles are stored in the database
5. Articles are analyzed in batches:
   - A single OpenAI prompt extracts both entities and quotes
   - Entities and their sentiment scores are stored
   - Quotes, speakers, topics, and sentiment are stored
6. Database summary is displayed
7. Data is available for the dashboard or browser extension
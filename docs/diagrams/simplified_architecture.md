# News Bias Analyzer - Simplified Architecture Diagrams

This document contains architectural diagrams showing the simplified structure of the News Bias Analyzer system after consolidation.

## Simplified System Overview

```mermaid
graph TB
    subgraph "External Systems"
        NewsWebsites[News Websites] 
        OpenAI[OpenAI API]
    end
    
    subgraph "Core Components"
        API[Unified API Server]
        Scrapers[Scrapers]
        Processor[Article Processor]
    end
    
    subgraph "Storage"
        Database[(PostgreSQL)]
    end
    
    subgraph "Clients"
        Dashboard[Web Dashboard]
        Extension[Browser Extension]
    end
    
    NewsWebsites --> Scrapers
    Scrapers --> Database
    
    API --> Database
    API --> OpenAI
    
    Dashboard --> API
    Extension --> API
    Processor --> API
    Processor --> OpenAI
    
    classDef primary fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef secondary fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef external fill:#D3D3D3,stroke:#333,stroke-width:1px;
    
    class Dashboard,Extension primary;
    class API,Scrapers,Processor secondary;
    class Database storage;
    class NewsWebsites,OpenAI external;
```

## Simplified Data Flow

```mermaid
flowchart TD
    subgraph External
        NewsSource[News Sources]
        OpenAI[OpenAI API]
    end
    
    subgraph Processing
        Scraper[Scraper Service]
        API[Unified API]
        Analyzer[Article Analyzer]
    end
    
    subgraph Storage
        Database[(PostgreSQL Database)]
    end
    
    subgraph Clients
        Extension[Browser Extension]
        Dashboard[Web Dashboard]
    end
    
    NewsSource -->|Web Content| Scraper
    Scraper -->|Article Data| Database
    
    Extension -->|Article for Analysis| API
    API -->|Request Analysis| Analyzer
    Analyzer -->|Analysis Request| OpenAI
    OpenAI -->|JSON Response| Analyzer
    Analyzer -->|Processed Data| API
    API -->|Analysis Results| Extension
    
    Dashboard -->|Data Requests| API
    API -->|Query Results| Database
    Database -->|Stored Data| API
    API -->|Visualization Data| Dashboard
    
    classDef external fill:#D3D3D3,stroke:#333,stroke-width:1px;
    classDef processing fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef client fill:#6495ED,stroke:#333,stroke-width:1px;
    
    class NewsSource,OpenAI external;
    class Scraper,API,Analyzer processing;
    class Database storage;
    class Extension,Dashboard client;
```

## Simplified Analysis Pipeline

```mermaid
sequenceDiagram
    participant Client
    participant API as Unified API
    participant Analyzer as OpenAI Analyzer
    participant OpenAI
    participant DB as Database
    
    Client->>API: Send article for analysis
    API->>Analyzer: Process article
    Analyzer->>OpenAI: Unified analysis request (entities & sentiment)
    OpenAI-->>Analyzer: JSON response with entities and sentiment
    
    Analyzer->>API: Return processed entities
    
    alt OpenAI Fails
        Analyzer->>API: Return error (no fallback)
        API-->>Client: Return error response
    else OpenAI Succeeds
        API->>API: Calculate statistical significance
        API->>DB: Look up historical data (optional)
        DB-->>API: Return baselines (if available)
        API->>API: Generate composite scores
        API-->>Client: Return analysis results
    end
```

## Component Structure

```mermaid
graph TD
    subgraph "Frontend Components"
        Dashboard[Dashboard]
        Extension[Browser Extension]
    end
    
    subgraph "API Components"
        AppPy[app.py]
    end
    
    subgraph "Processing Components"
        OpenAIProcessor[openai_integration.py]
        Prompts[prompts.py]
    end
    
    subgraph "Data Collection"
        BaseScraper[base_scraper.py]
        RssScraper[rss_scraper.py]
        NewsSources[news_sources.py]
    end
    
    subgraph "Database"
        Models[models.py]
        DBManager[db.py]
    end
    
    subgraph "Analysis"
        StatisticalModels[statistical_models.py]
    end
    
    Dashboard --> AppPy
    Extension --> AppPy
    
    AppPy --> DBManager
    AppPy --> Models
    AppPy --> OpenAIProcessor
    AppPy --> StatisticalModels
    
    OpenAIProcessor --> Prompts
    
    RssScraper --> BaseScraper
    RssScraper --> NewsSources
    
    DBManager --> Models
    
    classDef frontend fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef api fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef processor fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef scraper fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef db fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef analysis fill:#98FB98,stroke:#333,stroke-width:1px;
    
    class Dashboard,Extension frontend;
    class AppPy api;
    class OpenAIProcessor,Prompts processor;
    class BaseScraper,RssScraper,NewsSources scraper;
    class Models,DBManager db;
    class StatisticalModels analysis;
```

## Simplified Operation Flow

```mermaid
graph TD
    Start([Start]) --> RunCommand{Command}
    
    RunCommand -->|api| StartAPI[Start API Server]
    RunCommand -->|dashboard| StartDashboard[Start Dashboard]
    RunCommand -->|all| StartAll[Start API & Dashboard]
    RunCommand -->|scraper| RunScraper[Run News Scraper]
    RunCommand -->|analyze| RunAnalyzer[Run Article Analyzer]
    RunCommand -->|setup| SetupEnvironment[Set Up Environment]
    RunCommand -->|stop| StopAll[Stop All Components]
    
    StartAPI --> CheckOpenAI{OpenAI Available?}
    
    CheckOpenAI -->|Yes| UseOpenAI[Use OpenAI for Analysis]
    CheckOpenAI -->|No| ShowWarning[Show Warning]
    
    UseOpenAI --> ServerRunning[API Server Running]
    ShowWarning --> ServerRunning
    
    StartDashboard --> DashboardRunning[Dashboard Running]
    
    StartAll --> StartAPI
    StartAll --> StartDashboard
    
    RunScraper --> ScrapeArticles[Scrape News Articles]
    ScrapeArticles --> SaveArticles[Save to Database]
    
    RunAnalyzer --> CheckOpenAIKey{OpenAI Key Set?}
    CheckOpenAIKey -->|No| ShowKeyError[Show API Key Error]
    CheckOpenAIKey -->|Yes| AnalyzeArticles[Analyze with OpenAI]
    AnalyzeArticles --> SaveAnalysis[Save Analysis to DB]
    
    SetupEnvironment --> SetupPython[Set Up Python Environment]
    SetupPython --> SetupDatabase[Set Up Database]
    SetupDatabase --> SetupDashboard[Set Up Dashboard]
    
    StopAll --> StopAPI[Stop API Server]
    StopAll --> StopDashboard[Stop Dashboard]
    
    ServerRunning --> End([End])
    DashboardRunning --> End
    SaveArticles --> End
    SaveAnalysis --> End
    ShowKeyError --> End
    SetupDashboard --> End
    StopDashboard --> End
    
    classDef start fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef end fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef command fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef state fill:#FFB6C1,stroke:#333,stroke-width:1px;
    
    class Start,End start;
    class RunCommand,CheckOpenAI,CheckOpenAIKey decision;
    class StartAPI,StartDashboard,StartAll,RunScraper,RunAnalyzer,SetupEnvironment,StopAll command;
    class UseOpenAI,ShowWarning,ScrapeArticles,SaveArticles,ShowKeyError,AnalyzeArticles,SaveAnalysis,SetupPython,SetupDatabase,SetupDashboard,StopAPI,StopDashboard process;
    class ServerRunning,DashboardRunning state;
```

## Browser Extension Flow

```mermaid
sequenceDiagram
    participant User
    participant Extension as Browser Extension
    participant API as Unified API
    participant OpenAI
    participant DB as Database
    
    User->>Extension: Click extension icon
    Extension->>Extension: Extract article content
    Extension->>API: Send article for analysis
    
    API->>OpenAI: Analyze article content
    OpenAI-->>API: Return entity & sentiment data
    
    alt OpenAI Analysis Succeeds
        API->>DB: Get baselines for statistical significance
        DB-->>API: Return baseline data
        API->>API: Calculate composite scores
        API-->>Extension: Return analysis results
        Extension-->>User: Display entity sentiment analysis
    else OpenAI Analysis Fails
        API-->>Extension: Return error
        Extension-->>User: Display error message
    end
    
    User->>Extension: Click "View Details"
    Extension->>Extension: Format detailed view
    Extension-->>User: Show detailed analysis
```

## Unified Architecture Pattern

This simplified architecture follows a more straightforward pattern:

1. **Single API Server**: One unified API (`app.py`) handles all endpoints
2. **OpenAI-Only Analysis**: All analysis is performed through OpenAI with no random fallbacks
3. **Simple Command Interface**: A single `run.sh` script handles all operations
4. **Minimal Dependencies**: Direct connections between components with fewer abstractions
5. **Clear Data Flow**: Straightforward flow from clients through API to database and OpenAI
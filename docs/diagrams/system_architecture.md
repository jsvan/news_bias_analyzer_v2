# News Bias Analyzer - System Architecture Diagrams

This document contains architectural diagrams showing the structure, dependencies, and data flows of the News Bias Analyzer system.

## System Overview

```mermaid
graph TB
    subgraph "External Systems"
        NewsWebsites[News Websites] 
        OpenAI[OpenAI API]
    end
    
    subgraph "Data Collection"
        Scrapers[Scrapers] --> Scheduler[Scheduler]
        Scheduler --> TaskQueue[Task Queue]
    end
    
    subgraph "Processing"
        Workers[Workers] --> ArticleProcessor[Article Processor]
        ArticleProcessor --> OpenAIProcessor[OpenAI Processor]
        OpenAIProcessor --> StatisticalModels[Statistical Models]
    end
    
    subgraph "Storage"
        Database[(PostgreSQL)]
        Cache[(Redis Cache)]
    end
    
    subgraph "API Layer"
        APIServer[FastAPI Server] --> AuthSystem[Authentication]
        APIServer --> Endpoints[API Endpoints]
    end
    
    subgraph "Clients"
        Dashboard[Web Dashboard]
        Extension[Browser Extension]
        ThirdParty[Third-party Apps]
    end
    
    NewsWebsites --> Scrapers
    TaskQueue --> Workers
    OpenAIProcessor --> OpenAI
    ArticleProcessor --> Database
    
    Endpoints --> Database
    Endpoints --> Cache
    
    Dashboard --> APIServer
    Extension --> APIServer
    ThirdParty --> APIServer
    
    classDef primary fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef secondary fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef external fill:#D3D3D3,stroke:#333,stroke-width:1px;
    
    class Dashboard,Extension,ThirdParty primary;
    class APIServer,Endpoints,AuthSystem,Workers,ArticleProcessor,OpenAIProcessor,StatisticalModels,Scrapers,Scheduler,TaskQueue secondary;
    class Database,Cache storage;
    class NewsWebsites,OpenAI external;
```

## Integrated Data Processing Pipeline

```mermaid
sequenceDiagram
    participant Scheduler
    participant TaskQueue as Task Queue (Redis)
    participant Worker
    participant Processor as Article Processor
    participant OpenAI as OpenAI API
    participant DB as Database
    
    Scheduler->>TaskQueue: Schedule article scraping
    TaskQueue->>Worker: Worker picks up task
    Worker->>Processor: Process article
    
    Processor->>OpenAI: Unified analysis request (entities & quotes)
    OpenAI-->>Processor: Combined JSON response
    
    Note over Processor: Transaction begins
    
    Processor->>DB: Save article
    
    Note over Processor: Entity processing
    Processor->>DB: Save/update entities
    Processor->>DB: Save entity mentions
    Processor->>DB: Update entity statistics
    
    Note over Processor: Quote processing
    Processor->>DB: Save/update public figures
    Processor->>DB: Save quotes
    Processor->>DB: Save/update topics
    Processor->>DB: Link quotes to topics
    
    Note over Processor: Transaction commits
    
    Worker-->>TaskQueue: Mark task as completed
    Scheduler->>TaskQueue: Check for failed tasks
    Scheduler->>TaskQueue: Reschedule failed tasks
```

## Component Dependencies

```mermaid
graph TD
    subgraph "Frontend Components"
        Dashboard[Dashboard]
        Extension[Browser Extension]
    end
    
    subgraph "API Components"
        APIMain[main.py]
        ArticleEndpoints[article_endpoints.py]
        EntityEndpoints[entity_endpoints.py]
        StatisticalEndpoints[statistical_endpoints.py]
        SourceEndpoints[source_endpoints.py]
        Authentication[auth.py]
    end
    
    subgraph "Processing Components"
        ArticleProcessor[article_processor.py]
        OpenAIProcessor[openai_processor.py]
        Prompts[prompts.py]
        Config[config.py]
    end
    
    subgraph "Data Collection"
        BaseScraper[base_scraper.py]
        RssScraper[rss_scraper.py]
        Scheduler[scheduler.py]
        NewsSources[news_sources.py]
    end
    
    subgraph "Database"
        Models[models.py]
        DBManager[db.py]
        Migrations[migrations/]
    end
    
    subgraph "Analysis"
        StatisticalModels[statistical_models.py]
    end
    
    Dashboard --> APIMain
    Extension --> ArticleEndpoints
    
    APIMain --> Authentication
    APIMain --> ArticleEndpoints
    APIMain --> EntityEndpoints
    APIMain --> StatisticalEndpoints
    APIMain --> SourceEndpoints
    
    ArticleEndpoints --> DBManager
    ArticleEndpoints --> Models
    ArticleEndpoints --> OpenAIProcessor
    
    EntityEndpoints --> DBManager
    EntityEndpoints --> Models
    
    StatisticalEndpoints --> DBManager
    StatisticalEndpoints --> Models
    StatisticalEndpoints --> StatisticalModels
    
    SourceEndpoints --> DBManager
    SourceEndpoints --> Models
    
    OpenAIProcessor --> Prompts
    OpenAIProcessor --> Config
    
    ArticleProcessor --> OpenAIProcessor
    ArticleProcessor --> StatisticalModels
    ArticleProcessor --> DBManager
    ArticleProcessor --> Models
    
    RssScraper --> BaseScraper
    RssScraper --> NewsSources
    
    Scheduler --> RssScraper
    Scheduler --> DBManager
    
    DBManager --> Models
    Migrations --> Models
    
    classDef frontend fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef api fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef processor fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef scraper fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef db fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef analysis fill:#98FB98,stroke:#333,stroke-width:1px;
    
    class Dashboard,Extension frontend;
    class APIMain,ArticleEndpoints,EntityEndpoints,StatisticalEndpoints,SourceEndpoints,Authentication api;
    class ArticleProcessor,OpenAIProcessor,Prompts,Config processor;
    class BaseScraper,RssScraper,Scheduler,NewsSources scraper;
    class Models,DBManager,Migrations db;
    class StatisticalModels analysis;
```

## Database Schema

```mermaid
erDiagram
    Source {
        int id PK
        string name
        string base_url
        string country
        string language
        string political_leaning
    }
    
    Article {
        int id PK
        string url
        string title
        string content
        datetime publish_date
        int source_id FK
        datetime scraped_at
        datetime processed_at
        float composite_percentile
        float composite_p_value
    }
    
    Entity {
        int id PK
        string name
        string entity_type
        int mention_count
        float avg_power_score
        float avg_moral_score
    }
    
    EntityMention {
        int id PK
        int entity_id FK
        int article_id FK
        string mentions
        float power_score
        float moral_score
    }
    
    PublicFigure {
        int id PK
        string name
        string title
        string country
        string political_party
        datetime first_quoted
        datetime last_quoted
    }
    
    Quote {
        int id PK
        int public_figure_id FK
        string article_id FK
        string quote_text
        datetime quote_date
        string topics
        string sentiment_scores
        string mentioned_entities
    }
    
    Topic {
        int id PK
        string name
        int parent_topic_id FK
        string description
    }
    
    QuoteTopic {
        int id PK
        int quote_id FK
        int topic_id FK
        float relevance_score
    }
    
    User {
        int id PK
        string username
        string email
        string password_hash
        boolean is_active
        boolean is_admin
        datetime created_at
        datetime last_login
    }
    
    ApiKey {
        int id PK
        int user_id FK
        string key_hash
        string description
        datetime created_at
        datetime expires_at
        boolean is_active
    }
    
    SavedSearch {
        int id PK
        int user_id FK
        string name
        json parameters
        datetime created_at
    }
    
    DashboardWidget {
        int id PK
        int user_id FK
        string widget_type
        json configuration
        int position
    }
    
    Source ||--o{ Article : "has"
    Article ||--o{ EntityMention : "contains"
    Entity ||--o{ EntityMention : "mentioned_in"
    
    Article ||--o{ Quote : "contains"
    PublicFigure ||--o{ Quote : "said"
    Topic ||--o{ Topic : "parent_of"
    Topic ||--o{ QuoteTopic : "categorizes"
    Quote ||--o{ QuoteTopic : "categorized_by"
    
    User ||--o{ ApiKey : "has"
    User ||--o{ SavedSearch : "has"
    User ||--o{ DashboardWidget : "has"
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "User Clients"
        Browser[Web Browser]
        ChromeExt[Chrome Extension]
    end
    
    subgraph "AWS Infrastructure"
        subgraph "Load Balancer"
            ELB[Elastic Load Balancer]
        end
        
        subgraph "EC2 Instances"
            subgraph "Web Server"
                Nginx[Nginx]
                API[API Container]
                Frontend[Frontend Container]
            end
            
            subgraph "Worker Server"
                TaskQueue[Redis Queue]
                Worker1[Worker Container 1]
                Worker2[Worker Container 2]
                Scraper[Scraper Container]
                Scheduler[Scheduler Container]
            end
        end
        
        subgraph "Database"
            RDS[(RDS PostgreSQL)]
            ElastiCache[(ElastiCache Redis)]
        end
        
        subgraph "Storage"
            S3[S3 Buckets]
        end
        
        subgraph "Monitoring"
            CloudWatch[CloudWatch]
            Alerts[SNS Alerts]
        end
    end
    
    Browser --> ELB
    ChromeExt --> ELB
    
    ELB --> Nginx
    Nginx --> API
    Nginx --> Frontend
    
    API --> RDS
    API --> ElastiCache
    
    Worker1 --> API
    Worker2 --> API
    Worker1 --> RDS
    Worker2 --> RDS
    
    Scheduler --> TaskQueue
    Worker1 --> TaskQueue
    Worker2 --> TaskQueue
    Scraper --> TaskQueue
    
    API --> S3
    Worker1 --> S3
    Worker2 --> S3
    
    API --> CloudWatch
    Worker1 --> CloudWatch
    Worker2 --> CloudWatch
    Scraper --> CloudWatch
    Scheduler --> CloudWatch
    RDS --> CloudWatch
    ElastiCache --> CloudWatch
    
    CloudWatch --> Alerts
    
    classDef client fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef lb fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef server fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef db fill:#FFB6C1,stroke:#333,stroke-width:1px;
    classDef storage fill:#D3D3D3,stroke:#333,stroke-width:1px;
    classDef monitoring fill:#FFA07A,stroke:#333,stroke-width:1px;
    
    class Browser,ChromeExt client;
    class ELB lb;
    class Nginx,API,Frontend,TaskQueue,Worker1,Worker2,Scraper,Scheduler server;
    class RDS,ElastiCache db;
    class S3 storage;
    class CloudWatch,Alerts monitoring;
```

## Integrated Analysis Process Flow

```mermaid
graph TD
    Start([Start]) --> FetchArticle[Fetch Article]
    FetchArticle --> PreprocessText[Preprocess Text]
    PreprocessText --> PreparePrompt[Prepare Combined Prompt]
    PreparePrompt --> CallOpenAI[Call OpenAI API]
    
    CallOpenAI --> ParseResponse[Parse JSON Response]
    
    ParseResponse --> ProcessEntities[Process Entities]
    ParseResponse --> ProcessQuotes[Process Quotes]
    
    ProcessEntities --> EntitySentiment{Extract Sentiment}
    EntitySentiment --> |Power Dimension| PowerScore[Power Score -2 to +2]
    EntitySentiment --> |Moral Dimension| MoralScore[Moral Score -2 to +2]
    
    ProcessQuotes --> QuoteProcessing{Process Quote Data}
    QuoteProcessing --> |Speaker| IdentifySpeaker[Identify/Create Speaker]
    QuoteProcessing --> |Quote Text| ExtractQuote[Extract Quote Text]
    QuoteProcessing --> |Topics| ClassifyTopics[Classify Topics]
    QuoteProcessing --> |Sentiment| QuoteSentiment[Quote Sentiment -2 to +2]
    
    PowerScore --> StoreEntity[Store Entity]
    MoralScore --> StoreEntity
    
    IdentifySpeaker --> StoreSpeaker[Store Public Figure]
    ExtractQuote --> StoreQuote[Store Quote]
    ClassifyTopics --> StoreTopics[Store Topics]
    QuoteSentiment --> StoreQuote
    
    StoreEntity --> RetrieveHistory[Retrieve Historical Data]
    RetrieveHistory --> CalculateStats[Calculate Statistical Significance]
    
    CalculateStats --> |Distribution Comparison| CompareDistribution[Compare to Baseline]
    CalculateStats --> |P-Value Calculation| CalculatePValue[Calculate P-Value]
    
    CompareDistribution --> GenerateComposite[Generate Composite Score]
    CalculatePValue --> GenerateComposite
    
    GenerateComposite --> StoreResults[Store Analysis Results]
    
    StoreSpeaker --> UpdateDatabase[Commit to Database]
    StoreQuote --> UpdateDatabase
    StoreTopics --> UpdateDatabase
    StoreResults --> UpdateDatabase
    
    UpdateDatabase --> End([End])
    
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef data fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef terminal fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef openai fill:#D8BFD8,stroke:#333,stroke-width:1px;
    
    class FetchArticle,PreprocessText,PreparePrompt,ParseResponse,ProcessEntities,ProcessQuotes,PowerScore,MoralScore,IdentifySpeaker,ExtractQuote,ClassifyTopics,QuoteSentiment,RetrieveHistory,CompareDistribution,CalculatePValue,GenerateComposite process;
    class EntitySentiment,QuoteProcessing,CalculateStats decision;
    class StoreEntity,StoreSpeaker,StoreQuote,StoreTopics,StoreResults,UpdateDatabase data;
    class Start,End terminal;
    class CallOpenAI openai;
```

## Browser Extension Flow

```mermaid
sequenceDiagram
    participant User
    participant Extension as Browser Extension
    participant ContentScript as Content Script
    participant API as Backend API
    participant Dashboard as Web Dashboard
    
    User->>+Extension: Click extension icon
    Extension->>+ContentScript: Request page content
    ContentScript-->>-Extension: Return article content
    
    Extension->>+API: Send article for analysis
    API-->>-Extension: Return analysis results
    
    Extension->>Extension: Process and format results
    Extension-->>User: Display entity sentiment analysis
    
    User->>Extension: Click "View Detailed Analysis"
    Extension->>+Dashboard: Open dashboard with analysis
    Dashboard-->>-User: Show full interactive analysis
    
    User->>Dashboard: Explore historical data
    Dashboard->>+API: Request historical data
    API-->>-Dashboard: Return trend data
    Dashboard-->>User: Display trend visualizations
```

## Admin Tools Flow

```mermaid
graph TD
    Start([Start]) --> CLICommand[Run Admin CLI Command]
    
    CLICommand --> |db| DBMaintenance{Database Maintenance}
    CLICommand --> |user| UserManagement{User Management}
    CLICommand --> |monitor| ScraperMonitoring{Scraper Monitoring}
    CLICommand --> |validate| DataValidation{Data Validation}
    CLICommand --> |config| ConfigManagement{Config Management}
    
    DBMaintenance --> |backup| BackupDB[Backup Database]
    DBMaintenance --> |restore| RestoreDB[Restore Database]
    DBMaintenance --> |cleanup| CleanupOldData[Clean Old Data]
    DBMaintenance --> |optimize| OptimizeDB[Optimize Database]
    DBMaintenance --> |stats| ShowDBStats[Show DB Statistics]
    
    UserManagement --> |create| CreateUser[Create User]
    UserManagement --> |delete| DeleteUser[Delete User]
    UserManagement --> |update| UpdateUser[Update User]
    UserManagement --> |list| ListUsers[List Users]
    UserManagement --> |apikey| ManageAPIKeys[Manage API Keys]
    
    ScraperMonitoring --> |performance| AnalyzePerformance[Analyze Performance]
    ScraperMonitoring --> |detect-failures| DetectFailures[Detect Failures]
    ScraperMonitoring --> |live| MonitorLive[Monitor Live]
    ScraperMonitoring --> |repair| RepairIssues[Repair Issues]
    
    DataValidation --> |articles| ValidateArticles[Validate Articles]
    DataValidation --> |entities| ValidateEntities[Validate Entities]
    DataValidation --> |mentions| ValidateMentions[Validate Mentions]
    DataValidation --> |normalize| NormalizeEntities[Normalize Entities]
    DataValidation --> |report| GenerateReport[Generate Report]
    
    ConfigManagement --> |show| ShowConfig[Show Config]
    ConfigManagement --> |set| SetConfig[Set Config Value]
    ConfigManagement --> |reset| ResetConfig[Reset to Defaults]
    
    BackupDB --> End([End])
    RestoreDB --> End
    CleanupOldData --> End
    OptimizeDB --> End
    ShowDBStats --> End
    
    CreateUser --> End
    DeleteUser --> End
    UpdateUser --> End
    ListUsers --> End
    ManageAPIKeys --> End
    
    AnalyzePerformance --> End
    DetectFailures --> End
    MonitorLive --> End
    RepairIssues --> End
    
    ValidateArticles --> End
    ValidateEntities --> End
    ValidateMentions --> End
    NormalizeEntities --> End
    GenerateReport --> End
    
    ShowConfig --> End
    SetConfig --> End
    ResetConfig --> End
    
    classDef start fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef end fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef command fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef category fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef action fill:#90EE90,stroke:#333,stroke-width:1px;
    
    class Start,End start;
    class CLICommand command;
    class DBMaintenance,UserManagement,ScraperMonitoring,DataValidation,ConfigManagement category;
    class BackupDB,RestoreDB,CleanupOldData,OptimizeDB,ShowDBStats,CreateUser,DeleteUser,UpdateUser,ListUsers,ManageAPIKeys,AnalyzePerformance,DetectFailures,MonitorLive,RepairIssues,ValidateArticles,ValidateEntities,ValidateMentions,NormalizeEntities,GenerateReport,ShowConfig,SetConfig,ResetConfig action;
```
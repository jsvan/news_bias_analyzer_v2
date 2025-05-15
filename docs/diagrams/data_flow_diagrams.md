# News Bias Analyzer - Data Flow Diagrams

This document contains detailed data flow diagrams showing how information moves through the News Bias Analyzer system.

## Article Processing Data Flow

```mermaid
flowchart TD
    subgraph External
        NewsSource[News Sources]
        OpenAI[OpenAI API]
    end
    
    subgraph Ingestion
        Scraper[Scraper Service]
        Queue[(Task Queue)]
    end
    
    subgraph Processing
        Worker[Worker Service]
        ArticleProcessor[Article Processor]
        OpenAIProcessor[OpenAI Processor]
        EntityExtractor[Entity Extractor]
        SentimentAnalyzer[Sentiment Analyzer]
        StatisticalEngine[Statistical Engine]
    end
    
    subgraph Storage
        ArticleDB[(Article Repository)]
        EntityDB[(Entity Repository)]
        MentionDB[(Mention Repository)]
        StatsDB[(Statistics Repository)]
    end
    
    NewsSource -->|RSS Feeds or Web Content| Scraper
    Scraper -->|Raw Article Data| Queue
    Queue -->|Article Task| Worker
    
    Worker -->|Article Data| ArticleProcessor
    ArticleProcessor -->|Text Content| OpenAIProcessor
    OpenAIProcessor -->|Processed Content| EntityExtractor
    EntityExtractor -->|Entity List| SentimentAnalyzer
    
    OpenAIProcessor -.->|API Request| OpenAI
    OpenAI -.->|API Response| OpenAIProcessor
    
    SentimentAnalyzer -->|Entity Sentiment Scores| StatisticalEngine
    ArticleDB -.->|Historical Data| StatisticalEngine
    EntityDB -.->|Entity Baselines| StatisticalEngine
    
    ArticleProcessor -->|Processed Article| ArticleDB
    EntityExtractor -->|Extracted Entities| EntityDB
    SentimentAnalyzer -->|Entity Mentions with Sentiment| MentionDB
    StatisticalEngine -->|Statistical Metrics| StatsDB
    
    classDef external fill:#D3D3D3,stroke:#333,stroke-width:1px;
    classDef ingestion fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef processing fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef storage fill:#6495ED,stroke:#333,stroke-width:1px;
    
    class NewsSource,OpenAI external;
    class Scraper,Queue ingestion;
    class Worker,ArticleProcessor,OpenAIProcessor,EntityExtractor,SentimentAnalyzer,StatisticalEngine processing;
    class ArticleDB,EntityDB,MentionDB,StatsDB storage;
```

## Sentiment Analysis Pipeline

```mermaid
flowchart TD
    RawText[Raw Article Text] --> TextPrep[Text Preparation]
    TextPrep -->|Cleaned Text| PromptConstruction[Prompt Construction]
    PromptConstruction -->|Article + Prompt| OpenAIRequest[OpenAI API Request]
    OpenAIRequest -->|JSON Response| ResponseParsing[Response Parsing]
    
    ResponseParsing -->|Structured Data| EntityExtraction[Entity Extraction]
    EntityExtraction -->|Entity List| Normalization[Entity Normalization]
    
    Normalization -->|Normalized Entities| SentimentScoring{Sentiment Scoring}
    SentimentScoring -->|Power Dimension| PowerScore[Power Score Calculation]
    SentimentScoring -->|Moral Dimension| MoralScore[Moral Score Calculation]
    
    PowerScore --> MentionCollection[Mention Collection]
    MoralScore --> MentionCollection
    
    EntityDB[(Entity Database)] -.->|Existing Entities| Normalization
    EntityDB -.->|Historical Scores| StatisticalAnalysis
    
    MentionCollection -->|Entity Mentions| StatisticalAnalysis[Statistical Analysis]
    StatisticalAnalysis -->|Significance Testing| SignificanceCalculation[Calculate Statistical Significance]
    SignificanceCalculation -->|P-Values| CompositeScore[Composite Score Generation]
    
    CompositeScore --> FinalResults[Processed Results]
    
    classDef data fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFA07A,stroke:#333,stroke-width:1px;
    
    class RawText,ResponseParsing,FinalResults data;
    class TextPrep,PromptConstruction,OpenAIRequest,EntityExtraction,Normalization,PowerScore,MoralScore,MentionCollection,StatisticalAnalysis,SignificanceCalculation,CompositeScore process;
    class SentimentScoring decision;
    class EntityDB storage;
```

## Entity Resolution Process

```mermaid
flowchart LR
    NewEntity[New Entity] --> NameNormalization[Name Normalization]
    NameNormalization -->|Normalized Name| EntityLookup{Existing Entity?}
    
    EntityLookup -->|Yes| ExactMatch[Exact Match Processing]
    EntityLookup -->|No| SimilarityCheck{Check Similar Entities}
    
    SimilarityCheck -->|Found Similar| FuzzyMatch[Fuzzy Match Processing]
    SimilarityCheck -->|No Match| CreateNew[Create New Entity]
    
    ExactMatch -->|Update Stats| UpdateEntityStats[Update Entity Statistics]
    FuzzyMatch -->|Merge or Link| EntityMerge[Entity Merge/Link]
    CreateNew -->|New Record| SaveEntity[Save New Entity]
    
    UpdateEntityStats --> FinalizeEntity[Finalize Entity Processing]
    EntityMerge --> FinalizeEntity
    SaveEntity --> FinalizeEntity
    
    subgraph "Similarity Metrics"
        StringSimilarity[String Similarity]
        ContextSimilarity[Context Similarity]
        TypeConsistency[Type Consistency]
    end
    
    SimilarityCheck -.->|Check Methods| StringSimilarity
    SimilarityCheck -.->|Check Methods| ContextSimilarity
    SimilarityCheck -.->|Check Methods| TypeConsistency
    
    EntityDB[(Entity Repository)] -.->|Existing Records| EntityLookup
    EntityDB -.->|Similar Entities| SimilarityCheck
    FinalizeEntity -.->|Store Results| EntityDB
    
    classDef input fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef metrics fill:#D3D3D3,stroke:#333,stroke-width:1px;
    
    class NewEntity input;
    class NameNormalization,ExactMatch,FuzzyMatch,CreateNew,UpdateEntityStats,EntityMerge,SaveEntity,FinalizeEntity process;
    class EntityLookup,SimilarityCheck decision;
    class EntityDB storage;
    class StringSimilarity,ContextSimilarity,TypeConsistency metrics;
```

## Statistical Analysis Flow

```mermaid
flowchart TD
    NewSentiment[New Entity Sentiment] --> HistoricalRetrieval[Retrieve Historical Data]
    
    subgraph "Data Sources"
        GlobalData[Global Entity Data]
        SourceData[Source-Specific Data]
        CountryData[Country-Specific Data]
    end
    
    HistoricalRetrieval -.->|Fetch Data| GlobalData
    HistoricalRetrieval -.->|Fetch Data| SourceData
    HistoricalRetrieval -.->|Fetch Data| CountryData
    
    HistoricalRetrieval --> DistributionModeling[Distribution Modeling]
    DistributionModeling -->|Create Models| PowerDistribution[Power Score Distribution]
    DistributionModeling -->|Create Models| MoralDistribution[Moral Score Distribution]
    
    PowerDistribution --> CalculatePercentile[Calculate Percentiles]
    MoralDistribution --> CalculatePercentile
    
    CalculatePercentile --> SignificanceTesting[Statistical Significance Testing]
    SignificanceTesting -->|P-Value| SignificanceThreshold{Significant?}
    
    SignificanceThreshold -->|Yes| FlagUnusual[Flag as Unusual Pattern]
    SignificanceThreshold -->|No| MarkTypical[Mark as Typical Pattern]
    
    FlagUnusual --> CompositeCalculation[Calculate Composite Score]
    MarkTypical --> CompositeCalculation
    
    CompositeCalculation --> StoreResults[Store Statistical Results]
    StoreResults --> AnalysisComplete[Complete Analysis]
    
    StatsDB[(Statistics Repository)] -.->|Historical Data| HistoricalRetrieval
    StoreResults -.->|Update Statistics| StatsDB
    
    classDef input fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef data fill:#D3D3D3,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef storage fill:#FFA07A,stroke:#333,stroke-width:1px;
    
    class NewSentiment input;
    class HistoricalRetrieval,DistributionModeling,PowerDistribution,MoralDistribution,CalculatePercentile,SignificanceTesting,FlagUnusual,MarkTypical,CompositeCalculation,StoreResults,AnalysisComplete process;
    class GlobalData,SourceData,CountryData data;
    class SignificanceThreshold decision;
    class StatsDB storage;
```

## API Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant APIGateway as API Gateway
    participant Auth as Authentication Service
    participant APIService as API Service
    participant Cache as Redis Cache
    participant DB as Database

    Client->>APIGateway: Request with API Key/Token
    APIGateway->>Auth: Validate Credentials
    Auth-->>APIGateway: Authentication Result
    
    alt Authentication Failed
        APIGateway-->>Client: 401 Unauthorized
    else Authentication Successful
        APIGateway->>APIService: Forward Request
        
        APIService->>Cache: Check Cache for Response
        
        alt Cache Hit
            Cache-->>APIService: Return Cached Response
            APIService-->>APIGateway: Return Response
            APIGateway-->>Client: Response Data
        else Cache Miss
            APIService->>DB: Query Database
            DB-->>APIService: Database Results
            APIService->>APIService: Process Results
            APIService->>Cache: Store in Cache
            APIService-->>APIGateway: Return Response
            APIGateway-->>Client: Response Data
        end
    end
    
    Note over Client,DB: Rate Limiting Applied at API Gateway
```

## Dashboard Data Loading Flow

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant APIClient as API Client
    participant APIServer as API Server
    participant Cache as Redis Cache
    participant DB as Database
    
    User->>Dashboard: Load Dashboard
    Dashboard->>APIClient: Request Initial Data
    
    APIClient->>APIServer: Request Summary Stats
    APIServer->>Cache: Check Cache
    Cache-->>APIServer: Summary Stats
    APIServer-->>APIClient: Return Summary Stats
    APIClient-->>Dashboard: Display Summary
    
    Dashboard->>APIClient: Request Entity Trends
    APIClient->>APIServer: Request Trend Data
    APIServer->>DB: Query Time Series Data
    DB-->>APIServer: Trend Results
    APIServer->>Cache: Store in Cache (TTL: 1 hour)
    APIServer-->>APIClient: Return Trend Data
    APIClient-->>Dashboard: Display Charts
    
    Dashboard->>APIClient: Request Recent Articles
    APIClient->>APIServer: Request Recent Articles
    APIServer->>DB: Query Recent Articles
    DB-->>APIServer: Article Results
    APIServer-->>APIClient: Return Articles
    APIClient-->>Dashboard: Display Article List
    
    User->>Dashboard: Select Entity for Detail
    Dashboard->>APIClient: Request Entity Details
    APIClient->>APIServer: Request Entity Data
    APIServer->>DB: Query Entity Details
    DB-->>APIServer: Entity Detail Results
    APIServer-->>APIClient: Return Entity Data
    APIClient-->>Dashboard: Display Entity Details
```

## Browser Extension Processing Flow

```mermaid
flowchart TD
    WebPage[News Website] --> ContentScript[Content Script]
    ContentScript -->|Extract Content| ArticleExtraction[Article Extraction]
    
    ArticleExtraction -->|Article Data| ContentValidation{Valid Article?}
    ContentValidation -->|No| DisplayError[Display Error Message]
    ContentValidation -->|Yes| CacheCheck{In Cache?}
    
    LocalStorage[(Local Storage)] -.->|Check Cache| CacheCheck
    
    CacheCheck -->|Yes| LoadCache[Load Cached Analysis]
    CacheCheck -->|No| PrepareRequest[Prepare API Request]
    
    PrepareRequest -->|Article Data| APIRequest[Make API Request]
    APIServer[API Server] -.->|Process Request| APIRequest
    APIRequest -->|Analysis Results| ProcessResponse[Process API Response]
    
    LoadCache --> RenderResults[Render Results UI]
    ProcessResponse --> RenderResults
    ProcessResponse -.->|Store Results| LocalStorage
    
    RenderResults -->|Basic View| PopupDisplay[Display in Popup]
    RenderResults -.->|"If Requested"| DetailedView[Open Detailed View]
    
    PopupDisplay -->|User Interaction| UserInteraction{User Action}
    UserInteraction -->|View Details| DetailedView
    UserInteraction -->|Close| End[End]
    
    DetailedView -->|Dashboard URL| OpenDashboard[Open Dashboard]
    
    classDef input fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef display fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef storage fill:#D3D3D3,stroke:#333,stroke-width:1px;
    classDef external fill:#D8BFD8,stroke:#333,stroke-width:1px;
    
    class WebPage input;
    class ContentScript,ArticleExtraction,PrepareRequest,APIRequest,ProcessResponse,LoadCache process;
    class ContentValidation,CacheCheck,UserInteraction decision;
    class DisplayError,RenderResults,PopupDisplay,DetailedView,OpenDashboard display;
    class LocalStorage storage;
    class APIServer,End external;
```

## User Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Frontend (Dashboard/Extension)
    participant AuthService as Authentication Service
    participant UserDB as User Database
    participant APIService as API Service
    
    User->>Frontend: Attempt Login
    Frontend->>AuthService: Login Request
    AuthService->>UserDB: Verify Credentials
    
    alt Invalid Credentials
        UserDB-->>AuthService: Authentication Failed
        AuthService-->>Frontend: Return Error
        Frontend-->>User: Display Error Message
    else Valid Credentials
        UserDB-->>AuthService: Authentication Successful
        AuthService->>AuthService: Generate JWT Token
        AuthService-->>Frontend: Return Token & User Info
        Frontend->>Frontend: Store Token (Cookie/LocalStorage)
        Frontend-->>User: Login Successful
    end
    
    User->>Frontend: Request Protected Resource
    Frontend->>APIService: Request with Auth Token
    APIService->>AuthService: Validate Token
    
    alt Invalid or Expired Token
        AuthService-->>APIService: Token Invalid
        APIService-->>Frontend: 401 Unauthorized
        Frontend->>Frontend: Clear Token
        Frontend-->>User: Redirect to Login
    else Valid Token
        AuthService-->>APIService: Token Valid (User info)
        APIService->>APIService: Process Request
        APIService-->>Frontend: Return Protected Resource
        Frontend-->>User: Display Protected Resource
    end
```

## Data Validation Process Flow

```mermaid
flowchart TD
    Start([Start Validation]) --> SelectValidationType{Validation Type}
    
    SelectValidationType -->|Articles| ArticleValidation[Validate Articles]
    SelectValidationType -->|Entities| EntityValidation[Validate Entities]
    SelectValidationType -->|Mentions| MentionValidation[Validate Mentions]
    
    ArticleValidation --> CheckArticleFields[Check Required Fields]
    CheckArticleFields --> ValidateArticleURLs[Validate URLs]
    ValidateArticleURLs --> CheckArticleDuplicates[Check for Duplicates]
    
    EntityValidation --> CheckEntityFields[Check Required Fields]
    CheckEntityFields --> ValidateEntityTypes[Validate Entity Types]
    ValidateEntityTypes --> CheckSimilarEntities[Find Similar Entities]
    
    MentionValidation --> CheckMentionFields[Check Required Fields]
    CheckMentionFields --> ValidateArticleEntityRefs[Validate Article/Entity References]
    ValidateArticleEntityRefs --> CheckMentionText[Validate Mention Text]
    
    CheckArticleDuplicates --> FixArticleIssues{Fix Issues?}
    CheckSimilarEntities --> FixEntityIssues{Fix Issues?}
    CheckMentionText --> FixMentionIssues{Fix Issues?}
    
    FixArticleIssues -->|Yes| RepairArticles[Repair Article Issues]
    FixArticleIssues -->|No| LogArticleIssues[Log Article Issues]
    
    FixEntityIssues -->|Yes| RepairEntities[Repair Entity Issues]
    FixEntityIssues -->|No| LogEntityIssues[Log Entity Issues]
    
    FixMentionIssues -->|Yes| RepairMentions[Repair Mention Issues]
    FixMentionIssues -->|No| LogMentionIssues[Log Mention Issues]
    
    RepairArticles --> ArticleValidationReport[Generate Article Report]
    LogArticleIssues --> ArticleValidationReport
    
    RepairEntities --> EntityValidationReport[Generate Entity Report]
    LogEntityIssues --> EntityValidationReport
    
    RepairMentions --> MentionValidationReport[Generate Mention Report]
    LogMentionIssues --> MentionValidationReport
    
    ArticleValidationReport --> End([End Validation])
    EntityValidationReport --> End
    MentionValidationReport --> End
    
    classDef start fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef report fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef end fill:#6495ED,stroke:#333,stroke-width:1px;
    
    class Start,End start;
    class ArticleValidation,CheckArticleFields,ValidateArticleURLs,CheckArticleDuplicates,EntityValidation,CheckEntityFields,ValidateEntityTypes,CheckSimilarEntities,MentionValidation,CheckMentionFields,ValidateArticleEntityRefs,CheckMentionText,RepairArticles,RepairEntities,RepairMentions process;
    class SelectValidationType,FixArticleIssues,FixEntityIssues,FixMentionIssues decision;
    class LogArticleIssues,LogEntityIssues,LogMentionIssues,ArticleValidationReport,EntityValidationReport,MentionValidationReport report;
```

## Scraper Monitoring Process

```mermaid
flowchart TD
    Start([Start Monitoring]) --> MonitoringMode{Monitoring Mode}
    
    MonitoringMode -->|Performance Analysis| PerformanceAnalysis[Analyze Historical Performance]
    MonitoringMode -->|Failure Detection| FailureDetection[Detect Failing Scrapers]
    MonitoringMode -->|Live Monitoring| LiveMonitoring[Monitor in Real-time]
    
    PerformanceAnalysis --> LoadScraperHistory[Load Scraper History]
    LoadScraperHistory --> CalculateMetrics[Calculate Performance Metrics]
    CalculateMetrics --> GenerateCharts[Generate Performance Charts]
    GenerateCharts --> PerformanceReport[Create Performance Report]
    
    FailureDetection --> LoadRecentActivity[Load Recent Activity]
    LoadRecentActivity --> IdentifyInactive[Identify Inactive Scrapers]
    IdentifyInactive --> ApplyThresholds[Apply Failure Thresholds]
    ApplyThresholds --> AlertCondition{Alert Condition?}
    
    AlertCondition -->|Yes| SendAlerts[Send Failure Alerts]
    AlertCondition -->|No| LogStatus[Log Normal Status]
    
    SendAlerts --> FailureReport[Create Failure Report]
    LogStatus --> FailureReport
    
    LiveMonitoring --> InitializeMonitor[Initialize Live Monitor]
    InitializeMonitor --> TrackActivity[Track Scraper Activity]
    TrackActivity --> UpdateStats[Update Stats Periodically]
    UpdateStats --> DisplayLive[Display Live Dashboard]
    DisplayLive --> MonitoringComplete{Complete?}
    
    MonitoringComplete -->|No| TrackActivity
    MonitoringComplete -->|Yes| LiveReport[Create Monitoring Report]
    
    PerformanceReport --> End([End Monitoring])
    FailureReport --> End
    LiveReport --> End
    
    classDef start fill:#6495ED,stroke:#333,stroke-width:1px;
    classDef process fill:#90EE90,stroke:#333,stroke-width:1px;
    classDef decision fill:#FFD700,stroke:#333,stroke-width:1px;
    classDef report fill:#FFA07A,stroke:#333,stroke-width:1px;
    classDef end fill:#6495ED,stroke:#333,stroke-width:1px;
    
    class Start,End start;
    class LoadScraperHistory,CalculateMetrics,GenerateCharts,LoadRecentActivity,IdentifyInactive,ApplyThresholds,SendAlerts,LogStatus,InitializeMonitor,TrackActivity,UpdateStats,DisplayLive process;
    class MonitoringMode,AlertCondition,MonitoringComplete decision;
    class PerformanceAnalysis,FailureDetection,LiveMonitoring,PerformanceReport,FailureReport,LiveReport report;
```
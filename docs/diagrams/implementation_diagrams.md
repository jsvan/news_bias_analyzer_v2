# News Bias Analyzer - Implementation Diagrams

This document contains detailed implementation diagrams showing the technical components, class structures, and code organization of the News Bias Analyzer system.

## Database Schema Implementation

```mermaid
classDiagram
    class Base {
        <<SQLAlchemy Base>>
    }
    
    class Source {
        +id: Integer
        +name: String
        +base_url: String
        +country: String
        +language: String
        +political_leaning: String
        +created_at: DateTime
        +updated_at: DateTime
        +articles: Relationship
    }
    
    class Article {
        +id: Integer
        +url: String
        +title: String
        +content: Text
        +publish_date: DateTime
        +source_id: Integer
        +source_name: String
        +composite_percentile: Float
        +composite_p_value: Float
        +created_at: DateTime
        +updated_at: DateTime
        +entities: Relationship
        +get_entity_mentions() List
    }
    
    class Entity {
        +id: Integer
        +name: String
        +type: String
        +mention_count: Integer
        +avg_power_score: Float
        +avg_moral_score: Float
        +first_seen: DateTime
        +last_seen: DateTime
        +created_at: DateTime
        +updated_at: DateTime
        +mentions: Relationship
        +get_sentiment_history() List
    }
    
    class EntityMention {
        +id: Integer
        +entity_id: Integer
        +article_id: Integer
        +text: String
        +context: String
        +power_score: Float
        +moral_score: Float
        +national_significance: Float
        +global_significance: Float
        +created_at: DateTime
    }
    
    class User {
        +id: Integer
        +username: String
        +email: String
        +password_hash: String
        +is_active: Boolean
        +is_admin: Boolean
        +created_at: DateTime
        +last_login: DateTime
        +api_keys: Relationship
        +preferences: Relationship
        +saved_searches: Relationship
        +check_password(password) Boolean
        +set_password(password) void
    }
    
    class ApiKey {
        +id: Integer
        +user_id: Integer
        +key_hash: String
        +description: String
        +created_at: DateTime
        +expires_at: DateTime
        +is_active: Boolean
        +generate_key() String
        +validate_key(key) Boolean
    }
    
    class UserPreference {
        +id: Integer
        +user_id: Integer
        +preference_key: String
        +preference_value: String
        +created_at: DateTime
        +updated_at: DateTime
    }
    
    class SavedSearch {
        +id: Integer
        +user_id: Integer
        +name: String
        +parameters: JSON
        +created_at: DateTime
        +updated_at: DateTime
    }
    
    class DashboardWidget {
        +id: Integer
        +user_id: Integer
        +widget_type: String
        +configuration: JSON
        +position: Integer
        +created_at: DateTime
        +updated_at: DateTime
    }
    
    class TimeSeriesData {
        +id: Integer
        +entity_id: Integer
        +source_id: Integer
        +date: Date
        +power_score: Float
        +moral_score: Float
        +mention_count: Integer
    }
    
    Base <|-- Source
    Base <|-- Article
    Base <|-- Entity
    Base <|-- EntityMention
    Base <|-- User
    Base <|-- ApiKey
    Base <|-- UserPreference
    Base <|-- SavedSearch
    Base <|-- DashboardWidget
    Base <|-- TimeSeriesData
    
    Source "1" -- "many" Article
    Article "1" -- "many" EntityMention
    Entity "1" -- "many" EntityMention
    User "1" -- "many" ApiKey
    User "1" -- "many" UserPreference
    User "1" -- "many" SavedSearch
    User "1" -- "many" DashboardWidget
    Entity "1" -- "many" TimeSeriesData
    Source "1" -- "many" TimeSeriesData
```

## API Endpoint Implementation

```mermaid
classDiagram
    class APIRouter {
        <<FastAPI Router>>
    }
    
    class AuthRouter {
        +post_token(credentials) Response
        +post_api_key_token(api_key) Response
        +validate_token(token) User
    }
    
    class ArticleRouter {
        +post_analyze_article(request, session) Response
        +get_article(article_id, session) Response
        +get_recent_articles(source_id, limit, offset, session) Response
    }
    
    class EntityRouter {
        +get_entities(entity_type, limit, offset, session) Response
        +get_entity(entity_id, session) Response
        +get_entity_sentiment(entity_id, start_date, end_date, source_id, country, session) Response
    }
    
    class SourceRouter {
        +get_sources(country, political_leaning, limit, offset, session) Response
        +get_source(source_id, session) Response
        +get_source_bias(source_id, days, session) Response
    }
    
    class StatisticalRouter {
        +get_entity_distribution(entity_id, country, source_id, days, session) Response
        +get_trends(entity_ids, entity_types, days, source_id, country, session) Response
    }
    
    class ExtensionRouter {
        +post_extension_analyze(request, session) Response
        +get_extension_history(days, session) Response
    }
    
    class DashboardRouter {
        +get_dashboard_summary(session) Response
        +get_dashboard_widgets(user_id, session) Response
        +post_dashboard_widget(widget_data, user_id, session) Response
    }
    
    APIRouter <|-- AuthRouter
    APIRouter <|-- ArticleRouter
    APIRouter <|-- EntityRouter
    APIRouter <|-- SourceRouter
    APIRouter <|-- StatisticalRouter
    APIRouter <|-- ExtensionRouter
    APIRouter <|-- DashboardRouter
```

## OpenAI Processor Implementation

```mermaid
classDiagram
    class OpenAIProcessor {
        -api_key: String
        -client: OpenAI
        -model_name: String
        -max_tokens: Integer
        -temperature: Float
        +__init__(api_key, model_name, max_tokens, temperature)
        +analyze_article(article_data) Dict
        -extract_entities_with_sentiments(text) List
        +batch_process(articles, batch_size) List
        -calculate_query_tokens(text) Integer
        +get_usage_stats() Dict
    }
    
    class PromptManager {
        -prompts: Dict
        +__init__()
        +get_entity_extraction_prompt() String
        +get_sentiment_analysis_prompt() String
        +get_article_summary_prompt() String
        +format_prompt(template, variables) String
    }
    
    class SentimentResponse {
        +entities: List
        +composite_score: Dict
        +processing_time: Float
        +__init__(data)
        +to_dict() Dict
    }
    
    class EntityMention {
        +text: String
        +context: String
        +__init__(text, context)
        +to_dict() Dict
    }
    
    class EntitySentiment {
        +entity: String
        +entity_type: String
        +power_score: Float
        +moral_score: Float
        +mentions: List[EntityMention]
        +national_significance: Float
        +global_significance: Float
        +__init__(data)
        +to_dict() Dict
    }
    
    class APIError {
        +message: String
        +code: String
        +status: Integer
        +__init__(message, code, status)
        +to_dict() Dict
    }
    
    OpenAIProcessor -- PromptManager : uses
    OpenAIProcessor -- SentimentResponse : returns
    SentimentResponse -- EntitySentiment : contains
    EntitySentiment -- EntityMention : contains
    OpenAIProcessor -- APIError : throws
```

## Entity Resolution Implementation

```mermaid
classDiagram
    class EntityResolver {
        -db_manager: DatabaseManager
        -similarity_threshold: Float
        +__init__(db_manager, similarity_threshold)
        +resolve_entity(name, entity_type) Entity
        -find_exact_match(name, entity_type) Entity
        -find_similar_entities(name, entity_type) List[Entity]
        -calculate_string_similarity(str1, str2) Float
        -should_merge_entities(entity1, entity2) Boolean
        +merge_entities(primary_entity_id, secondary_entity_id) void
        +normalize_entity_name(name) String
    }
    
    class EntityNormalizer {
        -name_replacements: Dict
        -country_codes: Dict
        -organization_synonyms: Dict
        +__init__()
        +normalize_name(name, entity_type) String
        -normalize_country(name) String
        -normalize_organization(name) String
        -normalize_person(name) String
        -remove_titles(name) String
        -standardize_spelling(name) String
    }
    
    class FuzzyMatcher {
        -vectorizer: TfidfVectorizer
        -string_matcher: SequenceMatcher
        +__init__()
        +compute_similarity(str1, str2) Float
        +find_best_match(target, candidates) Tuple[String, Float]
        -preprocess_string(text) String
        -compute_tfidf_similarity(str1, str2) Float
        -compute_levenshtein_similarity(str1, str2) Float
    }
    
    EntityResolver -- EntityNormalizer : uses
    EntityResolver -- FuzzyMatcher : uses
```

## Statistical Models Implementation

```mermaid
classDiagram
    class StatisticalModel {
        -db_manager: DatabaseManager
        +__init__(db_manager)
        +calculate_entity_percentile(entity_id, power_score, moral_score) Float
        +calculate_p_value(entity_id, power_score, moral_score) Float
        +generate_distribution(entity_id) Dict
        +detect_anomalies(entity_id, days) List
        +compare_sources(entity_id, source_ids) Dict
    }
    
    class DistributionModel {
        -data: Array
        -mean: Float
        -std: Float
        -min: Float
        -max: Float
        +__init__(data)
        +fit() void
        +pdf(x) Float
        +cdf(x) Float
        +percentile(x) Float
        +p_value(x) Float
        +to_dict() Dict
    }
    
    class SentimentTrend {
        -entity_id: Integer
        -dates: Array
        -power_scores: Array
        -moral_scores: Array
        -mention_counts: Array
        +__init__(entity_id, data)
        +detect_shifts(window_size) List
        +calculate_slope() Tuple[Float, Float]
        +get_overall_trend() String
        +correlation_with(other_trend) Float
        +to_dict() Dict
    }
    
    class CompositeScoreCalculator {
        -p_value_threshold: Float
        +__init__(p_value_threshold)
        +calculate_composite_score(entity_sentiments) Dict
        -calculate_weighted_average(p_values, weights) Float
        -adjust_for_entity_count(score, count) Float
        -map_to_percentile(p_value) Float
    }
    
    StatisticalModel -- DistributionModel : uses
    StatisticalModel -- SentimentTrend : creates
    StatisticalModel -- CompositeScoreCalculator : uses
```

## Browser Extension Implementation

```mermaid
classDiagram
    class ContentScript {
        -isArticlePage() Boolean
        -extractArticleContent() Object
        -injectAnalysisButton() void
        -setupMessageListeners() void
        -handleAnalysisButtonClick() void
        -sendContentToPopup(content) void
    }
    
    class BackgroundScript {
        -API_BASE_URL: String
        -setupMessageListeners() void
        -handleAnalysisRequest(article) Promise
        -cacheArticleAnalysis(url, analysis) void
        -getCachedAnalysis(url) Object
        -handleOpenDashboard(data) void
    }
    
    class PopupScript {
        -setupEventListeners() void
        -renderAnalysisResults(results) void
        -displayEntityList(entities) void
        -createSentimentVisualization(entity) void
        -handleViewDetails() void
        -handleOptionsClick() void
        -showLoadingState() void
        -showErrorState(message) void
    }
    
    class OptionsScript {
        -loadUserPreferences() void
        -saveUserPreferences(preferences) void
        -handleApiEndpointChange() void
        -handleThemeChange() void
        -handleAutomaticAnalysisToggle() void
        -validateApiCredentials() Promise
        -resetToDefaults() void
    }
    
    class HistoryScript {
        -loadAnalysisHistory() void
        -renderHistoryList(items) void
        -handleItemClick(itemId) void
        -handleClearHistory() void
        -exportHistory() void
        -filterHistoryItems(filter) void
    }
    
    class APIClient {
        -API_BASE_URL: String
        -API_KEY: String
        -getAuthToken() Promise
        -refreshToken() Promise
        -analyzeArticle(articleData) Promise
        -getEntity(entityId) Promise
        -getSourceInfo(sourceId) Promise
        -handleApiError(error) void
    }
    
    class StorageManager {
        -get(key) Promise
        -set(key, value) Promise
        -remove(key) Promise
        -clear() Promise
        -getAllArticleAnalyses() Promise
        -getArticleAnalysis(url) Promise
        -saveArticleAnalysis(url, data) Promise
        -removeArticleAnalysis(url) Promise
        -getUserPreferences() Promise
        -setUserPreferences(preferences) Promise
    }
    
    ContentScript -- BackgroundScript : communicates with
    PopupScript -- BackgroundScript : communicates with
    OptionsScript -- BackgroundScript : communicates with
    HistoryScript -- BackgroundScript : communicates with
    BackgroundScript -- APIClient : uses
    BackgroundScript -- StorageManager : uses
    PopupScript -- StorageManager : uses
    OptionsScript -- StorageManager : uses
    HistoryScript -- StorageManager : uses
```

## Admin Tools Implementation

```mermaid
classDiagram
    class AdminCLI {
        -config: ConfigParser
        +main() Integer
        -load_config(config_path) ConfigParser
        -setup_parsers() ArgumentParser
        -handle_db_commands(args, config) Integer
        -handle_user_commands(args, config) Integer
        -handle_monitor_commands(args, config) Integer
        -handle_validate_commands(args, config) Integer
        -handle_config_commands(args, config) Integer
    }
    
    class DatabaseManager {
        -host: String
        -port: Integer
        -dbname: String
        -user: String
        -password: String
        -engine: Engine
        -session_factory: sessionmaker
        +__init__(host, port, dbname, user, password)
        +get_session() Session
        +execute_query(query) ResultProxy
        +close() void
    }
    
    class DBMaintenance {
        +backup_database(db_manager, output_dir, tables) String
        +restore_from_backup(db_manager, backup_file, tables) void
        +cleanup_old_data(db_manager, days_threshold, dry_run) Dict
        +optimize_database(db_manager, vacuum, reindex) Dict
        +analyze_db_stats(db_manager, detailed, output_file) Dict
    }
    
    class UserManagement {
        +create_user(db_manager, username, email, password, is_admin, is_active) Tuple
        +delete_user(db_manager, username, force) Boolean
        +update_user(db_manager, username, email, password, is_admin, is_active) Boolean
        +list_users(db_manager, admin_only, active_only, output_format) List
        +create_api_key(db_manager, username, description, expires) String
        +revoke_api_key(db_manager, key_id) Boolean
        +list_api_keys(db_manager, username, include_expired, output_format) List
    }
    
    class ScraperMonitor {
        +analyze_scraper_performance(db_manager, days_back, by_source, output_dir) DataFrame
        +detect_failing_scrapers(db_manager, threshold_days, alert_email) List
        +monitor_scrapers_live(db_manager, interval, sources) void
        +repair_scraper_issues(db_manager, source, dry_run) Dict
    }
    
    class DataValidation {
        +validate_articles(db_manager, fix_issues, sample_size) Dict
        +validate_entities(db_manager, fix_issues, similarity_threshold) Dict
        +validate_mentions(db_manager, fix_issues) Dict
        +normalize_entities(db_manager, similarity_threshold, dry_run) Dict
        +generate_validation_report(db_manager, output_dir, report_format) String
    }
    
    AdminCLI -- DatabaseManager : uses
    AdminCLI -- DBMaintenance : uses
    AdminCLI -- UserManagement : uses
    AdminCLI -- ScraperMonitor : uses
    AdminCLI -- DataValidation : uses
```

## Dashboard Frontend Implementation

```mermaid
classDiagram
    class App {
        -authProvider: AuthProvider
        -theme: ThemeProvider
        -router: Router
        +render() JSX
    }
    
    class AuthProvider {
        -token: String
        -user: Object
        -isAuthenticated: Boolean
        -login(username, password) Promise
        -logout() void
        -getToken() String
        -register(userData) Promise
        -resetPassword(email) Promise
        -updateProfile(userData) Promise
    }
    
    class ApiService {
        -BASE_URL: String
        -token: String
        -getEntities(params) Promise
        -getEntity(entityId) Promise
        -getEntitySentiment(entityId, params) Promise
        -getSources(params) Promise
        -getSource(sourceId) Promise
        -getSourceBias(sourceId, params) Promise
        -getEntityDistribution(entityId, params) Promise
        -getTrends(params) Promise
        -analyzeArticle(article) Promise
        -getDashboardSummary() Promise
    }
    
    class DashboardLayout {
        -drawerOpen: Boolean
        -handleDrawerToggle() void
        -render() JSX
    }
    
    class EntityTable {
        -entities: Array
        -loading: Boolean
        -error: String
        -page: Number
        -pageSize: Number
        -fetchEntities() void
        -handlePageChange(page) void
        -handleFilterChange(filters) void
        -render() JSX
    }
    
    class SentimentChart {
        -data: Array
        -entityId: Number
        -timeRange: String
        -fetchData() void
        -renderChart() JSX
        -handleTimeRangeChange(range) void
        -exportChart() void
        -render() JSX
    }
    
    class SentimentDistributionChart {
        -data: Object
        -entityId: Number
        -sourceId: Number
        -showGlobal: Boolean
        -showNational: Boolean
        -fetchDistribution() void
        -renderDistribution() JSX
        -handleSourceChange(sourceId) void
        -toggleGlobal() void
        -toggleNational() void
        -render() JSX
    }
    
    class TrendLineChart {
        -trends: Array
        -entityIds: Array
        -days: Number
        -sourceId: Number
        -fetchTrends() void
        -renderChart() JSX
        -handleEntitySelection(entities) void
        -handleDaysChange(days) void
        -handleSourceChange(sourceId) void
        -render() JSX
    }
    
    class LoginPage {
        -username: String
        -password: String
        -error: String
        -loading: Boolean
        -handleUsernameChange(e) void
        -handlePasswordChange(e) void
        -handleSubmit(e) void
        -render() JSX
    }
    
    class Dashboard {
        -summary: Object
        -loading: Boolean
        -fetchSummary() void
        -renderWidgets() JSX
        -render() JSX
    }
    
    class EntitiesPage {
        -entities: Array
        -filters: Object
        -loading: Boolean
        -fetchEntities() void
        -handleFilterChange(filters) void
        -render() JSX
    }
    
    class EntityDetailPage {
        -entity: Object
        -sentiment: Object
        -distribution: Object
        -loading: Boolean
        -fetchEntityDetails(entityId) void
        -render() JSX
    }
    
    class SourcesPage {
        -sources: Array
        -filters: Object
        -loading: Boolean
        -fetchSources() void
        -handleFilterChange(filters) void
        -render() JSX
    }
    
    class SourceDetailPage {
        -source: Object
        -bias: Object
        -loading: Boolean
        -fetchSourceDetails(sourceId) void
        -render() JSX
    }
    
    class TrendsPage {
        -trends: Object
        -selectedEntities: Array
        -timeRange: String
        -sourceId: Number
        -loading: Boolean
        -fetchTrends() void
        -handleEntitySelection(entities) void
        -handleTimeRangeChange(range) void
        -handleSourceChange(sourceId) void
        -render() JSX
    }
    
    class AnalyzePage {
        -url: String
        -title: String
        -text: String
        -source: String
        -results: Object
        -loading: Boolean
        -handleSubmit() void
        -handleClear() void
        -renderResults() JSX
        -render() JSX
    }
    
    App -- AuthProvider : contains
    App -- DashboardLayout : renders
    DashboardLayout -- Dashboard : renders
    DashboardLayout -- EntitiesPage : renders
    DashboardLayout -- EntityDetailPage : renders
    DashboardLayout -- SourcesPage : renders
    DashboardLayout -- SourceDetailPage : renders
    DashboardLayout -- TrendsPage : renders
    DashboardLayout -- AnalyzePage : renders
    LoginPage -- AuthProvider : uses
    Dashboard -- ApiService : uses
    EntitiesPage -- ApiService : uses
    EntitiesPage -- EntityTable : contains
    EntityDetailPage -- ApiService : uses
    EntityDetailPage -- SentimentChart : contains
    EntityDetailPage -- SentimentDistributionChart : contains
    SourcesPage -- ApiService : uses
    SourceDetailPage -- ApiService : uses
    TrendsPage -- ApiService : uses
    TrendsPage -- TrendLineChart : contains
    AnalyzePage -- ApiService : uses
```

## Continuous Integration/Deployment Implementation

```mermaid
flowchart LR
    subgraph "GitHub"
        PR[Pull Request]
        Commit[Commit]
        GHA[GitHub Actions]
    end
    
    subgraph "Testing"
        Linting[Linting]
        UnitTests[Unit Tests]
        IntegrationTests[Integration Tests]
        CodeCov[Code Coverage]
    end
    
    subgraph "Building"
        BuildAPI[Build API]
        BuildWorker[Build Worker]
        BuildFrontend[Build Frontend]
        BuildExtension[Build Extension]
    end
    
    subgraph "Deployment"
        TerraformValidate[Terraform Validate]
        TerraformPlan[Terraform Plan]
        TerraformApply[Terraform Apply]
        DockerPublish[Publish Docker Images]
    end
    
    subgraph "AWS Infrastructure"
        EC2[EC2 Instances]
        RDS[RDS Database]
        S3[S3 Storage]
        ElastiCache[Redis Cache]
        ELB[Load Balancer]
    end
    
    PR --> GHA
    Commit --> GHA
    
    GHA --> Linting
    GHA --> UnitTests
    GHA --> IntegrationTests
    
    UnitTests --> CodeCov
    IntegrationTests --> CodeCov
    
    Linting --> BuildAPI
    UnitTests --> BuildAPI
    IntegrationTests --> BuildAPI
    
    BuildAPI --> DockerPublish
    BuildWorker --> DockerPublish
    BuildFrontend --> DockerPublish
    BuildExtension --> DockerPublish
    
    DockerPublish --> TerraformValidate
    TerraformValidate --> TerraformPlan
    TerraformPlan --> TerraformApply
    
    TerraformApply --> EC2
    TerraformApply --> RDS
    TerraformApply --> S3
    TerraformApply --> ElastiCache
    TerraformApply --> ELB
    
    classDef github fill:#f9f9f9,stroke:#333,stroke-width:1px;
    classDef testing fill:#e1f5fe,stroke:#333,stroke-width:1px;
    classDef building fill:#e8f5e9,stroke:#333,stroke-width:1px;
    classDef deployment fill:#fff3e0,stroke:#333,stroke-width:1px;
    classDef aws fill:#f3e5f5,stroke:#333,stroke-width:1px;
    
    class PR,Commit,GHA github;
    class Linting,UnitTests,IntegrationTests,CodeCov testing;
    class BuildAPI,BuildWorker,BuildFrontend,BuildExtension building;
    class TerraformValidate,TerraformPlan,TerraformApply,DockerPublish deployment;
    class EC2,RDS,S3,ElastiCache,ELB aws;
```
-- Statistical Intelligence Database Schema
-- SQLite database for storing analysis state and findings

-- Analysis state table - tracks the latest computed state for each analysis type
CREATE TABLE analysis_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_type TEXT NOT NULL, -- 'sentiment_anomaly', 'polarization', 'source_divergence', 'clustering_cache'
    entity_id INTEGER, -- NULL for global analyses
    source_id INTEGER, -- NULL for global analyses  
    time_window_start DATETIME NOT NULL,
    time_window_end DATETIME NOT NULL,
    state_data TEXT NOT NULL, -- JSON blob containing analysis state
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT, -- JSON blob for additional metadata
    UNIQUE(analysis_type, entity_id, source_id, time_window_start)
);

-- Statistical findings table - stores significant anomalies and patterns
CREATE TABLE statistical_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_type TEXT NOT NULL, -- 'sentiment_anomaly', 'polarization', 'source_divergence', 'editorial_shift'
    entity_id INTEGER, 
    source_id INTEGER,
    source_id_2 INTEGER, -- For divergence analysis (second source)
    cluster_id TEXT, -- For cluster-based findings
    
    -- Statistical significance
    p_value REAL NOT NULL,
    z_score REAL,
    effect_size REAL,
    confidence_interval_low REAL,
    confidence_interval_high REAL,
    
    -- Time information
    detection_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_start_date DATETIME NOT NULL,
    event_end_date DATETIME,
    
    -- Finding details
    baseline_value REAL, -- Historical average/baseline
    current_value REAL, -- Current observed value
    change_magnitude REAL, -- Size of change
    consecutive_days INTEGER, -- How many consecutive days this pattern held
    
    -- Descriptive information
    title TEXT NOT NULL, -- Human-readable title
    description TEXT NOT NULL, -- Detailed description
    severity_score REAL, -- 0-1 score indicating how unusual this finding is
    
    -- Dashboard display
    is_active BOOLEAN DEFAULT TRUE, -- Whether to show on dashboard
    priority_score REAL DEFAULT 0.5, -- 0-1 score for dashboard ordering
    dashboard_category TEXT, -- 'trending', 'polarization', 'divergence', 'anomaly'
    
    -- Raw data for visualization
    supporting_data TEXT, -- JSON blob with charts/data for dashboard
    
    UNIQUE(finding_type, entity_id, source_id, source_id_2, event_start_date)
);

-- Clustering cache table - stores processed clustering results from main database
CREATE TABLE clustering_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time_window_start DATETIME NOT NULL,
    time_window_end DATETIME NOT NULL,
    country TEXT,
    cluster_id TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    
    -- Cluster metrics
    intra_cluster_similarity REAL,
    silhouette_score REAL,
    centroid_vector TEXT, -- JSON blob of entity_id -> sentiment
    
    -- Change detection
    previous_similarity REAL, -- Similarity to previous time window
    similarity_change REAL, -- Change in internal similarity
    member_changes TEXT, -- JSON array of sources that joined/left
    
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(cluster_id, time_window_start)
);

-- Baseline statistics table - stores rolling statistics for anomaly detection
CREATE TABLE baseline_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_type TEXT NOT NULL, -- 'entity_sentiment', 'source_polarization', 'cluster_cohesion'
    entity_id INTEGER,
    source_id INTEGER,
    country TEXT,
    
    -- Rolling statistics (past N weeks)
    window_weeks INTEGER NOT NULL DEFAULT 12,
    mean_value REAL NOT NULL,
    std_dev REAL NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    percentile_95 REAL,
    percentile_5 REAL,
    
    -- Trend analysis
    trend_slope REAL, -- Linear trend coefficient
    trend_r_squared REAL, -- How strong the trend is
    
    -- Temporal information
    calculation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_start_date DATETIME NOT NULL,
    data_end_date DATETIME NOT NULL,
    sample_count INTEGER NOT NULL,
    
    UNIQUE(metric_type, entity_id, source_id, country, window_weeks, calculation_date)
);

-- Divergence tracking table - tracks sources that historically moved together
CREATE TABLE source_divergence_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id_1 INTEGER NOT NULL,
    source_id_2 INTEGER NOT NULL,
    
    -- Historical relationship
    historical_correlation REAL NOT NULL, -- Past correlation coefficient
    historical_window_start DATETIME NOT NULL,
    historical_window_end DATETIME NOT NULL,
    
    -- Recent divergence
    recent_correlation REAL NOT NULL,
    recent_window_start DATETIME NOT NULL, 
    recent_window_end DATETIME NOT NULL,
    
    -- Statistical significance of divergence
    divergence_p_value REAL NOT NULL,
    divergence_magnitude REAL NOT NULL, -- Absolute change in correlation
    
    -- Entities driving the divergence
    top_divergent_entities TEXT, -- JSON array of entity_id, sentiment_diff pairs
    
    -- Status
    is_significant BOOLEAN NOT NULL DEFAULT FALSE, -- p < 0.01
    first_detected DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_id_1, source_id_2, recent_window_start)
);

-- Create indexes for efficient querying
CREATE INDEX idx_analysis_state_type_time ON analysis_state(analysis_type, time_window_start, time_window_end);
CREATE INDEX idx_findings_active_priority ON statistical_findings(is_active, priority_score DESC);
CREATE INDEX idx_findings_type_date ON statistical_findings(finding_type, detection_date);
CREATE INDEX idx_findings_entity ON statistical_findings(entity_id, detection_date);
CREATE INDEX idx_findings_p_value ON statistical_findings(p_value);
CREATE INDEX idx_clustering_cache_time ON clustering_cache(time_window_start, time_window_end);
CREATE INDEX idx_baseline_stats_lookup ON baseline_statistics(metric_type, entity_id, source_id, calculation_date);
CREATE INDEX idx_divergence_sources ON source_divergence_tracking(source_id_1, source_id_2);
CREATE INDEX idx_divergence_significant ON source_divergence_tracking(is_significant, last_updated);

-- System metrics table - tracks cumulative system statistics
CREATE TABLE IF NOT EXISTS system_metrics (
    metric_name TEXT PRIMARY KEY,
    metric_value INTEGER NOT NULL DEFAULT 0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT -- JSON blob for additional info
);
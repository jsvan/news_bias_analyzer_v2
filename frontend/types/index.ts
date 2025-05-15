// Entity Types
export interface Entity {
  id: number;
  name: string;
  type: EntityType;
  mention_count?: number;
  first_seen?: string;
  last_seen?: string;
  avg_power_score?: number;
  avg_moral_score?: number;
}

export type EntityType = 'person' | 'country' | 'organization' | 'political_party' | 'company' | string;

// Sentiment Data Types
export interface SentimentPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
  sources?: string[];
}

export interface Distribution {
  mean: number;
  std: number;
  min: number;
  max: number;
  count?: number;
  pdf?: {
    x: number[];
    y: number[];
  };
}

export interface SentimentDistributions {
  global?: {
    power: Distribution;
    moral: Distribution;
  };
  national?: {
    country: string;
    power: Distribution;
    moral: Distribution;
  };
  source?: {
    source_id: number;
    source_name: string;
    power: Distribution;
    moral: Distribution;
  };
}

export interface EntitySentiment {
  entity: Entity;
  sentiment_data: SentimentPoint[];
  averages: {
    power_score: number;
    moral_score: number;
  };
  distributions: SentimentDistributions;
}

// Source Types
export interface NewsSource {
  id: number;
  name: string;
  base_url: string;
  country: string;
  language: string;
  political_leaning?: string;
  article_count?: number;
}

export interface BiasProfile {
  partisan_bias?: {
    detected: boolean;
    direction?: string;
    confidence: number;
    evidence: string[];
  };
  national_bias?: {
    detected: boolean;
    favored?: string[];
    disfavored?: string[];
    confidence: number;
    evidence: string[];
  };
}

export interface SourceProfile {
  source: NewsSource;
  bias_profile: BiasProfile;
  entity_sentiment: {
    countries: EntitySentimentSummary[];
    people: EntitySentimentSummary[];
  };
}

export interface EntitySentimentSummary {
  entity: string;
  power_score: number;
  moral_score: number;
  global_percentile: number;
}

// Trend Types
export interface TrendPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
}

export interface TrendData {
  id: number;
  name: string;
  type: EntityType;
  data: TrendPoint[];
}

// Article Types
export interface Article {
  id: string;
  source_id: number;
  source_name?: string;
  url: string;
  title: string;
  text?: string;
  publish_date: string;
  entities?: ArticleEntity[];
  composite_score?: {
    percentile: number;
    p_value: number;
  };
}

export interface ArticleEntity {
  entity: string;
  entity_type: EntityType;
  power_score: number;
  moral_score: number;
  national_significance?: number;
  global_significance?: number;
  mentions: EntityMention[];
}

export interface EntityMention {
  text: string;
  context: string;
}

// User and Auth Types
export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
}

// Dashboard Types
export interface SavedSearch {
  id: number;
  name: string;
  description?: string;
  query_parameters: any;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  last_run?: string;
}

export interface DashboardWidget {
  id: number;
  name: string;
  widget_type: 'chart' | 'table' | 'metric';
  position: number;
  size: 'small' | 'medium' | 'large';
  config: any;
  search_id?: number;
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  detail: string;
  status?: number;
  retry_after?: number;
}
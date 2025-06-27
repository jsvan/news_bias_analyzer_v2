/**
 * Environment Configuration System
 * 
 * This module provides centralized configuration management for different environments
 * (development, staging, production) and deployment contexts (local, GitHub Pages, hosted).
 */

export interface EnvironmentConfig {
  apiBaseUrl: string;
  environment: 'development' | 'staging' | 'production';
  deploymentContext: 'local' | 'github-pages' | 'hosted';
  features: {
    enableAnalytics: boolean;
    enableDebugMode: boolean;
    enableOfflineMode: boolean;
  };
  api: {
    timeout: number;
    retryAttempts: number;
    enableCaching: boolean;
  };
}

/**
 * Development environment configuration
 */
const developmentConfig: EnvironmentConfig = {
  apiBaseUrl: 'http://localhost:8000',
  environment: 'development',
  deploymentContext: 'local',
  features: {
    enableAnalytics: false,
    enableDebugMode: true,
    enableOfflineMode: false,
  },
  api: {
    timeout: 10000,
    retryAttempts: 3,
    enableCaching: false,
  },
};

/**
 * Staging environment configuration
 */
const stagingConfig: EnvironmentConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'https://api-staging.news-bias-analyzer.example.com',
  environment: 'staging',
  deploymentContext: 'hosted',
  features: {
    enableAnalytics: false,
    enableDebugMode: true,
    enableOfflineMode: true,
  },
  api: {
    timeout: 15000,
    retryAttempts: 3,
    enableCaching: true,
  },
};

/**
 * Production environment configuration
 */
const productionConfig: EnvironmentConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'https://api.news-bias-analyzer.example.com',
  environment: 'production',
  deploymentContext: import.meta.env.VITE_GITHUB_PAGES === 'true' ? 'github-pages' : 'hosted',
  features: {
    enableAnalytics: true,
    enableDebugMode: false,
    enableOfflineMode: true,
  },
  api: {
    timeout: 20000,
    retryAttempts: 5,
    enableCaching: true,
  },
};

/**
 * GitHub Pages specific configuration
 * When deployed to GitHub Pages without a backend, we provide mock/demo data
 */
const githubPagesConfig: EnvironmentConfig = {
  ...productionConfig,
  apiBaseUrl: '', // No API available on GitHub Pages
  deploymentContext: 'github-pages',
  features: {
    ...productionConfig.features,
    enableDebugMode: false,
    enableOfflineMode: true, // Essential for GitHub Pages
  },
  api: {
    ...productionConfig.api,
    enableCaching: true,
  },
};

/**
 * Detect the current environment based on various factors
 */
function detectEnvironment(): 'development' | 'staging' | 'production' {
  // Check explicit environment variable first
  const envVar = import.meta.env.VITE_APP_ENV;
  if (envVar && ['development', 'staging', 'production'].includes(envVar)) {
    return envVar as 'development' | 'staging' | 'production';
  }

  // Check Vite mode
  const mode = import.meta.env.MODE;
  if (mode === 'production') {
    return 'production';
  } else if (mode === 'staging') {
    return 'staging';
  }

  // Default to development
  return 'development';
}

/**
 * Get the appropriate configuration for the current environment
 */
export function getEnvironmentConfig(): EnvironmentConfig {
  const environment = detectEnvironment();
  const isGitHubPages = import.meta.env.VITE_GITHUB_PAGES === 'true';

  // Special case for GitHub Pages deployment
  if (isGitHubPages && environment === 'production') {
    console.log('🚀 Running in GitHub Pages mode');
    return githubPagesConfig;
  }

  switch (environment) {
    case 'development':
      console.log('🛠️ Running in development mode');
      return developmentConfig;
    case 'staging':
      console.log('🧪 Running in staging mode');
      return stagingConfig;
    case 'production':
      console.log('📦 Running in production mode');
      return productionConfig;
    default:
      console.warn('⚠️ Unknown environment, falling back to development');
      return developmentConfig;
  }
}

/**
 * Check if API is available (for GitHub Pages deployments)
 */
export async function checkApiAvailability(apiBaseUrl: string): Promise<boolean> {
  if (!apiBaseUrl) {
    return false;
  }

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      method: 'GET',
      timeout: 5000,
    } as RequestInit);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get the current configuration instance
 */
export const config = getEnvironmentConfig();

/**
 * Utility function to check if we're in development mode
 */
export const isDevelopment = () => config.environment === 'development';

/**
 * Utility function to check if we're in production mode
 */
export const isProduction = () => config.environment === 'production';

/**
 * Utility function to check if we're running on GitHub Pages
 */
export const isGitHubPages = () => config.deploymentContext === 'github-pages';

/**
 * Utility function to check if debug mode is enabled
 */
export const isDebugMode = () => config.features.enableDebugMode;

/**
 * Export the configuration object for external use
 */
export default config;
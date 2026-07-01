/**
 * Environment configuration.
 *
 * The API base URL comes from VITE_API_BASE_URL. There is currently no hosted
 * backend: production builds without VITE_API_BASE_URL (e.g. GitHub Pages) get
 * an empty base URL and the UI shows its "API unavailable" state.
 */

export interface EnvironmentConfig {
  apiBaseUrl: string;
  deploymentContext: 'local' | 'github-pages' | 'hosted';
  api: {
    timeout: number;
    retryAttempts: number;
  };
}

function getEnvironmentConfig(): EnvironmentConfig {
  const isDev = import.meta.env.MODE !== 'production';
  const onGitHubPages = import.meta.env.VITE_GITHUB_PAGES === 'true';
  const apiBaseUrl =
    import.meta.env.VITE_API_BASE_URL || (isDev ? 'http://localhost:8000' : '');

  return {
    apiBaseUrl,
    deploymentContext: onGitHubPages ? 'github-pages' : isDev ? 'local' : 'hosted',
    api: {
      timeout: isDev ? 10000 : 20000,
      retryAttempts: 3,
    },
  };
}

export const config = getEnvironmentConfig();

export const isGitHubPages = () => config.deploymentContext === 'github-pages';

/**
 * Static-data mode: serve precomputed JSON snapshots (see server/export_snapshots.py)
 * instead of a live API. On by default on GitHub Pages (there is no hosted backend
 * unless VITE_API_BASE_URL is set); opt in elsewhere with VITE_DATA_MODE=static.
 */
export const isStaticMode = () =>
  import.meta.env.VITE_DATA_MODE === 'static' ||
  (isGitHubPages() && !import.meta.env.VITE_API_BASE_URL);

/** Check if the API is reachable (used on GitHub Pages deployments). */
export async function checkApiAvailability(apiBaseUrl: string): Promise<boolean> {
  if (!apiBaseUrl) {
    return false;
  }
  try {
    const response = await fetch(`${apiBaseUrl}/health`, { method: 'GET' });
    return response.ok;
  } catch {
    return false;
  }
}

export default config;

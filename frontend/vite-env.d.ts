/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_ENV: 'development' | 'staging' | 'production'
  readonly VITE_GITHUB_PAGES: string
  readonly VITE_REPO_NAME: string
  readonly MODE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}